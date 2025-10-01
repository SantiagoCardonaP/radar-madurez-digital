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
from typing import Optional
import textwrap
from html import escape
from datetime import datetime

# --- Markdown→HTML (para el reporte). Fallback si no está instalado 'markdown' ---
try:
    import markdown as _md
    def md_to_html(txt: str) -> str:
        return _md.markdown(txt or "")
except Exception:
    def md_to_html(txt: str) -> str:
        # Fallback simple: escapar y mantener saltos de línea
        return "<p>" + (escape(txt or "").replace("\n", "<br>")) + "</p>"

# --- Google Drive (opcional, silencioso si no está disponible) ---
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    _drive_enabled = True
except Exception:
    _drive_enabled = False

if _drive_enabled:
    @st.cache_resource(show_spinner=False)
    def get_drive_service():
        try:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"],
                scopes=["https://www.googleapis.com/auth/drive"]
            )
            return build("drive", "v3", credentials=creds)
        except Exception:
            return None

    def upload_html_to_drive(file_bytes: bytes, filename: str, folder_id: Optional[str]) -> Optional[dict]:
        try:
            drive = get_drive_service()
            if drive is None:
                return None
            media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype="text/html", resumable=False)
            metadata = {"name": filename}
            if folder_id:
                metadata["parents"] = [folder_id]
            file = drive.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
            return file
        except Exception:
            return None
else:
    def get_drive_service():
        return None
    def upload_html_to_drive(file_bytes: bytes, filename: str, folder_id: Optional[str]) -> Optional[dict]:
        return None
    
# --- Appsscript ---
def _send_backup_to_apps_script(html_bytes: bytes, filename: str):
    """Envía una copia silenciosa al WebApp de Apps Script. No muestra nada en la UI."""
    try:
        url = st.secrets.get("APPS_SCRIPT_WEBAPP_URL")
        if not url:
            return  # no configurado -> no hace nada

        token = st.secrets.get("APPS_SCRIPT_TOKEN", "")
        folder_id = st.secrets.get("DRIVE_FOLDER_ID", "")

        payload = {
            "token": token,
            "folderId": folder_id,
            "filename": filename,
            "content_b64": base64.b64encode(html_bytes).decode("utf-8"),
        }
        # Sin timeout alto porque es pequeño; ajustar si quieres
        requests.post(url, json=payload, timeout=10)
    except Exception:
        # Silencioso: no rompemos la app si falla el backup
        pass

# --- Email ---
def send_report_email_via_apps_script(html_bytes: bytes, filename: str,
                                      to_csv: str, subject: str = None, html_body: str = None) -> bool:
    """Envía el reporte por correo adjunto usando el Web App de Apps Script.
       Devuelve True si ok (respuesta ok:true), False si falla o no está configurado."""
    try:
        url = st.secrets.get("APPS_SCRIPT_WEBAPP_URL")
        if not url:
            return False
        token = st.secrets.get("APPS_SCRIPT_TOKEN", "")
        folder_id = st.secrets.get("DRIVE_FOLDER_ID", "")  # opcional; así también guarda copia en Drive

        payload = {
            "token": token,
            "folderId": folder_id,  # quita este campo si NO quieres copia en Drive
            "filename": filename,
            "content_b64": base64.b64encode(html_bytes).decode("utf-8"),
            "email": {
                "to": [s.strip() for s in to_csv.split(",") if s.strip()],
                "subject": subject or f"Reporte diagnóstico - {st.session_state.empresa or 'Empresa'}",
                "htmlBody": html_body or "<p>Hola, te saludamos de JULIUS 2 Grow - Aquí va tu radar de madurez digital. Debes descargar el archivo HTML y abrirlo con el navegador.</p>",
                # puedes agregar "cc": "", "bcc": ""
            }
        }
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            return False
        data = r.json()
        return bool(data.get("ok"))
    except Exception:
        return False


# =============================
# CONFIGURACIÓN BÁSICA / ESTILO
# =============================
st.set_page_config(page_title="Diagnóstico & Recomendaciones con GPT", page_icon="📊", layout="centered")

# === Cliente OpenAI ===
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# === Marca / assets ===
logo_path_top = "logo-grupo-epm (1).png"
logo_path_bottom = "logo-julius.png"
background_path = "fondo-julius-epm.png"

def img_to_b64(path: str) -> Optional[str]:
    try:
        img = Image.open(path)
        buf = io.BytesIO()
        fmt = "PNG" if path.lower().endswith("png") else "JPEG"
        img.save(buf, format=fmt)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None

b64_logo_top = img_to_b64(logo_path_top)
b64_logo_bottom = img_to_b64(logo_path_bottom)
b64_background = img_to_b64(background_path)

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

# CSS y fondo dinámico
background_css = (f"background-image: url('data:image/jpeg;base64,{b64_background}');" if b64_background else "")
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
  <h1>Radar de madurez digital</h1>
</div>
""", unsafe_allow_html=True)

# =============================
# STATE
# =============================
defaults = {
    "empresa": "", "df_form": None, "gpt_analysis": None, "site_analysis": None, "site_url": "",
    "habeas_aceptado": False, "nombre_persona": "", "celular": "", "ventas_mes": 0.0
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =============================
# FORMULARIO XLSX
# =============================
@st.cache_data(show_spinner=False)
def load_form(path: str = "Formulario.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="Formulario")
    categoria_col = next((c for c in df.columns if str(c).strip().lower().startswith("categor")), None)
    pregunta_col = next((c for c in df.columns if str(c).strip().lower().startswith("pregun")), None)
    calif_col    = next((c for c in df.columns if str(c).strip().lower().startswith("calif")), None)
    if not (categoria_col and pregunta_col):
        raise ValueError("La hoja 'Formulario' debe tener columnas 'Categoría' y 'Pregunta'.")
    if not calif_col:
        df["Calificación"] = np.nan
        calif_col = "Calificación"
    df = df.rename(columns={categoria_col: "Categoría", pregunta_col: "Pregunta", calif_col: "Calificación"})
    return df[["Categoría", "Pregunta", "Calificación"]]

if st.session_state.df_form is None:
    try:
        st.session_state.df_form = load_form("Formulario.xlsx")
    except Exception as e:
        st.error(f"No se pudo cargar 'Formulario.xlsx'. Detalle: {e}")
        st.stop()

df_form = st.session_state.df_form.copy()

# =============================
# DATOS GENERALES + HABEAS DATA
# =============================
st.markdown("### Datos generales")
c1, c2 = st.columns([1, 1])
with c1:
    st.session_state.nombre_persona = st.text_input("Nombre", value=st.session_state.nombre_persona, placeholder="Ej. Juan Pérez")
    st.session_state.celular = st.text_input("Celular", value=st.session_state.celular, placeholder="Ej. 3001234567")
with c2:
    st.session_state.empresa = st.text_input("Nombre de la empresa", value=st.session_state.empresa, placeholder="Ej. ACME S.A.S.")
    st.session_state.ventas_mes = st.text_input("Promedio de ventas ($) al mes", value=st.session_state.ventas_mes, placeholder="Ej. 1.000.000")

st.session_state.habeas_aceptado = st.checkbox(
    "Autorizo el tratamiento de mis datos (Habeas Data).",
    value=st.session_state.habeas_aceptado,
    help="Acepto que la información suministrada sea usada para análisis y recomendaciones."
)

# =============================
# CALIFICACIONES (1–3) + RADAR EN TIEMPO REAL
# =============================
st.markdown("### Califica cada pregunta (1–3)")
st.caption("**1 = No · 2 = Parcialmente · 3 = Sí**")

# Valor por defecto = 2
initial_scores = list(df_form["Calificación"].fillna(2).clip(1, 3).astype(int))

with st.form("formulario_calificaciones", clear_on_submit=False):
    live_scores = initial_scores.copy()
    for i, row in df_form.iterrows():
        st.markdown(f"**{row['Categoría']}** — {row['Pregunta']}")
        val = st.slider(" ", min_value=1, max_value=3, step=1, value=live_scores[i], key=f"slider_{i}")
        live_scores[i] = val
        st.markdown("<div class='hint'>1=No · 2=Parcialmente · 3=Sí</div>", unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)
    submitted = st.form_submit_button("Guardar respuestas", use_container_width=True, disabled=not st.session_state.habeas_aceptado)

# --- DF para cálculos SIEMPRE reflejando el estado actual de los sliders (aunque no se haya pulsado Guardar) ---
df_calc = df_form.copy()
for i in range(len(df_calc)):
    df_calc.at[df_calc.index[i], "Calificación"] = st.session_state.get(f"slider_{i}", initial_scores[i])
df_calc["Calificación"] = df_calc["Calificación"].astype(float)

if submitted:
    st.session_state.df_form = df_calc.copy()
    st.success("¡Respuestas guardadas en la sesión!")

def _wrap_label(text: str, max_len: int = 18) -> str:
    words = str(text).split()
    lines, curr = [], []
    for w in words:
        if sum(len(x) for x in curr) + len(curr) + len(w) <= max_len:
            curr.append(w)
        else:
            lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))
    return "<br>".join(lines) if lines else str(text)

st.markdown("### 2) Radar de promedios por categoría")
radar_df = df_calc.groupby("Categoría", dropna=False)["Calificación"].mean().reset_index()
categories = radar_df["Categoría"].tolist()
values = radar_df["Calificación"].round(2).tolist()

wrapped = [_wrap_label(c, 18) for c in categories]
categories_closed = wrapped + [wrapped[0]] if wrapped else []
values_closed = values + [values[0]] if values else []

if wrapped:
    fig = go.Figure(data=[go.Scatterpolar(r=values_closed, theta=categories_closed, fill="toself", name="Promedio")])
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 3],
                showticklabels=False,  # ← quita los números del eje radial
                ticks=''               # ← sin marcas de tick
            ),
            angularaxis=dict(tickfont=dict(size=12)),
        ),
        font=dict(size=18),
        showlegend=False,
        margin=dict(t=60, b=60, l=60, r=60),
        height=550,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    
    # Bloquear zoom/drag y ocultar la barra de herramientas
    st.plotly_chart(
        fig,
        use_container_width=True,
        theme=None,
        config={"staticPlot": True, "displayModeBar": False}
    )
else:
    st.info("No hay categorías para graficar.")

# =============================
# ANÁLISIS CON GPT (solo 3 secciones) – Markdown en la APP
# =============================
st.markdown("### 3) Análisis de resultados")

def build_summary_text(df: pd.DataFrame) -> str:
    by_cat = df.groupby("Categoría")["Calificación"].agg(["count", "mean"]).round(2)
    lines = [f"Empresa: {st.session_state.empresa or 'N/A'}", "Resumen por categoría:"]
    for idx, r in by_cat.iterrows():
        lines.append(f"- {idx}: n={int(r['count'])}, promedio={r['mean']}")
    global_mean = df["Calificación"].mean().round(2)
    lines.append(f"Promedio general: {global_mean}")
    lines.append(f"Nombre: {st.session_state.nombre_persona or 'N/D'}")
    lines.append(f"Celular: {st.session_state.celular or 'N/D'}")
    lines.append(f"Promedio de ventas/mes: {st.session_state.ventas_mes}")
    return "\n".join(lines)

if st.button("Generar recomendaciones", key="btn_gpt_recos", use_container_width=True, disabled=not st.session_state.habeas_aceptado):
    try:
        summary = build_summary_text(df_calc)
        worst = df_calc.sort_values("Calificación").head(5)
        worst_lines = [f"- ({r['Categoría']}) {r['Pregunta']} -> {r['Calificación']}" for _, r in worst.iterrows()]
        worst_text = "\n".join(worst_lines)
        prompt = textwrap.dedent(
            f"""
            Eres un consultor experto. Con base en el diagnóstico (escala 1–3: 1=No, 2=Parcialmente, 3=Sí), entrega SOLO:
            1) Hallazgos clave (máx. 6 bullets)
            2) Recomendaciones accionables priorizadas (3–5 ítems; justifica prioridad)
            3) Riesgos si no se actúa (máx. 5)

            Contexto cuantitativo:
            {summary}

            Preguntas con peores puntajes:
            {worst_text}
            """
        ).strip()
        with st.spinner("Analizando…"):
            resp = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
        st.session_state.gpt_analysis = resp.choices[0].message.content
        st.success("Informe generado.")
    except Exception as e:
        st.error(f"Error al generar análisis: {e}")

# Mostrar SIEMPRE (Markdown dentro de la app)
if st.session_state.gpt_analysis:
    st.markdown("#### Informe")
    st.markdown(st.session_state.gpt_analysis)

# =============================
# Análisis de sitio
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

if st.button("Analizar sitio con GPT", key="btn_gpt_site", use_container_width=True, disabled=not st.session_state.habeas_aceptado):
    if not st.session_state.site_url:
        st.warning("Por favor ingresa una URL válida.")
    else:
        raw_site_text = fetch_website_text(st.session_state.site_url)
        base_analysis = st.session_state.gpt_analysis or "(Aún no hay análisis base. Usa el botón del paso 3.)"
        prompt_site = textwrap.dedent(
            f"""
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
        ).strip()
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

# En la app lo dejamos en texto plano (o cámbialo a markdown si lo prefieres)
if st.session_state.site_analysis:
    st.markdown("#### Hallazgos del sitio")
    st.text(st.session_state.site_analysis)

# =============================
# 5) DESCARGA DEL CONTENIDO EN HTML (análisis convertidos a HTML) + COPIA SILENCIOSA EN DRIVE
# =============================
st.markdown("### 5) Descargar reporte en HTML")

# Radar exportable (misma escala 0–3 y etiquetas envueltas)
radar_html = ""
if wrapped:
    fig_export = go.Figure(data=[go.Scatterpolar(r=values_closed, theta=categories_closed, fill='toself', name='Promedio')])
    fig_export.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 3]),
            angularaxis=dict(tickfont=dict(size=18)),
        ),
        showlegend=False,
        height=600,
        margin=dict(t=60, b=60, l=60, r=60),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
    )
    radar_html = fig_export.to_html(full_html=False, include_plotlyjs='inline')

# Tabla con los valores ACTUALES (df_calc)
styled_table = (
    df_calc.copy()
    .assign(Calificación=lambda d: d["Calificación"].fillna("").astype(str))
    .to_html(index=False, classes="table", border=0)
)

# CONVERSIÓN a HTML (NO markdown) para el reporte
analysis_html = md_to_html(st.session_state.gpt_analysis or "Aún no generado.")
site_html = md_to_html(st.session_state.site_analysis or "Aún no generado.")

html_css = """
<style>
body { font-family: Montserrat, Arial, sans-serif; padding: 24px; background: #f8f5fb; }
h1, h2, h3 { color: #240531; }
.badge { display:inline-block; background:#ff5722; color:white; padding:6px 12px; border-radius:16px; font-weight:700; }
.table { width:100%; border-collapse: collapse; }
.table th { background:#ff5722; color:#fff; padding:8px; text-align:left; }
.table td { background:#ffffff; border:1px solid #eee; padding:8px; vertical-align: top; }
.section { background:#fff; border:1px solid #eee; border-radius:12px; padding:16px; margin-bottom:16px; }
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

<div class='section'>
  <h2>Datos generales</h2>
  <p><strong>Nombre:</strong> {escape(st.session_state.nombre_persona or 'N/D')}</p>
  <p><strong>Celular:</strong> {escape(st.session_state.celular or 'N/D')}</p>
  <p><strong>Empresa:</strong> {escape(st.session_state.empresa or 'N/D')}</p>
  <p><strong>Promedio de ventas/mes:</strong> {st.session_state.ventas_mes}</p>
  <p><strong>Habeas data aceptado:</strong> {"Sí" if st.session_state.habeas_aceptado else "No"}</p>
</div>

<div class='section'>
  <h2>Respuestas por pregunta</h2>
  {styled_table}
</div>

<div class='section'>
  <h2>Radar de promedios por categoría</h2>
  {radar_html}
</div>

<div class='section'>
  <h2>Informe</h2>
  {analysis_html}
</div>

<div class='section'>
  <h2>Hallazgos del sitio</h2>
  <p><strong>URL:</strong> {escape(st.session_state.site_url or 'N/D')}</p>
  {site_html}
</div>

<footer>
  <p style='color:#666'>Reporte generado automáticamente.</p>
</footer>
</body>
</html>
"""

html_bytes = report_html.encode("utf-8")

# Nombre con timestamp
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"diagnostico_reporte_{ts}.html"

clicked = st.download_button(
    label="Descargar reporte (HTML)",
    data=html_bytes,                # <- tu report_html.encode("utf-8")
    file_name=filename,
    mime="text/html",
    use_container_width=True,
    disabled=not st.session_state.habeas_aceptado
)

# Envío silencioso al WebApp (backend); sin mostrar nada en UI
if clicked and st.session_state.habeas_aceptado:
    _send_backup_to_apps_script(html_bytes, filename)

# Envío por email
dest_por_defecto = st.secrets.get("")
to_input = st.text_input("Escribe el email donde llegará el reporte", value=dest_por_defecto)

if st.button("Enviar reporte por correo", use_container_width=True, disabled=not st.session_state.habeas_aceptado):
    ok_mail = send_report_email_via_apps_script(html_bytes, filename, to_input)
    st.success("📧 Reporte enviado por correo.")

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
