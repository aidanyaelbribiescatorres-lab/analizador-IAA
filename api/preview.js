/**
 * /api/preview — Promedios + PREDICCIÓN de ambos equipos antes de un partido
 *
 * GET /api/preview?sport=basketball&league=nba&event_id=401585857
 * GET /api/preview?sport=soccer&league=esp.1&home=Real Madrid&away=Barcelona
 * GET /api/preview?sport=basketball&league=nba&home_id=13&away_id=14
 *
 * Params:
 *   sport     basketball | football | baseball | hockey | soccer
 *   league    nba | nfl | mlb | nhl | eng.1 | esp.1 | ita.1 | ger.1 | fra.1 | mex.1 | usa.1 | uefa.champions
 *   event_id  ESPN event ID
 *   home / away   nombres de equipos
 *   home_id / away_id   IDs ESPN
 *   limit     jugadores por equipo (default 12, max 25)
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
  PTS:"Puntos", REB:"Rebotes", AST:"Asistencias", "3PM":"Triples",
  "FG%":"Tiro %", "FT%":"TL %", STL:"Robos", BLK:"Tapones", TO:"Pérdidas", MIN:"Minutos",
  PYDS:"Yds pase", PTD:"TD pase", RUYDS:"Yds corrida", RUTD:"TD corrida",
  REC:"Recepciones", REYDS:"Yds rec.", RETD:"TD rec.", SACKS:"Sacks", INT:"INT", QBR:"QBR",
  AVG:"Promedio", HR:"HR", RBI:"RBI", SB:"Bases rob.", OBP:"OBP", SLG:"SLG",
  OPS:"OPS", ERA:"ERA", WHIP:"WHIP", K:"Strikeouts",
  "+/-":"+/-", PIM:"Min. penalti", SOG:"Tiros", GF:"GF", GA:"GA", "SV%":"SV%",
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

// ─── Helpers ESPN ────────────────────────────────────────────────────────────

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
    const candidates = [tm.displayName, tm.shortDisplayName, tm.abbreviation, tm.name, tm.nickname].filter(Boolean);
    for (const c of candidates) {
      const cl = c.toLowerCase();
      if (cl === nl) return tm.id;
      if (cl.includes(nl) || nl.includes(cl)) {
        const score = Math.min(nl.length, cl.length);
        if (score > bestScore) { bestScore = score; bestId = tm.id; }
      }
    }
  }
  return bestId;
}

async function fetchMatchTeams(sport, league, eventId) {
  const data = await espnGet(`${ESPN_SITE}/${sport}/${league}/summary`, { event: eventId });
  const comp = data?.header?.competitions?.[0] ?? {};
  let home = null, away = null;
  for (const c of comp.competitors ?? []) {
    const team = c.team ?? {};
    const obj = {
      id:   team.id ?? "",
      name: team.displayName ?? team.name ?? "",
      abbr: team.abbreviation ?? "",
      logo: team.logo ?? (team.logos?.[0]?.href ?? ""),
    };
    if (c.homeAway === "home") home = obj;
    else away = obj;
  }
  const meta = {
    name:  `${away?.name ?? ""} @ ${home?.name ?? ""}`,
    date:  comp.date ?? "",
    venue: comp.venue?.fullName ?? data?.gameInfo?.venue?.fullName ?? "",
    status: comp.status?.type?.description ?? "",
  };
  return { home, away, meta };
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
  } catch { return {}; }
}

async function buildTeam(sport, league, teamMeta, limit) {
  const wantKeys = sport === "soccer"
    ? [...new Set([...SOCCER_FLD_STATS, ...SOCCER_GK_STATS])]
    : (STAT_MAPS[sport] ?? STAT_MAPS.basketball);

  const roster = (await fetchRoster(sport, league, teamMeta.id)).slice(0, limit);
  const players = await Promise.all(roster.map(async (p) => {
    const isGK = ["GK","G","Goalkeeper","Portero"].includes(p.position);
    const keys = sport === "soccer" ? (isGK ? SOCCER_GK_STATS : SOCCER_FLD_STATS) : wantKeys;
    return { ...p, stats: p.id ? await fetchStats(sport, league, p.id, keys) : {} };
  }));

  return { ...teamMeta, players };
}

// ─── Predicción ──────────────────────────────────────────────────────────────

function avg(arr) {
  const vals = arr.filter(v => v != null && !isNaN(v));
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
}

function poissonProb(lambda, k) {
  if (lambda <= 0) return k === 0 ? 1 : 0;
  let p = Math.exp(-lambda);
  for (let i = 1; i <= k; i++) p *= lambda / i;
  return p;
}

function poissonMatch(lambdaH, lambdaA, max = 8) {
  let homeWin = 0, draw = 0, awayWin = 0;
  let mostLikelyScore = { h: 0, a: 0, p: 0 };
  for (let h = 0; h <= max; h++) {
    for (let a = 0; a <= max; a++) {
      const p = poissonProb(lambdaH, h) * poissonProb(lambdaA, a);
      if (h > a) homeWin += p;
      else if (h === a) draw += p;
      else awayWin += p;
      if (p > mostLikelyScore.p) mostLikelyScore = { h, a, p };
    }
  }
  return { homeWin, draw, awayWin, mostLikelyScore };
}

function predictMatch(sport, homePlayers, awayPlayers) {
  if (sport === "soccer") {
    // Goles esperados = suma de goles de jugadores de campo / partidos jugados promedio
    const fldH = homePlayers.filter(p => !["GK","G"].includes(p.position));
    const fldA = awayPlayers.filter(p => !["GK","G"].includes(p.position));
    const goalsH = fldH.reduce((s, p) => s + (p.stats.G || 0), 0);
    const goalsA = fldA.reduce((s, p) => s + (p.stats.G || 0), 0);
    const appsH  = avg(fldH.map(p => p.stats.APP)) || 20;
    const appsA  = avg(fldA.map(p => p.stats.APP)) || 20;
    const lambdaH = Math.max(0.3, (goalsH / appsH) * 1.1); // leve ventaja local
    const lambdaA = Math.max(0.3,  goalsA / appsA);
    const { homeWin, draw, awayWin, mostLikelyScore } = poissonMatch(lambdaH, lambdaA);
    return {
      method: "Distribución de Poisson sobre goles de temporada",
      home_win_pct:  Math.round(homeWin * 100),
      draw_pct:      Math.round(draw    * 100),
      away_win_pct:  Math.round(awayWin * 100),
      predicted_score: `${mostLikelyScore.h} - ${mostLikelyScore.a}`,
      home_xg: Math.round(lambdaH * 10) / 10,
      away_xg: Math.round(lambdaA * 10) / 10,
    };
  }

  if (sport === "basketball") {
    const ptsH = avg(homePlayers.map(p => p.stats.PTS));
    const ptsA = avg(awayPlayers.map(p => p.stats.PTS));
    const rebH = avg(homePlayers.map(p => p.stats.REB));
    const rebA = avg(awayPlayers.map(p => p.stats.REB));
    const astH = avg(homePlayers.map(p => p.stats.AST));
    const astA = avg(awayPlayers.map(p => p.stats.AST));
    // Score ofensivo ponderado
    const offH = ptsH * 1.0 + rebH * 0.3 + astH * 0.5;
    const offA = ptsA * 1.0 + rebA * 0.3 + astA * 0.5;
    const total = offH + offA || 1;
    const homeWin = (offH / total) * 0.95 + 0.05; // pequeña ventaja de cancha
    // Marcador estimado: promedio NBA ~115pts por equipo como base
    const scaleH = Math.round(105 + (offH / total - 0.5) * 30);
    const scaleA = Math.round(105 - (offH / total - 0.5) * 30);
    return {
      method: "Índice ofensivo ponderado (PTS + REB + AST)",
      home_win_pct: Math.round(Math.min(homeWin, 0.85) * 100),
      draw_pct: 0,
      away_win_pct: Math.round((1 - Math.min(homeWin, 0.85)) * 100),
      predicted_score: `${scaleH} - ${scaleA}`,
      home_avg_pts: Math.round(ptsH * 10) / 10,
      away_avg_pts: Math.round(ptsA * 10) / 10,
    };
  }

  if (sport === "hockey") {
    const gfH = avg(homePlayers.map(p => p.stats.G));
    const gfA = avg(awayPlayers.map(p => p.stats.G));
    const lambdaH = Math.max(0.5, gfH * 3.5 + 0.2);
    const lambdaA = Math.max(0.5, gfA * 3.5);
    const { homeWin, draw, awayWin, mostLikelyScore } = poissonMatch(lambdaH, lambdaA, 10);
    return {
      method: "Poisson sobre promedio de goles por jugador",
      home_win_pct: Math.round(homeWin * 100),
      draw_pct:     Math.round(draw    * 100),
      away_win_pct: Math.round(awayWin * 100),
      predicted_score: `${mostLikelyScore.h} - ${mostLikelyScore.a}`,
    };
  }

  if (sport === "baseball") {
    const avgH = avg(homePlayers.map(p => p.stats.AVG));
    const avgA = avg(awayPlayers.map(p => p.stats.AVG));
    const rbiH = avg(homePlayers.map(p => p.stats.RBI));
    const rbiA = avg(awayPlayers.map(p => p.stats.RBI));
    const offH = avgH * 10 + rbiH * 0.1;
    const offA = avgA * 10 + rbiA * 0.1;
    const total = offH + offA || 1;
    const homeWin = (offH / total) * 0.94 + 0.05;
    const runsH = Math.round(3 + (offH / total - 0.5) * 6);
    const runsA = Math.round(3 - (offH / total - 0.5) * 6);
    return {
      method: "Índice ofensivo (AVG + RBI)",
      home_win_pct: Math.round(Math.min(homeWin, 0.82) * 100),
      draw_pct: 0,
      away_win_pct: Math.round((1 - Math.min(homeWin, 0.82)) * 100),
      predicted_score: `${Math.max(runsH, 1)} - ${Math.max(runsA, 1)}`,
    };
  }

  if (sport === "football") {
    const pydsH = avg(homePlayers.map(p => p.stats.PYDS));
    const pydsA = avg(awayPlayers.map(p => p.stats.PYDS));
    const ruydsH = avg(homePlayers.map(p => p.stats.RUYDS));
    const ruydsA = avg(awayPlayers.map(p => p.stats.RUYDS));
    const offH = (pydsH || 0) + (ruydsH || 0);
    const offA = (pydsA || 0) + (ruydsA || 0);
    const total = offH + offA || 1;
    const homeWin = (offH / total) * 0.93 + 0.05;
    const ptsH = Math.round(17 + (offH / total - 0.5) * 28);
    const ptsA = Math.round(17 - (offH / total - 0.5) * 28);
    return {
      method: "Yardas totales (pase + corrida)",
      home_win_pct: Math.round(Math.min(homeWin, 0.82) * 100),
      draw_pct: 0,
      away_win_pct: Math.round((1 - Math.min(homeWin, 0.82)) * 100),
      predicted_score: `${Math.max(ptsH, 3)} - ${Math.max(ptsA, 3)}`,
    };
  }

  return null;
}

// ─── Main handler ────────────────────────────────────────────────────────────

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  if (req.method === "OPTIONS") return res.status(204).end();

  const {
    sport = "basketball", league = "nba",
    event_id = "", home = "", away = "",
    home_id = "", away_id = "", limit = "12",
  } = req.query;

  const maxPlayers = Math.min(parseInt(limit) || 12, 25);

  try {
    let homeMeta, awayMeta, meta = {};

    if (event_id) {
      const m = await fetchMatchTeams(sport, league, event_id);
      if (!m.home || !m.away) throw new Error(`No se encontraron los equipos del partido ${event_id}`);
      homeMeta = m.home; awayMeta = m.away; meta = m.meta;
    } else {
      let hId = home_id, aId = away_id;
      if (!hId) {
        if (!home) throw new Error("Falta 'event_id' o ('home' y 'away')");
        hId = await findTeamId(sport, league, home);
        if (!hId) throw new Error(`Equipo local '${home}' no encontrado`);
      }
      if (!aId) {
        if (!away) throw new Error("Falta 'away' (equipo visitante)");
        aId = await findTeamId(sport, league, away);
        if (!aId) throw new Error(`Equipo visitante '${away}' no encontrado`);
      }
      homeMeta = { id: hId, name: home || `Equipo ${hId}`, abbr: "", logo: "" };
      awayMeta = { id: aId, name: away || `Equipo ${aId}`, abbr: "", logo: "" };
    }

    const [homeTeam, awayTeam] = await Promise.all([
      buildTeam(sport, league, homeMeta, maxPlayers),
      buildTeam(sport, league, awayMeta, maxPlayers),
    ]);

    const prediction = predictMatch(sport, homeTeam.players, awayTeam.players);

    const wantKeys = sport === "soccer"
      ? [...new Set([...SOCCER_FLD_STATS, ...SOCCER_GK_STATS])]
      : (STAT_MAPS[sport] ?? STAT_MAPS.basketball);
    const allKeys = [...new Set([...wantKeys, ...SOCCER_GK_STATS])];
    const statLabels = Object.fromEntries(allKeys.map(k => [k, STAT_LABELS[k] ?? k]));

    res.setHeader("Cache-Control", "s-maxage=1800, stale-while-revalidate");
    return res.status(200).json({
      sport, league,
      league_name: SOCCER_LEAGUES[league] ?? league.toUpperCase(),
      match: meta,
      stat_labels: statLabels,
      prediction,
      home: homeTeam,
      away: awayTeam,
    });

  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
}
