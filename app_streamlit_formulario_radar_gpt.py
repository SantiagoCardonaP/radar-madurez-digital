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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
import textwrap

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

custom_css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Montserrat', sans-serif !important; }}
.stApp {{
    background-image: url("data:image/jpeg;base64,{b64_background}") if {bool(b64_background)} else none;
    background-repeat: no-repeat; background-position: top center; background-size: auto; background-attachment: scroll;
}}
.stApp .main .block-container {{
    background-image: linear-gradient(to bottom, transparent 330px, #240531 330px) !important;
    background-repeat: no-repeat !important; background-size: 100% 100% !important;
    border-radius: 20px !important; padding: 50px !important; max-width: 900px !important; margin: 2rem auto !important;
}}
label, .stSelectbox label, .stMultiSelect label {{ color: white !important; font-size: 0.95em; }}
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
# 1) LECTURA DE FORMULARIO DESDE EXCEL Y UI DE CALIFICACIÓN
# =============================
# Se espera un archivo /mnt/.../Formulario.xlsx con una hoja "Formulario" y columnas:
# A: "Categoría", B: "Pregunta", C: "Calificación" (esta se sobre-escribe en la app)

@st.cache_data(show_spinner=False)
def load_form(path: str = "Formulario.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Formulario")
    # Normaliza nombres esperados
    cols = {c.lower(): c for c in df.columns}
    # Intento robusto
    categoria_col = next((df.columns[i] for i, c in enumerate(df.columns) if str(c).strip().lower().startswith("categor")), None)
    pregunta_col = next((df.columns[i] for i, c in enumerate(df.columns) if str(c).strip().lower().startswith("pregun")), None)
    calif_col    = next((df.columns[i] for i, c in enumerate(df.columns) if str(c).strip().lower().startswith("calif")), None)
    if not (categoria_col and pregunta_col):
        raise ValueError("La hoja 'Formulario' debe tener columnas 'Categoría' y 'Pregunta'.")
    if not calif_col:
        # si no existe, créala
        df["Calificación"] = np.nan
        calif_col = "Calificación"
    # Renombra a canónico
    df = df.rename(columns={categoria_col: "Categoría", pregunta_col: "Pregunta", calif_col: "Calificación"})
    return df[["Categoría", "Pregunta", "Calificación"]]

try:
    df_form = load_form("Formulario.xlsx")
except Exception as e:
    st.error(f"No se pudo cargar 'Formulario.xlsx'. Detalle: {e}")
    st.stop()

st.markdown("### 1) Califica cada pregunta (1–5)")
updated_scores = []

with st.form("formulario_calificaciones"):
    for i, row in df_form.iterrows():
        with st.container():
            st.markdown(f"**{row['Categoría']}** — {row['Pregunta']}")
            val = st.slider(" ", min_value=1, max_value=5, value=int(row["Calificación"]) if not pd.isna(row["Calificación"]) else 3, key=f"slider_{i}")
            updated_scores.append(val)
            st.markdown("<div class='hint'>Arrastra para ajustar la calificación</div>", unsafe_allow_html=True)
            st.markdown("<hr>", unsafe_allow_html=True)
    submitted = st.form_submit_button("Guardar respuestas")

if submitted:
    df_form["Calificación"] = updated_scores
    st.success("¡Respuestas guardadas en la sesión!")

# =============================
# 2) GRÁFICO RADAR (promedio por categoría)
# =============================
if df_form["Calificación"].isna().any():
    # Rellena pendientes con 3 para no romper el radar antes de guardar
    df_plot = df_form.copy()
    df_plot["Calificación"] = df_plot["Calificación"].fillna(3)
else:
    df_plot = df_form.copy()

radar_df = df_plot.groupby("Categoría", dropna=False)["Calificación"].mean().reset_index()

st.markdown("### 2) Radar de promedios por categoría")
categories = radar_df["Categoría"].tolist()
values = radar_df["Calificación"].round(2).tolist()

# Cierra el polígono
categories_closed = categories + [categories[0]] if categories else []
values_closed = values + [values[0]] if values else []

if categories:
    fig = go.Figure(
        data=[go.Scatterpolar(r=values_closed, theta=categories_closed, fill='toself', name='Promedio')]
    )
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,5])), showlegend=False, margin=dict(t=10,b=10,l=10,r=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No hay categorías para graficar.")

# =============================
# 3) ANÁLISIS CON GPT (recomendaciones y sugerencias)
# =============================
st.markdown("### 3) Análisis de resultados con IA")

def build_summary_text(df: pd.DataFrame) -> str:
    by_cat = df.groupby("Categoría")["Calificación"].agg(["count", "mean"]).round(2)
    lines = ["Resumen por categoría:"]
    for idx, r in by_cat.iterrows():
        lines.append(f"- {idx}: n={int(r['count'])}, promedio={r['mean']}")
    global_mean = df["Calificación"].mean().round(2)
    lines.append(f"Promedio general: {global_mean}")
    return "\n".join(lines)

if st.button("Generar recomendaciones con GPT"):
    try:
        summary = build_summary_text(df_plot)
        # Enviaremos un prompt claro con el resumen + preguntas con menor puntaje
        worst = df_plot.sort_values("Calificación").head(5)
        worst_text = "\n".join([f"- ({r['Categoría']}) {r['Pregunta']} -> {r['Calificación']}" for _, r in worst.iterrows()])
        prompt = f"""
Eres un consultor experto. Con base en un diagnóstico tipo encuesta (escala 1–5), genera:
1) Hallazgos clave (máx. 6 bullets),
2) 3–5 recomendaciones accionables priorizadas (RICE o impacto/esfuerzo),
3) 3 quick wins (≤30 días),
4) Riesgos si no se actúa,
5) Métricas de seguimiento (KPI y umbrales).

Contexto cuantitativo:\n{summary}\n\nPreguntas con peores puntajes:\n{worst_text}
"""
        with st.spinner("Analizando…"):
            resp = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
        gpt_analysis = resp.choices[0].message.content
        st.session_state["gpt_analysis"] = gpt_analysis
        st.markdown("#### Informe de IA")
        st.write(gpt_analysis)
    except Exception as e:
        st.error(f"Error al generar análisis: {e}")

# =============================
# 4) Campo URL + Botón para analizar sitio con GPT
# =============================
st.markdown("### 4) Análisis de sitio web (opcional)")
url = st.text_input("Pega la URL del sitio web a analizar")

def fetch_website_text(target_url: str, timeout: int = 15) -> str:
    try:
        r = requests.get(target_url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Quita scripts/estilos
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        # Limita a ~8000 chars para no exceder el modelo
        return text[:8000]
    except Exception as ex:
        return f"[ERROR] No se pudo obtener el contenido: {ex}"

if st.button("Analizar sitio con GPT"):
    if not url:
        st.warning("Por favor ingresa una URL válida.")
    else:
        raw_site_text = fetch_website_text(url)
        base_analysis = st.session_state.get("gpt_analysis", "(Aún no hay análisis base. Usa el botón del paso 3.)")
        prompt_site = f"""
Eres un consultor digital. Toma el diagnóstico cuantitativo y cualitativo previo y contrástalo con el contenido del sitio.
Entrega:
- Señales de alineación/desalineación entre el diagnóstico y el sitio.
- Recomendaciones de UX, contenido y confianza (trust signals).
- 5 acciones web priorizadas (impacto vs. esfuerzo).

[Diagnóstico IA previo]\n{base_analysis}\n\n[Contenido del sitio]\n{raw_site_text}
"""
        with st.spinner("Analizando el sitio…"):
            try:
                resp2 = client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt_site}],
                )
                site_analysis = resp2.choices[0].message.content
                st.session_state["site_analysis"] = site_analysis
                st.markdown("#### Hallazgos del sitio")
                st.write(site_analysis)
            except Exception as e:
                st.error(f"No fue posible analizar el sitio: {e}")

# =============================
# 5) Descargar toda la página en PDF (reporte integral)
# =============================
st.markdown("### 5) Descargar reporte en PDF")

def build_pdf(df_src: pd.DataFrame, radar_bytes: bytes | None, analysis_text: str | None, site_text: str | None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Diagnóstico y Recomendaciones", styles['Title']))
    story.append(Spacer(1, 12))

    # Tabla de respuestas
    story.append(Paragraph("Respuestas por pregunta", styles['Heading2']))
    table_data = [["Categoría", "Pregunta", "Calificación"]]
    for _, r in df_src.iterrows():
        table_data.append([str(r['Categoría']), str(r['Pregunta']), str(int(r['Calificación'])) if not pd.isna(r['Calificación']) else ""]) 
    tbl = Table(table_data, repeatRows=1, colWidths=[4*cm, 9*cm, 3*cm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ff5722')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 16))

    # Radar
    if radar_bytes:
        img_buf = io.BytesIO(radar_bytes)
        story.append(Paragraph("Radar de promedios por categoría", styles['Heading2']))
        story.append(Spacer(1, 6))
        story.append(RLImage(img_buf, width=14*cm, height=14*cm))
        story.append(Spacer(1, 16))

    # Análisis IA
    if analysis_text:
        story.append(Paragraph("Análisis con IA", styles['Heading2']))
        for para in textwrap.fill(analysis_text, 120).split('\n'):
            story.append(Paragraph(para, styles['Normal']))
        story.append(Spacer(1, 12))

    # Análisis del sitio
    if site_text:
        story.append(Paragraph("Hallazgos del sitio", styles['Heading2']))
        for para in textwrap.fill(site_text, 120).split('\n'):
            story.append(Paragraph(para, styles['Normal']))
        story.append(Spacer(1, 12))

    doc.build(story)
    return buf.getvalue()

# Captura el radar como imagen para el PDF
radar_png = None
try:
    # vuelve a generar la figura para exportar (si hay categorías)
    if categories:
        fig_export = go.Figure(data=[go.Scatterpolar(r=values_closed, theta=categories_closed, fill='toself', name='Promedio')])
        fig_export.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,5])), showlegend=False)
        radar_png = fig_export.to_image(format="png", width=1000, height=1000, scale=2)
except Exception:
    radar_png = None

col_a, col_b = st.columns(2)
with col_a:
    if st.button("Generar PDF"):
        try:
            pdf_bytes = build_pdf(
                df_plot,
                radar_png,
                st.session_state.get("gpt_analysis"),
                st.session_state.get("site_analysis"),
            )
            st.session_state["pdf_bytes"] = pdf_bytes
            st.success("PDF generado.")
        except Exception as e:
            st.error(f"No se pudo generar el PDF: {e}")
with col_b:
    if "pdf_bytes" in st.session_state:
        st.download_button(
            label="Descargar reporte PDF",
            data=st.session_state["pdf_bytes"],
            file_name="diagnostico_reporte.pdf",
            mime="application/pdf",
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
