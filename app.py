import streamlit as st
import pandas as pd
import requests
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from math import exp, factorial

st.set_page_config(page_title="ScoutAI Pro", page_icon="⚽", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
.stApp { background:#0a0a1a; color:#e2e8f0; }
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding-top:0!important;max-width:820px!important;margin:auto;}

/* Radio → pills */
div[role="radiogroup"]{display:flex;flex-wrap:wrap;gap:6px;}
div[role="radiogroup"] label{
  background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
  border-radius:20px!important;padding:5px 16px!important;
  color:#94a3b8!important;font-size:.8rem!important;cursor:pointer;}
div[role="radiogroup"] label:has(input:checked){
  background:rgba(124,58,237,.45)!important;border-color:#7c3aed!important;
  color:#c4b5fd!important;font-weight:700!important;}
div[role="radiogroup"] label>div:first-child{display:none!important;}

/* Buttons */
.stButton>button{
  background:rgba(255,255,255,.04)!important;border:1px solid rgba(255,255,255,.09)!important;
  color:#e2e8f0!important;border-radius:10px!important;transition:all .18s!important;}
.stButton>button:hover{
  background:rgba(124,58,237,.25)!important;border-color:rgba(124,58,237,.6)!important;}

/* Inputs */
.stTextInput>div>div>input,.stNumberInput>div>div>input,.stTextArea textarea{
  background:rgba(255,255,255,.05)!important;border:1px solid rgba(255,255,255,.1)!important;
  border-radius:10px!important;color:#e2e8f0!important;}
.stSelectbox>div>div{background:rgba(255,255,255,.05)!important;border-radius:10px!important;}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:2px;background:rgba(255,255,255,.03);border-radius:12px;padding:3px;}
.stTabs [data-baseweb="tab"]{border-radius:10px;color:#64748b;font-size:.8rem;padding:7px 14px;}
.stTabs [data-baseweb="tab"][aria-selected="true"]{background:rgba(124,58,237,.4);color:#c4b5fd;font-weight:700;}
.stTabs [data-baseweb="tab-highlight"]{display:none;}

/* Metrics */
div[data-testid="stMetricValue"]{color:#a78bfa!important;}
div[data-testid="stMetricLabel"]{color:#475569!important;}
label{color:#64748b!important;font-size:.8rem!important;}
</style>
""", unsafe_allow_html=True)

# ─── Persistence ──────────────────────────────────────────────────────────────
APP_DIR   = os.path.dirname(os.path.abspath(__file__))
HIST_FILE = os.path.join(APP_DIR, 'historial.json')
FOTOS_DIR = os.path.join(APP_DIR, 'fotos_apuestas')
os.makedirs(FOTOS_DIR, exist_ok=True)

def load_hist():
    try:
        with open(HIST_FILE,'r',encoding='utf-8') as f: return json.load(f)
    except: return []

def save_hist(d):
    with open(HIST_FILE,'w',encoding='utf-8') as f: json.dump(d,f,indent=2,ensure_ascii=False)

# ─── Session state ─────────────────────────────────────────────────────────────
for k,v in [('saldo',24.27),('view','home'),('sel_game',None),
            ('sel_cfg',None),('sel_league',''),('quick_reg',None)]:
    if k not in st.session_state: st.session_state[k]=v

historial = load_hist()
net_pl    = sum(b.get('ganancia',0) for b in historial if b.get('resultado') in ('ganado','perdido'))
capital   = st.session_state.saldo + net_pl

# ─── Constants ─────────────────────────────────────────────────────────────────
ODDS_KEY  = '8d90dd7eb80726fb3a98683ee7d2e734'
ODDS_BASE = 'https://api.the-odds-api.com/v4'
ESPN_SITE = 'https://site.api.espn.com/apis/site/v2/sports'
ESPN_CMVN = 'https://site.web.api.espn.com/apis/common/v3/sports'

LEAGUES = {
    'Copa del Mundo 2026':      {'key':'soccer_fifa_world_cup',         'sport':'soccer','league':'fifa.world','soccer':True,  'total':'Goles'},
    'Premier League':           {'key':'soccer_epl',                    'sport':'soccer','league':'eng.1',    'soccer':True,  'total':'Goles'},
    'La Liga':                  {'key':'soccer_spain_la_liga',          'sport':'soccer','league':'esp.1',    'soccer':True,  'total':'Goles'},
    'Champions League':         {'key':'soccer_uefa_champs_league',     'sport':'soccer','league':'uefa.champions','soccer':True,'total':'Goles'},
    'Liga MX':                  {'key':'soccer_mexico_ligamx',          'sport':'soccer','league':'mex.1',   'soccer':True,  'total':'Goles'},
    'MLS':                      {'key':'soccer_usa_mls',                'sport':'soccer','league':'usa.1',   'soccer':True,  'total':'Goles'},
    'Serie A':                  {'key':'soccer_italy_serie_a',          'sport':'soccer','league':'ita.1',   'soccer':True,  'total':'Goles'},
    'Bundesliga':               {'key':'soccer_germany_bundesliga',     'sport':'soccer','league':'ger.1',   'soccer':True,  'total':'Goles'},
    'NBA':                      {'key':'basketball_nba',                'sport':'basketball','league':'nba','soccer':False,'total':'Puntos','players':True},
    'NFL':                      {'key':'americanfootball_nfl',          'sport':'football','league':'nfl',   'soccer':False, 'total':'Puntos'},
    'MLB':                      {'key':'baseball_mlb',                  'sport':'baseball','league':'mlb',  'soccer':False, 'total':'Carreras'},
    'NHL':                      {'key':'icehockey_nhl',                 'sport':'hockey','league':'nhl',    'soccer':False, 'total':'Goles'},
}

# Country → flag emoji
FLAGS = {
    'USA':'🇺🇸','United States':'🇺🇸','Mexico':'🇲🇽','Brazil':'🇧🇷','Argentina':'🇦🇷',
    'Spain':'🇪🇸','Germany':'🇩🇪','France':'🇫🇷','Italy':'🇮🇹','Portugal':'🇵🇹',
    'England':'🏴󠁧󠁢󠁥󠁮󠁧󠁿','Netherlands':'🇳🇱','Croatia':'🇭🇷','Morocco':'🇲🇦',
    'Japan':'🇯🇵','South Korea':'🇰🇷','Australia':'🇦🇺','Canada':'🇨🇦',
    'Paraguay':'🇵🇾','Uruguay':'🇺🇾','Colombia':'🇨🇴','Ecuador':'🇪🇨','Chile':'🇨🇱',
    'Costa Rica':'🇨🇷','Panama':'🇵🇦','Honduras':'🇭🇳','Guatemala':'🇬🇹',
    'Bosnia & Herzegovina':'🇧🇦','Serbia':'🇷🇸','Switzerland':'🇨🇭','Belgium':'🇧🇪',
    'Denmark':'🇩🇰','Sweden':'🇸🇪','Poland':'🇵🇱','Greece':'🇬🇷','Turkey':'🇹🇷',
    'Ukraine':'🇺🇦','Austria':'🇦🇹','Scotland':'🏴󠁧󠁢󠁳󠁣󠁴󠁿','Wales':'🏴󠁧󠁢󠁷󠁬󠁳󠁿',
    'Norway':'🇳🇴','Finland':'🇫🇮','Romania':'🇷🇴','Hungary':'🇭🇺','Slovakia':'🇸🇰',
    'Slovenia':'🇸🇮','Albania':'🇦🇱','Georgia':'🇬🇪','Venezuela':'🇻🇪','Bolivia':'🇧🇴',
    'Peru':'🇵🇪','Saudi Arabia':'🇸🇦','Japan':'🇯🇵','Iran':'🇮🇷','Senegal':'🇸🇳',
    'Nigeria':'🇳🇬','Ghana':'🇬🇭','Cameroon':'🇨🇲','Egypt':'🇪🇬','Tunisia':'🇹🇳',
    'New Zealand':'🇳🇿','Jamaica':'🇯🇲','Cuba':'🇨🇺',
}

def flag(team):
    for k,v in FLAGS.items():
        if k.lower() in team.lower(): return v
    return '⚽'

# ─── Data fetching ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300,show_spinner=False)
def fetch_odds(sport_key):
    try:
        r=requests.get(f'{ODDS_BASE}/sports/{sport_key}/odds/',timeout=12,params={
            'apiKey':ODDS_KEY,'regions':'us,eu','markets':'h2h,totals,spreads','oddsFormat':'decimal'})
        return r.json() if r.ok else []
    except: return []

@st.cache_data(ttl=7200,show_spinner=False)
def fetch_espn_teams(sport,league):
    try:
        r=requests.get(f'{ESPN_SITE}/{sport}/{league}/teams',params={'limit':100},timeout=10)
        if not r.ok: return {}
        t=r.json().get('sports',[{}])[0].get('leagues',[{}])[0].get('teams',[])
        return {x['team']['displayName']:x['team']['id'] for x in t}
    except: return {}

@st.cache_data(ttl=1800,show_spinner=False)
def fetch_roster(sport,league,team_id):
    try:
        r=requests.get(f'{ESPN_SITE}/{sport}/{league}/teams/{team_id}/roster',timeout=10)
        if not r.ok: return [],[]
        players,injured=[],[]
        for g in r.json().get('athletes',[]):
            items=g.get('items',[]) if isinstance(g,dict) else (g if isinstance(g,list) else [])
            for a in items:
                pid=str(a.get('id','')); pname=a.get('displayName') or a.get('fullName','')
                pr=a.get('position',{}); pos=pr.get('abbreviation','') if isinstance(pr,dict) else ''
                if pid and pname: players.append({'id':pid,'name':pname,'pos':pos})
                for inj in a.get('injuries',[]):
                    injured.append({'name':pname,'status':inj.get('status','OUT'),'note':inj.get('shortComment','')})
        return players[:12],injured[:6]
    except: return [],[]

@st.cache_data(ttl=3600,show_spinner=False)
def fetch_nba_stats(aid):
    try:
        r=requests.get(f'{ESPN_CMVN}/basketball/nba/athletes/{aid}/stats',timeout=10)
        if not r.ok: return {}
        s={}
        for cat in r.json().get('splits',{}).get('categories',[]):
            for x in cat.get('stats',[]): s[x.get('abbreviation','')] = x.get('value')
        return s
    except: return {}

@st.cache_data(ttl=1800,show_spinner=False)
def fetch_news(sport,league,team_name):
    try:
        url = f'{ESPN_SITE}/{sport}/{league}/news' if league else f'{ESPN_SITE}/{sport}/news'
        r=requests.get(url,params={'limit':30},timeout=10)
        if not r.ok: return []
        arts=r.json().get('articles',[])
        tn=team_name.lower().split()[-1]
        filtered=[a for a in arts if tn in a.get('headline','').lower()]
        return (filtered or arts)[:8]
    except: return []

# ─── Math ───────────────────────────────────────────────────────────────────────
def _avg(lst): return sum(lst)/len(lst) if lst else None
def _med(lst):
    if not lst: return None
    s=sorted(lst);n=len(s)
    return (s[n//2-1]+s[n//2])/2 if n%2==0 else s[n//2]

def rm(*odds):
    valid=[o for o in odds if o and o>1]
    if not valid: return [50.0]*len(odds)
    imps=[1/o for o in valid]; mg=sum(imps)
    return [(i/mg)*100 for i in imps]

def kelly(p,o):
    b=o-1; p=p/100; return max((b*p-(1-p))/b,0)

def fmt_s(v):
    try: return f"{float(v):.1f}"
    except: return "—"

def pois(lam,k):
    try: return (lam**k*exp(-lam))/factorial(k)
    except: return 0.0

def estimate_xg(line,p_over):
    return max(0.5, line+(p_over-0.5)*1.5)

def split_xg(lam,p_h,p_a):
    rel=p_h/max(p_h+p_a,0.01)
    frac=0.5+(rel-0.5)*0.45
    return lam*frac, lam*(1-frac)

def probable_scores(lh,la,top=5):
    s={(f"{h}-{a}"):pois(lh,h)*pois(la,a) for h in range(7) for a in range(7)}
    return sorted(s.items(),key=lambda x:-x[1])[:top]

def btts(lh,la): return (1-exp(-lh))*(1-exp(-la))

def match_team(name,tdict):
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

# ─── Market parsers ─────────────────────────────────────────────────────────────
def parse_h2h(game,home,away):
    h,a,d=[],[],[]
    for bk in game.get('bookmakers',[]):
        for mkt in bk.get('markets',[]):
            if mkt['key']!='h2h': continue
            for o in mkt.get('outcomes',[]):
                if o['name']==home:      h.append(o['price'])
                elif o['name']==away:    a.append(o['price'])
                elif o['name']=='Draw':  d.append(o['price'])
    return _avg(h),_avg(a),_avg(d)

def parse_all_totals(game):
    lines={}
    for bk in game.get('bookmakers',[]):
        for mkt in bk.get('markets',[]):
            if mkt['key']!='totals': continue
            for o in mkt.get('outcomes',[]):
                pt=o.get('point',0)
                if pt not in lines: lines[pt]={'o':[],'u':[]}
                if o['name']=='Over':  lines[pt]['o'].append(o['price'])
                elif o['name']=='Under': lines[pt]['u'].append(o['price'])
    return {pt:(_avg(d['o']),_avg(d['u'])) for pt,d in sorted(lines.items()) if d['o'] and d['u']}

def parse_spreads(game,home,away):
    h_pts,a_pts,h_o,a_o=[],[],[],[]
    for bk in game.get('bookmakers',[]):
        for mkt in bk.get('markets',[]):
            if mkt['key']!='spreads': continue
            for o in mkt.get('outcomes',[]):
                pt=o.get('point',0)
                if o['name']==home:   h_pts.append(pt);h_o.append(o['price'])
                elif o['name']==away: a_pts.append(pt);a_o.append(o['price'])
    return _avg(h_pts),_avg(h_o),_avg(a_pts),_avg(a_o)

def game_dt(game):
    try: return datetime.fromisoformat(game.get('commence_time','').replace('Z','+00:00'))
    except: return None

def game_time(game):
    dt=game_dt(game)
    if not dt: return "?"
    return (dt-timedelta(hours=6)).strftime('%H:%M')

# ─── Prediction card HTML ────────────────────────────────────────────────────────
def bar_color(p):
    if p>=65: return '#22c55e'
    if p>=45: return '#f59e0b'
    return '#ef4444'

def pred_card(label,prob,odds,wide=False):
    bc=bar_color(prob)
    w='100%' if wide else 'calc(50% - 4px)'
    return f"""
<div style="background:#12122a;border-radius:12px;padding:14px 14px 12px;
     width:{w};box-sizing:border-box;display:inline-block;vertical-align:top;margin-bottom:8px;">
  <div style="font-size:.8rem;color:#94a3b8;margin-bottom:8px;">{label}</div>
  <div style="display:flex;justify-content:space-between;align-items:baseline;">
    <span style="font-size:1.45rem;font-weight:900;color:#e2e8f0;">{prob:.0f}%</span>
    <span style="font-size:1.1rem;font-weight:700;color:#a78bfa;">{odds:.2f}</span>
  </div>
  <div style="height:5px;background:#1e1e3a;border-radius:3px;margin-top:10px;overflow:hidden;">
    <div style="height:100%;width:{prob:.0f}%;background:{bc};border-radius:3px;"></div>
  </div>
</div>"""

def section_box(title,content_html):
    return f"""
<div style="background:#0f0f26;border:1px solid rgba(255,255,255,.06);border-radius:14px;
     padding:16px;margin-bottom:10px;">
  <div style="font-size:.7rem;color:#475569;text-transform:uppercase;letter-spacing:1px;
       font-weight:700;margin-bottom:12px;">{title}</div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;">{content_html}</div>
</div>"""

LEGEND = """
<div style="display:flex;gap:18px;flex-wrap:wrap;justify-content:center;
     padding:10px 0;font-size:.72rem;color:#475569;">
  <span>🟢 Alta confianza ≥65%</span>
  <span>🟡 Media 45-65%</span>
  <span>🔴 Baja / arriesgada &lt;45%</span>
</div>"""

# ─── Global header ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(90deg,#1a0a3c,#0d0d26);padding:14px 20px;
     margin:-0.5rem -1rem 1rem;border-bottom:1px solid rgba(124,58,237,.3);
     display:flex;align-items:center;justify-content:space-between;">
  <div style="display:flex;align-items:center;gap:10px;">
    <span style="font-size:1.4rem;">⚽</span>
    <span style="font-weight:900;font-size:1.15rem;color:#fff;letter-spacing:2px;">
      SCOUT<span style="color:#7c3aed;">AI</span>
      <span style="font-size:.65rem;color:#475569;font-weight:400;margin-left:4px;">Pro</span>
    </span>
  </div>
  <div style="background:rgba(124,58,237,.2);border:1px solid rgba(124,58,237,.4);
       border-radius:20px;padding:5px 12px;font-size:.8rem;color:#a78bfa;font-weight:600;">
    💼 ${capital:.2f}
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Main tabs ───────────────────────────────────────────────────────────────────
t1,t2,t3,t4 = st.tabs(["🏠 Partidos","🎯 Con Valor","📝 Registrar","📊 Contabilidad"])

# ═══════════════════════════ TAB 1 — PARTIDOS ════════════════════════════════════
with t1:

    # ── DETAIL VIEW ──────────────────────────────────────────────────────────────
    if st.session_state.view=='detail' and st.session_state.sel_game:
        game = st.session_state.sel_game
        cfg  = st.session_state.sel_cfg or {}
        home, away = game['home_team'], game['away_team']
        is_soccer  = cfg.get('soccer',True)
        league_nm  = st.session_state.sel_league
        sport_k    = cfg.get('sport','soccer')
        league_k   = cfg.get('league','')

        if st.button("‹  Volver"):
            st.session_state.view='home'; st.rerun()

        # Header
        fh,fa = flag(home), flag(away)
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#1e1040,#0d0d26);border-radius:16px;
     padding:20px 16px;text-align:center;margin-bottom:12px;">
  <div style="font-size:.78rem;color:#7c3aed;font-weight:600;margin-bottom:12px;">
    {league_nm} · {game_time(game)}
  </div>
  <div style="display:flex;align-items:center;justify-content:center;gap:16px;">
    <div style="flex:1;text-align:right;">
      <div style="font-size:2rem;margin-bottom:4px;">{fh}</div>
      <div style="font-weight:700;color:#fff;font-size:.95rem;">{home}</div>
    </div>
    <div style="background:rgba(255,255,255,.08);border:2px solid rgba(124,58,237,.5);
         border-radius:12px;padding:10px 18px;min-width:80px;text-align:center;">
      <div style="font-size:1.25rem;font-weight:900;color:#fff;">vs</div>
      <div style="font-size:.65rem;color:#475569;margin-top:2px;">Próximo</div>
    </div>
    <div style="flex:1;text-align:left;">
      <div style="font-size:2rem;margin-bottom:4px;">{fa}</div>
      <div style="font-weight:700;color:#fff;font-size:.95rem;">{away}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        d1,d2,d3,d4 = st.tabs(["⚡ Predicción","📊 Situación","📋 Datos","📰 Noticias"])

        # Parse markets once
        avg_h,avg_a,avg_d = parse_h2h(game,home,away)
        totals = parse_all_totals(game)
        h_pt,h_sp,a_pt,a_sp = parse_spreads(game,home,away)

        # Compute probs
        p_h=p_a=p_d=50.0
        lh=la=1.3
        if avg_h and avg_a:
            if is_soccer and avg_d:
                p_h,p_d,p_a = rm(avg_h,avg_d,avg_a)
            else:
                p_h,p_a = rm(avg_h,avg_a); p_d=0.0

            # Expected goals
            if totals:
                line_val = list(totals.keys())[0]
                o_odds,u_odds = list(totals.values())[0]
                p_over,_ = rm(o_odds,u_odds)
                lam_total = estimate_xg(line_val,p_over/100)
                lh,la = split_xg(lam_total,p_h,p_a)
            else:
                lam_total=2.5; lh,la=split_xg(lam_total,p_h,p_a)

        # ─── PREDICCIÓN ────────────────────────────────────────────────────────
        with d1:
            if avg_h and avg_a:
                html=""

                # Resultado
                if is_soccer and avg_d:
                    html+=section_box("RESULTADO DEL PARTIDO",
                        pred_card(f"{fh} {home}",p_h,avg_h)+
                        pred_card("Empate",p_d,avg_d)+
                        pred_card(f"{fa} {away}",p_a,avg_a))
                else:
                    html+=section_box("RESULTADO",
                        pred_card(f"{fh} {home}",p_h,avg_h)+
                        pred_card(f"{fa} {away}",p_a,avg_a))

                # Total de goles/puntos
                if totals:
                    total_lbl=cfg.get('total','Goles').upper()
                    cards=""
                    for pt,(oo,uo) in totals.items():
                        po,pu=rm(oo,uo)
                        cards+=pred_card(f"Más de {pt} {cfg.get('total','goles').lower()}",po,oo)
                        cards+=pred_card(f"Menos de {pt} {cfg.get('total','goles').lower()}",pu,uo)
                    html+=section_box(f"TOTAL DE {total_lbl}",cards)

                # BTTS (soccer only)
                if is_soccer:
                    p_btts=btts(lh,la)*100
                    p_no_btts=100-p_btts
                    o_btts=max(1.01,100/max(p_btts,1))
                    o_no_btts=max(1.01,100/max(p_no_btts,1))
                    html+=section_box("AMBOS EQUIPOS MARCAN",
                        pred_card("Ambos marcan: Sí",p_btts,o_btts)+
                        pred_card("Ambos marcan: No",p_no_btts,o_no_btts))

                    # Portería a cero
                    p_cs_h=exp(-la)*100; p_cs_a=exp(-lh)*100
                    o_cs_h=max(1.01,100/max(p_cs_h,1)); o_cs_a=max(1.01,100/max(p_cs_a,1))
                    html+=section_box("PORTERÍA A CERO",
                        pred_card(f"{home} no recibe",p_cs_h,o_cs_h)+
                        pred_card(f"{away} no recibe",p_cs_a,o_cs_a))

                # Hándicap
                if h_pt is not None and h_sp and a_sp:
                    phs,pas=rm(h_sp,a_sp)
                    hs=f"+{h_pt:.1f}" if h_pt>0 else f"{h_pt:.1f}"
                    as_=( f"+{a_pt:.1f}" if a_pt>0 else f"{a_pt:.1f}") if a_pt is not None else "—"
                    html+=section_box("HÁNDICAP",
                        pred_card(f"{home} {hs}",phs,h_sp)+
                        pred_card(f"{away} {as_}",pas,a_sp))

                html+=LEGEND
                st.markdown(html, unsafe_allow_html=True)

                # Apuesta sugerida
                best_p=max(p_h,p_a)
                best_lbl=home if p_h>=p_a else away
                best_o=(avg_h if p_h>=p_a else avg_a) or 1.5
                k=kelly(best_p,best_o); monto=(capital*k)/4
                st.markdown("---")
                st.markdown("**💰 Apuesta sugerida (Kelly/4)**")
                if monto>=0.50:
                    c1,c2,c3=st.columns(3)
                    c1.metric("Favorito",best_lbl)
                    c2.metric("Prob IA",f"{best_p:.1f}%")
                    c3.metric("Apostar",f"${monto:.2f}",delta=f"G: ${monto*best_o-monto:.2f}")
                else:
                    st.info("⚠️ Sin ventaja Kelly suficiente.")

                # Quick register
                st.markdown("---")
                st.markdown("**☑️ REGISTRAR RESULTADO**")
                rc1,rc2=st.columns(2)
                with rc1:
                    if st.button("✅  Ganó",use_container_width=True):
                        st.session_state.quick_reg={'game':f"{home} vs {away}",'result':'ganado',
                            'league':league_nm,'prob':best_p,'team':best_lbl,'odds':best_o,'monto':monto}
                with rc2:
                    if st.button("❌  Perdió",use_container_width=True):
                        st.session_state.quick_reg={'game':f"{home} vs {away}",'result':'perdido',
                            'league':league_nm,'prob':best_p,'team':best_lbl,'odds':best_o,'monto':monto}

                if st.session_state.quick_reg:
                    qr=st.session_state.quick_reg
                    with st.form("qform",clear_on_submit=True):
                        st.markdown(f"**{qr['game']}** — {qr['result'].upper()}")
                        qa=st.number_input("Monto apostado ($)",value=float(max(qr['monto'],1.0)),min_value=0.01,step=0.5,format="%.2f")
                        qo=st.number_input("Cuota",value=float(qr['odds']),min_value=1.01,step=0.01,format="%.2f")
                        if st.form_submit_button("💾 Confirmar"):
                            gan=round(qa*qo-qa,2) if qr['result']=='ganado' else -round(qa,2)
                            historial.append({'id':str(uuid.uuid4()),
                                'fecha':datetime.now().strftime('%Y-%m-%d %H:%M'),
                                'deporte':league_nm,'partido':qr['game'],'apuesta':qr['team'],
                                'cuota':qo,'monto':qa,'prob_ia':qr['prob'],
                                'resultado':qr['result'],'ganancia':gan,'foto':None,'notas':''})
                            save_hist(historial)
                            st.session_state.quick_reg=None
                            st.success(f"{'🟢' if qr['result']=='ganado' else '🔴'} Guardado | P&L: ${gan:+.2f}")
                            st.rerun()
            else:
                st.warning("Sin datos de odds disponibles para este partido.")

        # ─── SITUACIÓN ───────────────────────────────────────────────────────────
        with d2:
            st.markdown(f"""
<div style="background:#0f0f26;border-radius:14px;padding:16px;margin-bottom:10px;">
  <div style="font-size:.7rem;color:#475569;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:12px;">GOLES ESPERADOS</div>
  <div style="display:flex;gap:8px;">
    <div style="flex:1;background:#12122a;border-radius:10px;padding:16px;text-align:center;">
      <div style="font-size:2.2rem;font-weight:900;color:#7c3aed;">{lh:.2f}</div>
      <div style="font-size:.75rem;color:#64748b;margin-top:4px;">{home}</div>
    </div>
    <div style="display:flex;align-items:center;color:#475569;font-size:.8rem;padding:0 6px;">vs</div>
    <div style="flex:1;background:#12122a;border-radius:10px;padding:16px;text-align:center;">
      <div style="font-size:2.2rem;font-weight:900;color:#7c3aed;">{la:.2f}</div>
      <div style="font-size:.75rem;color:#64748b;margin-top:4px;">{away}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
            st.caption("*Goles esperados estimados a partir de las cuotas del mercado (modelo Poisson).*")

        # ─── DATOS ───────────────────────────────────────────────────────────────
        with d3:
            # Marcadores más probables — build rows separately (Python 3.11 no nested triple f-strings)
            scores = probable_scores(lh,la)
            score_rows = ''.join(
                f'<div style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04);">'
                f'<span style="font-size:1rem;font-weight:700;color:#a78bfa;width:40px;">{s}</span>'
                f'<span style="font-size:.8rem;color:#64748b;width:36px;">{p*100:.0f}%</span>'
                f'<span style="font-size:.85rem;color:#94a3b8;flex:1;text-align:right;">{max(1.01,1/max(p,0.001)):.2f}</span>'
                f'</div>'
                for s,p in scores
            )
            st.markdown(f"""
<div style="background:#0f0f26;border-radius:14px;padding:16px;margin-bottom:10px;">
  <div style="font-size:.7rem;color:#475569;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:12px;">MARCADORES MÁS PROBABLES</div>
  {score_rows}
</div>
""", unsafe_allow_html=True)

            # Notas del análisis
            fav_lbl = home if p_h>=p_a else away
            btts_note = f'• <b>Ambos anotan:</b> {btts(lh,la)*100:.0f}% de probabilidad<br>' if is_soccer else ''
            margin_pct = f'{((1/avg_h+1/avg_a+(1/avg_d if avg_d else 0))-1)*100:.1f}' if (avg_h and avg_a) else '?'
            st.markdown(f"""
<div style="background:#0f0f26;border-radius:14px;padding:16px;margin-bottom:10px;">
  <div style="font-size:.7rem;color:#475569;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:10px;">NOTAS DEL ANÁLISIS</div>
  <div style="font-size:.82rem;color:#94a3b8;line-height:1.7;">
    • <b>Favorito estadístico:</b> {fav_lbl} ({max(p_h,p_a):.1f}%)<br>
    • <b>Goles esperados:</b> {home}: {lh:.2f} | {away}: {la:.2f}<br>
    {btts_note}
    • <b>Total esperado:</b> {lh+la:.2f} goles<br>
    • <b>Nota:</b> Las cuotas mostradas son promedio de todas las casas. Las probabilidades son calculadas eliminando el margen del bookmaker (+{margin_pct}%).
  </div>
</div>
""", unsafe_allow_html=True)

            # NBA players
            if cfg.get('players') and sport_k:
                espn_t=fetch_espn_teams(sport_k,league_k)
                if espn_t:
                    st.markdown("#### ⭐ Jugadores clave")
                    for team in [home,away]:
                        tid=match_team(team,espn_t)
                        if not tid: continue
                        pl,_=fetch_roster(sport_k,league_k,tid)
                        st.markdown(f"**{team}**")
                        rows=[]
                        for p in pl[:5]:
                            s=fetch_nba_stats(p['id'])
                            rows.append({'Jugador':p['name'],'Pos':p['pos'],
                                'PTS':fmt_s(s.get('PTS') or s.get('PPG')),
                                'REB':fmt_s(s.get('REB') or s.get('RPG')),
                                'AST':fmt_s(s.get('AST') or s.get('APG')),
                                '3PM':fmt_s(s.get('3PM') or s.get('FG3M'))})
                        if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

        # ─── NOTICIAS ─────────────────────────────────────────────────────────
        with d4:
            news=fetch_news(sport_k,league_k,home)
            if news:
                for art in news:
                    hl=art.get('headline','Sin título')
                    desc=art.get('description','') or art.get('story','')[:120] if art.get('story') else ''
                    date_str=art.get('published','')[:10] if art.get('published') else ''
                    img_url=art.get('images',[{}])[0].get('url','') if art.get('images') else ''
                    st.markdown(f"""
<div style="background:#0f0f26;border-radius:12px;padding:14px;margin-bottom:8px;
     display:flex;gap:12px;align-items:flex-start;">
  {'<img src="'+img_url+'" style="width:80px;height:60px;border-radius:8px;object-fit:cover;flex-shrink:0;">' if img_url else '<div style="width:80px;height:60px;background:#1a1a3a;border-radius:8px;flex-shrink:0;"></div>'}
  <div>
    <div style="font-size:.85rem;font-weight:600;color:#e2e8f0;margin-bottom:4px;">{hl}</div>
    {'<div style="font-size:.75rem;color:#64748b;">'+desc[:100]+'...</div>' if desc else ''}
    <div style="font-size:.7rem;color:#475569;margin-top:4px;">{date_str}</div>
  </div>
</div>
""", unsafe_allow_html=True)
            else:
                st.info("Sin noticias disponibles para este partido.")

    # ── HOME VIEW ─────────────────────────────────────────────────────────────────
    else:
        # League selector + mode pills
        league_name = st.selectbox("",list(LEAGUES.keys()),label_visibility='collapsed')
        cfg_sel = LEAGUES[league_name]

        st.radio("",["⚡ Súper rápido","⚡ Rápido","🔍 Analizado","🧠 Profundo"],
                 horizontal=True,label_visibility='collapsed',index=0)

        # Date selector
        today=datetime.now(timezone.utc).date()
        date_opts=[today+timedelta(days=i) for i in range(7)]
        date_lbls=[("HOY" if d==today else ("MAÑANA" if d==today+timedelta(1) else d.strftime("%a %d").upper())) for d in date_opts]
        sel_lbl=st.radio("",date_lbls,horizontal=True,label_visibility='collapsed')
        sel_date=date_opts[date_lbls.index(sel_lbl)]

        if st.button("Ver partidos de hoy →",use_container_width=True):
            pass  # just triggers a re-render

        # Fetch games
        with st.spinner("Cargando partidos..."):
            raw=fetch_odds(cfg_sel['key'])
            games=[g for g in raw if (lambda d: d and d.date()==sel_date)(game_dt(g))]

        if not games:
            st.markdown("""
<div style="text-align:center;padding:50px 20px;color:#475569;">
  <div style="font-size:3rem;margin-bottom:10px;">📭</div>
  <div style="font-size:.9rem;">Sin partidos para esta fecha.</div>
  <div style="font-size:.75rem;margin-top:4px;">Prueba otra fecha u otra liga.</div>
</div>""", unsafe_allow_html=True)
        else:
            for game in games:
                home,away=game['home_team'],game['away_team']
                fh,fa=flag(home),flag(away)
                t_str=game_time(game)
                avg_h,avg_a,avg_d=parse_h2h(game,home,away)
                if avg_h and avg_a:
                    probs=rm(avg_h,avg_d,avg_a) if (avg_d and cfg_sel.get('soccer')) else rm(avg_h,avg_a)
                    best=max(probs); bc=bar_color(best)
                else:
                    best=50; bc='#475569'

                n_bk=len(game.get('bookmakers',[]))
                uid=game.get('id',str(uuid.uuid4()))[:8]

                c1,c2=st.columns([5,1])
                with c1:
                    st.markdown(f"""
<div style="background:#0f0f26;border:1px solid rgba(255,255,255,.06);border-radius:14px;
     padding:14px 16px;margin-bottom:6px;">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <div style="flex:1;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
        <span style="font-size:1.3rem;">{fh}</span>
        <span style="font-size:.92rem;font-weight:600;color:#e2e8f0;">{home}</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="font-size:1.3rem;">{fa}</span>
        <span style="font-size:.92rem;color:#94a3b8;">{away}</span>
      </div>
    </div>
    <div style="text-align:right;min-width:70px;">
      <div style="font-size:.75rem;color:#7c3aed;font-weight:600;">⏰ {t_str}</div>
      <div style="font-size:.72rem;color:#475569;margin-top:2px;">{n_bk} casas</div>
      <div style="height:4px;background:#1e1e3a;border-radius:2px;margin-top:6px;overflow:hidden;">
        <div style="height:100%;width:{best:.0f}%;background:{bc};border-radius:2px;"></div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
                with c2:
                    if st.button("›",key=f"g_{uid}",use_container_width=True):
                        st.session_state.view='detail'
                        st.session_state.sel_game=game
                        st.session_state.sel_cfg=cfg_sel
                        st.session_state.sel_league=league_name
                        st.rerun()

            st.caption(f"📋 {len(games)} partido(s) · {sel_lbl}")

# ═══════════════════════════ TAB 2 — CON VALOR ═══════════════════════════════════
with t2:
    st.markdown("### 🎯 Apuestas con Valor Positivo")
    st.caption("EV > 1.04 · Probabilidad 38-78% · Todas las ligas")
    if st.button("🔍 Escanear ahora",use_container_width=True):
        with st.spinner("Escaneando todas las ligas..."):
            rows=[]
            for lname,cfg in LEAGUES.items():
                gs=fetch_odds(cfg['key'])
                for g in gs:
                    h2,a2=g['home_team'],g['away_team']
                    hl,al=[],[]
                    for bk in g.get('bookmakers',[]):
                        for mkt in bk.get('markets',[]):
                            if mkt['key']!='h2h': continue
                            for o in mkt.get('outcomes',[]):
                                if o['name']==h2: hl.append(o['price'])
                                elif o['name']==a2: al.append(o['price'])
                    if len(hl)<3 or len(al)<3: continue
                    mh,ma=_med(hl),_med(al)
                    bh,ba=max(hl),max(al)
                    ph,pa=rm(mh,ma)
                    for team,tp,bo in [(h2,ph/100,bh),(a2,pa/100,ba)]:
                        ev=bo*tp
                        if ev>1.04 and 0.38<=tp<=0.78:
                            k_=kelly(tp*100,bo); m_=(capital*k_)/4
                            rows.append({'Liga':lname,'Partido':f'{a2} @ {h2}','Apostar a':team,
                                'Cuota':f'{bo:.2f}','Prob IA':f'{tp*100:.1f}%',
                                'EV':round(ev,4),'Ventaja':f'+{(ev-1)*100:.1f}%',
                                'Sugerido':f'${m_:.2f}' if m_>=0.50 else '<$0.50'})
        rows=sorted(rows,key=lambda x:x['EV'],reverse=True)
        if rows:
            st.dataframe(pd.DataFrame(rows).style.background_gradient(subset=['EV'],cmap='Purples'),
                         use_container_width=True,hide_index=True)
            st.caption(f"✅ {len(rows)} apuesta(s) encontradas")
        else:
            st.info("Sin apuestas con valor en este momento.")

# ═══════════════════════════ TAB 3 — REGISTRAR ═══════════════════════════════════
with t3:
    st.markdown("### 📝 Registrar resultado")
    with st.form("regform",clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1:
            fp=st.text_input("Partido *",placeholder="USA vs Paraguay")
            fd=st.selectbox("Liga *",list(LEAGUES.keys()))
            fa_=st.text_input("Apostaste a *",placeholder="USA")
            fc=st.number_input("Cuota *",min_value=1.01,value=1.85,step=0.01,format="%.2f")
        with c2:
            fm=st.number_input("Monto ($) *",min_value=0.01,value=5.0,step=0.5,format="%.2f")
            fpr=st.number_input("Prob IA (%)",min_value=1.0,max_value=99.0,value=55.0,step=0.5)
            fr=st.radio("Resultado *",["ganado","perdido","pendiente"],horizontal=True)
            ff=st.file_uploader("📸 Comprobante",type=["jpg","jpeg","png","webp"])
        fn=st.text_area("Notas",height=50)
        if st.form_submit_button("💾 Guardar",use_container_width=True):
            fpath=None
            if ff:
                ext=ff.name.rsplit('.',1)[-1]; fname=f"{uuid.uuid4().hex}.{ext}"
                fpath=os.path.join(FOTOS_DIR,fname)
                with open(fpath,'wb') as fp2: fp2.write(ff.read())
            g_=round(fm*fc-fm,2) if fr=='ganado' else (-round(fm,2) if fr=='perdido' else 0.0)
            historial.append({'id':str(uuid.uuid4()),'fecha':datetime.now().strftime('%Y-%m-%d %H:%M'),
                'deporte':fd,'partido':fp,'apuesta':fa_,'cuota':fc,'monto':fm,
                'prob_ia':fpr,'resultado':fr,'ganancia':g_,'foto':fpath,'notas':fn})
            save_hist(historial)
            ic="🟢" if fr=="ganado" else "🔴" if fr=="perdido" else "🟡"
            st.success(f"{ic} Guardado | P&L: ${g_:+.2f}")
            st.rerun()

    if historial:
        st.markdown("---")
        for b in reversed(historial[-5:]):
            r=b.get('resultado','pendiente'); ic="🟢" if r=="ganado" else "🔴" if r=="perdido" else "🟡"
            with st.expander(f"{ic} {b['fecha'][:10]} — {b.get('partido','')} | ${b.get('ganancia',0):+.2f}"):
                cc1,cc2=st.columns([1,2])
                with cc1:
                    fp2=b.get('foto')
                    if fp2 and os.path.exists(fp2): st.image(fp2,use_container_width=True)
                    else: st.info("Sin foto")
                with cc2:
                    st.markdown(f"""**{b.get('partido','')}** · {b.get('deporte','')}
**Aposté a:** {b.get('apuesta','')} @ {b.get('cuota',0):.2f}
**Monto:** ${b.get('monto',0):.2f} · **Prob IA:** {b.get('prob_ia',0):.1f}%
**Resultado:** {r.upper()} {ic} · **P&L:** ${b.get('ganancia',0):+.2f}""")

# ═══════════════════════════ TAB 4 — CONTABILIDAD ═════════════════════════════════
with t4:
    st.markdown("### 📊 Contabilidad & Rentabilidad")
    closed=[b for b in historial if b.get('resultado') in ('ganado','perdido')]
    if not closed:
        st.info("📭 Sin apuestas cerradas. Registra resultados para ver estadísticas.")
    else:
        total=len(closed); won=sum(1 for b in closed if b['resultado']=='ganado')
        wag=sum(b.get('monto',0) for b in closed)
        ret=sum(b.get('monto',0)*b.get('cuota',1) for b in closed if b['resultado']=='ganado')
        prof=ret-wag; roi=prof/wag*100 if wag else 0

        k1,k2,k3,k4,k5=st.columns(5)
        k1.metric("Apuestas",total); k2.metric("✅",won); k3.metric("❌",total-won)
        k4.metric("Win Rate",f"{won/total*100:.1f}%"); k5.metric("ROI",f"{roi:+.1f}%",delta=f"${prof:+.2f}")
        st.caption(f"Apostado: ${wag:.2f} · Retornado: ${ret:.2f} · Profit: ${prof:+.2f}")
        st.divider()

        if len(closed)>=2:
            st.markdown("#### 📈 Evolución del Capital")
            run=st.session_state.saldo; evo=[]
            for b in closed:
                run+=b.get('ganancia',0); evo.append({'Fecha':b['fecha'][:10],'Capital':round(run,2)})
            st.line_chart(pd.DataFrame(evo).set_index('Fecha'))

        st.markdown("#### 🏆 Por Liga")
        sm={}
        for b in closed:
            d=b.get('deporte','Otro')
            if d not in sm: sm[d]={'won':0,'total':0,'profit':0.0}
            sm[d]['total']+=1; sm[d]['profit']+=b.get('ganancia',0)
            if b['resultado']=='ganado': sm[d]['won']+=1
        if sm:
            st.dataframe(pd.DataFrame([{'Liga':d,'Apuestas':v['total'],'Ganadas':v['won'],
                'Win%':f"{v['won']/v['total']*100:.0f}%",'Profit':f"${v['profit']:+.2f}"}
                for d,v in sm.items()]),use_container_width=True,hide_index=True)

        st.markdown("#### 🧠 Calibración IA")
        cal={}
        for b in closed:
            p=b.get('prob_ia',0); bk=f"{int(p//10)*10}-{int(p//10)*10+10}%"
            if bk not in cal: cal[bk]={'won':0,'total':0}
            cal[bk]['total']+=1
            if b['resultado']=='ganado': cal[bk]['won']+=1
        if cal:
            rows=[{'Rango':bk,'Apuestas':d['total'],'Ganadas':d['won'],
                   'Precisión':f"{d['won']/d['total']*100:.0f}%"} for bk,d in sorted(cal.items())]
            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

        st.markdown("#### 📋 Historial")
        hrows=[{'Fecha':b['fecha'][:10],'Liga':b.get('deporte',''),'Partido':b.get('partido',''),
                'Apuesta':b.get('apuesta',''),'Cuota':b.get('cuota',0),'Monto':f"${b.get('monto',0):.2f}",
                'Prob IA':f"{b.get('prob_ia',0):.1f}%",'Result.':b.get('resultado','').upper(),
                'P&L':f"${b.get('ganancia',0):+.2f}"} for b in reversed(historial)]
        if hrows: st.dataframe(pd.DataFrame(hrows),use_container_width=True,hide_index=True)
        if st.button("🗑 Borrar historial",type="secondary"): save_hist([]); st.rerun()

    st.divider()
    new_s=st.number_input("Capital inicial ($):",value=float(st.session_state.saldo),min_value=1.0,step=5.0)
    if abs(new_s-st.session_state.saldo)>0.001: st.session_state.saldo=new_s; st.rerun()
