import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="NEON BET AI", page_icon="🟢", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #050505; color: #00FF00; }
    #MainMenu, footer, header { visibility: hidden; }
    h1, h2, h3, h4 { color: #00FF41 !important; font-family: 'Courier New', monospace; text-shadow: 0 0 5px #00FF41; }
    .stButton>button { background-color: #000; color: #00FF41; border: 1px solid #00FF41; border-radius: 5px; width: 100%; transition: all 0.3s; }
    .stButton>button:hover { background-color: #00FF41; color: #000; box-shadow: 0 0 15px #00FF41; }
    .stSelectbox label, .stNumberInput label { color: #00FF41 !important; font-family: 'Courier New', monospace; }
    div[data-testid="stMetricValue"] { color: #00FF41 !important; font-size: 1.4rem !important; }
    div[data-testid="stMetricLabel"] { color: #888 !important; }
    .stDataFrame { border: 1px solid #333; }
    div[data-testid="stExpander"] { border: 1px solid #1a1a1a; background-color: #080808; }
    </style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [('saldo', 24.27), ('messages', []), ('show_value', False)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Constants ──────────────────────────────────────────────────────────────────
ODDS_KEY  = '8d90dd7eb80726fb3a98683ee7d2e734'
ODDS_BASE = 'https://api.the-odds-api.com/v4'
ESPN_SITE = 'https://site.api.espn.com/apis/site/v2/sports'
ESPN_CMVN = 'https://site.web.api.espn.com/apis/common/v3/sports'

SPORTS = {
    '🏀 NBA': {'key': 'basketball_nba',      'sport': 'basketball', 'league': 'nba', 'total': 'puntos',   'players': True},
    '🏈 NFL': {'key': 'americanfootball_nfl', 'sport': 'football',   'league': 'nfl', 'total': 'puntos',   'players': False},
    '⚾ MLB': {'key': 'baseball_mlb',         'sport': 'baseball',   'league': 'mlb', 'total': 'carreras', 'players': False},
    '🏒 NHL': {'key': 'icehockey_nhl',        'sport': 'hockey',     'league': 'nhl', 'total': 'goles',    'players': False},
}

# ── Data fetching ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_odds(sport_key):
    try:
        r = requests.get(
            f'{ODDS_BASE}/sports/{sport_key}/odds/',
            params={'apiKey': ODDS_KEY, 'regions': 'us,eu',
                    'markets': 'h2h,totals,spreads', 'oddsFormat': 'decimal'},
            timeout=12
        )
        return r.json() if r.ok else []
    except Exception:
        return []

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_espn_teams(sport, league):
    try:
        r = requests.get(f'{ESPN_SITE}/{sport}/{league}/teams',
                         params={'limit': 100}, timeout=10)
        if not r.ok:
            return {}
        d = r.json()
        teams = d.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])
        return {t['team']['displayName']: t['team']['id'] for t in teams}
    except Exception:
        return {}

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_roster(sport, league, team_id):
    """Returns (players_list, injured_list)."""
    try:
        r = requests.get(f'{ESPN_SITE}/{sport}/{league}/teams/{team_id}/roster', timeout=10)
        if not r.ok:
            return [], []
        data = r.json()
        players, injured = [], []

        for group in data.get('athletes', []):
            items = group.get('items', []) if isinstance(group, dict) else (group if isinstance(group, list) else [])
            for a in items:
                pid   = str(a.get('id', ''))
                pname = a.get('displayName') or a.get('fullName', '')
                pos_raw = a.get('position', {})
                pos = pos_raw.get('abbreviation', '') if isinstance(pos_raw, dict) else str(pos_raw)

                if pid and pname:
                    players.append({'id': pid, 'name': pname, 'pos': pos})

                for inj in a.get('injuries', []):
                    status = inj.get('status', '') or inj.get('type', {}).get('description', '') if isinstance(inj.get('type'), dict) else ''
                    injured.append({
                        'name':   pname,
                        'status': status or 'OUT',
                        'note':   inj.get('shortComment', '')
                    })

        return players[:12], injured[:6]
    except Exception:
        return [], []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_nba_stats(athlete_id):
    """NBA player season averages from ESPN."""
    try:
        r = requests.get(f'{ESPN_CMVN}/basketball/nba/athletes/{athlete_id}/stats', timeout=10)
        if not r.ok:
            return {}
        data = r.json()
        stats = {}
        for cat in data.get('splits', {}).get('categories', []):
            for s in cat.get('stats', []):
                stats[s.get('abbreviation', '')] = s.get('value')
        return stats
    except Exception:
        return {}

# ── Math helpers ───────────────────────────────────────────────────────────────

def _avg(lst):
    return sum(lst) / len(lst) if lst else None

def _median(lst):
    if not lst:
        return None
    s = sorted(lst)
    n = len(s)
    return (s[n//2-1] + s[n//2]) / 2 if n % 2 == 0 else s[n//2]

def true_probs(o1, o2):
    i1, i2 = 1/o1, 1/o2
    m = i1 + i2
    return (i1/m)*100, (i2/m)*100

def kelly_frac(prob_pct, decimal_odds):
    b = decimal_odds - 1
    p = prob_pct / 100
    return max((b*p - (1-p)) / b, 0)

def fmt_stat(v):
    try:
        return f"{float(v):.1f}"
    except (TypeError, ValueError):
        return "—"

def match_team(name, teams_dict):
    if not teams_dict:
        return None
    if name in teams_dict:
        return teams_dict[name]
    nl = name.lower()
    for k, v in teams_dict.items():
        if nl in k.lower() or k.lower() in nl:
            return v
    for word in reversed(name.split()):
        if len(word) > 3:
            for k, v in teams_dict.items():
                if word.lower() in k.lower():
                    return v
    return None

# ── Market parsers ─────────────────────────────────────────────────────────────

def parse_h2h(game, home, away):
    h, a = [], []
    for bk in game.get('bookmakers', []):
        for mkt in bk.get('markets', []):
            if mkt['key'] != 'h2h':
                continue
            for o in mkt.get('outcomes', []):
                if o['name'] == home:   h.append(o['price'])
                elif o['name'] == away: a.append(o['price'])
    return _avg(h), _avg(a), (max(h) if h else None), (max(a) if a else None)

def parse_totals(game):
    overs, unders, lines = [], [], []
    for bk in game.get('bookmakers', []):
        for mkt in bk.get('markets', []):
            if mkt['key'] != 'totals':
                continue
            for o in mkt.get('outcomes', []):
                pt = o.get('point', 0)
                lines.append(pt)
                if o['name'] == 'Over':   overs.append(o['price'])
                elif o['name'] == 'Under': unders.append(o['price'])
    return (lines[0] if lines else None), _avg(overs), _avg(unders)

def parse_spreads(game, home, away):
    h_pts, a_pts, h_odds, a_odds = [], [], [], []
    for bk in game.get('bookmakers', []):
        for mkt in bk.get('markets', []):
            if mkt['key'] != 'spreads':
                continue
            for o in mkt.get('outcomes', []):
                pt = o.get('point', 0)
                if o['name'] == home:
                    h_pts.append(pt); h_odds.append(o['price'])
                elif o['name'] == away:
                    a_pts.append(pt); a_odds.append(o['price'])
    return _avg(h_pts), _avg(h_odds), _avg(a_pts), _avg(a_odds)

# ── Game analysis ──────────────────────────────────────────────────────────────

def analyze(game, cfg):
    home, away   = game['home_team'], game['away_team']
    sport, league = cfg['sport'], cfg['league']
    lines = [f"### 📡 {away.upper()} @ {home.upper()}\n"]

    # ─ 1. Ganador estimado ─
    avg_h, avg_a, best_h, best_a = parse_h2h(game, home, away)
    if avg_h and avg_a:
        p_h, p_a = true_probs(avg_h, avg_a)
        fav    = home if p_h >= p_a else away
        fav_p  = max(p_h, p_a)
        fav_o  = avg_h if p_h >= p_a else avg_a
        k      = kelly_frac(fav_p, fav_o)
        monto  = (st.session_state.saldo * k) / 4

        lines += [
            "#### 🏆 GANADOR ESTIMADO",
            "| Equipo | Prob IA | Cuota Prom |",
            "|--------|---------|------------|",
            f"| {'⭐ ' if p_h>=p_a else ''}{home} | {p_h:.1f}% | {avg_h:.3f} |",
            f"| {'⭐ ' if p_a>p_h else ''}{away} | {p_a:.1f}% | {avg_a:.3f} |",
        ]
        if monto >= 0.50:
            lines.append(f"\n💰 **Apuesta sugerida: ${monto:.2f}** → Ganancia potencial: **${monto*fav_o - monto:.2f}**\n")
        else:
            lines.append(f"\n⚠️ *Sin ventaja suficiente en moneyline (Kelly negativo)*\n")

    # ─ 2. Total puntos/carreras/goles ─
    line_val, o_odds, u_odds = parse_totals(game)
    if line_val and o_odds and u_odds:
        p_o, p_u = true_probs(o_odds, u_odds)
        lbl = cfg['total'].upper()
        rec = f"OVER {line_val} ⬆️" if p_o >= p_u else f"UNDER {line_val} ⬇️"
        lines += [
            f"#### 📊 TOTAL DE {lbl} — Línea: **{line_val}**",
            "| | Prob IA | Cuota |",
            "|-|---------|-------|",
            f"| Over  {line_val} | {p_o:.1f}% | {o_odds:.3f} |",
            f"| Under {line_val} | {p_u:.1f}% | {u_odds:.3f} |",
            f"**→ {rec}** ({max(p_o,p_u):.1f}%)\n",
        ]

    # ─ 3. Hándicap / Spread ─
    h_pt, h_sp, a_pt, a_sp = parse_spreads(game, home, away)
    if h_pt is not None and h_sp and a_sp:
        p_hs, p_as = true_probs(h_sp, a_sp)
        h_sign = f"+{h_pt:.1f}" if h_pt > 0 else f"{h_pt:.1f}"
        a_sign = f"+{a_pt:.1f}" if a_pt is not None and a_pt > 0 else f"{a_pt:.1f}" if a_pt is not None else "—"
        rec_sp = f"{home} {h_sign}" if p_hs >= p_as else f"{away} {a_sign}"
        lines += [
            "#### 🎯 HÁNDICAP",
            "| Línea | Prob IA | Cuota |",
            "|-------|---------|-------|",
            f"| {home} {h_sign} | {p_hs:.1f}% | {h_sp:.3f} |",
            f"| {away} {a_sign} | {p_as:.1f}% | {a_sp:.3f} |",
            f"**→ {rec_sp}** ({max(p_hs,p_as):.1f}%)\n",
        ]

    # ─ 4. Lesiones ─
    espn_teams = fetch_espn_teams(sport, league)
    lines.append("#### 🏥 LESIONES")
    for team in [home, away]:
        tid = match_team(team, espn_teams)
        if tid:
            _, injured = fetch_roster(sport, league, tid)
            if injured:
                parts = " | ".join(f"🤕 {i['name']} ({i['status']}){' — '+i['note'] if i['note'] else ''}" for i in injured[:4])
                lines.append(f"⚠️ **{team}:** {parts}")
            else:
                lines.append(f"✅ **{team}:** Sin lesiones reportadas")
        else:
            lines.append(f"❓ **{team}:** Sin datos ESPN disponibles")
    lines.append("")

    # ─ 5. Jugadores clave (solo NBA) ─
    if cfg.get('players'):
        lines.append("#### ⭐ JUGADORES CLAVE — PROMEDIOS DE TEMPORADA")
        for team in [home, away]:
            tid = match_team(team, espn_teams)
            if not tid:
                continue
            players, _ = fetch_roster(sport, league, tid)
            lines.append(f"\n**{team}**")
            lines.append("| Jugador | Pos | PTS | REB | AST | 3PM |")
            lines.append("|---------|-----|-----|-----|-----|-----|")
            for p in players[:5]:
                s = fetch_nba_stats(p['id'])
                pts = s.get('PTS') or s.get('PPG')
                reb = s.get('REB') or s.get('RPG')
                ast = s.get('AST') or s.get('APG')
                fg3 = s.get('3PM') or s.get('FG3M') or s.get('TPM')
                lines.append(f"| {p['name']} | {p['pos']} | {fmt_stat(pts)} | {fmt_stat(reb)} | {fmt_stat(ast)} | {fmt_stat(fg3)} |")

    return "\n".join(lines)

# ── Query processor ────────────────────────────────────────────────────────────

def process_query(text, cfg):
    games = fetch_odds(cfg['key'])
    if not games:
        return "❌ Sin datos de la API. Intenta en unos minutos."

    pl = text.lower()
    found = None
    for g in games:
        ht, at = g['home_team'].lower(), g['away_team'].lower()
        if ht in pl or at in pl:
            found = g; break
        for word in pl.split():
            if len(word) > 3 and (word in ht or word in at):
                found = g; break
        if found:
            break

    if not found:
        sample = ', '.join({g['home_team'].split()[-1] for g in games[:10]})
        return f"🔍 No encontré ese equipo hoy en {list(SPORTS.keys())[[v['key'] for v in SPORTS.values()].index(cfg['key'])]}.\n\n*Equipos disponibles (aprox): {sample}...*"

    return analyze(found, cfg)

# ── Value bet scanner ──────────────────────────────────────────────────────────

def scan_value_bets():
    rows = []
    for sname, cfg in SPORTS.items():
        games = fetch_odds(cfg['key'])
        for g in games:
            home, away = g['home_team'], g['away_team']
            h_list, a_list = [], []
            for bk in g.get('bookmakers', []):
                for mkt in bk.get('markets', []):
                    if mkt['key'] != 'h2h':
                        continue
                    for o in mkt.get('outcomes', []):
                        if o['name'] == home:   h_list.append(o['price'])
                        elif o['name'] == away: a_list.append(o['price'])

            if len(h_list) < 3 or len(a_list) < 3:
                continue

            med_h, med_a = _median(h_list), _median(a_list)
            best_h, best_a = max(h_list), max(a_list)

            imp_h = 1/med_h; imp_a = 1/med_a
            mg = imp_h + imp_a
            tp_h = imp_h/mg; tp_a = imp_a/mg

            ev_h = best_h * tp_h
            ev_a = best_a * tp_a

            for team, ev, tp, best_o in [(home, ev_h, tp_h, best_h), (away, ev_a, tp_a, best_a)]:
                if ev > 1.04 and 0.38 <= tp <= 0.78:
                    k = kelly_frac(tp*100, best_o)
                    monto = (st.session_state.saldo * k) / 4
                    rows.append({
                        'Deporte':   sname,
                        'Partido':   f'{away} @ {home}',
                        'Apostar a': team,
                        'Cuota':     f'{best_o:.2f}',
                        'Prob IA':   f'{tp*100:.1f}%',
                        'EV':        round(ev, 4),
                        'Ventaja':   f'+{(ev-1)*100:.1f}%',
                        'Sugerido':  f'${monto:.2f}' if monto >= 0.50 else '<$0.50',
                    })

    return sorted(rows, key=lambda x: x['EV'], reverse=True)

# ── UI ─────────────────────────────────────────────────────────────────────────

col1, col2 = st.columns([3, 1])
with col1:
    st.title("🧠 NEON BET AI")
    st.caption("SYSTEM ONLINE // NBA · NFL · MLB · NHL — NO SOCCER")
with col2:
    st.metric("CAPITAL DISPONIBLE", f"${st.session_state.saldo:.2f}")

st.divider()

with st.sidebar:
    st.markdown("### ⚙️ SISTEMA")
    sport_name = st.selectbox("DEPORTE:", list(SPORTS.keys()))
    active_cfg = SPORTS[sport_name]

    st.markdown("---")
    new_saldo = st.number_input("Actualizar Capital ($):", value=float(st.session_state.saldo), min_value=1.0, step=5.0)
    if abs(new_saldo - st.session_state.saldo) > 0.001:
        st.session_state.saldo = new_saldo

    st.markdown("---")
    if st.button("🔍 BUSCAR APUESTAS CON VALOR\n(Escanea todos los deportes)", use_container_width=True):
        st.session_state.show_value = True

    if st.button("🗑 Limpiar Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption("💡 Escribe un equipo en el chat para analizar el partido: ganador, total, hándicap, lesiones y jugadores clave.")

# ── Value bets panel ───────────────────────────────────────────────────────────
if st.session_state.show_value:
    st.markdown("### 🎯 APUESTAS CON VALOR POSITIVO — TODOS LOS DEPORTES")
    with st.spinner("🔄 Escaneando NBA · NFL · MLB · NHL..."):
        vbets = scan_value_bets()

    if vbets:
        df = pd.DataFrame(vbets)
        # Highlight EV column
        st.dataframe(
            df.style.background_gradient(subset=['EV'], cmap='Greens'),
            use_container_width=True,
            hide_index=True
        )
        st.caption(f"✅ {len(vbets)} apuesta(s) con valor encontradas. Criterio: EV > 1.04, Prob 38–78% (realistas).")
    else:
        st.info("🔍 No hay apuestas con valor positivo en este momento.")

    if st.button("✖ Cerrar Panel de Valor"):
        st.session_state.show_value = False
        st.rerun()

    st.divider()

# ── Chat ───────────────────────────────────────────────────────────────────────
chat_box    = st.container()
user_prompt = st.chat_input("⌨️ ESCRIBE UN EQUIPO (Lakers, Chiefs, Yankees, Maple Leafs...)")

with chat_box:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("🔄 PROCESANDO ALGORITMO..."):
                resp = process_query(user_prompt, active_cfg)
            st.markdown(resp)
            st.session_state.messages.append({"role": "assistant", "content": resp})
