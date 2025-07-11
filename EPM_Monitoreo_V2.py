import streamlit as st
import pandas as pd
import re
from openai import OpenAI
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
from PIL import Image
import base64
import io
from collections import Counter
import os
import requests
import time

# === Configuración de cliente OpenAI ===
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# === Configuración de D-ID API ===
DID_API_URL = "https://api.d-id.com/talks"
DID_API_KEY = st.secrets.get("DID_API_KEY")
HEADERS_DID = {
    "Authorization": f"Bearer {DID_API_KEY}",
    "Content-Type": "application/json"
}

# Función para crear vídeo con D-ID
@st.cache_data
def crear_video_did(script_text: str) -> str:
    payload = {
        "source_url": "https://storage.googleapis.com/d-id-static-content/demo-avatar.jpg",  # Reemplaza con URL pública o ID de avatar en D-ID
        "script": {
            "type": "text",
            "input": script_text,
            "voice": "female-1",
            "ssml": False
        },
        "config": {
            "stitch": True,
            "quality": "720p"
        }
    }
    # Inicia la petición
    resp = requests.post(DID_API_URL, json=payload, headers=HEADERS_DID)
    resp.raise_for_status()
    job = resp.json()
    job_id = job.get("id")

    # Polling hasta finalizar
    status_url = f"{DID_API_URL}/{job_id}"
    for _ in range(30):
        status = requests.get(status_url, headers=HEADERS_DID).json()
        if status.get("status") == "finished":
            return status.get("resultUrl")
        if status.get("status") == "failed":
            raise RuntimeError("D-ID API error: " + status.get("error", "desconocido"))
        time.sleep(2)
    raise TimeoutError("Tiempo de espera superado en la generación del vídeo con D-ID")

# === Logos y Estilos ===
logo_path = "logo-grupo-epm (1).png"
img = Image.open(logo_path)
buffered = io.BytesIO()
img.save(buffered, format="PNG")
img_b64 = base64.b64encode(buffered.getvalue()).decode()
st.markdown(
    f"""
    <div style='position: absolute; top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999;'>
        <img src="data:image/png;base64,{img_b64}" width="233px"/>
    </div>
    """, unsafe_allow_html=True)
st.markdown("<div style='margin-top: 120px;'></div>", unsafe_allow_html=True)

# Fondo y tipografía
image_path = "fondo-julius-epm.png"
img = Image.open(image_path)
buffered = io.BytesIO()
img.save(buffered, format="PNG")
img_b64 = base64.b64encode(buffered.getvalue()).decode()
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat&display=swap');
    html, body, [class*="css"] {{ font-family: 'Montserrat', sans-serif !important; }}
    .stApp {{ background-image: url("data:image/jpeg;base64,{img_b64}"); background-repeat: no-repeat; background-position: top center; background-size: auto; background-attachment: scroll; }}
    .stApp .main .block-container {{ background-image: linear-gradient(to bottom, transparent 330px, #240531 330px) !important; border-radius: 20px !important; padding: 50px !important; max-width: 800px !important; margin: 2rem auto !important; }}
    h1 {{ color: white; font-size: 2.5em; }}
    h2 {{ font-size: 1.3em; color: #ff5722; margin-bottom: 1em; }}
    label, .stSelectbox label, .stMultiSelect label {{ color: white !important; font-size: 0.9em; }}
    div.stButton > button {{ background-color: #ff5722; color: #ffffff !important; font-weight: bold; font-size: 16px; padding: 12px 24px; border-radius: 50px; border: none; width: 100%; margin-top: 10px; }}
    div.stButton > button:hover {{ background-color: #e64a19; }}
    </style>
    """, unsafe_allow_html=True)

# === Título ===
st.markdown("<h1 style='text-align: center; margin-top:100px;'>Asistente de percepción de marca con IA</h1>", unsafe_allow_html=True)

# === Cargar datos ===
df = pd.read_csv("Menciones_EPM.csv", sep=";")

# === Carga prompt base ===
with open("prompt_base.txt", "r", encoding="utf-8") as f:
    base_prompt = f.read()

# === Función para generar informe ===
def generar_informe(df):
    agg = df.groupby("Fuente")[['Negativo','Neutral','Positivo','Total']].sum().reset_index()
    for col in ['Negativo','Neutral','Positivo']:
        agg[f"{col}_pct"] = (agg[col] / agg["Total"] * 100).round(1)
    headers = ["Fuente","Neg","Neu","Pos","Total","Neg_pct","Neu_pct","Pos_pct"]
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"]*len(headers)) + " |"]
    for _, row in agg.iterrows():
        vals = [
            row["Fuente"], row["Negativo"], row["Neutral"], row["Positivo"],
            row["Total"], f'{row["Negativo_pct"]}%', f'{row["Neutral_pct"]}%', f'{row["Positivo_pct"]}%'
        ]
        lines.append("| " + " | ".join(str(v) for v in vals) + " |")
    agg_md = "\n".join(lines)

    ejemplos = (df.dropna(subset=["Mencion"])  
                  .groupby("Fuente")["Mencion"]  
                  .apply(lambda s: s.sample(min(len(s), 5), random_state=42).tolist())  
                  .to_dict())
    ejemplos_md = "\n".join(
        f"- **{fuente}**: «{'; '.join(textos)}»"
        for fuente, textos in ejemplos.items()
    )

    all_txt = " ".join(df["Mencion"].dropna().str.lower())
    palabras = re.findall(r"\w+", all_txt)
    top20 = Counter(palabras).most_common(20)
    longitud_media = df["Mencion"].dropna().str.len().mean().round(1)
    stats_md = (
        f"- Longitud media de mención: {longitud_media} caracteres\n"
        f"- Top 20 palabras clave: {', '.join(w for w,_ in top20)}"
    )

    prompt = f"""
## Resumen agregado por fuente
{agg_md}

## Ejemplos representativos de menciones (5 por fuente)
{ejemplos_md}

## Insights cuantitativos
{stats_md}

Genera un análisis de las menciones de máximo 100 palabras, con los siguientes componentes:
Resumen del estado, Temas positivos y negativos, Canales y tópicos destacados.
No incluyas títulos.

"""
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user","content": prompt}],
        temperature=0.4,
        max_tokens=512
    )
    return resp.choices[0].message.content

@st.cache_data(show_spinner=False)
def generar_informe_cache(df):
    return generar_informe(df)

# === Generar y mostrar informe inicial ===
informe = generar_informe_cache(df)
st.markdown("### Informe generado")
st.write(informe)

# === Botón para generar vídeo ===
if st.button("Generar vídeo con avatar"):
    with st.spinner("Creando vídeo con D-ID..."):
        try:
            video_url = crear_video_did(informe)
            st.success("Vídeo generado con éxito 🎬")
            st.video(video_url)
        except Exception as e:
            st.error(f"Error al generar el vídeo: {e}")

# === Preguntas abiertas ===
st.markdown("<h1>¿Quieres profundizar en algo más?</h1>", unsafe_allow_html=True)
entrada = st.text_area("Presiona ctrl + enter para preguntar", "")
if entrada:
    ejemplos = df[['Mencion','Negativo','Neutral','Positivo']].head(10).to_string(index=False)
    prompt2 = f"""

Estos son ejemplos individuales de menciones:
{ejemplos}

Responde de forma clara y útil:
{entrada}
"""
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt2}],
        temperature=0.3
    )
    st.markdown("### Respuesta de la IA")
    st.write(resp.choices[0].message.content)

# === Visualizaciones ===
with st.expander("Vista general de los datos"):
    st.dataframe(df.sample(frac=1).reset_index(drop=True))

with st.expander("Distribución de sentimientos"):
    sentiments = df[['Negativo','Neutral','Positivo']].sum()
    fig, ax = plt.subplots()
    ax.pie(sentiments, labels=sentiments.index, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    st.pyplot(fig)

with st.expander("Volumen por red social"):
    volumen = df['Fuente'].value_counts().reset_index()
    volumen.columns = ['Fuente','Total']
    st.bar_chart(volumen.set_index('Fuente'))

with st.expander("Nube de palabras"):
    text = " ".join(df['Mencion'].dropna().astype(str)).lower()
    text = re.sub(r'[^\w\s]', '', text)
    stop_es = set(STOPWORDS) | {"de","la","que","el","en","y","a","los","del","se","las","por","un","para","con","no","una","su","al","es","lo","como","más","pero","sus","ya","o","este","sí","porque","esta","entre","cuando","muy","sin","sobre","también","me","hasta","hay","donde","quien","desde","todo","nos","durante","todos","uno","les","ni","contra","otros","ese","eso","ante","ellos","e","esto","mí","antes","algunos","qué","unos","yo","otro","otras","otra","él","tanto","esa","estos","mucho","quienes","nada","muchos","cual","poco","ella","estar","estas"}
    wc = WordCloud(width=800, height=400, background_color='white', stopwords=stop_es).generate(text)
    fig2, ax2 = plt.subplots(figsize=(10,5))
    ax2.imshow(wc, interpolation='bilinear')
    ax2.axis('off')
    st.pyplot(fig2)

# === Logo final ===
final_logo_path = "logo-julius.png"
final_img = Image.open(final_logo_path)
buffered = io.BytesIO()
final_img.save(buffered, format="PNG")
final_b64 = base64.b64encode(buffered.getvalue()).decode()
st.markdown(
    f"""
    <div style='display: flex; justify-content: center; align-items: center; margin-top: 60px; margin-bottom: 40px;'>
        <img src="data:image/png;base64,{final_b64}" width="96" height="69"/>
    </div>
    """, unsafe_allow_html=True)
