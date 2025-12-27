import streamlit as st
import pandas as pd
import requests

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ChatIA Apuestas", page_icon="🤖", layout="centered")

# Memoria del dinero
if 'saldo' not in st.session_state:
    st.session_state.saldo = 24.27 

API_KEY = '8d90dd7eb80726fb3a98683ee7d2e734'

# --- BARRA LATERAL ---
st.sidebar.title("💳 Mi Cuenta")
st.sidebar.markdown(f"""
    <div style="background-color:#1E1E1E; padding:15px; border-radius:10px; text-align:center; border: 1px solid #333;">
        <h3 style="color:#00FF00; margin:0;">${st.session_state.saldo:.2f}</h3>
        <p style="color:#888; margin:0; font-size:12px;">Saldo Actual</p>
    </div>
    """, unsafe_allow_html=True)

deporte = st.sidebar.selectbox("Liga:", [
    ('🏀 NBA', 'basketball_nba'),
    ('🏈 NFL', 'americanfootball_nfl'),
    ('⚽ Liga MX', 'soccer_mexico_ligamx'),
    ('⚽ Premier League', 'soccer_epl')
], format_func=lambda x: x[0])

# --- PANTALLA PRINCIPAL ---
st.title("💬 Chat con IA Financiera")
st.caption("Selecciona un partido y presiona 'ENVIAR PREGUNTA' para iniciar la conversación.")

# Obtener partidos
url = f'https://api.the-odds-api.com/v4/sports/{deporte[1]}/odds/?apiKey={API_KEY}&regions=us&markets=h2h&oddsFormat=decimal'

try:
    res = requests.get(url)
    data = res.json()
    partidos_dict = {f"{g['home_team']} vs {g['away_team']}": g for g in data}
    
    # Selector de pregunta
    juego_seleccionado = st.selectbox("¿Sobre qué partido quieres preguntar?", list(partidos_dict.keys()))
    
    # --- BOTÓN DE CHAT ---
    if st.button("📩 ENVIAR PREGUNTA"):
        
        # 1. TU BURBUJA
        with st.chat_message("user"):
            st.write(f"Hola IA. ¿Me conviene apostar en **{juego_seleccionado}**?")
        
        # 2. RESPUESTA DE LA IA
        datos = partidos_dict[juego_seleccionado]
        bookies = datos['bookmakers']
        
        if bookies:
            odds = bookies[0]['markets'][0]['outcomes']
            local, visita = datos['home_team'], datos['away_team']
            c_local = next((x['price'] for x in odds if x['name'] == local), 1.0)
            c_visita = next((x['price'] for x in odds if x['name'] == visita), 1.0)
            
            # Cálculo rápido
            imp_l, imp_v = 1/c_local, 1/c_visita
            margen = imp_l + imp_v
            p_real_l = (imp_l / margen) * 100
            p_real_v = (imp_v / margen) * 100
            
            if p_real_l > p_real_v:
                pick, prob, cuota = local, p_real_l, c_local
            else:
                pick, prob, cuota = visita, p_real_v, c_visita
                
            kelly = ((cuota - 1) * (prob/100) - (1 - (prob/100))) / (cuota - 1)
            apuesta = (st.session_state.saldo * kelly) / 4 if kelly > 0 else 0
            ganancia = (apuesta * cuota) - apuesta

            with st.chat_message("assistant"):
                st.write(f"Analizando **{local}** vs **{visita}**... 🧠")
                if apuesta > 0:
                    st.success(f"✅ SÍ. **{pick}** es favorito con {round(prob,1)}%.")
                    st.metric("Debes apostar:", f"${round(apuesta, 2)}")
                    st.write(f"Ganancia esperada: **${round(ganancia, 2)}**")
                else:
                    st.error("⛔ NO APOSTAR. Riesgo demasiado alto.")
        else:
            st.warning("No hay datos suficientes para este partido.")

except:
    st.info("Conectando con la base de datos...")
