/**
 * /api/preview — Análisis pre-partido: promedios de equipo + predicción
 *
 * Usa la API pública GRATUITA de ESPN (sin API key).
 * Obtiene estadísticas a nivel equipo (una sola llamada por equipo)
 * para evitar timeouts en Vercel free tier (límite 10s).
 *
 * GET /api/preview?sport=basketball&league=nba&event_id=401585857
 * GET /api/preview?sport=soccer&league=esp.1&home=Real Madrid&away=Barcelona
 * GET /api/preview?sport=basketball&league=nba&home_id=13&away_id=14
 */

const ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports";

const SOCCER_LEAGUES = {
  "eng.1":"Premier League","esp.1":"La Liga","ita.1":"Serie A","ger.1":"Bundesliga",
  "fra.1":"Ligue 1","mex.1":"Liga MX","usa.1":"MLS",
  "uefa.champions":"Champions League","fifa.world":"Copa del Mundo",
};

// ─── ESPN fetch ───────────────────────────────────────────────────────────────

async function espnGet(url, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const full = qs ? `${url}?${qs}` : url;
  const res = await fetch(full, {
    headers: { "User-Agent": "Mozilla/5.0 (compatible; ScoutAI/1.0)" },
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) throw new Error(`ESPN ${res.status}`);
  return res.json();
}

// ─── Buscar equipo por nombre ─────────────────────────────────────────────────

async function findTeam(sport, league, name) {
  const data = await espnGet(`${ESPN_SITE}/${sport}/${league}/teams`, { limit: 100 });
  const teams = data?.sports?.[0]?.leagues?.[0]?.teams ?? [];
  const nl = name.toLowerCase();
  let best = null, bestScore = 0;
  for (const t of teams) {
    const tm = t.team ?? {};
    const candidates = [tm.displayName, tm.shortDisplayName, tm.abbreviation, tm.name, tm.nickname].filter(Boolean);
    for (const c of candidates) {
      const cl = c.toLowerCase();
      if (cl === nl) return { id: tm.id, name: tm.displayName||tm.name, abbr: tm.abbreviation||"", logo: tm.logos?.[0]?.href||tm.logo||"" };
      if (cl.includes(nl) || nl.includes(cl)) {
        const score = Math.min(nl.length, cl.length);
        if (score > bestScore) {
          bestScore = score;
          best = { id: tm.id, name: tm.displayName||tm.name, abbr: tm.abbreviation||"", logo: tm.logos?.[0]?.href||tm.logo||"" };
        }
      }
    }
  }
  return best;
}

// ─── Stats de equipo (una sola llamada, muy rápida) ───────────────────────────

async function fetchTeamStats(sport, league, teamId) {
  try {
    const data = await espnGet(`${ESPN_SITE}/${sport}/${league}/teams/${teamId}/statistics`);
    // ESPN devuelve categories con arrays de stats
    const result = {};
    for (const cat of data?.results?.stats?.categories ?? []) {
      for (const s of cat.stats ?? []) {
        const k = s.abbreviation ?? s.name ?? "";
        if (k && s.value != null) result[k] = Math.round(Number(s.value) * 100) / 100;
      }
    }
    // fallback: raíz del objeto
    if (!Object.keys(result).length) {
      for (const cat of data?.stats?.categories ?? []) {
        for (const s of cat.stats ?? []) {
          const k = s.abbreviation ?? s.name ?? "";
          if (k && s.value != null) result[k] = Math.round(Number(s.value) * 100) / 100;
        }
      }
    }
    return result;
  } catch { return {}; }
}

// ─── Roster ligero (sin stats por jugador) ────────────────────────────────────

async function fetchRosterLight(sport, league, teamId) {
  try {
    const data = await espnGet(`${ESPN_SITE}/${sport}/${league}/teams/${teamId}/roster`);
    const players = [];
    for (const group of data.athletes ?? []) {
      const items = Array.isArray(group) ? group : (group.items ?? []);
      for (const a of items.slice(0, 15)) {
        players.push({
          name:     a.displayName ?? a.fullName ?? "",
          jersey:   a.jersey ?? "",
          position: a.position?.abbreviation ?? "",
          headshot: a.headshot?.href ?? "",
        });
      }
    }
    return players;
  } catch { return []; }
}

// ─── Datos del partido desde event_id ────────────────────────────────────────

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
      logo: team.logo ?? team.logos?.[0]?.href ?? "",
    };
    if (c.homeAway === "home") home = obj;
    else away = obj;
  }
  const meta = {
    name:   `${away?.name ?? ""} @ ${home?.name ?? ""}`,
    date:   comp.date ?? "",
    venue:  comp.venue?.fullName ?? data?.gameInfo?.venue?.fullName ?? "",
    status: comp.status?.type?.description ?? "",
  };
  return { home, away, meta };
}

// ─── Claves relevantes por deporte ────────────────────────────────────────────

const TEAM_STAT_KEYS = {
  basketball: {
    off: ["PPG","RPG","APG","3PM","FGP","FTP","SPG","BPG","TOV"],
    labels: { PPG:"Puntos/partido",RPG:"Rebotes/partido",APG:"Asist./partido",
              "3PM":"Triples/partido","FGP":"TC%","FTP":"TL%",
              SPG:"Robos/partido",BPG:"Tapones/partido",TOV:"Pérdidas/partido" }
  },
  football: {
    off: ["PYD","RYD","PPG","3RD","TOV","SCK"],
    labels: { PYD:"Yds pase/partido",RYD:"Yds corrida/partido",PPG:"Puntos/partido",
              "3RD":"Conv. 3ra","TOV":"Turnovers",SCK:"Sacks recibidos" }
  },
  baseball: {
    off: ["AVG","OBP","SLG","OPS","HR","RBI","ERA","WHIP"],
    labels: { AVG:"Promedio",OBP:"OBP",SLG:"SLG",OPS:"OPS",
              HR:"HR",RBI:"RBI",ERA:"ERA equipo",WHIP:"WHIP equipo" }
  },
  hockey: {
    off: ["GF","GA","PP%","PK%","SOG","SV%"],
    labels: { GF:"Goles a favor/p",GA:"Goles en contra/p",
              "PP%":"Power play%","PK%":"Penalti kill%",SOG:"Tiros/partido","SV%":"SV%" }
  },
  soccer: {
    off: ["GF","GA","SH","SHG","POSS","YC"],
    labels: { GF:"Goles anotados",GA:"Goles recibidos",SH:"Tiros/partido",
              SHG:"Al arco/partido",POSS:"Posesión%",YC:"Amarillas" }
  },
};

// ─── Predicción ───────────────────────────────────────────────────────────────

function poissonProb(lambda, k) {
  if (lambda <= 0) return k === 0 ? 1 : 0;
  let p = Math.exp(-lambda);
  for (let i = 1; i <= k; i++) p *= lambda / i;
  return p;
}

function poissonMatch(lH, lA, max = 9) {
  let hw = 0, d = 0, aw = 0, best = { h:0, a:0, p:0 };
  for (let h = 0; h <= max; h++) for (let a = 0; a <= max; a++) {
    const p = poissonProb(lH, h) * poissonProb(lA, a);
    if (h > a) hw += p; else if (h === a) d += p; else aw += p;
    if (p > best.p) best = { h, a, p };
  }
  return { hw, d, aw, best };
}

function clamp(v, mn, mx) { return Math.max(mn, Math.min(mx, v)); }

function makePrediction(sport, homeStats, awayStats, homeName, awayName) {
  if (sport === "soccer") {
    const lH = clamp((homeStats.GF || 1.2) * 1.1, 0.3, 4);
    const lA = clamp(awayStats.GF || 1.0, 0.3, 4);
    const { hw, d, aw, best } = poissonMatch(lH, lA);
    return {
      method: "Poisson — goles de temporada",
      home_win_pct: Math.round(hw * 100),
      draw_pct:     Math.round(d  * 100),
      away_win_pct: Math.round(aw * 100),
      predicted_score: `${best.h} - ${best.a}`,
      extra: `xG: ${awayName} ${lA.toFixed(1)} — ${homeName} ${lH.toFixed(1)}`,
    };
  }
  if (sport === "basketball") {
    const offH = (homeStats.PPG||0)*1 + (homeStats.RPG||0)*0.3 + (homeStats.APG||0)*0.5;
    const offA = (awayStats.PPG||0)*1 + (awayStats.RPG||0)*0.3 + (awayStats.APG||0)*0.5;
    const tot  = (offH + offA) || 1;
    const hw   = clamp(offH/tot * 0.94 + 0.05, 0.15, 0.85);
    const sH   = Math.round(105 + (offH/tot - 0.5) * 30);
    const sA   = Math.round(105 - (offH/tot - 0.5) * 30);
    return {
      method: "Índice ofensivo (PTS + REB + AST)",
      home_win_pct: Math.round(hw * 100),
      draw_pct: 0,
      away_win_pct: Math.round((1-hw) * 100),
      predicted_score: `${sA} - ${sH}`,
      extra: `PPG: ${awayName} ${awayStats.PPG||"?"} — ${homeName} ${homeStats.PPG||"?"}`,
    };
  }
  if (sport === "hockey") {
    const lH = clamp((homeStats.GF||2.8)*1.05, 0.5, 6);
    const lA = clamp(awayStats.GF||2.5, 0.5, 6);
    const { hw, d, aw, best } = poissonMatch(lH, lA, 10);
    return {
      method: "Poisson — goles por partido",
      home_win_pct: Math.round(hw * 100),
      draw_pct:     Math.round(d  * 100),
      away_win_pct: Math.round(aw * 100),
      predicted_score: `${best.h} - ${best.a}`,
      extra: `GF/p: ${awayName} ${(awayStats.GF||"?").toString()} — ${homeName} ${(homeStats.GF||"?").toString()}`,
    };
  }
  if (sport === "football") {
    const offH = (homeStats.PYD||0) + (homeStats.RYD||0);
    const offA = (awayStats.PYD||0) + (awayStats.RYD||0);
    const tot  = (offH + offA) || 1;
    const hw   = clamp(offH/tot * 0.93 + 0.05, 0.15, 0.82);
    const sH   = Math.max(3, Math.round((homeStats.PPG||21) * 1.05));
    const sA   = Math.max(3, Math.round((awayStats.PPG||21) * 0.95));
    return {
      method: "Yardas totales + puntos por partido",
      home_win_pct: Math.round(hw * 100),
      draw_pct: 0,
      away_win_pct: Math.round((1-hw) * 100),
      predicted_score: `${sA} - ${sH}`,
      extra: `PPG: ${awayName} ${awayStats.PPG||"?"} — ${homeName} ${homeStats.PPG||"?"}`,
    };
  }
  if (sport === "baseball") {
    const offH = (homeStats.OPS||0.7)*10 + (homeStats.RBI||0)*0.01;
    const offA = (awayStats.OPS||0.7)*10 + (awayStats.RBI||0)*0.01;
    const tot  = (offH + offA) || 1;
    const hw   = clamp(offH/tot * 0.93 + 0.05, 0.18, 0.82);
    const sH   = Math.max(1, Math.round(4 + (offH/tot - 0.5) * 6));
    const sA   = Math.max(1, Math.round(4 - (offH/tot - 0.5) * 6));
    return {
      method: "OPS + RBI del equipo",
      home_win_pct: Math.round(hw * 100),
      draw_pct: 0,
      away_win_pct: Math.round((1-hw) * 100),
      predicted_score: `${sA} - ${sH}`,
      extra: `OPS: ${awayName} ${awayStats.OPS||"?"} — ${homeName} ${homeStats.OPS||"?"}`,
    };
  }
  return null;
}

// ─── Main handler ─────────────────────────────────────────────────────────────

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
  if (req.method === "OPTIONS") return res.status(204).end();

  const { sport="basketball", league="nba", event_id="", home="", away="", home_id="", away_id="" } = req.query;

  try {
    let homeMeta, awayMeta, meta = {};

    if (event_id) {
      const m = await fetchMatchTeams(sport, league, event_id);
      if (!m.home || !m.away) throw new Error(`No se encontraron los equipos del partido`);
      homeMeta = m.home; awayMeta = m.away; meta = m.meta;
    } else {
      let hId = home_id, aId = away_id;
      if (!hId) {
        if (!home) throw new Error("Falta 'event_id' o ('home' y 'away')");
        const t = await findTeam(sport, league, home);
        if (!t) throw new Error(`Equipo '${home}' no encontrado`);
        hId = t.id; homeMeta = t;
      } else {
        homeMeta = { id: hId, name: home||`Equipo ${hId}`, abbr:"", logo:"" };
      }
      if (!aId) {
        if (!away) throw new Error("Falta 'away'");
        const t = await findTeam(sport, league, away);
        if (!t) throw new Error(`Equipo '${away}' no encontrado`);
        aId = t.id; awayMeta = t;
      } else {
        awayMeta = { id: aId, name: away||`Equipo ${aId}`, abbr:"", logo:"" };
      }
    }

    // Obtener stats de equipo + roster en paralelo (4 llamadas en total, muy rápido)
    const [homeStats, awayStats, homeRoster, awayRoster] = await Promise.all([
      fetchTeamStats(sport, league, homeMeta.id),
      fetchTeamStats(sport, league, awayMeta.id),
      fetchRosterLight(sport, league, homeMeta.id),
      fetchRosterLight(sport, league, awayMeta.id),
    ]);

    const prediction = makePrediction(sport, homeStats, awayStats, homeMeta.name, awayMeta.name);
    const keys = TEAM_STAT_KEYS[sport] ?? TEAM_STAT_KEYS.basketball;

    res.setHeader("Cache-Control", "s-maxage=1800, stale-while-revalidate=3600");
    return res.status(200).json({
      sport, league,
      league_name: SOCCER_LEAGUES[league] ?? league.toUpperCase(),
      match: meta,
      stat_keys: keys.off,
      stat_labels: keys.labels,
      prediction,
      home: { ...homeMeta, stats: homeStats, roster: homeRoster },
      away: { ...awayMeta, stats: awayStats, roster: awayRoster },
    });

  } catch (err) {
    return res.status(400).json({ error: err.message });
  }
}
