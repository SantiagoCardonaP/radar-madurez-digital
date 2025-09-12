import streamlit as st
from openai import OpenAI
import pandas as pd
import numpy as np
import base64
import io
import requests
from bs4 import BeautifulSoup
from PIL import Image
import plotly.graph_objects as go

# =============================
# CONFIGURACIÓN BÁSICA / ESTILO
# =============================
st.set_page_config(page_title="Diagnóstico & Recomendaciones con GPT", page_icon="📊", layout="centered")

# === Cliente OpenAI (usa el mismo mecanismo que tu app actual) ===
# Agrega tu API Key en .streamlit/secrets.toml -> OPENAI_API_KEY = "..."
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])  # mismo patrón que el proyecto original

# === Marca y estilos (reutiliza el look&feel del proyecto existente) ===
# Intenta cargar los mismos recursos; si no existen, continúa sin romper
logo_path_top = "logo-grupo-epm (1).png"
logo_path_bottom = "logo-julius.png"
background_path = "fondo-julius-epm.png"

def _img_to_b64(path: str) -> str | None:
    try:
        img = Image.open(path)
        buf = io.BytesIO()
        fmt = "PNG" if path.lower().endswith("png") else "JPEG"
        img.save(buf, format=fmt)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None

b64_logo_top = _img_to_b64(logo_path_top)
b64_logo_bottom = _img_to_b64(logo_path_bottom)
b64_background = _img_to_b64(background_path)

# Encabezado con logo centrado
if b64_logo_top:
    st.markdown(
        f"""
        <div style='position: absolute; top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999;'>
            <img src="data:image/png;base64,{b64_logo_top}" width="233px"/>
        </div>
        <div style='margin-top: 220px;'></div>
        """,
        unsafe_allow_html=True,
    )

# CSS seguro (escapando llaves) + fondo dinámico
background_css = (
    f"background-image: url('data:image/jpeg;base64,{b64_background}');" if b64_background else ""
)

custom_css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Montserrat', sans-serif !important; }}
.stApp {{
    {background_css}
    background-repeat: no-repeat; background-position: top center; background-size: auto; background-attachment: scroll;
}}
.stApp .main .block-container {{
    background-image: linear-gradient(to bottom, transparent 330px, #240531 330px) !important;
    background-repeat: no-repeat !important; background-size: 100% 100% !important;
    border-radius: 20px !important; padding: 50px !important; max-width: 1200px !important; margin: 2rem auto !important;
}}
label, .stSelectbox label, .stMultiSelect label {{ color: white !important; font-size: 1.05em; }}
:root {{ --brand: #ff5722; }}
div.stButton > button {{ background-color: var(--brand); color: #ffffff !important; font-weight: 700; font-size: 16px; padding: 12px 24px; border-radius: 50px; border: none; width: 100%; margin-top: 10px; }}
div.stButton > button:hover {{ background-color: #e64a19; color:#4B006E !important; }}
.block {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 18px; margin-bottom: 14px; }}
.hint {{ color:#ddd; font-size: 12px; margin-top: -6px; }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

st.markdown("""
<div style='position: relative; z-index: 1; padding-top: 20px; text-align:center;'>
  <h1>Diagnóstico tipo formulario + Radar + Recomendaciones con IA</h1>
  <h3>Evaluación 1–5 por pregunta y promedio por categoría</h3>
</div>
""", unsafe_allow_html=True)

# =============================
# STATE SEGURO PARA NO PERDER NADA ENTRE CLICS
# =============================
if "empresa" not in st.session_state:
    st.session_state.empresa = ""
if "df_form" not in st.session_state:
    st.session_state.df_form = None
if "gpt_analysis" not in st.session_state:
    st.session_state.gpt_analysis = None
if "site_analysis" not in st.session_state:
    st.session_state.site_analysis = None
if "site_url" not in st.session_state:
    st.session_state.site_url = ""

# =============================
# 1) LECTURA DE FORMULARIO DESDE EXCEL Y UI DE CALIFICACIÓN + EMPRESA
# =============================
@st.cache_data(show_spinner=False)
def load_form(path: str = "Formulario.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Formulario")
    # Detecta columnas esperadas
    categoria_col = next((df.columns[i] for i, c in enumerate(df.columns) if str(c).strip().lower().startswith("categor")), None)
    pregunta_col = next((df.columns[i] for i, c in enumerate(df.columns) if str(c).strip().lower().startswith("pregun")), None)
    calif_col    = next((df.columns[i] for i, c in enumerate(df.columns) if str(c).strip().lower().startswith("calif")), None)
    if not (categoria_col and pregunta_col):
        raise ValueError("La hoja 'Formulario' debe tener columnas 'Categoría' y 'Pregunta'.")
    if not calif_col:
        df["Calificación"] = np.nan
        calif_col = "Calificación"
    df = df.rename(columns={categoria_col: "Categoría", pregunta_col: "Pregunta", calif_col: "Calificación"})
    return df[["Categoría", "Pregunta", "Calificación"]]

# Cargar DF en memoria de sesión una sola vez
if st.session_state.df_form is None:
    try:
        st.session_state.df_form = load_form("Formulario.xlsx")
    except Exception as e:
        st.error(f"No se pudo cargar 'Formulario.xlsx'. Detalle: {e}")
        st.stop()

df_form = st.session_state.df_form.copy()

# Campo de empresa (persistente)
st.markdown("### 0) Datos generales")
st.session_state.empresa = st.text_input("Nombre de la empresa", value=st.session_state.empresa, placeholder="Ej. ACME S.A.S.")

st.markdown("### 1) Califica cada pregunta (1–5)")
updated_scores = list(df_form["Calificación"].fillna(3).astype(int))

with st.form("formulario_calificaciones", clear_on_submit=False):
    for i, row in df_form.iterrows():
        with st.container():
            st.markdown(f"**{row['Categoría']}** — {row['Pregunta']}")
            val = st.slider(" ", min_value=1, max_value=5, value=updated_scores[i], key=f"slider_{i}")
            updated_scores[i] = val
            st.markdown("<div class='hint'>Arrastra para ajustar la calificación</div>", unsafe_allow_html=True)
            st.markdown("<hr>", unsafe_allow_html=True)
    submitted = st.form_submit_button("Guardar respuestas", use_container_width=True)

if submitted:
    df_form["Calificación"] = updated_scores
    st.session_state.df_form = df_form  # persistir en sesión
    st.success("¡Respuestas guardadas en la sesión!")

# DF que usaremos para cálculos/gráficas
df_plot = st.session_state.df_form.copy()
if df_plot["Calificación"].isna().any():
    df_plot["Calificación"] = df_plot["Calificación"].fillna(3)

# =============================
# 2) GRÁFICO RADAR (promedio por categoría) - MÁS GRANDE Y LEGIBLE
# =============================
st.markdown("### 2) Radar de promedios por categoría")
radar_df = df_plot.groupby("Categoría", dropna=False)["Calificación"].mean().reset_index()
categories = radar_df["Categoría"].tolist()
values = radar_df["Calificación"].round(2).tolist()

categories_closed = categories + [categories[0]] if categories else []
values_closed = values + [values[0]] if values else []

if categories:
    fig = go.Figure(
        data=[go.Scatterpolar(r=values_closed, theta=categories_closed, fill='toself', name='Promedio')]
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0,5], tickfont=dict(size=16)),
            angularaxis=dict(tickfont=dict(size=14))
        ),
        font=dict(size=18),
        showlegend=False,
        margin=dict(t=40, b=40, l=40, r=40),
        height=700,
    )
    st.plotly_chart(fig, use_container_width=True, theme=None)
else:
    st.info("No hay categorías para graficar.")

# =============================
# 3) ANÁLISIS CON GPT (recomendaciones y sugerencias)
# =============================
st.markdown("### 3) Análisis de resultados con IA")

def build_summary_text(df: pd.DataFrame) -> str:
    by_cat = df.groupby("Categoría")["Calificación"].agg(["count", "mean"]).round(2)
    lines = [f"Empresa: {st.session_state.empresa or 'N/A'}", "Resumen por categoría:"]
    for idx, r in by_cat.iterrows():
        lines.append(f"- {idx}: n={int(r['count'])}, promedio={r['mean']}")
    global_mean = df["Calificación"].mean().round(2)
    lines.append(f"Promedio general: {global_mean}")
    return "".join(lines)

if st.button("Generar recomendaciones con GPT", key="btn_gpt_recos", use_container_width=True):
    try:
        summary = build_summary_text(df_plot)
        worst = df_plot.sort_values("Calificación").head(5)
        worst_text = "
".join([f"- ({r['Categoría']}) {r['Pregunta']} -> {r['Calificación']}" for _, r in worst.iterrows()])
        prompt = f"""
Eres un consultor experto. Con base en un diagnóstico tipo encuesta (escala 1–5), genera:
1) Hallazgos clave (máx. 6 bullets),
2) 3–5 recomendaciones accionables priorizadas (RICE o impacto/esfuerzo),
3) 3 quick wins (≤30 días),
4) Riesgos si no se actúa,
5) Métricas de seguimiento (KPI y umbrales).

Contexto cuantitativo:
{summary}

Preguntas con peores puntajes:
{worst_text}
"""
        with st.spinner("Analizando…"):
            resp = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
        st.session_state.gpt_analysis = resp.choices[0].message.content
        st.success("Informe de IA generado.")
    except Exception as e:
        st.error(f"Error al generar análisis: {e}")

# Mostrar siempre si existe en sesión
if st.session_state.gpt_analysis:
    st.markdown("#### Informe de IA")
    st.write(st.session_state.gpt_analysis)

# =============================
# 4) Campo URL + Botón para analizar sitio con GPT (persistente)
# =============================
st.markdown("### 4) Análisis de sitio web (opcional)")
st.session_state.site_url = st.text_input("Pega la URL del sitio web a analizar", value=st.session_state.site_url)

def fetch_website_text(target_url: str, timeout: int = 15) -> str:
    try:
        r = requests.get(target_url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:8000]
    except Exception as ex:
        return f"[ERROR] No se pudo obtener el contenido: {ex}"

if st.button("Analizar sitio con GPT", key="btn_gpt_site", use_container_width=True):
    if not st.session_state.site_url:
        st.warning("Por favor ingresa una URL válida.")
    else:
        raw_site_text = fetch_website_text(st.session_state.site_url)
        base_analysis = st.session_state.gpt_analysis or "(Aún no hay análisis base. Usa el botón del paso 3.)"
        prompt_site = f"""
Eres un consultor digital. Toma el diagnóstico cuantitativo y cualitativo previo y contrástalo con el contenido del sitio.
Entrega:
- Señales de alineación/desalineación entre el diagnóstico y el sitio.
- Recomendaciones de UX, contenido y confianza (trust signals).
- 5 acciones web priorizadas (impacto vs. esfuerzo).

[Empresa]
{st.session_state.empresa or 'N/A'}

[Diagnóstico IA previo]
{base_analysis}

[Contenido del sitio]
{raw_site_text}
"""
        with st.spinner("Analizando el sitio…"):
            try:
                resp2 = client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt_site}],
                )
                st.session_state.site_analysis = resp2.choices[0].message.content
                st.success("Análisis del sitio generado.")
            except Exception as e:
                st.error(f"No fue posible analizar el sitio: {e}")

# Mostrar siempre si existe en sesión
if st.session_state.site_analysis:
    st.markdown("#### Hallazgos del sitio")
    st.write(st.session_state.site_analysis)

# =============================
# 5) DESCARGA DEL CONTENIDO COMPLETO EN HTML (formato más conveniente)
# =============================
st.markdown("### 5) Descargar reporte en HTML")

# Prepara fragmentos reutilizables para el HTML exportable
radar_html = ""
if categories:
    # Inserta gráfico interactivo en el HTML del reporte (sin depender de kaleido)
    fig_export = go.Figure(data=[go.Scatterpolar(r=values_closed, theta=categories_closed, fill='toself', name='Promedio')])
    fig_export.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0,5])),
        showlegend=False,
        height=600,
        margin=dict(t=30,b=30,l=30,r=30)
    )
    radar_html = fig_export.to_html(full_html=False, include_plotlyjs='inline')

# Tabla de respuestas bonita
styled_table = (
    st.session_state.df_form.copy()
    .assign(Calificación=lambda d: d["Calificación"].fillna("").astype(str))
    .to_html(index=False, classes="table", border=0)
)

html_css = """
<style>
body { font-family: Montserrat, Arial, sans-serif; padding: 24px; background: #f8f5fb; }
h1, h2, h3 { color: #240531; }
.badge { display:inline-block; background:#ff5722; color:white; padding:6px 12px; border-radius:16px; font-weight:700; }
.table { width:100%; border-collapse: collapse; }
.table th { background:#ff5722; color:#fff; padding:8px; text-align:left; }
.table td { background:#ffffff; border:1px solid #eee; padding:8px; vertical-align: top; }
.section { background:#fff; border:1px solid #eee; border-radius:12px; padding:16px; margin-bottom:16px; }
pre { white-space: pre-wrap; word-wrap: break-word; }
</style>
"""

report_html = f"""
<!DOCTYPE html>
<html lang='es'>
<head>
<meta charset='utf-8'>
<title>Reporte Diagnóstico</title>
{html_css}
</head>
<body>
<h1>Reporte de Diagnóstico</h1>
<p class='badge'>Empresa: {st.session_state.empresa or 'N/A'}</p>

<div class='section'>
  <h2>Respuestas por pregunta</h2>
  {styled_table}
</div>

<div class='section'>
  <h2>Radar de promedios por categoría</h2>
  {radar_html}
</div>

<div class='section'>
  <h2>Informe de IA</h2>
  <pre>{(st.session_state.gpt_analysis or 'Aún no generado.')}</pre>
</div>

<div class='section'>
  <h2>Hallazgos del sitio</h2>
  <p><strong>URL:</strong> {st.session_state.site_url or 'N/D'}</p>
  <pre>{(st.session_state.site_analysis or 'Aún no generado.')}</pre>
</div>

<footer>
  <p style='color:#666'>Reporte generado automáticamente.</p>
</footer>
</body>
</html>
"""

html_bytes = report_html.encode("utf-8")
st.download_button(
    label="Descargar reporte (HTML)",
    data=html_bytes,
    file_name="diagnostico_reporte.html",
    mime="text/html",
    use_container_width=True,
)

# === Footer brand ===
if b64_logo_bottom:
    st.markdown(
        f"""
        <div style='display: flex; justify-content: center; align-items: center; margin-top: 60px; margin-bottom: 40px;'>
            <img src="data:image/png;base64,{b64_logo_bottom}" width="96" height="69"/>
        </div>
        """,
        unsafe_allow_html=True,
    )
