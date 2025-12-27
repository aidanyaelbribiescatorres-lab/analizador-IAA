import streamlit as st
import pandas as pd
import requests

# --- CONFIGURACIÓN DE PÁGINA (MODO WIDE) ---
st.set_page_config(page_title="NEON BET AI", page_icon="🟢", layout="wide")

# --- ESTILOS CSS "HACKER MODE" (PARA QUE NO SE VEA PEDORRA) ---
st.markdown("""
    <style>
    /* Fondo Negro Total */
    .stApp {
        background-color: #050505;
        color: #00FF00;
    }
    
    /* Ocultar menú de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Estilo de Tarjetas */
    div.css-1r6slb0, div.stMetric {
        background-color: #111111;
        border: 1px solid #333;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 0 10px rgba(0, 255, 0, 0.1);
    }
    
    /* Títulos Neón */
    h1, h2, h3 {
        color: #00FF41 !important;
        font-family: 'Courier New', Courier, monospace;
        text-shadow: 0 0 5px #00FF41;
    }
    
    /* Botones Estilo Cyberpunk */
    .stButton>button {
        background-color: #000;
        color: #00FF41;
        border: 1px solid #00FF41;
        border-radius: 5px;
        width: 100%;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #00FF41;
        color: #000;
        box-shadow: 0 0 15px #00FF41;
    }
    
    /* Chat Input */
    .stTextInput>div>div>input {
        background-color: #111;
        color: #00FF41;
        border: 1px solid #333;
    }
    </style>
""", unsafe_allow_html=True)

# --- MEMORIA Y API ---
if 'saldo' not in st.session_state:
    st.session_state.saldo = 24.27 
if "messages" not in st.session_state:
    st.session_state.messages = []

API_KEY = '8d90dd7eb80726fb3a98683ee7d2e734'

# --- HEADER (BILLETERA) ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🧠 NEON BET AI")
    st.caption("SYSTEM ONLINE // READY TO ANALYZE")
with col2:
    st.metric(label="CAPITAL DISPONIBLE", value=f"${st.session_state.saldo}", delta="READY")

st.divider()

# --- BARRA LATERAL (CONFIG) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2103/2103633.png", width=100)
    st.markdown("### ⚙️ SYSTEM CONFIG")
    deporte = st.selectbox("TARGET LEAGUE:", [
        ('🏀 NBA', 'basketball_nba'),
        ('🏈 NFL', 'americanfootball_nfl'),
        ('⚾ MLB', 'baseball_mlb'),
        ('⚽ PREMIER LEAGUE', 'soccer_epl')
    ], format_func=lambda x: x[0])
    
    st.markdown("---")
    st.info("⚠️ PROTOCOLO: Escribe el nombre del equipo en el chat para escanear probabilidades.")

# --- LÓGICA DE INTELIGENCIA ---
def procesar_pregunta(prompt):
    url = f'https://api.the-odds-api.com/v4/sports/{deporte[1]}/odds/?apiKey={API_KEY}&regions=us&markets=h2h&oddsFormat=decimal'
    try:
        res = requests.get(url)
        data = res.json()
        
        # Buscar equipo
        prompt = prompt.lower()
        match = None
        for g in data:
            if g['home_team'].lower() in prompt or g['away_team'].lower() in prompt:
                match = g
                break
        
        if match:
            # Cálculos
            home, away = match['home_team'], match['away_team']
            bookies = match['bookmakers']
            if not bookies: return "❌ DATOS INSUFICIENTES."
            
            odds = bookies[0]['markets'][0]['outcomes']
            c_h = next((x['price'] for x in odds if x['name'] == home), 1.0)
            c_a = next((x['price'] for x in odds if x['name'] == away), 1.0)
            
            # Prob Real
            imp_h, imp_a = 1/c_h, 1/c_a
            margin = imp_h + imp_a
            p_h = (imp_h/margin)*100
            p_a = (imp_a/margin)*100
            
            fav = home if p_h > p_a else away
            prob = p_h if p_h > p_a else p_a
            cuota = c_h if p_h > p_a else c_a
            
            # Kelly Money
            b = cuota - 1
            p = prob/100
            q = 1 - p
            kelly = (b*p - q)/b
            monto = (st.session_state.saldo * kelly) / 4 if kelly > 0 else 0
            
            msg = f"""
            ### 📡 SCAN COMPLETE: {home} vs {away}
            
            **FAVORITO DETECTADO:** {fav.upper()}
            - 📊 Probabilidad IA: **{prob:.1f}%**
            - 🔢 Cuota Mercado: **{cuota}**
            
            ---
            **💰 PLAN FINANCIERO:**
            """
            if monto > 0:
                msg += f"🟢 **INVERSIÓN RECOMENDADA: ${monto:.2f}**\n"
                msg += f"🚀 Ganancia Potencial: ${(monto*cuota)-monto:.2f}"
            else:
                msg += "🔴 **NO APOSTAR (RIESGO ALTO)**"
            
            return msg
            
        else:
            return "🔍 Buscando en la base de datos... No encontré ese equipo hoy. Intenta otro."
            
    except Exception as e:
        return f"❌ ERROR DE SISTEMA: {e}"

# --- INTERFAZ DE CHAT TIPO WHATSAPP ---
# Contenedor para mensajes
chat_container = st.container()

# Input fijo abajo
prompt = st.chat_input("⌨️ ESCRIBE COMANDO (EJ: LAKERS)...")

with chat_container:
    # Mostrar historial
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Procesar nuevo mensaje
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("🔄 PROCESANDO ALGORITMO..."):
                response = procesar_pregunta(prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

