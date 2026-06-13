/**
 * /api/live — Marcador en vivo + box score de jugadores (ESPN)
 *
 * GET /api/live?sport=basketball&league=nba
 *     → todos los partidos (en vivo / recientes) con stats de jugadores
 *
 * GET /api/live?sport=basketball&league=nba&event_id=401585857
 *     → box score completo de un partido específico
 *
 * Ligas disponibles:
 *   basketball: nba
 *   football:   nfl
 *   baseball:   mlb
 *   hockey:     nhl
 *   soccer:     eng.1 | esp.1 | ita.1 | ger.1 | fra.1 | mex.1 | usa.1 | uefa.champions
 *
 * Params:
 *   sport     basketball | football | baseball | hockey | soccer
 *   league    ver arriba
 *   event_id  ESPN event ID (opcional)
 *   top       max jugadores por equipo (default 8, max 20)
 */

const ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports";

const STAT_KEYS = {
  basketball: {
    order:  ["MIN","PTS","REB","AST","3PM","FG","FT","STL","BLK","TO"],
    labels: { MIN:"MIN",PTS:"PTS",REB:"REB",AST:"AST","3PM":"3PM",FG:"TC",FT:"TL",STL:"ROB",BLK:"TAP",TO:"PÉR" },
  },
  football: {
    order:  ["PYDS","PTD","INT","RUYDS","RUTD","REC","REYDS","RETD","SACKS"],
    labels: { PYDS:"Yds pase",PTD:"TD pase",INT:"INT",RUYDS:"Yds corrida",RUTD:"TD corrida",
              REC:"Rec.",REYDS:"Yds rec.",RETD:"TD rec.",SACKS:"Sacks" },
  },
  baseball: {
    order:  ["AB","R","H","HR","RBI","BB","SO","AVG","ERA","IP","K"],
    labels: { AB:"VB",R:"Carreras",H:"Hits",HR:"HR",RBI:"RBI",BB:"BB",SO:"K",
              AVG:"AVG",ERA:"ERA",IP:"IP",K:"K" },
  },
  hockey: {
    order:  ["G","A","PTS","+/-","PIM","SOG","TOI","SV","GA","SV%"],
    labels: { G:"Goles",A:"Asis.",PTS:"PTS","+/-":"+/-",PIM:"PIM",
              SOG:"Tiros",TOI:"Tiempo",SV:"Paradas",GA:"GA","SV%":"SV%" },
  },
  soccer: {
    order:  ["G","A","SH","SHG","FC","YC","RC","OFF","MIN"],
    labels: { G:"Goles",A:"Asis.",SH:"Tiros",SHG:"Al arco",
              FC:"Faltas",YC:"Amarillas",RC:"Rojas",OFF:"Fuera juego",MIN:"MIN" },
  },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function espnGet(url, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const full = qs ? `${url}?${qs}` : url;
  const res = await fetch(full, { headers: { "User-Agent": "ScoutAI/1.0" } });
  if (!res.ok) throw new Error(`ESPN ${res.status}: ${full}`);
  return res.json();
}

function parseStatus(comp) {
  const st    = comp.status ?? {};
  const stype = st.type ?? {};
  const name  = stype.name ?? "";
  const clock = st.displayClock ?? "";
  const period = st.period ?? 0;

  const isLive  = name === "STATUS_IN_PROGRESS";
  const isFinal = ["STATUS_FINAL","STATUS_FULL_TIME","STATUS_END_PERIOD"].includes(name);

  let status;
  if (isLive)       status = `EN VIVO · P${period} ${clock}`;
  else if (isFinal) status = "FINAL";
  else              status = stype.description ?? name;

  return { status, clock, period, isLive, isFinal };
}

function parseCompetitor(c) {
  const team = c.team ?? {};
  return {
    id:    team.id ?? "",
    name:  team.displayName ?? team.name ?? "",
    abbr:  team.abbreviation ?? "",
    logo:  team.logo ?? "",
    score: c.score ?? "—",
    home:  c.homeAway === "home",
  };
}

async function fetchBoxScore(eventId, sport, league, top) {
  const data = await espnGet(`${ESPN_SITE}/${sport}/${league}/summary`, { event: eventId });
  const sk = STAT_KEYS[sport] ?? STAT_KEYS.basketball;

  const teamsList = [];
  for (const teamBlock of data?.boxscore?.players ?? []) {
    const teamInfo = teamBlock.team ?? {};
    const players  = [];

    for (const statBlock of teamBlock.statistics ?? []) {
      const cols     = statBlock.names ?? [];
      const athletes = statBlock.athletes ?? [];

      for (const ath of athletes.slice(0, top)) {
        const info     = ath.athlete ?? {};
        const rawStats = ath.stats ?? [];

        const statsMap = {};
        rawStats.forEach((val, i) => {
          const col = cols[i];
          if (col && sk.labels[col] !== undefined) statsMap[col] = val;
        });

        // Ordered stats (only keys present)
        const ordered = {};
        for (const k of sk.order) {
          if (statsMap[k] !== undefined) ordered[k] = statsMap[k];
        }

        players.push({
          id:       String(info.id ?? ""),
          name:     info.displayName ?? info.shortName ?? "",
          jersey:   info.jersey ?? "",
          position: info.position?.abbreviation ?? "",
          headshot: info.headshot?.href ?? "",
          starter:  ath.starter ?? false,
          stats:    ordered,
        });
      }
    }

    teamsList.push({
      id:      teamInfo.id ?? "",
      name:    teamInfo.displayName ?? teamInfo.name ?? "",
      logo:    teamInfo.logo ?? "",
      players,
    });
  }

  return { teams: teamsList, labels: sk.labels };
}

async function fetchScoreboard(sport, league, top) {
  const data = await espnGet(`${ESPN_SITE}/${sport}/${league}/scoreboard`);
  const sk   = STAT_KEYS[sport] ?? STAT_KEYS.basketball;
  const games = [];

  for (const ev of data.events ?? []) {
    const comp  = ev.competitions?.[0] ?? {};
    const { status, clock, period, isLive, isFinal } = parseStatus(comp);
    const teams = (comp.competitors ?? []).map(parseCompetitor);
    const eventId = String(ev.id ?? "");

    let boxScore = [];
    if ((isLive || isFinal) && eventId) {
      try {
        const { teams: t } = await fetchBoxScore(eventId, sport, league, top);
        boxScore = t;
      } catch { /* skip */ }
    }

    games.push({
      event_id:  eventId,
      name:      ev.name ?? "",
      date:      ev.date ?? "",
      status,
      clock,
      period,
      is_live:   isLive,
      is_final:  isFinal,
      venue:     comp.venue?.fullName ?? "",
      teams,
      box_score: boxScore,
    });
  }

  return { sport, league, stat_labels: sk.labels, games };
}

// ─── Main handler ─────────────────────────────────────────────────────────────

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  if (req.method === "OPTIONS") return res.status(204).end();

  const { sport = "basketball", league = "nba", event_id = "", top = "8" } = req.query;
  const topN = Math.min(parseInt(top) || 8, 20);

  // Live data: very short cache
  res.setHeader("Cache-Control", "s-maxage=30, stale-while-revalidate=60");

  try {
    let data;
    if (event_id) {
      const sk = STAT_KEYS[sport] ?? STAT_KEYS.basketball;
      const { teams, labels } = await fetchBoxScore(event_id, sport, league, topN);
      data = { sport, league, event_id, stat_labels: labels, box_score: teams };
    } else {
      data = await fetchScoreboard(sport, league, topN);
    }
    return res.status(200).json(data);
  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
}
