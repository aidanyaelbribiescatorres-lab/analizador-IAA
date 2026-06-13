/**
 * /api/players — Estadísticas de jugadores por equipo (promedios de temporada)
 *
 * GET /api/players?team=Barcelona&sport=soccer&league=esp.1
 * GET /api/players?team=Lakers&sport=basketball&league=nba
 * GET /api/players?team=Chiefs&sport=football&league=nfl
 * GET /api/players?team=Dodgers&sport=baseball&league=mlb
 * GET /api/players?team=Oilers&sport=hockey&league=nhl
 * GET /api/players?team_id=83&sport=soccer&league=esp.1
 *
 * Params:
 *   sport    basketball | football | baseball | hockey | soccer
 *   league   nba | nfl | mlb | nhl | eng.1 | esp.1 | ita.1 | ger.1 | fra.1 | mex.1 | usa.1 | uefa.champions
 *   team     nombre del equipo (búsqueda aproximada)
 *   team_id  ESPN team ID (más rápido, sin búsqueda)
 *   limit    max jugadores (default 15, max 30)
 *   stats    true|false — incluir estadísticas (default true)
 */

const ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports";
const ESPN_CMVN = "https://site.web.api.espn.com/apis/common/v3/sports";

const STAT_MAPS = {
  basketball: ["PTS","REB","AST","3PM","FG%","FT%","STL","BLK","TO","MIN"],
  football:   ["PYDS","PTD","RUYDS","RUTD","REC","REYDS","RETD","SACKS","INT","QBR"],
  baseball:   ["AVG","HR","RBI","SB","OBP","SLG","OPS","ERA","WHIP","K"],
  hockey:     ["G","A","PTS","+/-","PIM","SOG","GF","GA","SV%"],
  soccer:     ["G","A","SH","SHG","FC","YC","RC","OFF","APP","MIN"],
};

const STAT_LABELS = {
  // Basketball
  PTS:"Puntos", REB:"Rebotes", AST:"Asistencias", "3PM":"Triples",
  "FG%":"Tiro %", "FT%":"TL %", STL:"Robos", BLK:"Tapones", TO:"Pérdidas", MIN:"Minutos",
  // Football
  PYDS:"Yds pase", PTD:"TD pase", RUYDS:"Yds corrida", RUTD:"TD corrida",
  REC:"Recepciones", REYDS:"Yds rec.", RETD:"TD rec.", SACKS:"Sacks", INT:"INT", QBR:"QBR",
  // Baseball
  AVG:"Promedio", HR:"HR", RBI:"RBI", SB:"Bases rob.", OBP:"OBP", SLG:"SLG",
  OPS:"OPS", ERA:"ERA", WHIP:"WHIP", K:"Strikeouts",
  // Hockey
  "+/-":"+/-", PIM:"Min. penalti", SOG:"Tiros", GF:"GF", GA:"GA", "SV%":"SV%",
  // Soccer
  G:"Goles", A:"Asistencias", SH:"Tiros", SHG:"Al arco",
  FC:"Faltas", YC:"Amarillas", RC:"Rojas", OFF:"Fuera juego", APP:"Partidos",
  GK_SV:"Paradas", GK_GA:"Goles recibidos",
};

const SOCCER_GK_STATS  = ["APP","MIN","GK_SV","GK_GA","YC","RC"];
const SOCCER_FLD_STATS = ["G","A","SH","SHG","FC","YC","RC","OFF","APP","MIN"];

const SOCCER_LEAGUES = {
  "eng.1":"Premier League","esp.1":"La Liga","ita.1":"Serie A","ger.1":"Bundesliga",
  "fra.1":"Ligue 1","mex.1":"Liga MX","usa.1":"MLS",
  "uefa.champions":"Champions League","fifa.world":"Copa del Mundo",
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function espnGet(url, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const full = qs ? `${url}?${qs}` : url;
  const res = await fetch(full, { headers: { "User-Agent": "ScoutAI/1.0" } });
  if (!res.ok) throw new Error(`ESPN ${res.status}: ${full}`);
  return res.json();
}

async function findTeamId(sport, league, name) {
  const data = await espnGet(`${ESPN_SITE}/${sport}/${league}/teams`, { limit: 100 });
  const teams = data?.sports?.[0]?.leagues?.[0]?.teams ?? [];
  const nl = name.toLowerCase();

  let bestId = null, bestScore = 0;
  for (const t of teams) {
    const tm = t.team ?? {};
    const tid = tm.id;
    const candidates = [
      tm.displayName, tm.shortDisplayName, tm.abbreviation, tm.name, tm.nickname,
    ].filter(Boolean);

    for (const c of candidates) {
      const cl = c.toLowerCase();
      if (cl === nl) return tid;                   // exact
      if (cl.includes(nl) || nl.includes(cl)) {
        const score = Math.min(nl.length, cl.length);
        if (score > bestScore) { bestScore = score; bestId = tid; }
      }
    }
  }
  return bestId;
}

async function fetchRoster(sport, league, teamId) {
  const data = await espnGet(`${ESPN_SITE}/${sport}/${league}/teams/${teamId}/roster`);
  const players = [];
  for (const group of data.athletes ?? []) {
    const items = Array.isArray(group) ? group : (group.items ?? []);
    for (const a of items) {
      players.push({
        id:       String(a.id ?? ""),
        name:     a.displayName ?? a.fullName ?? "",
        jersey:   a.jersey ?? "",
        position: a.position?.abbreviation ?? "",
        headshot: a.headshot?.href ?? "",
      });
    }
  }
  return players;
}

async function fetchStats(sport, league, playerId, wantKeys) {
  try {
    const data = await espnGet(`${ESPN_CMVN}/${sport}/${league}/athletes/${playerId}/stats`);
    const raw = {};
    for (const cat of data?.splits?.categories ?? []) {
      const catName = (cat.name ?? "").toLowerCase();
      for (const x of cat.stats ?? []) {
        const k = x.abbreviation ?? "";
        const v = x.value;
        if (v == null) continue;
        raw[k] = v;
        if (sport === "soccer" && ["goalkeeping","goalkeeper"].includes(catName)) {
          if (k === "SV") raw["GK_SV"] = v;
          if (k === "GA") raw["GK_GA"] = v;
        }
      }
    }
    const result = {};
    for (const k of wantKeys) {
      if (raw[k] != null) result[k] = Math.round(raw[k] * 10) / 10;
    }
    return result;
  } catch {
    return {};
  }
}

// ─── Main handler ─────────────────────────────────────────────────────────────

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  if (req.method === "OPTIONS") return res.status(204).end();

  const { sport = "basketball", league = "nba", team = "",
          team_id = "", limit = "15", stats = "true" } = req.query;

  const maxPlayers  = Math.min(parseInt(limit) || 15, 30);
  const includeStats = stats !== "false";

  try {
    let teamId = team_id;
    if (!teamId) {
      if (!team) throw new Error("Param 'team' or 'team_id' required");
      teamId = await findTeamId(sport, league, team);
      if (!teamId) throw new Error(`Team '${team}' not found in ${sport}/${league}`);
    }

    const wantKeys = sport === "soccer"
      ? [...new Set([...SOCCER_FLD_STATS, ...SOCCER_GK_STATS])]
      : (STAT_MAPS[sport] ?? STAT_MAPS.basketball);

    const roster = (await fetchRoster(sport, league, teamId)).slice(0, maxPlayers);

    const players = await Promise.all(roster.map(async (p) => {
      const isGK = ["GK","G","Goalkeeper","Portero"].includes(p.position);
      const keys = sport === "soccer"
        ? (isGK ? SOCCER_GK_STATS : SOCCER_FLD_STATS)
        : wantKeys;

      return {
        ...p,
        stats: (includeStats && p.id) ? await fetchStats(sport, league, p.id, keys) : {},
      };
    }));

    const allKeys = [...new Set([...wantKeys, ...SOCCER_GK_STATS])];
    const statLabels = Object.fromEntries(allKeys.map(k => [k, STAT_LABELS[k] ?? k]));

    res.setHeader("Cache-Control", "s-maxage=1800, stale-while-revalidate");
    return res.status(200).json({
      sport, league,
      league_name: SOCCER_LEAGUES[league] ?? league.toUpperCase(),
      team_id: teamId,
      stat_labels: statLabels,
      players,
    });

  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
}
