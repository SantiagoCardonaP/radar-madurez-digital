
import streamlit as st
import pandas as pd
import openai
import altair as alt
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# Configurar la clave de API (debe añadirse en secrets.toml en Streamlit Cloud o localmente)
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Título
st.title("Dashboard EPM – Análisis de Social Listening con IA")

# Cargar archivo CSV
file = st.file_uploader("Sube el archivo CSV de comentarios", type="csv")

if file:
    df = pd.read_csv(file)
    st.subheader("Vista general de los datos")
    st.dataframe(df.head())

    # Filtros interactivos
    filial = st.multiselect("Filial", df['filial'].unique())
    red = st.multiselect("Red social", df['red_social'].unique())
    comunidad = st.multiselect("Comunidad", df['comunidad'].unique())
    eje = st.multiselect("Eje temático", df['eje_tematico'].unique())

    # Aplicar filtros
    df_filtrado = df.copy()
    if filial:
        df_filtrado = df_filtrado[df_filtrado['filial'].isin(filial)]
    if red:
        df_filtrado = df_filtrado[df_filtrado['red_social'].isin(red)]
    if comunidad:
        df_filtrado = df_filtrado[df_filtrado['comunidad'].isin(comunidad)]
    if eje:
        df_filtrado = df_filtrado[df_filtrado['eje_tematico'].isin(eje)]

    st.subheader("Distribución de Sentimientos")
    st.bar_chart(df_filtrado['sentimiento'].value_counts())

    # Nube de palabras
    st.subheader("Nube de palabras (comentarios)")
    text = " ".join(df_filtrado['comentario'].dropna().astype(str))
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text)
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    st.pyplot(plt)

    # Entrada para la IA
    st.subheader("Hazle una pregunta a la IA sobre lo que estás viendo")
    user_input = st.text_area("¿Qué quieres saber?", "")

    if user_input:
        prompt = f"""
Eres un experto etnógrafo analizando datos de percepción ciudadana sobre Grupo EPM y sus filiales. 
Con base en estos comentarios filtrados:

{df_filtrado[['comentario','sentimiento','eje_tematico']].head(10).to_string(index=False)}

Responde de forma breve, útil y en español la siguiente pregunta:
{user_input}
"""
        with st.spinner("Generando respuesta..."):
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            answer = response['choices'][0]['message']['content']
            st.markdown("### Respuesta de la IA")
            st.write(answer)
