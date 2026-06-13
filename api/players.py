"""
Vercel serverless function: /api/players
Returns NBA/NFL/MLB/NHL/Soccer player stats from ESPN public API.

Usage:
  GET /api/players?team=Lakers&sport=basketball&league=nba
  GET /api/players?team=Chiefs&sport=football&league=nfl
  GET /api/players?team=Dodgers&sport=baseball&league=mlb
  GET /api/players?team=Oilers&sport=hockey&league=nhl
  GET /api/players?team=Barcelona&sport=soccer&league=esp.1
  GET /api/players?team=Arsenal&sport=soccer&league=eng.1
  GET /api/players?team_id=83&sport=soccer&league=esp.1   (exact ESPN team ID)
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, urllib.request, urllib.error

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_CMVN = "https://site.web.api.espn.com/apis/common/v3/sports"

STAT_MAPS = {
    "basketball": ["PTS","REB","AST","3PM","FG%","FT%","STL","BLK","TO","MIN"],
    "football":   ["PYDS","PTD","RUYDS","RUTD","REC","REYDS","RETD","SACKS","INT","QBR"],
    "baseball":   ["AVG","HR","RBI","SB","OBP","SLG","OPS","ERA","WHIP","K"],
    "hockey":     ["G","A","PTS","PPG","+/-","PIM","SOG","GF","GA","SV%"],
    "soccer":     ["G","A","SH","SHG","FC","YC","RC","OFF","MIN","APP","GK_SV","GK_GA"],
}

STAT_LABELS = {
    # Basketball
    "PTS":"Puntos","REB":"Rebotes","AST":"Asistencias","3PM":"Triples",
    "FG%":"Tiro %","FT%":"TL %","STL":"Robos","BLK":"Tapones","TO":"Pérdidas","MIN":"Minutos",
    # Football
    "PYDS":"Yardas pase","PTD":"TD pase","RUYDS":"Yardas corrida","RUTD":"TD corrida",
    "REC":"Recepciones","REYDS":"Yardas rec.","RETD":"TD rec.","SACKS":"Sacks","INT":"INT","QBR":"QBR",
    # Baseball
    "AVG":"Promedio","HR":"HR","RBI":"RBI","SB":"Bases robadas","OBP":"OBP","SLG":"SLG",
    "OPS":"OPS","ERA":"ERA","WHIP":"WHIP","K":"Strikeouts",
    # Hockey
    "GF":"GF","GA":"GA","SV%":"SV%","PPG":"PP Goles","PIM":"Min. penalti","SOG":"Tiros",
    # Soccer
    "G":"Goles","A":"Asistencias","SH":"Tiros","SHG":"Tiros al arco",
    "FC":"Faltas cometidas","YC":"Tarjetas amarillas","RC":"Tarjetas rojas",
    "OFF":"Fueras de juego","APP":"Partidos","GK_SV":"Paradas","GK_GA":"Goles recibidos",
    # Shared (keep last so hockey "+/-" wins)
    "+/-":"+/-",
}

# ESPN soccer leagues — used to validate/route requests
SOCCER_LEAGUES = {
    "eng.1":          "Premier League",
    "esp.1":          "La Liga",
    "ita.1":          "Serie A",
    "ger.1":          "Bundesliga",
    "fra.1":          "Ligue 1",
    "mex.1":          "Liga MX",
    "usa.1":          "MLS",
    "uefa.champions": "Champions League",
    "fifa.world":     "Copa del Mundo",
    "conmebol.copa":  "Copa América",
}


def _get(url, params=None):
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "ScoutAI/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def find_team_id(sport, league, name):
    data = _get(f"{ESPN_SITE}/{sport}/{league}/teams", {"limit": 100})
    teams = (data.get("sports", [{}])[0]
                 .get("leagues", [{}])[0]
                 .get("teams", []))
    name_l = name.lower()
    best_id, best_score = None, 0
    for t in teams:
        tm = t.get("team", {})
        tid = tm.get("id")
        candidates = [
            tm.get("displayName", ""),
            tm.get("shortDisplayName", ""),
            tm.get("abbreviation", ""),
            tm.get("name", ""),
            tm.get("nickname", ""),
        ]
        for c in candidates:
            if c and name_l == c.lower():
                return tid  # exact match
            if c and name_l in c.lower():
                score = len(name_l)
                if score > best_score:
                    best_score = score
                    best_id = tid
            elif c and c.lower() in name_l:
                score = len(c)
                if score > best_score:
                    best_score = score
                    best_id = tid
    return best_id


def fetch_roster(sport, league, team_id):
    data = _get(f"{ESPN_SITE}/{sport}/{league}/teams/{team_id}/roster")
    players = []
    for group in data.get("athletes", []):
        items = group.get("items", []) if isinstance(group, dict) else (group if isinstance(group, list) else [])
        for a in items:
            pos_d = a.get("position", {})
            players.append({
                "id":  str(a.get("id", "")),
                "name": a.get("displayName") or a.get("fullName", ""),
                "jersey": a.get("jersey", ""),
                "position": pos_d.get("abbreviation", "") if isinstance(pos_d, dict) else "",
                "headshot": (a.get("headshot") or {}).get("href", ""),
            })
    return players


def fetch_stats(sport, league, player_id, want_keys):
    try:
        data = _get(f"{ESPN_CMVN}/{sport}/{league}/athletes/{player_id}/stats")
        raw = {}
        for cat in data.get("splits", {}).get("categories", []):
            cat_name = cat.get("name", "").lower()
            for x in cat.get("stats", []):
                k = x.get("abbreviation", "")
                v = x.get("value")
                if v is None:
                    continue
                raw[k] = v
                # Map soccer goalkeeper stats with GK_ prefix to distinguish from field stats
                if sport == "soccer" and cat_name in ("goalkeeping", "goalkeeper"):
                    if k == "SV":
                        raw["GK_SV"] = v
                    elif k == "GA":
                        raw["GK_GA"] = v

        result = {}
        for k in want_keys:
            v = raw.get(k)
            if v is not None:
                result[k] = round(float(v), 1)
        return result
    except Exception:
        return {}


SOCCER_GK_STATS  = ["APP","MIN","GK_SV","GK_GA","YC","RC"]
SOCCER_FLD_STATS = ["G","A","SH","SHG","FC","YC","RC","OFF","APP","MIN"]

def build_response(sport, league, team_id, limit, include_stats):
    want = STAT_MAPS.get(sport, STAT_MAPS["basketball"])
    labels = {k: STAT_LABELS.get(k, k) for k in set(want + SOCCER_GK_STATS + SOCCER_FLD_STATS)}

    players = fetch_roster(sport, league, team_id)[:limit]
    out = []
    for p in players:
        is_gk = p["position"] in ("GK", "G", "Goalkeeper", "Portero")
        # For soccer pick stat set per position
        if sport == "soccer":
            keys = SOCCER_GK_STATS if is_gk else SOCCER_FLD_STATS
        else:
            keys = want

        entry = {
            "id":       p["id"],
            "name":     p["name"],
            "jersey":   p["jersey"],
            "position": p["position"],
            "headshot": p["headshot"],
            "stats":    {},
        }
        if include_stats and p["id"]:
            entry["stats"] = fetch_stats(sport, league, p["id"], keys)
        out.append(entry)

    return {
        "sport":       sport,
        "league":      league,
        "league_name": SOCCER_LEAGUES.get(league, league) if sport == "soccer" else league.upper(),
        "team_id":     team_id,
        "stat_labels": {k: STAT_LABELS.get(k, k) for k in set(want + SOCCER_GK_STATS + SOCCER_FLD_STATS)},
        "players":     out,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        def p(k, default=""):
            v = qs.get(k, [default])
            return v[0] if v else default

        sport   = p("sport", "basketball")
        league  = p("league", "nba")
        team    = p("team", "")
        team_id = p("team_id", "")
        limit   = min(int(p("limit", "15")), 30)
        stats   = p("stats", "true").lower() != "false"

        headers = {
            "Content-Type":                "application/json",
            "Access-Control-Allow-Origin": "*",
            "Cache-Control":               "s-maxage=1800, stale-while-revalidate",
        }

        try:
            if not team_id and not team:
                raise ValueError("Param 'team' or 'team_id' required")

            if not team_id:
                team_id = find_team_id(sport, league, team)
                if not team_id:
                    raise ValueError(f"Team '{team}' not found in {sport}/{league}")

            data = build_response(sport, league, team_id, limit, stats)
            body = json.dumps(data, ensure_ascii=False)
            self.send_response(200)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body.encode())

        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.send_response(400)
            for k, v in headers.items():
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
