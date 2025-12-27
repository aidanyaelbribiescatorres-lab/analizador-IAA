import streamlit as st
import pandas as pd
import requests

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="IA Financiera Yael", page_icon="💰", layout="centered")

# Inicializar saldo en la "memoria" de la app (Session State)
if 'saldo' not in st.session_state:
    st.session_state.saldo = 24.27  # Tu saldo inicial real

API_KEY = '8d90dd7eb80726fb3a98683ee7d2e734'

# --- BARRA LATERAL (BILLETERA) ---
st.sidebar.title("💼 Tu Cartera")
st.sidebar.markdown(f"""
    <div style="padding:15px; background-color:#2e2e2e; border-radius:10px; text-align:center;">
        <h2 style="color:#00ff00; margin:0;">${st.session_state.saldo:.2f}</h2>
        <p style="color:white; margin:0;">Capital Disponible</p>
    </div>
    """, unsafe_allow_html=True)

if st.sidebar.button("🔄 Reiniciar Saldo"):
    st.session_state.saldo = 24.27

st.sidebar.divider()
deporte = st.sidebar.selectbox("Selecciona Liga:", [
    ('🏀 NBA', 'basketball_nba'),
    ('🏈 NFL', 'americanfootball_nfl'),
    ('⚽ Liga MX', 'soccer_mexico_ligamx'),
    ('⚽ Premier League', 'soccer_epl')
], format_func=lambda x: x[0])

# --- CEREBRO FINANCIERO (KELLY CRITERION) ---
def calcular_inversion(prob_real, cuota, saldo):
    b = cuota - 1
    p = prob_real / 100
    q = 1 - p
    if b == 0: return 0
    kelly_pct = (b * p - q) / b
    if kelly_pct <= 0: return 0
    apuesta_segura = (saldo * kelly_pct) / 4
    return round(apuesta_segura, 2)

# --- INTERFAZ PRINCIPAL ---
st.title("🤖 Asesor de Rendimiento")
st.info("Selecciona un partido para calcular cuánto dinero puedes ganar.")

url = f'https://api.the-odds-api.com/v4/sports/{deporte[1]}/odds/?apiKey={API_KEY}&regions=us&markets=h2h&oddsFormat=decimal'

try:
    res = requests.get(url)
    data = res.json()
    partidos_dict = {f"{g['home_team']} vs {g['away_team']}": g for g in data}
    juego = st.selectbox("📅 Próximos Eventos:", list(partidos_dict.keys()))

    if st.button("📊 CALCULAR RENDIMIENTO"):
        datos = partidos_dict[juego]
        bookies = datos['bookmakers']
        if bookies:
            odds = bookies[0]['markets'][0]['outcomes']
            local = datos['home_team']
            visita = datos['away_team']
            c_local = next((x['price'] for x in odds if x['name'] == local), 1.0)
            c_visita = next((x['price'] for x in odds if x['name'] == visita), 1.0)
            
            imp_l = 1/c_local
            imp_v = 1/c_visita
            margen = imp_l + imp_v
            p_real_local = (imp_l / margen) * 100
            p_real_visita = (imp_v / margen) * 100
            
            if p_real_local > p_real_visita:
                ganador = local
                prob = p_real_local
                cuota = c_local
            else:
                ganador = visita
                prob = p_real_visita
                cuota = c_visita
            
            monto_sugerido = calcular_inversion(prob, cuota, st.session_state.saldo)
            ganancia_neta = (monto_sugerido * cuota) - monto_sugerido
            roi = ((cuota - 1) * 100)
            
            with st.chat_message("assistant"):
                st.write(f"Según mis cálculos, la mejor opción financiera es **{ganador}** ({round(prob,1)}% prob).")
                if monto_sugerido > 0:
                    st.success("✅ OPORTUNIDAD DE INVERSIÓN DETECTADA")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("💵 Apostar", f"${monto_sugerido}")
                    col2.metric("📈 Ganancia", f"${round(ganancia_neta, 2)}")
                    col3.metric("🚀 ROI", f"{round(roi, 1)}%")
                    if st.button(f"🎉 ¡Simular que {ganador} ganó!"):
                        st.session_state.saldo += ganancia_neta
                        st.rerun()
                else:
                    st.warning(f"📉 Rendimiento negativo. No apostar.")
        else:
            st.error("No hay cuotas disponibles.")
except:
    st.write("Conectando con el mercado...")
