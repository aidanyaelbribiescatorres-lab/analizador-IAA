"""
Vercel serverless function: /api/live
Returns LIVE game scores + player box-score stats from ESPN.

Endpoints:
  GET /api/live?sport=basketball&league=nba
      → all live/recent games with scores and player stats

  GET /api/live?sport=basketball&league=nba&event_id=401585857
      → single game full box score

  GET /api/live?sport=soccer&league=eng.1
  GET /api/live?sport=soccer&league=esp.1
  GET /api/live?sport=football&league=nfl
  GET /api/live?sport=baseball&league=mlb
  GET /api/live?sport=hockey&league=nhl

Query params:
  sport      basketball | football | baseball | hockey | soccer
  league     nba | nfl | mlb | nhl | eng.1 | esp.1 | ita.1 | ger.1 | mex.1 | usa.1 | uefa.champions
  event_id   ESPN event ID (optional — returns single game)
  top        max players per team to return (default 8)
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, urllib.request

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports"

# ─── Keys ESPN uses in box-score stats per sport ─────────────────────────────
STAT_KEYS = {
    "basketball": {
        "order": ["MIN","PTS","REB","AST","3PM","FG","FT","STL","BLK","TO","PF"],
        "labels": {
            "MIN":"MIN","PTS":"PTS","REB":"REB","AST":"AST","3PM":"3PM",
            "FG":"TC","FT":"TL","STL":"ROB","BLK":"TAP","TO":"PÉR","PF":"FALTAS",
        },
    },
    "football": {
        "order": ["PYDS","PTD","INT","RUYDS","RUTD","REC","REYDS","RETD","SACKS"],
        "labels": {
            "PYDS":"Yds pase","PTD":"TD pase","INT":"INT",
            "RUYDS":"Yds corrida","RUTD":"TD corrida",
            "REC":"Rec.","REYDS":"Yds rec.","RETD":"TD rec.","SACKS":"Sacks",
        },
    },
    "baseball": {
        "order": ["AB","R","H","HR","RBI","BB","SO","AVG","ERA","IP","K","BB2"],
        "labels": {
            "AB":"VB","R":"Carreras","H":"Hits","HR":"HR","RBI":"RBI",
            "BB":"BB","SO":"K","AVG":"AVG","ERA":"ERA","IP":"IP","K":"K","BB2":"BB",
        },
    },
    "hockey": {
        "order": ["G","A","PTS","+/-","PIM","SOG","TOI","SV","GA","SV%"],
        "labels": {
            "G":"Goles","A":"Asis.","PTS":"PTS","+/-":"+/-","PIM":"PIM",
            "SOG":"Tiros","TOI":"Tiempo","SV":"Paradas","GA":"GA","SV%":"SV%",
        },
    },
    "soccer": {
        "order": ["G","A","SH","SHG","FC","YC","RC","OFF","MIN"],
        "labels": {
            "G":"Goles","A":"Asis.","SH":"Tiros","SHG":"Al arco",
            "FC":"Faltas","YC":"Amarillas","RC":"Rojas","OFF":"Fuera juego","MIN":"MIN",
        },
    },
}


def _get(url, params=None):
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "ScoutAI/1.0"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read())


def parse_status(comp):
    """Returns (status_str, clock_str, is_live, is_final)."""
    st = comp.get("status", {})
    stype = st.get("type", {})
    name  = stype.get("name", "")
    desc  = stype.get("description", "")
    clock = st.get("displayClock", "")
    period = st.get("period", 0)

    is_live  = name in ("STATUS_IN_PROGRESS",)
    is_final = name in ("STATUS_FINAL", "STATUS_FULL_TIME", "STATUS_END_PERIOD")

    if is_live:
        status = f"EN VIVO · P{period} {clock}"
    elif is_final:
        status = "FINAL"
    else:
        status = desc or name

    return status, clock, is_live, is_final


def parse_competitor(comp_data):
    """Extract team name, score, logo from a competitor object."""
    team = comp_data.get("team", {})
    return {
        "id":     team.get("id", ""),
        "name":   team.get("displayName") or team.get("name", ""),
        "abbr":   team.get("abbreviation", ""),
        "logo":   team.get("logo", ""),
        "score":  comp_data.get("score", "—"),
        "home":   comp_data.get("homeAway", "") == "home",
    }


def parse_box_score(event_id, sport, league, top):
    """Fetch game summary and extract box score players."""
    data = _get(f"{ESPN_SITE}/{sport}/{league}/summary", {"event": event_id})

    sk = STAT_KEYS.get(sport, STAT_KEYS["basketball"])
    want_order  = sk["order"]
    want_labels = sk["labels"]

    teams_out = []
    for team_block in data.get("boxscore", {}).get("players", []):
        team_info = team_block.get("team", {})
        team_name = team_info.get("displayName") or team_info.get("name", "")
        team_logo = team_info.get("logo", "")

        players_out = []
        for stat_block in team_block.get("statistics", []):
            stat_names = stat_block.get("names", [])   # column headers
            athletes   = stat_block.get("athletes", [])

            for ath in athletes[:top]:
                ath_info = ath.get("athlete", {})
                raw_stats = ath.get("stats", [])

                stats_dict = {}
                for i, val in enumerate(raw_stats):
                    if i < len(stat_names):
                        col = stat_names[i]
                        if col in want_labels:
                            stats_dict[col] = val

                # Reorder
                ordered = {k: stats_dict[k] for k in want_order if k in stats_dict}

                pos_d = ath_info.get("position", {})
                players_out.append({
                    "id":       str(ath_info.get("id", "")),
                    "name":     ath_info.get("displayName") or ath_info.get("shortName", ""),
                    "jersey":   ath_info.get("jersey", ""),
                    "position": pos_d.get("abbreviation", "") if isinstance(pos_d, dict) else "",
                    "headshot": (ath_info.get("headshot") or {}).get("href", ""),
                    "starter":  ath.get("starter", False),
                    "stats":    ordered,
                })

        teams_out.append({
            "name":    team_name,
            "logo":    team_logo,
            "players": players_out,
        })

    return teams_out, want_labels


def fetch_scoreboard(sport, league, top):
    """Return all live/recent games with basic info + box scores."""
    data = _get(f"{ESPN_SITE}/{sport}/{league}/scoreboard")
    sk = STAT_KEYS.get(sport, STAT_KEYS["basketball"])

    games_out = []
    for ev in data.get("events", []):
        comps = ev.get("competitions", [{}])
        comp  = comps[0] if comps else {}

        competitors = comp.get("competitors", [])
        teams = [parse_competitor(c) for c in competitors]

        status, clock, is_live, is_final = parse_status(comp)

        event_id = str(ev.get("id", ""))
        venue_d  = comp.get("venue", {})

        # Fetch box score only for live/final games (saves quota for scheduled)
        players_by_team = []
        if (is_live or is_final) and event_id:
            try:
                players_by_team, _ = parse_box_score(event_id, sport, league, top)
            except Exception:
                players_by_team = []

        games_out.append({
            "event_id":   event_id,
            "name":       ev.get("name", ""),
            "date":       ev.get("date", ""),
            "status":     status,
            "is_live":    is_live,
            "is_final":   is_final,
            "venue":      venue_d.get("fullName", ""),
            "teams":      teams,
            "box_score":  players_by_team,
        })

    return {
        "sport":       sport,
        "league":      league,
        "stat_labels": sk["labels"],
        "games":       games_out,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)

        def p(k, default=""):
            v = qs.get(k, [default])
            return v[0] if v else default

        sport    = p("sport", "basketball")
        league   = p("league", "nba")
        event_id = p("event_id", "")
        top      = min(int(p("top", "8")), 20)

        resp_headers = {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
            # Live data: short cache (30s), stale-while-revalidate 60s
            "Cache-Control":               "s-maxage=30, stale-while-revalidate=60",
        }

        try:
            if event_id:
                # Single game box score
                sk = STAT_KEYS.get(sport, STAT_KEYS["basketball"])
                players_by_team, labels = parse_box_score(event_id, sport, league, top)
                data = {
                    "sport":       sport,
                    "league":      league,
                    "event_id":    event_id,
                    "stat_labels": labels,
                    "box_score":   players_by_team,
                }
            else:
                # Full scoreboard
                data = fetch_scoreboard(sport, league, top)

            body = json.dumps(data, ensure_ascii=False)
            self.send_response(200)
            for k, v in resp_headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body.encode())

        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.send_response(400)
            for k, v in resp_headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(err.encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *_):
        pass
