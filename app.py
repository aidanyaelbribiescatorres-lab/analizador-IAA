import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Master Analyser", page_icon="🧠", layout="wide")

# --- TU CONFIGURACIÓN ---
API_KEY = '8d90dd7eb80726fb3a98683ee7d2e734'
SALDO_REAL = 24.27 

# --- BARRA LATERAL (CONTROLES) ---
st.sidebar.title("🎛️ Centro de Control")
st.sidebar.write(f"💰 Saldo: **${SALDO_REAL}**")

# 1. Selector de Deporte (Agregué más ligas)
deporte = st.sidebar.selectbox("1. Selecciona Deporte:", [
    ('🏀 NBA', 'basketball_nba'),
    ('🏈 NFL', 'americanfootball_nfl'),
    ('⚽ Liga MX', 'soccer_mexico_ligamx'),
    ('⚽ Premier League', 'soccer_epl'),
    ('⚽ La Liga (España)', 'soccer_spain_la_liga'),
    ('⚾ MLB (Béisbol)', 'baseball_mlb'),
    ('🏒 NHL (Hockey)', 'icehockey_nhl')
], format_func=lambda x: x[0])

# 2. Selector de Mercado (¡Aquí está lo que pediste!)
tipo_apuesta = st.sidebar.selectbox("2. ¿Qué buscamos?", [
    ('🏆 Ganador del Partido', 'h2h'),
    ('⚖️ Handicap (Ventaja)', 'spreads'),
    ('🔢 Totales (Alta/Baja)', 'totals'),
    # Nota: Props de jugadores consumen muchos datos, úsalos con cuidado
    # ('👤 Puntos de Jugador (NBA)', 'player_points') 
])

st.title(f"Analizando: {deporte[0]} - {tipo_apuesta[0]}")

# --- BOTÓN DE ACCIÓN ---
if st.button("🚀 ESCANEAR EL MERCADO COMPLETO"):
    # Construimos la URL dinámica según lo que elegiste
    mercado_api = tipo_apuesta[1]
    url = f'https://api.the-odds-api.com/v4/sports/{deporte[1]}/odds/?apiKey={API_KEY}&regions=us&markets={mercado_api}&oddsFormat=decimal'
    
    with st.spinner('Hackeando las líneas de las casas de apuestas...'):
        try:
            res = requests.get(url)
            if res.status_code != 200:
                st.error(f"Error de conexión. Código: {res.status_code}")
            else:
                data = res.json()
                st.success(f"✅ Se encontraron {len(data)} eventos disponibles.")
                
                # --- VISUALIZACIÓN DE TARJETAS ---
                for juego in data:
                    with st.expander(f"📅 {juego['home_team']} vs {juego['away_team']}"):
                        
                        # Buscamos las cuotas dentro de los datos
                        if not juego['bookmakers']:
                            st.write("⚠️ No hay cuotas abiertas aún.")
                            continue
                            
                        # Usamos la primera casa (generalmente DraftKings o FanDuel en la API)
                        bookie = juego['bookmakers'][0]
                        mercados = bookie['markets']
                        
                        if not mercados:
                            st.write("🔒 Mercado cerrado.")
                            continue
                            
                        opciones = mercados[0]['outcomes']
                        
                        # CREAMOS UNA TABLA BONITA
                        filas = []
                        for op in opciones:
                            nombre = op['name']
                            cuota = op['price']
                            # Si es Handicap o Total, mostramos el punto (ej. -5.5 o 220.5)
                            punto = op.get('point', '') 
                            
                            # Lógica de Kelly simple para sugerencia
                            prob_estimada = 1/cuota # Probabilidad implícita base
                            # Ajuste defensivo: Solo sugerimos si la cuota paga bien
                            sugerencia = "Observar"
                            monto = 0
                            if cuota > 1.90: 
                                sugerencia = "✅ VALOR PROBABLE"
                                monto = SALDO_REAL * 0.02 # 2% del banco
                            
                            filas.append({
                                "Selección": nombre,
                                "Línea/Puntos": punto,
                                "Cuota (Momio)": cuota,
                                "Estado": sugerencia,
                                "Apuesta Sugerida": f"${round(monto, 2)}" if monto > 0 else "$0.00"
                            })
                        
                        st.table(pd.DataFrame(filas))
                        st.caption(f"Datos provistos por: {bookie['title']}")

        except Exception as e:
            st.error(f"Ocurrió un error al procesar los datos: {e}")

st.info("ℹ️ Selecciona 'Handicap' o 'Totales' en el menú de la izquierda para ver líneas de puntos y goles.")
