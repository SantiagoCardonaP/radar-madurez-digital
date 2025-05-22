
import streamlit as st
import pandas as pd
from openai import OpenAI
import altair as alt
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# Inicializar cliente OpenAI
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Título
st.title("Dashboard EPM – Análisis de Social Listening con IA")

# Subida de archivo CSV
file = st.file_uploader("Sube el archivo CSV de comentarios", type="csv")

if file:
    df = pd.read_csv(file, sep=";")
    st.subheader("Vista general de los datos")
    st.dataframe(df.head())

    # Filtros
    filial = st.multiselect("Filial", df['Filial'].dropna().unique())
    eje = st.multiselect("Eje temático", df['Eje_tematico'].dropna().unique())

    df_filtrado = df.copy()
    if filial:
        df_filtrado = df_filtrado[df_filtrado['Filial'].isin(filial)]
    if eje:
        df_filtrado = df_filtrado[df_filtrado['Eje_tematico'].isin(eje)]

    st.subheader("Distribución de Sentimientos")
    sentiments_df = df_filtrado[['Negativo', 'Neutral', 'Positivo']].sum().reset_index()
    sentiments_df.columns = ['Sentimiento', 'Total']
    st.bar_chart(sentiments_df.set_index('Sentimiento'))

    # Nube de palabras
    st.subheader("Nube de palabras (Menciones)")
    text = " ".join(df_filtrado['Mencion'].dropna().astype(str))
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text)
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    st.pyplot(plt)

    # Entrada a la IA
    st.subheader("Hazle una pregunta a la IA sobre lo que estás viendo")
    user_input = st.text_area("¿Qué quieres saber?", "")

    if user_input:
        prompt = f"""
Eres un experto etnógrafo analizando datos de percepción ciudadana sobre Grupo EPM y sus filiales. 
Con base en estos datos de menciones:

{df_filtrado[['Mencion','Negativo','Neutral','Positivo','Eje_tematico']].head(10).to_string(index=False)}

Responde de forma breve, útil y en español la siguiente pregunta:
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
