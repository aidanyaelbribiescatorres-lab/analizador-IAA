import streamlit as st
import pandas as pd
import requests
import json
import os
import uuid
from datetime import datetime

st.set_page_config(page_title="NEON BET AI", page_icon="🟢", layout="wide")

st.markdown("""
<style>
.stApp { background-color: #050505; color: #00FF00; }
#MainMenu, footer, header { visibility: hidden; }
h1,h2,h3,h4 { color:#00FF41 !important; font-family:'Courier New',monospace; text-shadow:0 0 5px #00FF41; }
.stButton>button { background:#000; color:#00FF41; border:1px solid #00FF41; border-radius:5px; width:100%; transition:all .3s; }
.stButton>button:hover { background:#00FF41; color:#000; box-shadow:0 0 15px #00FF41; }
div[data-testid="stMetricValue"] { color:#00FF41 !important; }
div[data-testid="stMetricLabel"] { color:#888 !important; }
.stTabs [data-baseweb="tab"] { color:#00FF41; font-family:'Courier New',monospace; font-size:0.9rem; }
.stSelectbox label,.stNumberInput label,.stTextInput label,.stTextArea label,.stRadio label { color:#00FF41 !important; font-family:'Courier New',monospace; }
</style>
""", unsafe_allow_html=True)

# ── Paths ────────────────────────────────────────────────────────────────────
APP_DIR   = os.path.dirname(os.path.abspath(__file__))
HIST_FILE = os.path.join(APP_DIR, 'historial.json')
FOTOS_DIR = os.path.join(APP_DIR, 'fotos_apuestas')
os.makedirs(FOTOS_DIR, exist_ok=True)

def load_hist():
    try:
        with open(HIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_hist(data):
    with open(HIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── Session state ────────────────────────────────────────────────────────────
for k, v in [('saldo', 24.27), ('messages', []), ('show_value', False)]:
    if k not in st.session_state:
        st.session_state[k] = v

historial = load_hist()

# ── Constants ────────────────────────────────────────────────────────────────
ODDS_KEY  = '8d90dd7eb80726fb3a98683ee7d2e734'
ODDS_BASE = 'https://api.the-odds-api.com/v4'
ESPN_SITE = 'https://site.api.espn.com/apis/site/v2/sports'
ESPN_CMVN = 'https://site.web.api.espn.com/apis/common/v3/sports'

SPORTS = {
    '🏀 NBA':              {'key': 'basketball_nba',           'sport': 'basketball', 'league': 'nba',          'total': 'puntos',   'players': True,  'soccer': False},
    '🏈 NFL':              {'key': 'americanfootball_nfl',      'sport': 'football',   'league': 'nfl',          'total': 'puntos',   'players': False, 'soccer': False},
    '⚾ MLB':              {'key': 'baseball_mlb',              'sport': 'baseball',   'league': 'mlb',          'total': 'carreras', 'players': False, 'soccer': False},
    '🏒 NHL':              {'key': 'icehockey_nhl',             'sport': 'hockey',     'league': 'nhl',          'total': 'goles',    'players': False, 'soccer': False},
    '⚽ Premier League':   {'key': 'soccer_epl',                'sport': 'soccer',     'league': 'eng.1',        'total': 'goles',    'players': False, 'soccer': True},
    '⚽ La Liga':          {'key': 'soccer_spain_la_liga',      'sport': 'soccer',     'league': 'esp.1',        'total': 'goles',    'players': False, 'soccer': True},
    '⚽ Champions League': {'key': 'soccer_uefa_champs_league', 'sport': 'soccer',     'league': 'uefa.champions','total': 'goles',   'players': False, 'soccer': True},
    '⚽ Liga MX':          {'key': 'soccer_mexico_ligamx',      'sport': 'soccer',     'league': 'mex.1',        'total': 'goles',    'players': False, 'soccer': True},
    '⚽ MLS':              {'key': 'soccer_usa_mls',            'sport': 'soccer',     'league': 'usa.1',        'total': 'goles',    'players': False, 'soccer': True},
    '⚽ Serie A':          {'key': 'soccer_italy_serie_a',      'sport': 'soccer',     'league': 'ita.1',        'total': 'goles',    'players': False, 'soccer': True},
    '⚽ Bundesliga':       {'key': 'soccer_germany_bundesliga', 'sport': 'soccer',     'league': 'ger.1',        'total': 'goles',    'players': False, 'soccer': True},
}

# ── Data fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def fetch_odds(sport_key):
    try:
        r = requests.get(f'{ODDS_BASE}/sports/{sport_key}/odds/', timeout=12, params={
            'apiKey': ODDS_KEY, 'regions': 'us,eu',
            'markets': 'h2h,totals,spreads', 'oddsFormat': 'decimal',
        })
        return r.json() if r.ok else []
    except Exception:
        return []

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_espn_teams(sport, league):
    try:
        r = requests.get(f'{ESPN_SITE}/{sport}/{league}/teams', params={'limit': 100}, timeout=10)
        if not r.ok:
            return {}
        d = r.json()
        teams = d.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])
        return {t['team']['displayName']: t['team']['id'] for t in teams}
    except Exception:
        return {}

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_roster(sport, league, team_id):
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
                pr    = a.get('position', {})
                pos   = pr.get('abbreviation', '') if isinstance(pr, dict) else str(pr)
                if pid and pname:
                    players.append({'id': pid, 'name': pname, 'pos': pos})
                for inj in a.get('injuries', []):
                    status = inj.get('status', '') or ''
                    injured.append({'name': pname, 'status': status or 'OUT', 'note': inj.get('shortComment', '')})
        return players[:12], injured[:6]
    except Exception:
        return [], []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_nba_stats(athlete_id):
    try:
        r = requests.get(f'{ESPN_CMVN}/basketball/nba/athletes/{athlete_id}/stats', timeout=10)
        if not r.ok:
            return {}
        stats = {}
        for cat in r.json().get('splits', {}).get('categories', []):
            for s in cat.get('stats', []):
                stats[s.get('abbreviation', '')] = s.get('value')
        return stats
    except Exception:
        return {}

# ── Math helpers ──────────────────────────────────────────────────────────────

def _avg(lst):
    return sum(lst) / len(lst) if lst else None

def _median(lst):
    if not lst:
        return None
    s = sorted(lst); n = len(s)
    return (s[n//2-1] + s[n//2]) / 2 if n % 2 == 0 else s[n//2]

def remove_margin(*odds):
    """True probabilities after removing bookmaker margin (any number of outcomes)."""
    imps = [1/o for o in odds if o and o > 1]
    mg   = sum(imps)
    return [(i / mg) * 100 for i in imps]

def kelly_frac(prob_pct, decimal_odds):
    b = decimal_odds - 1; p = prob_pct / 100
    return max((b * p - (1 - p)) / b, 0)

def fmt_s(v):
    try:    return f"{float(v):.1f}"
    except: return "—"

def match_team(name, teams_dict):
    if not teams_dict: return None
    if name in teams_dict: return teams_dict[name]
    nl = name.lower()
    for k, v in teams_dict.items():
        if nl in k.lower() or k.lower() in nl: return v
    for word in reversed(name.split()):
        if len(word) > 3:
            for k, v in teams_dict.items():
                if word.lower() in k.lower(): return v
    return None

# ── Market parsers ────────────────────────────────────────────────────────────

def parse_h2h(game, home, away):
    h, a, d = [], [], []
    for bk in game.get('bookmakers', []):
        for mkt in bk.get('markets', []):
            if mkt['key'] != 'h2h': continue
            for o in mkt.get('outcomes', []):
                nm = o['name']
                if nm == home:      h.append(o['price'])
                elif nm == away:    a.append(o['price'])
                elif nm == 'Draw':  d.append(o['price'])
    return _avg(h), _avg(a), _avg(d)

def parse_totals(game):
    overs, unders, lines = [], [], []
    for bk in game.get('bookmakers', []):
        for mkt in bk.get('markets', []):
            if mkt['key'] != 'totals': continue
            for o in mkt.get('outcomes', []):
                lines.append(o.get('point', 0))
                if   o['name'] == 'Over':  overs.append(o['price'])
                elif o['name'] == 'Under': unders.append(o['price'])
    return (lines[0] if lines else None), _avg(overs), _avg(unders)

def parse_spreads(game, home, away):
    h_pts, a_pts, h_odds, a_odds = [], [], [], []
    for bk in game.get('bookmakers', []):
        for mkt in bk.get('markets', []):
            if mkt['key'] != 'spreads': continue
            for o in mkt.get('outcomes', []):
                pt = o.get('point', 0)
                if   o['name'] == home: h_pts.append(pt); h_odds.append(o['price'])
                elif o['name'] == away: a_pts.append(pt); a_odds.append(o['price'])
    return _avg(h_pts), _avg(h_odds), _avg(a_pts), _avg(a_odds)

# ── Probability explainer ─────────────────────────────────────────────────────

def prob_explainer_text(home, away, avg_h, avg_a, avg_d=None):
    lines = []
    if avg_d:
        imp_h, imp_d, imp_a = 1/avg_h, 1/avg_d, 1/avg_a
        mg = imp_h + imp_d + imp_a
        p_h, p_d, p_a = imp_h/mg*100, imp_d/mg*100, imp_a/mg*100
        lines += [
            "**Paso 1 — Cuotas promedio de todas las casas:**",
            f"> `{home}` = **{avg_h:.3f}** | `Empate` = **{avg_d:.3f}** | `{away}` = **{avg_a:.3f}**",
            "",
            "**Paso 2 — Probabilidad implícita (1 ÷ cuota):**",
            f"> {home}={imp_h*100:.2f}% | Empate={imp_d*100:.2f}% | {away}={imp_a*100:.2f}% → Suma={mg*100:.2f}%",
            "",
            f"**Paso 3 — Margen del bookmaker:** `{(mg-1)*100:.2f}%` (el 'vig' que cobran las casas)",
            "",
            "**Paso 4 — Probabilidad REAL (normalizada):**",
            f"> {home}=**{p_h:.1f}%** | Empate=**{p_d:.1f}%** | {away}=**{p_a:.1f}%**",
            "",
            "*Fórmula: Prob_real = Prob_implícita ÷ Suma_total_implícitas*",
        ]
    else:
        imp_h, imp_a = 1/avg_h, 1/avg_a
        mg = imp_h + imp_a
        p_h, p_a = imp_h/mg*100, imp_a/mg*100
        lines += [
            "**Paso 1 — Cuotas promedio de todas las casas:**",
            f"> `{home}` = **{avg_h:.3f}** | `{away}` = **{avg_a:.3f}**",
            "",
            "**Paso 2 — Probabilidad implícita (1 ÷ cuota):**",
            f"> {home}={imp_h*100:.2f}% | {away}={imp_a*100:.2f}% → Suma={mg*100:.2f}%",
            "",
            f"**Paso 3 — Margen del bookmaker:** `{(mg-1)*100:.2f}%`",
            "",
            "**Paso 4 — Probabilidad REAL (normalizada):**",
            f"> {home}=**{p_h:.1f}%** | {away}=**{p_a:.1f}%**",
            "",
            "**Paso 5 — Kelly Criterion** para el tamaño de apuesta:",
            f"> f* = (b·p − q) / b   donde b=cuota−1, p=prob_real, q=1−p",
            "> Usamos **Kelly/4** para gestión de riesgo conservadora.",
        ]
    return "\n".join(lines)

# ── Calibration hint ──────────────────────────────────────────────────────────

def calibration_hint(prob_pct):
    """Check historical accuracy in the same probability bucket."""
    hist = load_hist()
    closed = [b for b in hist if b.get('resultado') in ('ganado', 'perdido')]
    if len(closed) < 5:
        return ""
    bucket_lo = int(prob_pct // 10) * 10
    bucket_hi = bucket_lo + 10
    bucket_bets = [b for b in closed if bucket_lo <= b.get('prob_ia', 0) < bucket_hi]
    if len(bucket_bets) < 3:
        return ""
    acc = sum(1 for b in bucket_bets if b['resultado'] == 'ganado') / len(bucket_bets) * 100
    diff = acc - prob_pct
    if diff > 8:
        return f"\n\n🟢 *Historial IA: en apuestas del {bucket_lo}-{bucket_hi}% hemos ganado **{acc:.0f}%** ({len(bucket_bets)} apuestas) — mejor de lo esperado*"
    elif diff < -8:
        return f"\n\n🟡 *Historial IA: en apuestas del {bucket_lo}-{bucket_hi}% hemos ganado **{acc:.0f}%** ({len(bucket_bets)} apuestas) — precaución, peor de lo esperado*"
    return f"\n\n🔵 *Historial IA: {acc:.0f}% de precisión en este rango de probabilidad ({len(bucket_bets)} apuestas pasadas)*"

# ── Game analysis ─────────────────────────────────────────────────────────────

def analyze(game, cfg):
    home, away    = game['home_team'], game['away_team']
    sport, league = cfg['sport'], cfg['league']
    is_soccer     = cfg.get('soccer', False)
    lines         = [f"### 📡 {away.upper()} @ {home.upper()}\n"]
    expl          = {}   # data for explainer

    # ─ 1. Ganador ─────────────────────────────────────────────────────────
    avg_h, avg_a, avg_d = parse_h2h(game, home, away)
    if avg_h and avg_a:
        expl = {'avg_h': avg_h, 'avg_a': avg_a, 'avg_d': avg_d, 'home': home, 'away': away}

        if is_soccer and avg_d:
            p_h, p_d, p_a = remove_margin(avg_h, avg_d, avg_a)
            best_p = max(p_h, p_d, p_a)
            lines += [
                "#### 🏆 GANADOR ESTIMADO (1X2)",
                "| Resultado | Prob IA | Cuota |",
                "|-----------|---------|-------|",
                f"| {'⭐ ' if p_h==best_p else ''}{home} | {p_h:.1f}% | {avg_h:.3f} |",
                f"| {'⭐ ' if p_d==best_p else ''}Empate | {p_d:.1f}% | {avg_d:.3f} |",
                f"| {'⭐ ' if p_a==best_p else ''}{away} | {p_a:.1f}% | {avg_a:.3f} |",
            ]
            # Solo recomendar local o visitante, nunca empate
            if p_h >= p_a:
                k = kelly_frac(p_h, avg_h); monto = (st.session_state.saldo * k) / 4
                fav_txt = home; fav_p = p_h; fav_o = avg_h
            else:
                k = kelly_frac(p_a, avg_a); monto = (st.session_state.saldo * k) / 4
                fav_txt = away; fav_p = p_a; fav_o = avg_a

            if monto >= 0.50:
                lines.append(f"\n💰 **Sugerido: ${monto:.2f} → {fav_txt}** ({fav_p:.1f}%) | Ganancia: ${monto*fav_o-monto:.2f}")
            else:
                lines.append(f"\n⚠️ *Sin ventaja Kelly suficiente — apostar con cautela*")
            lines.append(calibration_hint(max(p_h, p_a)) + "\n")

        else:
            p_h, p_a = remove_margin(avg_h, avg_a)
            fav_txt = home if p_h >= p_a else away
            fav_p   = max(p_h, p_a)
            fav_o   = avg_h if p_h >= p_a else avg_a
            k = kelly_frac(fav_p, fav_o); monto = (st.session_state.saldo * k) / 4
            lines += [
                "#### 🏆 GANADOR ESTIMADO",
                "| Equipo | Prob IA | Cuota |",
                "|--------|---------|-------|",
                f"| {'⭐ ' if p_h>=p_a else ''}{home} | {p_h:.1f}% | {avg_h:.3f} |",
                f"| {'⭐ ' if p_a>p_h else ''}{away} | {p_a:.1f}% | {avg_a:.3f} |",
            ]
            if monto >= 0.50:
                lines.append(f"\n💰 **Sugerido: ${monto:.2f} → {fav_txt}** | Ganancia: ${monto*fav_o-monto:.2f}")
            else:
                lines.append(f"\n⚠️ *Sin ventaja suficiente en moneyline*")
            lines.append(calibration_hint(fav_p) + "\n")

    # ─ 2. Total puntos/goles/carreras ─────────────────────────────────────
    line_v, o_odds, u_odds = parse_totals(game)
    if line_v and o_odds and u_odds:
        p_o, p_u = remove_margin(o_odds, u_odds)
        lbl = cfg['total'].upper()
        rec = f"OVER {line_v} ⬆️" if p_o >= p_u else f"UNDER {line_v} ⬇️"
        lines += [
            f"#### 📊 TOTAL DE {lbl} — Línea: **{line_v}**",
            "| | Prob IA | Cuota |", "|-|---------|-------|",
            f"| Over  {line_v} | {p_o:.1f}% | {o_odds:.3f} |",
            f"| Under {line_v} | {p_u:.1f}% | {u_odds:.3f} |",
            f"**→ {rec}** ({max(p_o,p_u):.1f}%)\n",
        ]

    # ─ 3. Hándicap / Spread ───────────────────────────────────────────────
    h_pt, h_sp, a_pt, a_sp = parse_spreads(game, home, away)
    if h_pt is not None and h_sp and a_sp:
        p_hs, p_as = remove_margin(h_sp, a_sp)
        h_sign = f"+{h_pt:.1f}" if h_pt > 0 else f"{h_pt:.1f}"
        a_sign = (f"+{a_pt:.1f}" if a_pt > 0 else f"{a_pt:.1f}") if a_pt is not None else "—"
        rec_sp = f"{home} {h_sign}" if p_hs >= p_as else f"{away} {a_sign}"
        lines += [
            "#### 🎯 HÁNDICAP",
            "| Línea | Prob IA | Cuota |", "|-------|---------|-------|",
            f"| {home} {h_sign} | {p_hs:.1f}% | {h_sp:.3f} |",
            f"| {away} {a_sign} | {p_as:.1f}% | {a_sp:.3f} |",
            f"**→ {rec_sp}** ({max(p_hs,p_as):.1f}%)\n",
        ]

    # ─ 4. Lesiones (no soccer) ────────────────────────────────────────────
    if not is_soccer:
        espn_teams = fetch_espn_teams(sport, league)
        if espn_teams:
            lines.append("#### 🏥 LESIONES")
            for team in [home, away]:
                tid = match_team(team, espn_teams)
                if tid:
                    _, injured = fetch_roster(sport, league, tid)
                    if injured:
                        parts = " | ".join(
                            f"🤕 {i['name']} ({i['status']}){' — '+i['note'] if i['note'] else ''}"
                            for i in injured[:4]
                        )
                        lines.append(f"⚠️ **{team}:** {parts}")
                    else:
                        lines.append(f"✅ **{team}:** Sin lesiones reportadas")
            lines.append("")

    # ─ 5. Jugadores clave (solo NBA) ──────────────────────────────────────
    if cfg.get('players'):
        espn_teams = fetch_espn_teams(sport, league)
        if espn_teams:
            lines.append("#### ⭐ JUGADORES CLAVE — PROMEDIOS DE TEMPORADA")
            for team in [home, away]:
                tid = match_team(team, espn_teams)
                if not tid: continue
                players, _ = fetch_roster(sport, league, tid)
                lines += [f"\n**{team}**",
                          "| Jugador | Pos | PTS | REB | AST | 3PM |",
                          "|---------|-----|-----|-----|-----|-----|"]
                for p in players[:5]:
                    s   = fetch_nba_stats(p['id'])
                    pts = s.get('PTS') or s.get('PPG')
                    reb = s.get('REB') or s.get('RPG')
                    ast = s.get('AST') or s.get('APG')
                    fg3 = s.get('3PM') or s.get('FG3M') or s.get('TPM')
                    lines.append(f"| {p['name']} | {p['pos']} | {fmt_s(pts)} | {fmt_s(reb)} | {fmt_s(ast)} | {fmt_s(fg3)} |")

    return "\n".join(lines), expl

# ── Query processor ───────────────────────────────────────────────────────────

def process_query(text, cfg):
    games = fetch_odds(cfg['key'])
    if not games:
        return "❌ Sin datos de la API. Intenta en unos minutos.", {}
    pl = text.lower()
    found = None
    for g in games:
        ht, at = g['home_team'].lower(), g['away_team'].lower()
        if ht in pl or at in pl: found = g; break
        for word in pl.split():
            if len(word) > 3 and (word in ht or word in at): found = g; break
        if found: break
    if not found:
        sample = ', '.join({g['home_team'].split()[-1] for g in games[:10]})
        return f"🔍 No encontré ese equipo. Prueba con: *{sample}...*", {}
    return analyze(found, cfg)

# ── Value bet scanner ─────────────────────────────────────────────────────────

def scan_value_bets():
    rows = []
    for sname, cfg in SPORTS.items():
        games = fetch_odds(cfg['key'])
        for g in games:
            home, away = g['home_team'], g['away_team']
            h_list, a_list = [], []
            for bk in g.get('bookmakers', []):
                for mkt in bk.get('markets', []):
                    if mkt['key'] != 'h2h': continue
                    for o in mkt.get('outcomes', []):
                        if   o['name'] == home: h_list.append(o['price'])
                        elif o['name'] == away: a_list.append(o['price'])
            if len(h_list) < 3 or len(a_list) < 3: continue
            med_h = _median(h_list); med_a = _median(a_list)
            best_h = max(h_list);    best_a = max(a_list)
            p_h, p_a = remove_margin(med_h, med_a)
            for team, tp, best_o in [(home, p_h/100, best_h), (away, p_a/100, best_a)]:
                ev = best_o * tp
                if ev > 1.04 and 0.38 <= tp <= 0.78:
                    k = kelly_frac(tp*100, best_o); monto = (st.session_state.saldo * k) / 4
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

# ── Accounting stats ──────────────────────────────────────────────────────────

def get_stats(hist):
    closed = [b for b in hist if b.get('resultado') in ('ganado', 'perdido')]
    if not closed:
        return None
    total    = len(closed)
    won      = sum(1 for b in closed if b['resultado'] == 'ganado')
    wagered  = sum(b.get('monto', 0) for b in closed)
    returned = sum(b.get('monto', 0) * b.get('cuota', 1) for b in closed if b['resultado'] == 'ganado')
    profit   = returned - wagered
    roi      = profit / wagered * 100 if wagered > 0 else 0
    # Calibration buckets
    cal = {}
    for b in closed:
        p  = b.get('prob_ia', 0)
        bk = f"{int(p//10)*10}-{int(p//10)*10+10}%"
        if bk not in cal: cal[bk] = {'won': 0, 'total': 0}
        cal[bk]['total'] += 1
        if b['resultado'] == 'ganado': cal[bk]['won'] += 1
    return {'total': total, 'won': won, 'lost': total-won,
            'win_rate': won/total*100, 'wagered': wagered,
            'returned': returned, 'profit': profit, 'roi': roi, 'cal': cal}

# ════════════════════════════════════════════════════════════════════════════
# UI HEADER
# ════════════════════════════════════════════════════════════════════════════

col1, col2 = st.columns([3, 1])
with col1:
    st.title("🧠 NEON BET AI")
    st.caption("SYSTEM ONLINE // NBA · NFL · MLB · NHL · Fútbol")
with col2:
    net_pl = sum(b.get('ganancia', 0) for b in historial if b.get('resultado') in ('ganado', 'perdido'))
    capital_actual = st.session_state.saldo + net_pl
    st.metric("CAPITAL DISPONIBLE", f"${capital_actual:.2f}",
              delta=f"${net_pl:+.2f}" if net_pl != 0 else None)

st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ SISTEMA")
    sport_name = st.selectbox("DEPORTE:", list(SPORTS.keys()))
    active_cfg = SPORTS[sport_name]
    st.markdown("---")
    new_saldo = st.number_input("Capital inicial ($):", value=float(st.session_state.saldo),
                                 min_value=1.0, step=5.0)
    if abs(new_saldo - st.session_state.saldo) > 0.001:
        st.session_state.saldo = new_saldo
    st.markdown("---")
    if st.button("🔍 APUESTAS CON VALOR\n(Todos los deportes)", use_container_width=True):
        st.session_state.show_value = True
    if st.button("🗑 Limpiar Chat", use_container_width=True):
        st.session_state.messages = []; st.rerun()
    st.markdown("---")
    st.caption("💡 Escribe un equipo en el chat para analizar el partido completo.")

# ── Value bets panel ──────────────────────────────────────────────────────────
if st.session_state.show_value:
    st.markdown("### 🎯 APUESTAS CON VALOR — ESCANEO COMPLETO")
    with st.spinner("🔄 Escaneando todos los deportes..."):
        vbets = scan_value_bets()
    if vbets:
        df_v = pd.DataFrame(vbets)
        st.dataframe(df_v.style.background_gradient(subset=['EV'], cmap='Greens'),
                     use_container_width=True, hide_index=True)
        st.caption(f"✅ {len(vbets)} apuesta(s) con valor | EV > 1.04 | Prob 38–78% (realistas)")
    else:
        st.info("Sin apuestas con valor positivo en este momento.")
    if st.button("✖ Cerrar Panel"):
        st.session_state.show_value = False; st.rerun()
    st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_chat, tab_log, tab_conta = st.tabs(["📡 Análisis", "📝 Registrar Resultado", "📊 Mi Contabilidad"])

# ════ TAB 1: ANÁLISIS / CHAT ══════════════════════════════════════════════════
with tab_chat:
    chat_box    = st.container()
    user_prompt = st.chat_input("⌨️ ESCRIBE UN EQUIPO (Lakers, Chiefs, Barcelona, Yankees...)")

    with chat_box:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("expl"):
                    ex = msg["expl"]
                    with st.expander("🧮 ¿Cómo calculó la IA las probabilidades?"):
                        st.markdown(prob_explainer_text(
                            ex.get('home', 'Local'), ex.get('away', 'Visitante'),
                            ex.get('avg_h', 2), ex.get('avg_a', 2), ex.get('avg_d')
                        ))

        if user_prompt:
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("🔄 PROCESANDO ALGORITMO..."):
                    resp, expl = process_query(user_prompt, active_cfg)
                st.markdown(resp)
                if expl:
                    with st.expander("🧮 ¿Cómo calculó la IA las probabilidades?"):
                        st.markdown(prob_explainer_text(
                            expl.get('home', 'Local'), expl.get('away', 'Visitante'),
                            expl.get('avg_h', 2), expl.get('avg_a', 2), expl.get('avg_d')
                        ))
                st.session_state.messages.append({
                    "role": "assistant", "content": resp, "expl": expl
                })

# ════ TAB 2: REGISTRAR RESULTADO ══════════════════════════════════════════════
with tab_log:
    st.markdown("### 📝 Registrar resultado de apuesta")
    st.caption("Sube la foto del comprobante y llena el resultado. La IA usará estos datos para calibrarse y hacer mejor contabilidad.")

    with st.form("form_bet", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            f_partido  = st.text_input("Partido *", placeholder="Lakers vs Warriors")
            f_deporte  = st.selectbox("Deporte *", list(SPORTS.keys()))
            f_apuesta  = st.text_input("Apostaste a *", placeholder="Lakers")
            f_cuota    = st.number_input("Cuota *", min_value=1.01, value=1.85, step=0.01, format="%.2f")
        with c2:
            f_monto    = st.number_input("Monto apostado ($) *", min_value=0.01, value=5.00, step=0.50, format="%.2f")
            f_prob     = st.number_input("Prob IA que te dio (%) *", min_value=1.0, max_value=99.0, value=55.0, step=0.5)
            f_result   = st.radio("Resultado *", ["ganado", "perdido", "pendiente"], horizontal=True)
            f_foto     = st.file_uploader("📸 Foto del comprobante (opcional)", type=["jpg","jpeg","png","webp"])
        f_notas = st.text_area("Notas (opcional)", height=60)
        submitted = st.form_submit_button("💾 GUARDAR", use_container_width=True)

    if submitted:
        foto_path = None
        if f_foto:
            ext = f_foto.name.rsplit('.', 1)[-1]
            fname = f"{uuid.uuid4().hex}.{ext}"
            foto_path = os.path.join(FOTOS_DIR, fname)
            with open(foto_path, 'wb') as fp:
                fp.write(f_foto.read())

        ganancia = 0.0
        if f_result == 'ganado':
            ganancia = round(f_monto * f_cuota - f_monto, 2)
        elif f_result == 'perdido':
            ganancia = -round(f_monto, 2)

        historial.append({
            'id':        str(uuid.uuid4()),
            'fecha':     datetime.now().strftime('%Y-%m-%d %H:%M'),
            'deporte':   f_deporte,
            'partido':   f_partido,
            'apuesta':   f_apuesta,
            'cuota':     f_cuota,
            'monto':     f_monto,
            'prob_ia':   f_prob,
            'resultado': f_result,
            'ganancia':  ganancia,
            'foto':      foto_path,
            'notas':     f_notas,
        })
        save_hist(historial)
        emoji = "🟢" if f_result=="ganado" else "🔴" if f_result=="perdido" else "🟡"
        st.success(f"{emoji} Guardado: **{f_partido}** → {f_apuesta} | {f_result.upper()} | P&L: ${ganancia:+.2f}")
        st.rerun()

    # Últimas apuestas con foto
    if historial:
        st.markdown("---")
        st.markdown("#### Últimas apuestas registradas")
        for b in reversed(historial[-6:]):
            r = b.get('resultado', 'pendiente')
            icon = "🟢" if r=="ganado" else "🔴" if r=="perdido" else "🟡"
            with st.expander(f"{icon} {b['fecha'][:10]} — {b.get('partido','')} | **{b.get('apuesta','')}** | ${b.get('ganancia',0):+.2f}"):
                fc1, fc2 = st.columns([1, 2])
                with fc1:
                    fp = b.get('foto')
                    if fp and os.path.exists(fp):
                        st.image(fp, use_container_width=True, caption="Comprobante")
                    else:
                        st.info("Sin foto")
                with fc2:
                    st.markdown(f"""
**Deporte:** {b.get('deporte','')}
**Partido:** {b.get('partido','')}
**Aposté a:** {b.get('apuesta','')}
**Cuota:** {b.get('cuota',0):.2f}
**Monto:** ${b.get('monto',0):.2f}
**Prob IA:** {b.get('prob_ia',0):.1f}%
**Resultado:** {r.upper()} {icon}
**P&L:** ${b.get('ganancia',0):+.2f}
""")
                    if b.get('notas'):
                        st.caption(f"📝 {b['notas']}")

# ════ TAB 3: CONTABILIDAD ═════════════════════════════════════════════════════
with tab_conta:
    st.markdown("### 📊 CONTABILIDAD & RENTABILIDAD")
    stats = get_stats(historial)

    if not stats:
        st.info("📭 Sin apuestas cerradas aún. Registra resultados en **Registrar Resultado**.")
    else:
        # ── KPIs ──────────────────────────────────────────────────────────
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Apuestas", stats['total'])
        k2.metric("✅ Ganadas", stats['won'])
        k3.metric("❌ Perdidas", stats['lost'])
        k4.metric("Win Rate", f"{stats['win_rate']:.1f}%")
        k5.metric("ROI", f"{stats['roi']:+.1f}%", delta=f"${stats['profit']:+.2f}")

        st.markdown(f"**Total apostado:** ${stats['wagered']:.2f} &nbsp;|&nbsp; "
                    f"**Retornado:** ${stats['returned']:.2f} &nbsp;|&nbsp; "
                    f"**Profit neto:** ${stats['profit']:+.2f}")
        st.divider()

        # ── Evolución capital ─────────────────────────────────────────────
        closed = [b for b in historial if b.get('resultado') in ('ganado','perdido')]
        if len(closed) >= 2:
            st.markdown("#### 📈 Evolución del Capital")
            running = st.session_state.saldo
            evo = []
            for b in closed:
                running += b.get('ganancia', 0)
                evo.append({'Fecha': b['fecha'][:10], 'Capital ($)': round(running, 2)})
            df_evo = pd.DataFrame(evo)
            st.line_chart(df_evo.set_index('Fecha'))

        # ── Por deporte ───────────────────────────────────────────────────
        st.markdown("#### 🏆 Rendimiento por Deporte")
        sport_map = {}
        for b in closed:
            d = b.get('deporte', 'Otro')
            if d not in sport_map: sport_map[d] = {'won':0,'total':0,'profit':0.0}
            sport_map[d]['total']  += 1
            sport_map[d]['profit'] += b.get('ganancia', 0)
            if b['resultado'] == 'ganado': sport_map[d]['won'] += 1
        rows_sp = [{
            'Deporte':   d,
            'Apuestas':  v['total'],
            'Ganadas':   v['won'],
            'Win %':     f"{v['won']/v['total']*100:.0f}%",
            'Profit':    f"${v['profit']:+.2f}",
        } for d, v in sport_map.items()]
        if rows_sp:
            st.dataframe(pd.DataFrame(rows_sp), use_container_width=True, hide_index=True)

        # ── Calibración IA ────────────────────────────────────────────────
        st.markdown("#### 🧠 Calibración de la IA")
        st.caption("¿Tan precisa es la probabilidad que da la IA vs el resultado real? Si la IA dice 60% y ganamos 60% de esas, la calibración es perfecta.")
        cal = stats.get('cal', {})
        if cal:
            cal_rows = []
            for bucket, data in sorted(cal.items()):
                acc = data['won'] / data['total'] * 100 if data['total'] else 0
                diff = acc - float(bucket.split('-')[0])
                icon = "🟢" if diff > 5 else "🔴" if diff < -5 else "🔵"
                cal_rows.append({
                    'Rango Prob IA': bucket,
                    'Apuestas':      data['total'],
                    'Ganadas':       data['won'],
                    'Precisión Real':f"{acc:.0f}%",
                    'Estado':        f"{icon} {'Mejor' if diff>5 else 'Peor' if diff<-5 else 'Calibrado'} de lo esperado",
                })
            st.dataframe(pd.DataFrame(cal_rows), use_container_width=True, hide_index=True)

        # ── Historial completo ────────────────────────────────────────────
        st.markdown("#### 📋 Historial Completo")
        all_rows = []
        for b in reversed(historial):
            r = b.get('resultado', 'pendiente')
            all_rows.append({
                'Fecha':    b['fecha'][:10],
                'Deporte':  b.get('deporte',''),
                'Partido':  b.get('partido',''),
                'Apuesta':  b.get('apuesta',''),
                'Cuota':    b.get('cuota',0),
                'Monto':    f"${b.get('monto',0):.2f}",
                'Prob IA':  f"{b.get('prob_ia',0):.1f}%",
                'Result.':  r.upper(),
                'P&L':      f"${b.get('ganancia',0):+.2f}",
            })
        if all_rows:
            st.dataframe(pd.DataFrame(all_rows), use_container_width=True, hide_index=True)

        st.markdown("---")
        if st.button("🗑 Borrar todo el historial", type="secondary"):
            save_hist([])
            st.rerun()
