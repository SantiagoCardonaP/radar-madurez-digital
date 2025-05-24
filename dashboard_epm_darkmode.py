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

# === LOGO FUERA DEL CONTENEDOR ===
logo_path = "logo-grupo-epm (1).png"
img = Image.open(logo_path)
buffered = io.BytesIO()
img.save(buffered, format="PNG")
img_b64 = base64.b64encode(buffered.getvalue()).decode()

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

# === ESTILO CON VARIABLES DE STREAMLIT ===
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
        color: var(--text-color);
    }}

    .stApp {{
        background-image: url("data:image/jpeg;base64,{img_b64}");
        background-repeat: no-repeat;
        background-position: top center;
        background-size: auto;
        background-attachment: scroll;
    }}

    .stApp .main .block-container,
    section.main > div,
    div[data-testid="stAppViewContainer"] > section > div {{
        background-image: linear-gradient(to bottom, transparent 330px, var(--secondary-background-color) 330px) !important;
        background-repeat: no-repeat !important;
        background-size: 100% 100% !important;
        border-radius: 20px !important;
        padding: 50px !important;
        max-width: 800px !important;
        margin: 2rem auto !important;
    }}

    h1 {{
        color: var(--text-color);
        font-size: 2.5em;
    }}

    h2 {{
        font-size: 1.3em;
        color: var(--primary-color);
        font-weight: normal;
        margin-bottom: 1em;
    }}

    label, .stSelectbox label, .stMultiSelect label {{
        color: var(--text-color) !important;
    }}

    div.stButton > button {{
        background-color: var(--primary-color);
        color: var(--text-color) !important;
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
        color: var(--secondary-background-color) !important;
    }}

    .stSelectbox div[data-baseweb="select"],
    .stTextArea textarea {{
        background-color: var(--secondary-background-color);
        color: var(--text-color);
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# === CARGAR PROMPT BASE ===
with open("prompt_base.txt", "r", encoding="utf-8") as f:
    base_prompt = f.read()

# === TÍTULOS ===
st.markdown("""
    <h1 style='text-align: center;'>Asistente de percepción de marca con IA</h1>
    <h2 style='text-align: center;'>Te cuento cómo está nuestra percepción de marca en los territorios</h2>
""", unsafe_allow_html=True)

# === CARGAR DATOS ===
file = "Menciones_EPM.csv"
if file:
    df = pd.read_csv(file, sep=";")
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
    territorios_filtrados = [t for t in territorios_disponibles if t.strip().lower() != "no asignado"]
    if territorio := st.multiselect("Territorio de comunicación", territorios_filtrados, placeholder="Elige una opción"):
        df_filtrado = df_filtrado_filial[df_filtrado_filial['Territorio_comunicacion'].isin(territorio)]
    else:
        territorio = []
        df_filtrado = df_filtrado_filial

    if st.button("¿Quieres que genere el informe de percepciones y recomendaciones?"):
        resumen = df_filtrado.groupby("Territorio_comunicacion")[["Negativo", "Neutral", "Positivo"]].sum().reset_index()
        resumen_str = resumen.to_string(index=False)

        prompt_informe = f"""
{base_prompt}
Estos son datos agregados por territorio de comunicación:
{resumen_str}

Genera un resumen de las percepciones con insights y recomendaciones de narrativa digital que contenga una frase de narrativa emocional y acciones puntuales con su respectiva táctica, basadas en estos datos. No pongas explícito en el análisis el Territorio_comunicacion No asignado.
"""

        with st.spinner("🧠 Aquí va el resumen generado por IA.."):
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_informe}],
                temperature=0.4
            )
            informe = response.choices[0].message.content
            st.markdown("### Informe generado")
            st.write(informe)

            texto_para_voz = re.sub(r'[^\w\s.,¡!¿?áéíóúÁÉÍÓÚñÑ]', '', informe)
            texto_para_voz = re.sub(r'\n+', '. ', texto_para_voz)

            tts = gTTS(text=texto_para_voz, lang='es')
            audio_path = "informe_audio.mp3"
            tts.save(audio_path)

            st.subheader("¿Quieres que te lea los insights?")
            st.audio(audio_path, format='audio/mp3')

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
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_pregunta}],
                temperature=0.3
            )
            answer = response.choices[0].message.content
            st.markdown("### Respuesta de la IA")
            st.write(answer)

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
        stopwords_es.update(["de", "la", "que", "el", "en", "y", ...])

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
    <div style='display: flex; justify-content: center; align-items: center; margin-top: 60px; margin-bottom: 40px;'>
        <img src="data:image/png;base64,{final_img_b64}" width="96" height="69"/>
    </div>
    """,
    unsafe_allow_html=True
)
