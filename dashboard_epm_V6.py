import streamlit as st
import pandas as pd
import re
from openai import OpenAI
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
from gtts import gTTS
import os
from PIL import Image
import base64
import io

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# === LOGO ABSOLUTO FUERA DEL CONTENEDOR ===
logo_path = "logo-grupo-epm (1).png"
img = Image.open(logo_path)
buffered = io.BytesIO()
img.save(buffered, format="PNG")
img_b64 = base64.b64encode(buffered.getvalue()).decode()

# Logo posicionado fuera del bloque morado
st.markdown(
    f"""
    <div style='
        position: absolute;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 9999;
    '>
        <img src="data:image/png;base64,{img_b64}" width="233px"/>
    </div>
    """,
    unsafe_allow_html=True
)
st.markdown("<div style='margin-top: 120px;'></div>", unsafe_allow_html=True)

# === ESTILO DE FONDO ===
image_path = "fondo-julius-epm.png"
img = Image.open(image_path)
buffered = io.BytesIO()
img.save(buffered, format="PNG")
img_b64 = base64.b64encode(buffered.getvalue()).decode()

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Montserrat', sans-serif !important;
    }}

    .stApp {{
        background-image: url("data:image/jpeg;base64,{img_b64}");
        background-repeat: no-repeat;
        background-position: top center;
        background-size: auto;
        background-attachment: scroll;
    }}

.stApp .main .block-container {{
    background-image: linear-gradient(to bottom, transparent 330px, #240531 330px) !important;
    background-repeat: no-repeat !important;
    background-size: 100% 100% !important;
    border-radius: 20px !important;
    padding: 50px !important;
    max-width: 800px !important;
    margin: 2rem auto !important;
}}

section.main > div {{
    background-image: linear-gradient(to bottom, transparent 330px, #240531 330px) !important;
    background-repeat: no-repeat !important;
    background-size: 100% 100% !important;
    border-radius: 20px !important;
    padding: 50px !important;
    max-width: 800px !important;
    margin: 2rem auto !important;
}}

div[data-testid="stAppViewContainer"] > section > div {{
    background-image: linear-gradient(to bottom, transparent 330px, #240531 330px) !important;
    background-repeat: no-repeat !important;
    background-size: 100% 100% !important;
    border-radius: 20px !important;
    padding: 50px !important;
    max-width: 800px !important;
    margin: 2rem auto !important;
}}

    h1 {{
        color: white;
        font-size: 2.5em;
    }}

    h2 {{
        font-size: 1.3em;
        color: #ff5722;
        font-weight: normal;
        margin-bottom: 1em;
    }}

    label, .stSelectbox label, .stMultiSelect label {{
        color: white !important;
        font-size: 0.9em;
    }}

    div.stButton > button {{
        background-color: #ff5722;
        color: #ffffff !important;
        font-weight: bold;
        font-size: 16px;
        padding: 12px 24px;
        border-radius: 50px;
        border: none;
        width: 100%;
        margin-top: 10px;
    }}

    div.stButton > button:hover {{
        background-color: #e64a19;
        color:#4B006E !important;
    }}

    .stSelectbox div[data-baseweb="select"] {{
        background-color: #4b006e !important;
        color: white !important;
        border-radius: 6px;
    }}

    .stTextArea textarea {{
        background-color: #4b006e;
        color: white;
    }}

    details {{
        background-color: transparent;
        color: white;
        border: none;
        border-bottom: 1px solid #4A3255;
        padding: 0.3em 0;
        font-family: 'Montserrat', sans-serif;
        margin: 0;
    }}

    summary {{
        color: #ff5722;
        font-size: 1.05em;
        font-weight: 500;
        cursor: pointer;
        list-style: none;
    }}

    summary::-webkit-details-marker {{
        color: #ffffff !important;
    }}

    summary::marker {{
        color: #ffffff !important;
    }}

    .st-emotion-cache-1pbsqtx {{
        vertical-align: middle;
        overflow: hidden;
        color: inherit;
        fill: #fff;
        display: inline-flex;
        -webkit-box-align: center;
        align-items: center;
        font-size: 1.25rem;
        width: 1.25rem;
        height: 1.25rem;
        flex-shrink: 0;
    }}
    h1#asistente-de-percepcion-de-marca-con-ia {{
    margin-top:100px;
    font-size: 2.75rem;
    font-weight: 700;
    padding: 1.25rem 0px 1rem;
}}
    .st-emotion-cache-seewz2 h2 {{
    font-size: 1.4rem;
    padding: 1rem 0px;
    color: #ff5722;
}}
    </style>
    """,
    unsafe_allow_html=True
)

# === CARGAR PROMPT BASE ===
with open("prompt_base.txt", "r", encoding="utf-8") as f:
    base_prompt = f.read()

st.markdown('<div style="margin-top: 2rem;"></div>', unsafe_allow_html=True)
# === TÍTULOS ===
st.markdown("<h1>Asistente de percepción de marca con IA</h1>", unsafe_allow_html=True)
st.markdown("<h2>Te cuento como está nuestra percepción de marca en los territorios</h2>", unsafe_allow_html=True)

# === CARGAR DATOS ===
file = "Menciones_EPM.csv"
if file:
    df = pd.read_csv(file, sep=";")

    # === FILTROS ===
    df_filtrado_region = df.copy()
    if region := st.multiselect("Región", df['Region'].unique(), placeholder="Elige una opción"):
        df_filtrado_region = df[df['Region'].isin(region)]
    else:
        region = []

    filiales_disponibles = df_filtrado_region['Filial'].unique()
    if filial := st.multiselect("Filial", filiales_disponibles, placeholder="Elige una opción"):
        df_filtrado_filial = df_filtrado_region[df_filtrado_region['Filial'].isin(filial)]
    else:
        filial = []
        df_filtrado_filial = df_filtrado_region

    territorios_disponibles = df_filtrado_filial['Territorio_comunicacion'].unique()
    if territorio := st.multiselect("Territorio de comunicación", territorios_disponibles, placeholder="Elige una opción"):
        df_filtrado = df_filtrado_filial[df_filtrado_filial['Territorio_comunicacion'].isin(territorio)]
    else:
        territorio = []
        df_filtrado = df_filtrado_filial

    # === GENERAR INFORME ===
    if st.button("¿Quieres que genere el informe de percepciones y recomendaciones?"):
        resumen = df_filtrado.groupby("Territorio_comunicacion")[["Negativo", "Neutral", "Positivo"]].sum().reset_index()
        resumen_str = resumen.to_string(index=False)

        prompt_informe = f"""
{base_prompt}

Estos son datos agregados por territorio de comunicación:
{resumen_str}

Genera un resumen de las percepciones con insights y recomendaciones de narrativa digital que contenga una frase de narrativa emocional y acciones puntuales con su respectiva táctica, 
basadas en estos datos. No pongas explícito en el análisis el Territorio_comunicacion No asignado.
"""

        with st.spinner("Generando informe..."):
            informe = "🧠 Aquí va el resumen generado por IA (simulado, descomenta para usar OpenAI API)."
            st.markdown("### Informe generado")
            st.write(informe)

            texto_para_voz = re.sub(r'[^\w\s.,¡!¿?áéíóúÁÉÍÓÚñÑ]', '', informe)
            texto_para_voz = re.sub(r'\n+', '. ', texto_para_voz)

            tts = gTTS(text=texto_para_voz, lang='es')
            audio_path = "informe_audio.mp3"
            tts.save(audio_path)

            st.subheader("¿Quieres que te lea los insights?")
            st.audio(audio_path, format='audio/mp3')

    # === PREGUNTAS ABIERTAS ===
    st.markdown("<h1>¿Quieres profundizar en algo más?</h1>", unsafe_allow_html=True)
    user_input = st.text_area("Ejemplo: ¿Qué podemos hacer para mejorar la percepción de la sostenibilidad en el territorio?", "")

    if user_input:
        prompt_pregunta = f"""
{base_prompt}

Estos son ejemplos individuales de menciones:
{df_filtrado[['Mencion','Negativo','Neutral','Positivo','Territorio_comunicacion']].head(10).to_string(index=False)}

Responde de forma clara y útil:
{user_input}
"""
        with st.spinner("Generando respuesta..."):
            answer = "💡 Esta sería una respuesta generada por IA (simulado)."
            st.markdown("### Respuesta de la IA")
            st.write(answer)

    # === DATOS Y VISUALIZACIONES ===
    with st.expander("Vista general de los datos"):
        st.dataframe(df_filtrado.sample(frac=1).reset_index(drop=True))

    with st.expander("Distribución de sentimientos"):
        sentiments_df = df_filtrado[['Negativo', 'Neutral', 'Positivo']].sum().reset_index()
        sentiments_df.columns = ['Sentimiento', 'Total']
        st.bar_chart(sentiments_df.set_index('Sentimiento'))

    with st.expander("Nube de palabras (Menciones) depurada"):
        raw_text = " ".join(df_filtrado['Mencion'].dropna().astype(str))
        raw_text = re.sub(r'[^\w\s]', '', raw_text.lower())

        stopwords_es = set(STOPWORDS)
        stopwords_es.update([
            "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las",
            "por", "un", "para", "con", "no", "una", "su", "al", "es", "lo",
            "como", "más", "pero", "sus", "ya", "o", "este", "sí", "porque",
            "esta", "entre", "cuando", "muy", "sin", "sobre", "también", "me",
            "hasta", "hay", "donde", "quien", "desde", "todo", "nos", "durante",
            "todos", "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante",
            "ellos", "e", "esto", "mí", "antes", "algunos", "qué", "unos", "yo",
            "otro", "otras", "otra", "él", "tanto", "esa", "estos", "mucho",
            "quienes", "nada", "muchos", "cual", "poco", "ella", "estar", "estas"
        ])

        wordcloud = WordCloud(width=800, height=400, background_color='white', stopwords=stopwords_es).generate(raw_text)
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis("off")
        st.pyplot(plt)

# === LOGO FINAL ===
final_logo_path = "logo-julius.png"
final_img = Image.open(final_logo_path)
buffered = io.BytesIO()
final_img.save(buffered, format="PNG")
final_img_b64 = base64.b64encode(buffered.getvalue()).decode()

st.markdown(
    f"""
    <div style='
        display: flex;
        justify-content: center;
        align-items: center;
        margin-top: 60px;
        margin-bottom: 40px;
    '>
        <img src="data:image/png;base64,{final_img_b64}" width="96" height="69"/>
    </div>
    """,
    unsafe_allow_html=True
)
