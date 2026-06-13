// Ejemplo de uso en React / tu app Vercel
// -----------------------------------------------

const BASE = process.env.NEXT_PUBLIC_API_URL || "";   // déjalo vacío si la API está en el mismo proyecto Vercel

/**
 * Obtiene los jugadores y estadísticas de un equipo.
 *
 * @param {string} team     - Nombre del equipo ("Lakers", "Warriors", "Chiefs")
 * @param {string} sport    - "basketball" | "football" | "baseball" | "hockey"
 * @param {string} league   - "nba" | "nfl" | "mlb" | "nhl"
 * @param {number} limit    - Máximo de jugadores (default 15)
 * @param {boolean} stats   - Incluir estadísticas (default true)
 */
export async function fetchPlayers(team, sport = "basketball", league = "nba", limit = 15, stats = true) {
  const url = `${BASE}/api/players?team=${encodeURIComponent(team)}&sport=${sport}&league=${league}&limit=${limit}&stats=${stats}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Respuesta ejemplo ────────────────────────────────────────────────────────
/*
{
  "sport": "basketball",
  "league": "nba",
  "team_id": "13",
  "stat_labels": {
    "PTS": "Puntos",
    "REB": "Rebotes",
    "AST": "Asistencias",
    "3PM": "Triples",
    "FG%": "Tiro %",
    "FT%": "TL %",
    "STL": "Robos",
    "BLK": "Tapones",
    "TO":  "Pérdidas",
    "MIN": "Minutos"
  },
  "players": [
    {
      "id": "1966",
      "name": "LeBron James",
      "jersey": "23",
      "position": "SF",
      "headshot": "https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/1966.png",
      "stats": {
        "PTS": 25.7,
        "REB": 7.3,
        "AST": 8.3,
        "3PM": 2.1,
        "FG%": 54.0,
        "FT%": 75.0,
        "STL": 1.3,
        "BLK": 0.5,
        "TO":  3.5,
        "MIN": 35.3
      }
    }
  ]
}
*/

// ── Ejemplos de uso ──────────────────────────────────────────────────────────

// NBA
// fetchPlayers("Lakers", "basketball", "nba")
// fetchPlayers("Warriors", "basketball", "nba")

// NFL
// fetchPlayers("Chiefs", "football", "nfl")
// fetchPlayers("Cowboys", "football", "nfl")

// MLB
// fetchPlayers("Dodgers", "baseball", "mlb")

// NHL
// fetchPlayers("Oilers", "hockey", "nhl")

// Por team_id exacto de ESPN (más rápido, sin búsqueda)
// fetch("/api/players?team_id=13&sport=basketball&league=nba")
