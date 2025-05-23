import streamlit as st
import pandas as pd
import re
from openai import OpenAI
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Leer prompt base
with open("prompt_base.txt", "r", encoding="utf-8") as f:
    base_prompt = f.read()

st.title("Dashboard EPM – Análisis de Social Listening con IA")

# Ruta del archivo predeterminado
file = "Menciones_EPM.csv"

if file:
    df = pd.read_csv(file, sep=";")

    # Nuevos filtros incluyendo Region
    region = st.multiselect("Region", df['Region'].dropna().unique())
    filial = st.multiselect("Filial", df['Filial'].dropna().unique())
    territorio = st.multiselect("Territorio de comunicación", df['Territorio_comunicacion'].dropna().unique())

    df_filtered = df.copy()
    if region:
        df_filtered = df_filtered[df_filtered['Region'].isin(region)]
    if filial:
        df_filtered = df_filtered[df_filtered['Filial'].isin(filial)]
    if territorio:
        df_filtered = df_filtered[df_filtered['Territorio_comunicacion'].isin(territorio)]

    st.subheader("Vista general de los datos")
    st.dataframe(df_filtered.sample(frac=1).reset_index(drop=True))

    st.subheader("Distribución de Sentimientos")
    sentiments_df = df_filtered[['Negativo', 'Neutral', 'Positivo']].sum().reset_index()
    sentiments_df.columns = ['Sentimiento', 'Total']
    st.bar_chart(sentiments_df.set_index('Sentimiento'))

    st.subheader("Nube de palabras (Menciones) depurada")
    raw_text = " ".join(df_filtered['Mencion'].dropna().astype(str))
    raw_text = re.sub(r'[^\w\s]', '', raw_text.lower())

    stopwords_es = set(STOPWORDS)
    stopwords_es.update([
        # Lista usual de stopwords...
    ])

    wordcloud = WordCloud(width=800, height=400, background_color='white', stopwords=stopwords_es).generate(raw_text)
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    st.pyplot(plt)

    # Generar informe con base en filtros
    if st.button("Generar informe de percepciones y recomendaciones"):
        resumen = df_filtered.groupby("Territorio_comunicacion")[["Negativo","Neutral","Positivo"]].sum().reset_index()
        resumen_str = resumen.to_string(index=False)

        prompt_informe = f"""
{base_prompt}

Estos son datos agregados por territorio de comunicación:
{resumen_str}

Genera un resumen de las percepciones y las acciones y recomendaciones para narrativa digital, basadas en estos datos.

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

    # Recuadro para preguntas libres
    st.subheader("Hazle una pregunta a la IA sobre lo que estás viendo")
    user_input = st.text_area("¿Qué quieres saber?", "")

    if user_input:
        prompt_pregunta = f"""
{base_prompt}

Estos son ejemplos individuales de menciones:
{df_filtered[['Mencion','Negativo','Neutral','Positivo','Territorio_comunicacion']].head(10).to_string(index=False)}

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