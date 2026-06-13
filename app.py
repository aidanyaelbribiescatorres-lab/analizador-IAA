import streamlit as st
import pandas as pd
import requests
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="ScoutAI", page_icon="⚽", layout="wide",
                   initial_sidebar_state="collapsed")

# ══════════════════════════════════════════════════════════════════════════════
# THEME — Forekick style (dark purple / navy)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Base ── */
.stApp {
    background: linear-gradient(180deg, #1a0538 0%, #0d0d2b 45%, #080818 100%);
    color: #e2e8f0;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 0.5rem !important; max-width: 860px !important; }

/* ── Radio pills ── */
div[role="radiogroup"] { display: flex; flex-wrap: wrap; gap: 6px; }
div[role="radiogroup"] label {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 20px !important;
    padding: 5px 14px !important;
    color: #94a3b8 !important;
    cursor: pointer;
    font-size: 0.82rem !important;
}
div[role="radiogroup"] label:has(input:checked) {
    background: rgba(124,58,237,0.4) !important;
    border-color: #7c3aed !important;
    color: #c4b5fd !important;
    font-weight: 600 !important;
}
div[role="radiogroup"] label > div:first-child { display: none !important; }

/* ── Buttons ── */
.stButton > button {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    color: #e2e8f0 !important;
    border-radius: 10px !important;
    transition: all .18s !important;
    font-size: 0.88rem !important;
}
.stButton > button:hover {
    background: rgba(124,58,237,0.22) !important;
    border-color: rgba(124,58,237,0.55) !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea textarea {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
}
.stSelectbox > div > div { background: rgba(255,255,255,0.06) !important; border-radius:10px !important; }

/* ── Metrics ── */
div[data-testid="stMetricValue"]  { color: #a78bfa !important; }
div[data-testid="stMetricLabel"]  { color: #64748b !important; }
div[data-testid="stMetricDelta"]  { font-size:0.8rem !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: rgba(255,255,255,0.03); border-radius: 12px; padding: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 10px; color: #94a3b8; font-size: 0.82rem; padding: 6px 14px; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { background: rgba(124,58,237,0.4); color: #c4b5fd; font-weight: 600; }
.stTabs [data-baseweb="tab-highlight"] { display: none; }

/* ── Dataframe ── */
.stDataFrame { border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; }
div[data-testid="stDataFrameResizable"] { background: rgba(255,255,255,0.02); }

/* ── Forms ── */
.stForm { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius:14px; padding:16px; }
label { color: #94a3b8 !important; font-size: 0.82rem !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════
APP_DIR   = os.path.dirname(os.path.abspath(__file__))
HIST_FILE = os.path.join(APP_DIR, 'historial.json')
FOTOS_DIR = os.path.join(APP_DIR, 'fotos_apuestas')
os.makedirs(FOTOS_DIR, exist_ok=True)

def load_hist():
    try:
        with open(HIST_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_hist(data):
    with open(HIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for k, v in [('saldo', 24.27), ('view', 'home'), ('selected_game', None),
             ('selected_cfg', None), ('selected_league_name', '')]:
    if k not in st.session_state: st.session_state[k] = v

historial = load_hist()

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
ODDS_KEY  = '8d90dd7eb80726fb3a98683ee7d2e734'
ODDS_BASE = 'https://api.the-odds-api.com/v4'
ESPN_SITE = 'https://site.api.espn.com/apis/site/v2/sports'
ESPN_CMVN = 'https://site.web.api.espn.com/apis/common/v3/sports'

SOCCER_LEAGUES = {
    'soccer_epl':                '⚽ Premier League',
    'soccer_spain_la_liga':      '⚽ La Liga',
    'soccer_uefa_champs_league': '⚽ Champions League',
    'soccer_mexico_ligamx':      '⚽ Liga MX',
    'soccer_usa_mls':            '⚽ MLS',
    'soccer_italy_serie_a':      '⚽ Serie A',
    'soccer_germany_bundesliga': '⚽ Bundesliga',
}

ALL_SPORTS = {
    **SOCCER_LEAGUES,
    'basketball_nba':           '🏀 NBA',
    'americanfootball_nfl':     '🏈 NFL',
    'baseball_mlb':             '⚾ MLB',
    'icehockey_nhl':            '🏒 NHL',
}

SPORT_META = {
    'basketball_nba':           {'sport':'basketball','league':'nba','total':'Puntos','soccer':False,'players':True},
    'americanfootball_nfl':     {'sport':'football',  'league':'nfl','total':'Puntos','soccer':False,'players':False},
    'baseball_mlb':             {'sport':'baseball',  'league':'mlb','total':'Carreras','soccer':False,'players':False},
    'icehockey_nhl':            {'sport':'hockey',    'league':'nhl','total':'Goles','soccer':False,'players':False},
}
for k in SOCCER_LEAGUES:
    SPORT_META[k] = {'sport':'soccer','league':'','total':'Goles','soccer':True,'players':False}

# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def fetch_odds(sport_key):
    try:
        r = requests.get(f'{ODDS_BASE}/sports/{sport_key}/odds/', timeout=12, params={
            'apiKey': ODDS_KEY, 'regions': 'us,eu',
            'markets': 'h2h,totals,spreads', 'oddsFormat': 'decimal'})
        return r.json() if r.ok else []
    except: return []

@st.cache_data(ttl=7200, show_spinner=False)
def fetch_espn_teams(sport, league):
    try:
        r = requests.get(f'{ESPN_SITE}/{sport}/{league}/teams', params={'limit':100}, timeout=10)
        if not r.ok: return {}
        teams = r.json().get('sports',[{}])[0].get('leagues',[{}])[0].get('teams',[])
        return {t['team']['displayName']: t['team']['id'] for t in teams}
    except: return {}

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_roster(sport, league, team_id):
    try:
        r = requests.get(f'{ESPN_SITE}/{sport}/{league}/teams/{team_id}/roster', timeout=10)
        if not r.ok: return [], []
        players, injured = [], []
        for g in r.json().get('athletes', []):
            items = g.get('items', []) if isinstance(g, dict) else (g if isinstance(g, list) else [])
            for a in items:
                pid = str(a.get('id',''))
                pname = a.get('displayName') or a.get('fullName','')
                pr = a.get('position',{}); pos = pr.get('abbreviation','') if isinstance(pr,dict) else ''
                if pid and pname: players.append({'id':pid,'name':pname,'pos':pos})
                for inj in a.get('injuries',[]):
                    injured.append({'name':pname,'status':inj.get('status','OUT'),'note':inj.get('shortComment','')})
        return players[:12], injured[:6]
    except: return [], []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_nba_stats(athlete_id):
    try:
        r = requests.get(f'{ESPN_CMVN}/basketball/nba/athletes/{athlete_id}/stats', timeout=10)
        if not r.ok: return {}
        stats = {}
        for cat in r.json().get('splits',{}).get('categories',[]):
            for s in cat.get('stats',[]): stats[s.get('abbreviation','')] = s.get('value')
        return stats
    except: return {}

# ══════════════════════════════════════════════════════════════════════════════
# MATH
# ══════════════════════════════════════════════════════════════════════════════

def _avg(lst): return sum(lst)/len(lst) if lst else None
def _med(lst):
    if not lst: return None
    s=sorted(lst); n=len(s)
    return (s[n//2-1]+s[n//2])/2 if n%2==0 else s[n//2]

def rm(*odds):
    """Remove bookmaker margin, return true probs as list."""
    valid = [o for o in odds if o and o > 1]
    if len(valid) < len(odds): return [50.0]*len(odds)
    imps = [1/o for o in valid]
    mg = sum(imps)
    return [(i/mg)*100 for i in imps]

def kelly(prob_pct, odds):
    b=odds-1; p=prob_pct/100
    return max((b*p-(1-p))/b, 0)

def fmt_s(v):
    try: return f"{float(v):.1f}"
    except: return "—"

def match_team(name, tdict):
    if not tdict: return None
    if name in tdict: return tdict[name]
    nl=name.lower()
    for k,v in tdict.items():
        if nl in k.lower() or k.lower() in nl: return v
    for w in reversed(name.split()):
        if len(w)>3:
            for k,v in tdict.items():
                if w.lower() in k.lower(): return v
    return None

def game_dt(game):
    try:
        return datetime.fromisoformat(game.get('commence_time','').replace('Z','+00:00'))
    except: return None

def game_time_str(game):
    dt = game_dt(game)
    if not dt: return "?"
    local = dt - timedelta(hours=6)
    return local.strftime('%H:%M')

# ══════════════════════════════════════════════════════════════════════════════
# MARKET PARSERS
# ══════════════════════════════════════════════════════════════════════════════

def parse_h2h(game, home, away):
    h,a,d = [],[],[]
    for bk in game.get('bookmakers',[]):
        for mkt in bk.get('markets',[]):
            if mkt['key']!='h2h': continue
            for o in mkt.get('outcomes',[]):
                if o['name']==home:     h.append(o['price'])
                elif o['name']==away:   a.append(o['price'])
                elif o['name']=='Draw': d.append(o['price'])
    return _avg(h), _avg(a), _avg(d)

def parse_all_totals(game):
    lines = {}
    for bk in game.get('bookmakers',[]):
        for mkt in bk.get('markets',[]):
            if mkt['key']!='totals': continue
            for o in mkt.get('outcomes',[]):
                pt = o.get('point',0)
                if pt not in lines: lines[pt] = {'o':[],'u':[]}
                if o['name']=='Over':  lines[pt]['o'].append(o['price'])
                elif o['name']=='Under': lines[pt]['u'].append(o['price'])
    return {pt: (_avg(d['o']), _avg(d['u'])) for pt,d in sorted(lines.items()) if d['o'] and d['u']}

def parse_spreads(game, home, away):
    h_pts,a_pts,h_o,a_o = [],[],[],[]
    for bk in game.get('bookmakers',[]):
        for mkt in bk.get('markets',[]):
            if mkt['key']!='spreads': continue
            for o in mkt.get('outcomes',[]):
                pt=o.get('point',0)
                if o['name']==home:   h_pts.append(pt); h_o.append(o['price'])
                elif o['name']==away: a_pts.append(pt); a_o.append(o['price'])
    return _avg(h_pts), _avg(h_o), _avg(a_pts), _avg(a_o)

# ══════════════════════════════════════════════════════════════════════════════
# PREDICTION CARD HTML
# ══════════════════════════════════════════════════════════════════════════════

def tier(prob):
    if prob >= 68: return 'optimo'
    if prob >= 57: return 'premium'
    if prob >= 50: return 'general'
    return 'norec'

TIER_STYLE = {
    'optimo':  ('#ef4444', 'rgba(239,68,68,0.15)',   '2px solid #ef4444',              '⚡ Óptimo'),
    'premium': ('#a78bfa', 'rgba(124,58,237,0.15)',  '2px solid #7c3aed',              '⭐ Premium'),
    'general': ('#60a5fa', 'rgba(59,130,246,0.12)',  '2px solid #3b82f6',              '● General'),
    'norec':   ('#475569', 'rgba(255,255,255,0.04)', '1px solid rgba(255,255,255,0.1)','○ No rec.'),
}

def pred_card(label, prob, odds):
    t = tier(prob)
    col, bg, brd, badge = TIER_STYLE[t]
    return f"""
<div style="background:{bg};border:{brd};border-radius:12px;padding:14px 10px;
     text-align:center;min-width:88px;flex:1;max-width:160px;">
  <div style="font-size:0.66rem;color:#94a3b8;text-transform:uppercase;
       letter-spacing:.6px;margin-bottom:6px;">{label}</div>
  <div style="font-size:1.55rem;font-weight:900;color:{col};line-height:1.1;">{prob:.0f}%</div>
  <div style="font-size:0.72rem;color:#64748b;margin-top:3px;">{odds:.2f}</div>
  <div style="font-size:0.6rem;color:{col};margin-top:6px;">{badge}</div>
</div>"""

def cards_row(*cards): return f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin:6px 0;">{"".join(cards)}</div>'

def section_hdr(title): return f'<div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin:18px 0 8px;font-weight:700;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.07);">{title}</div>'

LEGEND_HTML = """
<div style="display:flex;gap:14px;flex-wrap:wrap;padding:12px 0;margin-top:8px;
     border-top:1px solid rgba(255,255,255,0.06);font-size:0.7rem;color:#94a3b8;">
  <span>🔴 <span style="color:#ef4444;">Óptimo</span> ≥68%</span>
  <span>🟣 <span style="color:#a78bfa;">Premium</span> 57-68%</span>
  <span>🔵 <span style="color:#60a5fa;">General</span> 50-57%</span>
  <span>⬜ <span style="color:#475569;">No rec.</span> &lt;50%</span>
</div>"""

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="background:linear-gradient(90deg,#2d1b69,#1a0a3c);padding:14px 20px;
     margin:-0.5rem -1rem 1rem;border-bottom:1px solid rgba(124,58,237,.35);
     display:flex;align-items:center;justify-content:space-between;">
  <div style="font-weight:900;font-size:1.25rem;letter-spacing:2px;color:#fff;">
    SCOUT<span style="color:#7c3aed;">AI</span>
  </div>
  <div style="font-size:0.75rem;color:#64748b;">⚡ Powered by IA</div>
</div>
""", unsafe_allow_html=True)

# Net P&L for capital display
net_pl = sum(b.get('ganancia',0) for b in historial if b.get('resultado') in ('ganado','perdido'))
capital = st.session_state.saldo + net_pl

# ══════════════════════════════════════════════════════════════════════════════
# MAIN TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_home, tab_val, tab_log, tab_conta = st.tabs(
    ["🏠 Partidos", "🎯 Con Valor", "📝 Registrar", "📊 Contabilidad"])

# ════════════════════════════ TAB 1 — PARTIDOS ════════════════════════════════
with tab_home:

    # ── DETAIL VIEW ──────────────────────────────────────────────────────────
    if st.session_state.view == 'detail' and st.session_state.selected_game:
        game = st.session_state.selected_game
        cfg  = st.session_state.selected_cfg or {}
        home, away = game['home_team'], game['away_team']
        is_soccer  = cfg.get('soccer', True)
        time_str   = game_time_str(game)
        league_nm  = st.session_state.selected_league_name

        if st.button("← Volver a partidos"):
            st.session_state.view = 'home'; st.rerun()

        # Game header
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#2d1b69,#1a0a3c);border-radius:14px;
     padding:18px 16px;text-align:center;margin-bottom:12px;">
  <div style="font-size:0.8rem;color:#a78bfa;margin-bottom:10px;">{league_nm} · {time_str}</div>
  <div style="display:flex;align-items:center;justify-content:center;gap:20px;">
    <div style="flex:1;text-align:right;">
      <div style="font-size:1.1rem;font-weight:700;color:#fff;">{home}</div>
      <div style="font-size:0.72rem;color:#64748b;">Local</div>
    </div>
    <div style="background:rgba(255,255,255,0.1);border:2px solid rgba(124,58,237,.5);
         border-radius:10px;padding:10px 18px;font-size:1.3rem;font-weight:900;color:#fff;">
      Próximo
    </div>
    <div style="flex:1;text-align:left;">
      <div style="font-size:1.1rem;font-weight:700;color:#fff;">{away}</div>
      <div style="font-size:0.72rem;color:#64748b;">Visitante</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        dtab_pred, dtab_datos = st.tabs(["⚡ Predicción", "📋 Datos del partido"])

        # ── PREDICCIÓN ──────────────────────────────────────────────────────
        with dtab_pred:
            avg_h, avg_a, avg_d = parse_h2h(game, home, away)
            totals = parse_all_totals(game)
            h_pt, h_sp, a_pt, a_sp = parse_spreads(game, home, away)

            if avg_h and avg_a:
                html = ""

                # ─ 1×2 ─
                if is_soccer and avg_d:
                    p_h, p_d, p_a = rm(avg_h, avg_d, avg_a)
                    html += section_hdr("Partido (1X2)")
                    html += cards_row(
                        pred_card("Local", p_h, avg_h),
                        pred_card("Empate", p_d, avg_d),
                        pred_card("Visitante", p_a, avg_a),
                    )
                    # Double chance
                    p_12 = min(p_h+p_a, 99); p_1x = min(p_h+p_d, 99); p_x2 = min(p_d+p_a, 99)
                    o_12 = 1/(p_12/100+0.001); o_1x = 1/(p_1x/100+0.001); o_x2 = 1/(p_x2/100+0.001)
                    html += section_hdr("Doble Oportunidad")
                    html += cards_row(
                        pred_card("1-2 (no Empate)", p_12, o_12),
                        pred_card("1X (no Visitante)", p_1x, o_1x),
                        pred_card("X2 (no Local)", p_x2, o_x2),
                    )
                    # Best bet
                    best_p = max(p_h, p_d, p_a)
                    best_lbl = "Local" if p_h==best_p else ("Empate" if p_d==best_p else "Visitante")
                    best_o = avg_h if p_h==best_p else (avg_d if p_d==best_p else avg_a)
                else:
                    p_h, p_a = rm(avg_h, avg_a)
                    html += section_hdr("Partido (Moneyline)")
                    html += cards_row(
                        pred_card("Local", p_h, avg_h),
                        pred_card("Visitante", p_a, avg_a),
                    )
                    best_p = max(p_h, p_a)
                    best_lbl = "Local" if p_h >= p_a else "Visitante"
                    best_o = avg_h if p_h >= p_a else avg_a

                # ─ Gol (Over/Under) ─
                if totals:
                    html += section_hdr(f"Goles / {cfg.get('total','Total')}")
                    cards = ""
                    for pt, (o_o, u_o) in totals.items():
                        p_o, p_u = rm(o_o, u_o)
                        cards += pred_card(f"Más {pt}", p_o, o_o)
                        cards += pred_card(f"Menos {pt}", p_u, u_o)
                    html += cards_row(cards)

                # ─ Hándicap ─
                if h_pt is not None and h_sp and a_sp:
                    p_hs, p_as = rm(h_sp, a_sp)
                    h_sign = f"+{h_pt:.1f}" if h_pt>0 else f"{h_pt:.1f}"
                    a_sign = (f"+{a_pt:.1f}" if a_pt>0 else f"{a_pt:.1f}") if a_pt is not None else "—"
                    html += section_hdr("Hándicap")
                    html += cards_row(
                        pred_card(f"Local {h_sign}", p_hs, h_sp),
                        pred_card(f"Visit. {a_sign}", p_as, a_sp),
                    )

                html += LEGEND_HTML
                st.markdown(html, unsafe_allow_html=True)

                # ─ Kelly suggestion ─
                st.markdown("---")
                st.markdown("**💰 Apuesta sugerida (Kelly/4)**")
                k = kelly(best_p, best_o)
                monto = (capital * k) / 4
                if monto >= 0.50:
                    c1,c2,c3 = st.columns(3)
                    c1.metric("Equipo", best_lbl)
                    c2.metric("Prob IA", f"{best_p:.1f}%")
                    c3.metric("Apostar", f"${monto:.2f}", delta=f"Ganancia: ${monto*best_o-monto:.2f}")
                else:
                    st.info("⚠️ Sin ventaja Kelly suficiente — odds demasiado ajustadas.")

                # ─ Explainer ─
                with st.expander("🧮 ¿Cómo calculó la IA estas probabilidades?"):
                    if is_soccer and avg_d:
                        imp_h, imp_d, imp_a = 1/avg_h, 1/avg_d, 1/avg_a
                        mg = imp_h+imp_d+imp_a
                        st.markdown(f"""
**1. Cuotas promedio:** Local={avg_h:.3f} | Empate={avg_d:.3f} | Visitante={avg_a:.3f}

**2. Probabilidad implícita (1÷cuota):**
Local={imp_h*100:.2f}% | Empate={imp_d*100:.2f}% | Visitante={imp_a*100:.2f}% → Suma={mg*100:.2f}%

**3. Margen del bookmaker:** `{(mg-1)*100:.2f}%` — lo que se quedan las casas

**4. Probabilidad real (normalizada):**
Local=**{imp_h/mg*100:.1f}%** | Empate=**{imp_d/mg*100:.1f}%** | Visitante=**{imp_a/mg*100:.1f}%**

*Fórmula: Prob_real = (1/cuota) ÷ Σ(1/cuotas)*
                        """)
                    else:
                        imp_h2, imp_a2 = 1/avg_h, 1/avg_a
                        mg2 = imp_h2+imp_a2
                        st.markdown(f"""
**1. Cuotas promedio:** Local={avg_h:.3f} | Visitante={avg_a:.3f}

**2. Prob implícita (1÷cuota):** Local={imp_h2*100:.2f}% | Visit.={imp_a2*100:.2f}% → Suma={mg2*100:.2f}%

**3. Margen de la casa:** `{(mg2-1)*100:.2f}%`

**4. Prob real (normalizada):** Local=**{imp_h2/mg2*100:.1f}%** | Visitante=**{imp_a2/mg2*100:.1f}%**

**5. Kelly Criterion:** f* = (b·p − q) ÷ b, donde b=cuota−1, p=prob_real. Usamos Kelly÷4.
                        """)
            else:
                st.warning("Sin datos de odds para este partido.")

        # ── DATOS DEL PARTIDO ───────────────────────────────────────────────
        with dtab_datos:
            sport_k = cfg.get('sport','')
            league_k= cfg.get('league','')

            # NBA players
            if cfg.get('players') and sport_k:
                espn_teams = fetch_espn_teams(sport_k, league_k)
                if espn_teams:
                    st.markdown("#### ⭐ Jugadores clave — Promedios de temporada")
                    for team in [home, away]:
                        tid = match_team(team, espn_teams)
                        if not tid: continue
                        players, _ = fetch_roster(sport_k, league_k, tid)
                        st.markdown(f"**{team}**")
                        rows = []
                        for p in players[:5]:
                            s = fetch_nba_stats(p['id'])
                            rows.append({'Jugador':p['name'],'Pos':p['pos'],
                                'PTS':fmt_s(s.get('PTS') or s.get('PPG')),
                                'REB':fmt_s(s.get('REB') or s.get('RPG')),
                                'AST':fmt_s(s.get('AST') or s.get('APG')),
                                '3PM':fmt_s(s.get('3PM') or s.get('FG3M'))})
                        if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            # Injuries (non-soccer)
            if not is_soccer and sport_k and league_k:
                espn_teams2 = fetch_espn_teams(sport_k, league_k)
                if espn_teams2:
                    st.markdown("#### 🏥 Lesiones")
                    for team in [home, away]:
                        tid = match_team(team, espn_teams2)
                        if tid:
                            _, inj = fetch_roster(sport_k, league_k, tid)
                            if inj:
                                st.warning(f"**{team}:** " + " · ".join(
                                    f"🤕 {i['name']} ({i['status']})" for i in inj[:4]))
                            else:
                                st.success(f"✅ **{team}:** Sin lesiones")

            # Bookmaker comparison
            st.markdown("#### 📊 Comparación de cuotas por casa")
            bk_rows = []
            for bk in game.get('bookmakers', [])[:8]:
                row = {'Casa': bk['name']}
                for mkt in bk.get('markets', []):
                    if mkt['key'] != 'h2h': continue
                    for o in mkt.get('outcomes', []):
                        nm = o['name']
                        if nm == home:     row['Local'] = o['price']
                        elif nm == away:   row['Visit.'] = o['price']
                        elif nm == 'Draw': row['Empate'] = o['price']
                bk_rows.append(row)
            if bk_rows:
                st.dataframe(pd.DataFrame(bk_rows), use_container_width=True, hide_index=True)

    # ── HOME VIEW (game list) ─────────────────────────────────────────────────
    else:
        # Sport selector
        sport_filter = st.radio("", ["⚽ Fútbol","🏀 NBA","🏈 NFL","⚾ MLB","🏒 NHL"],
                                horizontal=True, label_visibility='collapsed')

        # Map filter → sport keys
        filter_keys = {
            "⚽ Fútbol": list(SOCCER_LEAGUES.keys()),
            "🏀 NBA":    ['basketball_nba'],
            "🏈 NFL":    ['americanfootball_nfl'],
            "⚾ MLB":    ['baseball_mlb'],
            "🏒 NHL":    ['icehockey_nhl'],
        }
        active_keys = filter_keys[sport_filter]

        # Date selector (next 7 days)
        today = datetime.now(timezone.utc).date()
        date_opts = [today + timedelta(days=i) for i in range(7)]
        date_labels = []
        for d in date_opts:
            if d == today: date_labels.append("HOY")
            elif d == today+timedelta(1): date_labels.append("MAÑANA")
            else: date_labels.append(d.strftime("%a %d").upper())

        sel_date_lbl = st.radio("", date_labels, horizontal=True, label_visibility='collapsed')
        sel_date = date_opts[date_labels.index(sel_date_lbl)]

        # Search
        search = st.text_input("", placeholder="🔍 Buscar equipo...", label_visibility='collapsed')

        # Fetch & filter games
        with st.spinner("Cargando partidos..."):
            all_games = []
            for key in active_keys:
                games = fetch_odds(key)
                for g in games:
                    gd = game_dt(g)
                    if gd and gd.date() == sel_date:
                        g['_key'] = key
                        g['_league'] = ALL_SPORTS.get(key, key)
                        all_games.append(g)

        # Apply search
        if search:
            sl = search.lower()
            all_games = [g for g in all_games
                         if sl in g['home_team'].lower() or sl in g['away_team'].lower()]

        if not all_games:
            st.markdown("""
<div style="text-align:center;padding:40px 20px;color:#475569;">
  <div style="font-size:3rem;margin-bottom:12px;">📭</div>
  <div>Sin partidos para esta fecha en este deporte.</div>
  <div style="font-size:0.8rem;margin-top:6px;">Prueba otra fecha o liga.</div>
</div>""", unsafe_allow_html=True)
        else:
            # Group by league
            by_league = {}
            for g in all_games:
                lbl = g['_league']
                by_league.setdefault(lbl, []).append(g)

            for league_lbl, games in by_league.items():
                # League header
                st.markdown(f"""
<div style="background:rgba(255,255,255,0.04);border-left:3px solid #7c3aed;
     padding:8px 14px;margin:14px 0 4px;border-radius:0 8px 8px 0;
     font-size:0.78rem;font-weight:700;color:#a78bfa;letter-spacing:.5px;">
  {league_lbl}
</div>""", unsafe_allow_html=True)

                for game in games:
                    home = game['home_team']
                    away = game['away_team']
                    time_s = game_time_str(game)

                    # Quick prob for display
                    avg_h, avg_a, avg_d = parse_h2h(game, home, away)
                    if avg_h and avg_a:
                        if avg_d:
                            p_h, p_d, p_a = rm(avg_h, avg_d, avg_a)
                        else:
                            p_h, p_a = rm(avg_h, avg_a)
                            p_d = 0

                        best_p = max(p_h, p_d, p_a)
                        best_t = tier(best_p)
                        dot_col = TIER_STYLE[best_t][0]
                        prob_disp = f'<span style="color:{dot_col};font-weight:700;">{best_p:.0f}%</span>'
                    else:
                        prob_disp = '<span style="color:#475569;">—</span>'

                    # Card row
                    c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
                    with c1:
                        st.markdown(f"""
<div style="padding:6px 0;">
  <div style="font-size:0.88rem;font-weight:600;color:#e2e8f0;">{home}</div>
  <div style="font-size:0.88rem;color:#94a3b8;margin-top:2px;">{away}</div>
</div>""", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""
<div style="padding:6px 0;text-align:center;">
  <div style="font-size:0.75rem;color:#7c3aed;font-weight:700;">⏰ {time_s}</div>
  <div style="margin-top:2px;">{prob_disp}</div>
</div>""", unsafe_allow_html=True)
                    with c3:
                        n_bk = len(game.get('bookmakers', []))
                        st.markdown(f"""
<div style="padding:6px 0;text-align:center;">
  <div style="font-size:0.72rem;color:#475569;">{n_bk} casas</div>
</div>""", unsafe_allow_html=True)
                    with c4:
                        if st.button("→", key=f"btn_{game.get('id','')}_{league_lbl}"):
                            st.session_state.view = 'detail'
                            st.session_state.selected_game = game
                            st.session_state.selected_cfg  = SPORT_META.get(game['_key'], {})
                            st.session_state.selected_league_name = league_lbl
                            st.rerun()

                    st.markdown('<hr style="border:none;border-top:1px solid rgba(255,255,255,0.05);margin:0;">', unsafe_allow_html=True)

            st.caption(f"📋 {len(all_games)} partido(s) para {sel_date_lbl}")

# ════════════════════════════ TAB 2 — VALOR ═══════════════════════════════════
with tab_val:
    st.markdown("### 🎯 Apuestas con Valor Positivo")
    st.caption("Buscamos cuotas donde el bookmaker paga más de lo que la probabilidad real indica (EV > 1.04, Prob 38-78%).")

    if st.button("🔍 Escanear todos los deportes y ligas", use_container_width=True):
        with st.spinner("Escaneando NBA · NFL · MLB · NHL · Fútbol..."):
            rows = []
            for skey, sname in ALL_SPORTS.items():
                games = fetch_odds(skey)
                for g in games:
                    home, away = g['home_team'], g['away_team']
                    h_list, a_list = [], []
                    for bk in g.get('bookmakers',[]):
                        for mkt in bk.get('markets',[]):
                            if mkt['key']!='h2h': continue
                            for o in mkt.get('outcomes',[]):
                                if o['name']==home:     h_list.append(o['price'])
                                elif o['name']==away:   a_list.append(o['price'])
                    if len(h_list)<3 or len(a_list)<3: continue
                    med_h,med_a = _med(h_list),_med(a_list)
                    best_h,best_a = max(h_list),max(a_list)
                    p_h,p_a = rm(med_h, med_a)
                    for team,tp,bo in [(home,p_h/100,best_h),(away,p_a/100,best_a)]:
                        ev = bo*tp
                        if ev>1.04 and 0.38<=tp<=0.78:
                            k_ = kelly(tp*100, bo)
                            monto_ = (capital*k_)/4
                            rows.append({'Liga':sname,'Partido':f'{away} @ {home}',
                                'Apostar a':team,'Cuota':f'{bo:.2f}',
                                'Prob IA':f'{tp*100:.1f}%','EV':round(ev,4),
                                'Ventaja':f'+{(ev-1)*100:.1f}%',
                                'Sugerido':f'${monto_:.2f}' if monto_>=0.50 else '<$0.50'})
        rows = sorted(rows, key=lambda x: x['EV'], reverse=True)
        if rows:
            df_v = pd.DataFrame(rows)
            st.dataframe(df_v.style.background_gradient(subset=['EV'], cmap='Purples'),
                         use_container_width=True, hide_index=True)
            st.caption(f"✅ {len(rows)} apuesta(s) con valor encontradas.")
        else:
            st.info("Sin apuestas con valor positivo en este momento.")

# ════════════════════════════ TAB 3 — REGISTRAR ═══════════════════════════════
with tab_log:
    st.markdown("### 📝 Registrar resultado")
    st.caption("Guarda el comprobante y resultado para que la IA lleve la contabilidad y se calibre.")

    with st.form("form_bet", clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1:
            f_partido = st.text_input("Partido *", placeholder="Lakers vs Warriors")
            f_deporte = st.selectbox("Deporte *", list(ALL_SPORTS.values()))
            f_apuesta = st.text_input("Apostaste a *", placeholder="Lakers")
            f_cuota   = st.number_input("Cuota *", min_value=1.01, value=1.85, step=0.01, format="%.2f")
        with c2:
            f_monto   = st.number_input("Monto apostado ($) *", min_value=0.01, value=5.00, step=0.50, format="%.2f")
            f_prob    = st.number_input("Prob IA que te dio (%) *", min_value=1.0, max_value=99.0, value=55.0, step=0.5)
            f_result  = st.radio("Resultado *", ["ganado","perdido","pendiente"], horizontal=True)
            f_foto    = st.file_uploader("📸 Foto comprobante", type=["jpg","jpeg","png","webp"])
        f_notas = st.text_area("Notas", height=55)
        submitted = st.form_submit_button("💾 Guardar", use_container_width=True)

    if submitted:
        foto_path = None
        if f_foto:
            ext = f_foto.name.rsplit('.',1)[-1]
            fname = f"{uuid.uuid4().hex}.{ext}"
            foto_path = os.path.join(FOTOS_DIR, fname)
            with open(foto_path,'wb') as fp: fp.write(f_foto.read())
        ganancia = round(f_monto*f_cuota-f_monto,2) if f_result=='ganado' else (-round(f_monto,2) if f_result=='perdido' else 0.0)
        historial.append({'id':str(uuid.uuid4()),'fecha':datetime.now().strftime('%Y-%m-%d %H:%M'),
            'deporte':f_deporte,'partido':f_partido,'apuesta':f_apuesta,'cuota':f_cuota,
            'monto':f_monto,'prob_ia':f_prob,'resultado':f_result,'ganancia':ganancia,
            'foto':foto_path,'notas':f_notas})
        save_hist(historial)
        icon = "🟢" if f_result=="ganado" else "🔴" if f_result=="perdido" else "🟡"
        st.success(f"{icon} Guardado: **{f_partido}** → {f_result.upper()} | P&L: ${ganancia:+.2f}")
        st.rerun()

    if historial:
        st.markdown("---")
        st.markdown("#### Últimas apuestas")
        for b in reversed(historial[-5:]):
            r = b.get('resultado','pendiente')
            icon = "🟢" if r=="ganado" else "🔴" if r=="perdido" else "🟡"
            with st.expander(f"{icon} {b['fecha'][:10]} — {b.get('partido','')} | **{b.get('apuesta','')}** | ${b.get('ganancia',0):+.2f}"):
                fc1,fc2 = st.columns([1,2])
                with fc1:
                    fp = b.get('foto')
                    if fp and os.path.exists(fp): st.image(fp, use_container_width=True)
                    else: st.info("Sin foto")
                with fc2:
                    st.markdown(f"""
**Deporte:** {b.get('deporte','')}
**Partido:** {b.get('partido','')}
**Aposté a:** {b.get('apuesta','')}
**Cuota:** {b.get('cuota',0):.2f} | **Monto:** ${b.get('monto',0):.2f}
**Prob IA:** {b.get('prob_ia',0):.1f}% | **Result.:** {r.upper()} {icon}
**P&L:** ${b.get('ganancia',0):+.2f}
""")
                    if b.get('notas'): st.caption(f"📝 {b['notas']}")

# ════════════════════════════ TAB 4 — CONTABILIDAD ════════════════════════════
with tab_conta:
    st.markdown("### 📊 Contabilidad & Rentabilidad")
    closed = [b for b in historial if b.get('resultado') in ('ganado','perdido')]

    if not closed:
        st.info("📭 Sin apuestas cerradas aún. Registra resultados en **Registrar**.")
    else:
        total   = len(closed)
        won     = sum(1 for b in closed if b['resultado']=='ganado')
        wagered = sum(b.get('monto',0) for b in closed)
        returned= sum(b.get('monto',0)*b.get('cuota',1) for b in closed if b['resultado']=='ganado')
        profit  = returned-wagered
        roi     = profit/wagered*100 if wagered else 0

        # KPIs
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Apuestas",  total)
        k2.metric("✅ Ganadas", won)
        k3.metric("❌ Perdidas",total-won)
        k4.metric("Win Rate",  f"{won/total*100:.1f}%")
        k5.metric("ROI",       f"{roi:+.1f}%", delta=f"${profit:+.2f}")

        st.caption(f"Apostado: ${wagered:.2f} · Retornado: ${returned:.2f} · Profit: ${profit:+.2f}")
        st.divider()

        # Capital evolution
        if len(closed) >= 2:
            st.markdown("#### 📈 Evolución del Capital")
            run = st.session_state.saldo; evo = []
            for b in closed:
                run += b.get('ganancia',0)
                evo.append({'Fecha':b['fecha'][:10],'Capital ($)':round(run,2)})
            st.line_chart(pd.DataFrame(evo).set_index('Fecha'))

        # By sport
        st.markdown("#### 🏆 Por Deporte")
        sp_map = {}
        for b in closed:
            d=b.get('deporte','Otro')
            if d not in sp_map: sp_map[d]={'won':0,'total':0,'profit':0.0}
            sp_map[d]['total']+=1; sp_map[d]['profit']+=b.get('ganancia',0)
            if b['resultado']=='ganado': sp_map[d]['won']+=1
        sp_rows = [{'Deporte':d,'Apuestas':v['total'],'Ganadas':v['won'],
                    'Win%':f"{v['won']/v['total']*100:.0f}%",'Profit':f"${v['profit']:+.2f}"}
                   for d,v in sp_map.items()]
        if sp_rows: st.dataframe(pd.DataFrame(sp_rows), use_container_width=True, hide_index=True)

        # Calibration
        st.markdown("#### 🧠 Calibración de la IA")
        cal = {}
        for b in closed:
            p=b.get('prob_ia',0); bk=f"{int(p//10)*10}-{int(p//10)*10+10}%"
            if bk not in cal: cal[bk]={'won':0,'total':0}
            cal[bk]['total']+=1
            if b['resultado']=='ganado': cal[bk]['won']+=1
        if cal:
            cal_rows=[]
            for bk,data in sorted(cal.items()):
                acc=data['won']/data['total']*100 if data['total'] else 0
                diff=acc-float(bk.split('-')[0])
                ic="🟢" if diff>5 else "🔴" if diff<-5 else "🔵"
                cal_rows.append({'Rango Prob IA':bk,'Apuestas':data['total'],'Ganadas':data['won'],
                                 'Precisión Real':f"{acc:.0f}%",
                                 'Estado':f"{ic} {'Mejor' if diff>5 else 'Peor' if diff<-5 else 'Calibrado'}"})
            st.dataframe(pd.DataFrame(cal_rows), use_container_width=True, hide_index=True)
            st.caption("Perfecta calibración = la IA dice 60% → ganamos 60%.")

        # Full history
        st.markdown("#### 📋 Historial")
        hrows=[{'Fecha':b['fecha'][:10],'Deporte':b.get('deporte',''),'Partido':b.get('partido',''),
                'Apuesta':b.get('apuesta',''),'Cuota':b.get('cuota',0),
                'Monto':f"${b.get('monto',0):.2f}",'Prob IA':f"{b.get('prob_ia',0):.1f}%",
                'Result.':b.get('resultado','').upper(),'P&L':f"${b.get('ganancia',0):+.2f}"}
               for b in reversed(historial)]
        if hrows: st.dataframe(pd.DataFrame(hrows), use_container_width=True, hide_index=True)

        if st.button("🗑 Borrar historial", type="secondary"):
            save_hist([]); st.rerun()

    # Capital input at bottom
    st.divider()
    new_s = st.number_input("Actualizar capital inicial ($):", value=float(st.session_state.saldo), min_value=1.0, step=5.0)
    if abs(new_s-st.session_state.saldo)>0.001: st.session_state.saldo=new_s; st.rerun()
