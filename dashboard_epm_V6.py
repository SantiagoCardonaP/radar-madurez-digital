import streamlit as st
import pandas as pd
import re
from openai import OpenAI
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
from gtts import gTTS
import os

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Leer prompt base
with open("prompt_base.txt", "r", encoding="utf-8") as f:
    base_prompt = f.read()

st.image("https://raw.githubusercontent.com/SantiagoCardonaP/epm-dashboard-social-listening/2fdfac81f49d7c03afea8e29c0d67d96bcdcf750/logo-grupo-epm%20(1).png")
st.title("Asistente de percepción de marca con IA")
st.subheader("Te cuento cómo está nuestra percepción de marca en los territorios")

# Ruta del archivo predeterminado
file = "Menciones_EPM.csv"

if file:
    df = pd.read_csv(file, sep=";")

    # Filtrado en cascada para que opciones se actualicen según selección previa
    df_filtrado_region = df.copy()
    if region := st.multiselect("Región", df['Region'].unique()):
        df_filtrado_region = df[df['Region'].isin(region)]
    else:
        region = []

    # Filtrar filiales solo en la región seleccionada
    filiales_disponibles = df_filtrado_region['Filial'].unique()
    if filial := st.multiselect("Filial", filiales_disponibles):
        df_filtrado_filial = df_filtrado_region[df_filtrado_region['Filial'].isin(filial)]
    else:
        filial = []
        df_filtrado_filial = df_filtrado_region

    # Filtrar territorios solo en la región y filiales seleccionadas
    territorios_disponibles = df_filtrado_filial['Territorio_comunicacion'].unique()
    if territorio := st.multiselect("Territorio de comunicación", territorios_disponibles):
        df_filtrado = df_filtrado_filial[df_filtrado_filial['Territorio_comunicacion'].isin(territorio)]
    else:
        territorio = []
        df_filtrado = df_filtrado_filial

    # Generar informe con base en filtros
    # CSS para estilizar el botón
    st.markdown("""
    <style>
    div.stButton > button:first-child {
        display: block;
        margin: 0 auto;
        font-weight: bold;
        font-size: 20px;
        padding: 10px 30px;
    }
    </style>
    """, unsafe_allow_html=True)

    if st.button("¿Quieres que genere el informe de percepciones y recomendaciones?"):
        resumen = df_filtrado.groupby("Territorio_comunicacion")[["Negativo","Neutral","Positivo"]].sum().reset_index()
        resumen_str = resumen.to_string(index=False)

        prompt_informe = f"""
{base_prompt}

Estos son datos agregados por territorio de comunicación:
{resumen_str}

Genera un resumen de las percepciones con insights y recomendaciones de narrativa digital que contenga una frase de narrativa emocional y acciones puntuales con su respectiva táctica, 
basadas en estos datos. No pongas explícito en el análisis el Territorio_comunicacion No asignado.

"""

        with st.spinner("Generando informe..."):
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_informe}],
                temperature=0.4
            )
            informe = response.choices[0].message.content
            st.markdown("### Informe generado")
            st.write(informe)

            # Limpiar y formatear el texto para una mejor lectura
            texto_para_voz = re.sub(r'[^\w\s.,¡!¿?áéíóúÁÉÍÓÚñÑ]', '', informe)
            texto_para_voz = re.sub(r'\n+', '. ', texto_para_voz)

            # Generar y guardar el audio
            tts = gTTS(text=texto_para_voz, lang='es')
            audio_path = "informe_audio.mp3"
            tts.save(audio_path)

            # Reproducir el audio en Streamlit
            st.subheader("¿Quieres que te lea los insights?")
            st.audio(audio_path, format='audio/mp3')

    # Recuadro para preguntas libres
    st.header("Quieres profundizar en algo mas? ¡Pregúntame!")
    user_input = st.text_area("Ejemplo: Qué podemos hacer para mejorar la percepción de la sostenibildiad en el territorio?", "")

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

    st.subheader("Vista general de los datos")
    st.dataframe(df_filtrado.sample(frac=1).reset_index(drop=True))

    st.subheader("Distribución de Sentimientos")
    sentiments_df = df_filtrado[['Negativo', 'Neutral', 'Positivo']].sum().reset_index()
    sentiments_df.columns = ['Sentimiento', 'Total']
    st.bar_chart(sentiments_df.set_index('Sentimiento'))

    st.subheader("Nube de palabras (Menciones) depurada")
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
