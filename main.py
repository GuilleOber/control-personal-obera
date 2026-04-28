import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
import requests
from bs4 import BeautifulSoup

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Control de Personal MTE", layout="centered")

def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

# ---------------- FONDO ----------------
def fondo():
    st.markdown(
        """
        <style>
        .stApp {
            background-image: url("https://upload.wikimedia.org/wikipedia/commons/6/6e/Escudo_de_la_Provincia_de_Misiones.svg");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }
        .bloque {
            background-color: rgba(255,255,255,0.9);
            padding: 20px;
            border-radius: 15px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

fondo()

# ---------------- DB ----------------
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS empleados (id TEXT, nombre TEXT, foto TEXT)''')
conn.commit()

# ---------------- NOTICIAS CACHE ----------------
@st.cache_data(ttl=604800)  # 1 semana
def obtener_noticia():
    try:
        url = "https://trabajo.misiones.gob.ar/noticias/"
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")

        titulo = soup.find("h2")
        if titulo:
            return titulo.get_text()

        return "No hay noticias disponibles"
    except:
        return "No se pudo cargar noticias"

# ---------------- UI ----------------
st.markdown("<div class='bloque'>", unsafe_allow_html=True)

st.title("📸 Control de Personal MTE")
st.caption(f"🕒 {ahora().strftime('%H:%M:%S')}")

empleados = c.execute("SELECT * FROM empleados").fetchall()

if not empleados:
    st.warning("No hay empleados cargados")
    st.stop()

nombre = st.selectbox("Empleado", [e[1] for e in empleados])
tipo = st.radio("Tipo", ["Entrada", "Salida"])

foto = st.camera_input("Tomar selfie")

# ---------------- ACCIÓN ----------------
if foto:
    img = Image.open(foto)
    draw = ImageDraw.Draw(img)

    fecha = ahora().strftime("%d-%m-%Y")
    hora = ahora().strftime("%H:%M")

    draw.text((10, 10), f"{nombre} {fecha} {hora}", fill=(255, 0, 0))

    path = f"foto_{uuid.uuid4()}.jpg"
    img.save(path)

    # MENSAJE GRANDE
    st.markdown(f"""
    <h1 style='text-align:center; color:green; font-size:60px;'>
    ✅ BIENVENIDO {nombre.upper()}
    </h1>
    """, unsafe_allow_html=True)

    st.markdown("### 📰 Información")

    noticia = obtener_noticia()
    st.info(noticia)

    # RESET automático
    st.rerun()

st.markdown("</div>", unsafe_allow_html=True)
