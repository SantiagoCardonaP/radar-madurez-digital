
import streamlit as st
import pandas as pd
from openai import OpenAI
import altair as alt
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
import re
import os

# Inicializar cliente OpenAI
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Título
st.title("Dashboard EPM – Análisis de Social Listening con IA")

# Ruta del archivo predeterminado
default_csv_path = "Menciones_EPM.csv"

# Subida de archivo CSV
file = st.file_uploader("Sube el archivo CSV de comentarios (delimitado por punto y coma)", type="csv")

# Si no se sube archivo, usar el predeterminado
if file is not None:
    df = pd.read_csv(file, sep=";")
else:
    if os.path.exists(default_csv_path):
        df = pd.read_csv(default_csv_path, sep=";")
        st.info(f"Usando archivo predeterminado: {default_csv_path}")
    else:
        st.error("No se ha subido un archivo y no se encontró un archivo predeterminado.")
        st.stop()

# Filtros
filial = st.multiselect("Filial", df['Filial'].dropna().unique())
eje = st.multiselect("Eje temático", df['Eje_tematico'].dropna().unique())

df_filtrado = df.copy()
if filial:
    df_filtrado = df_filtrado[df_filtrado['Filial'].isin(filial)]
if eje:
    df_filtrado = df_filtrado[df_filtrado['Eje_tematico'].isin(eje)]

# Mostrar menciones aleatorias
st.subheader("Vista general de los datos")
st.dataframe(df_filtrado.sample(frac=1).reset_index(drop=True))

st.subheader("Distribución de Sentimientos")
sentiments_df = df_filtrado[['Negativo', 'Neutral', 'Positivo']].sum().reset_index()
sentiments_df.columns = ['Sentimiento', 'Total']
st.bar_chart(sentiments_df.set_index('Sentimiento'))

# Nube de palabras con limpieza
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

wordcloud = WordCloud(
    width=800,
    height=400,
    background_color='white',
    stopwords=stopwords_es
).generate(raw_text)

plt.imshow(wordcloud, interpolation='bilinear')
plt.axis("off")
st.pyplot(plt)

# Entrada a la IA
st.subheader("Hazle una pregunta a la IA sobre lo que estás viendo")
user_input = st.text_area("¿Qué quieres saber?", "")

if user_input:
    resumen = df_filtrado.groupby("Eje_tematico")[["Negativo","Neutral","Positivo"]].sum().reset_index()
    resumen_str = resumen.to_string(index=False)

    prompt = f"""
Eres un experto etnógrafo analizando datos de percepción ciudadana sobre el Grupo EPM y sus filiales en Colombia.
Tu objetivo es interpretar la percepción pública con enfoque en sostenibilidad, servicio, atención comunitaria y confianza institucional.

Estos son datos agregados por eje temático:
{resumen_str}

Aquí hay ejemplos individuales de menciones:
{df_filtrado[['Mencion','Negativo','Neutral','Positivo','Eje_tematico']].head(10).to_string(index=False)}

Con base en la información anterior, responde en español de manera clara y útil:
{user_input}
"""
    with st.spinner("Generando respuesta..."):
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        answer = response.choices[0].message.content
        st.markdown("### Respuesta de la IA")
        st.write(answer)
