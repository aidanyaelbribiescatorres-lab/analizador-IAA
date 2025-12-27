import streamlit as st
import pandas as pd
import requests

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ChatIA Apuestas", page_icon="🤖", layout="centered")

# Memoria del dinero
if 'saldo' not in st.session_state:
    st.session_state.saldo = 24.27 

API_KEY = '8d90dd7eb80726fb3a98683ee7d2e734'

# --- BARRA LATERAL (TU CUENTA) ---
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

# --- PANTALLA DE CHAT ---
st.title("💬 Chat con IA Financiera")
st.caption("Selecciona un partido y presiona 'Enviar' para iniciar la conversación.")

# 1. Obtener partidos
url = f'https://api.the-odds-api.com/v4/sports/{deporte[1]}/odds/?apiKey={API_KEY}&regions=us&markets=h2h&oddsFormat=decimal'

try:
    res = requests.get(url)
    data = res.json()
    partidos_dict = {f"{g['home_team']} vs {g['away_team']}": g for g in data}
    
    # --- ZONA DE INTERACCIÓN ---
    # En lugar de escribir, seleccionas el tema para que la IA no se equivoque
    juego_seleccionado = st.selectbox("¿Sobre qué partido quieres preguntar?", list(partidos_dict.keys()))
    
    # Botón que simula el "Enviar" del chat
    if st.button("📩 ENVIAR PREGUNTA"):
        
        # 1. TU BURBUJA (Usuario)
        with st.chat_message("user"):
            st.write(f"Hola IA. Tengo ${st.session_state.saldo}. ¿Me conviene apostar en el juego **{juego_seleccionado}**? ¿Cuánto ganaría?")
        
        # 2. CÁLCULOS (Cerebro)
        datos = partidos_dict[juego_seleccionado]
        bookies = datos['bookmakers']
        
        if bookies:
            # Lógica matemática oculta
            odds = bookies[0]['markets'][0]['outcomes']
            local, visita = datos['home_team'], datos['away_team']
            c_local = next((x['price'] for x in odds if x['name'] == local), 1.0)
            c_visita = next((x['price'] for x in odds if x['name'] == visita), 1.0)
            
            # Probabilidad Real
            imp_l, imp_v = 1/c_local, 1/c_visita
            margen = imp_l + imp_v
            p_real_l = (imp_l / margen) * 100
            p_real_v = (imp_v / margen) * 100
            
            if p_real_l > p_real_v:
                pick, prob, cuota = local, p_real_l, c_local
            else:
                pick, prob, cuota = visita, p_real_v, c_visita
            
            # Kelly Criterion (Gestión de dinero)
            b = cuota - 1
            p = prob / 100
            q = 1 - p
            kelly = (b * p - q) / b if b > 0 else 0
            apuesta = (st.session_state.saldo * kelly) / 4 if kelly > 0 else 0
            ganancia = (apuesta * cuota) - apuesta
            
            # 3. BURBUJA DE LA IA (Respuesta)
            with st.chat_message("assistant"):
                st.write(f"Analizando **{local}** vs **{visita}**... 🧠")
                
                if apuesta > 0:
                    st.success(f"¡Sí! Detecto valor en **{pick}**.")
                    st.write(f"Mi modelo le da un **{round(prob,1)}%** de probabilidad de ganar.")
                    st.write("Aquí tienes mi plan financiero para ti:")
                    
                    # Tarjeta de datos
                    col1, col2 = st.columns(2)
                    col1.metric("💵 Debes apostar", f"${round(apuesta, 2)}")
                    col2.metric("📈 Tu Ganancia", f"${round(ganancia, 2)}")
                    
                    st.write(f"Si ganamos, tu saldo subirá a: **${round(st.session_state.saldo + ganancia, 2)}**")
                    
                    # Botón para simular victoria dentro del chat
                    if st.button("💰 ¡Simular que ganamos!"):
                        st.session_state.saldo += ganancia
                        st.rerun()
                else:
                    st.error(f"No te lo recomiendo. La cuota de {cuota} paga muy poco para el riesgo.")
                    st.write("Mejor guarda tu dinero para otro partido más seguro.")
        else:
            with st.chat_message("assistant"):
                st.write("Lo siento, las casas de apuestas aún no han publicado líneas para este juego.")

except:
    st.write("⏳ Conectando con el servidor de apuestas...")
