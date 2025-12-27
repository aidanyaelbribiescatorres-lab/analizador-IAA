import streamlit as st
import pandas as pd
import requests

# --- CONFIGURACIÓN ESTILO CHATGPT ---
st.set_page_config(page_title="IA Apuestas Yael", page_icon="🤖", layout="centered")

# Memoria del dinero y del chat
if 'saldo' not in st.session_state:
    st.session_state.saldo = 24.27 
if "messages" not in st.session_state:
    st.session_state.messages = []

API_KEY = '8d90dd7eb80726fb3a98683ee7d2e734'

# --- BARRA LATERAL (TU DINERO) ---
st.sidebar.title("💳 Tu Banca")
st.sidebar.markdown(f"""
    <div style="background-color:#222; padding:10px; border-radius:10px; text-align:center; border: 1px solid #444;">
        <h2 style="color:#00FF00; margin:0;">${st.session_state.saldo:.2f}</h2>
    </div>
    """, unsafe_allow_html=True)

deporte = st.sidebar.selectbox("Selecciona Liga:", [
    ('🏀 NBA', 'basketball_nba'),
    ('🏈 NFL', 'americanfootball_nfl'),
    ('⚾ MLB', 'baseball_mlb'),
    ('⚽ Premier League', 'soccer_epl')
], format_func=lambda x: x[0])

st.sidebar.info("💡 **Tip:** Escribe el nombre del equipo en el chat para analizarlo.")

# --- TÍTULO ---
st.title("💬 Chat Inteligente")
st.caption("Escribe algo como: '¿Analiza a los Lakers?' o '¿Quién gana entre Real Madrid y Barça?'")

# --- MOSTRAR HISTORIAL DEL CHAT ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CEREBRO: PROCESAR TU MENSAJE ---
def responder_usuario(pregunta, datos_api):
    pregunta = pregunta.lower()
    
    # Buscar si mencionó algún equipo
    juego_encontrado = None
    equipo_mencionado = ""
    
    for juego in datos_api:
        local = juego['home_team'].lower()
        visita = juego['away_team'].lower()
        
        # Inteligencia de búsqueda (busca palabras clave)
        if local in pregunta or visita in pregunta or \
           local.split()[-1] in pregunta or visita.split()[-1] in pregunta: 
            juego_encontrado = juego
            equipo_mencionado = juego['home_team'] if local in pregunta else juego['away_team']
            break
    
    if juego_encontrado:
        # Calcular Matemáticas
        bookies = juego_encontrado['bookmakers']
        if not bookies: return "Ese partido no tiene cuotas disponibles todavía. 🛑"
        
        odds = bookies[0]['markets'][0]['outcomes']
        loc_name = juego_encontrado['home_team']
        vis_name = juego_encontrado['away_team']
        
        # Extraer cuotas
        c_loc = next((x['price'] for x in odds if x['name'] == loc_name), 1.0)
        c_vis = next((x['price'] for x in odds if x['name'] == vis_name), 1.0)
        
        # Probabilidades
        impl_l, impl_v = 1/c_loc, 1/c_vis
        margen = impl_l + impl_v
        p_real_l = (impl_l/margen)*100
        p_real_v = (impl_v/margen)*100
        
        # Decisión
        if p_real_l > p_real_v:
            fav, prob, cuota = loc_name, p_real_l, c_loc
        else:
            fav, prob, cuota = vis_name, p_real_v, c_vis
            
        # Kelly (Dinero)
        b = cuota - 1
        p = prob/100
        q = 1 - p
        kelly = (b*p - q)/b if b > 0 else 0
        apuesta = (st.session_state.saldo * kelly) / 4 if kelly > 0 else 0
        ganancia = (apuesta * cuota) - apuesta
        
        respuesta = f"📊 **Análisis del {loc_name} vs {vis_name}:**\n\n"
        respuesta += f"El favorito matemático es **{fav}** con un **{round(prob,1)}%** de probabilidad.\n\n"
        
        if apuesta > 0.5:
            respuesta += f"✅ **Recomendación:** ¡Apuesta con valor!\n"
            respuesta += f"- 💰 Métele: **${round(apuesta, 2)}**\n"
            respuesta += f"- 📈 Ganarías: **${round(ganancia, 2)}** limpios.\n\n"
            respuesta += "Si ganas, avísame escribiendo 'ganamos' para sumar tu saldo."
        else:
            respuesta += f"⚠️ **Cuidado:** Aunque {fav} es favorito, la cuota paga muy poco. Mejor **no apuestes** tu dinero aquí."
            
        return respuesta
        
    elif "ganamos" in pregunta:
        # Truco para sumar dinero manual
        st.session_state.saldo += 1.50 # Suma fija simulada
        return "¡Eso es todo! 🎉 He sumado ganancias a tu cuenta. ¿Cuál es el siguiente partido?"
        
    else:
        return "🤔 No encontré ese equipo en la liga seleccionada hoy. Intenta escribir el nombre exacto (ej: 'Warriors' o 'Arsenal')."

# --- INPUT DEL CHAT (LO QUE TÚ ESCRIBES) ---
if prompt := st.chat_input("Escribe tu pregunta aquí..."):
    # 1. Mostrar lo que tú escribiste
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Obtener datos y pensar respuesta
    url = f'https://api.the-odds-api.com/v4/sports/{deporte[1]}/odds/?apiKey={API_KEY}&regions=us&markets=h2h&oddsFormat=decimal'
    try:
        res = requests.get(url)
        datos = res.json()
        respuesta_ia = responder_usuario(prompt, datos)
    except:
        respuesta_ia = "Error de conexión con las casas de apuestas. Intenta de nuevo."

    # 3. Mostrar respuesta de la IA
    st.session_state.messages.append({"role": "assistant", "content": respuesta_ia})
    with st.chat_message("assistant"):
        st.markdown(respuesta_ia)
