import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
import requests
from bs4 import BeautifulSoup
import math

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Control Personal MTE", layout="wide")

def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

# ---------------- ESTILO ----------------
st.markdown("""
<style>
.stApp {
    background-image: url("https://upload.wikimedia.org/wikipedia/commons/6/6e/Escudo_de_la_Provincia_de_Misiones.svg");
    background-size: cover;
}
.card {
    background-color: rgba(255,255,255,0.92);
    padding: 20px;
    border-radius: 15px;
}
.big-title {
    text-align:center;
    font-size:50px;
    color:green;
}
</style>
""", unsafe_allow_html=True)

# ---------------- DB PRINCIPAL ----------------
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS empleados (id TEXT, nombre TEXT, foto TEXT)")
conn.commit()

# ---------------- COLA LOCAL ----------------
q_conn = sqlite3.connect("queue.db", check_same_thread=False)
q = q_conn.cursor()

q.execute("""
CREATE TABLE IF NOT EXISTS cola (
    id TEXT,
    nombre TEXT,
    tipo TEXT,
    fecha TEXT,
    hora TEXT
)
""")
q_conn.commit()

# ---------------- NOTICIAS ----------------
@st.cache_data(ttl=604800)
def noticia():
    try:
        r = requests.get("https://trabajo.misiones.gob.ar/noticias/")
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.find("h2").text
    except:
        return "No disponible"

# ---------------- GOOGLE SHEETS ----------------
def conectar():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )

    return gspread.authorize(creds)

def enviar_a_sheets(nombre, tipo, fecha, hora):
    try:
        client = conectar()

        archivo = f"Asistencia_{fecha[:7].replace('-','_')}"
        hoja = fecha

        try:
            ss = client.open(archivo)
        except:
            ss = client.create(archivo)

        try:
            ws = ss.worksheet(hoja)
        except:
            ws = ss.add_worksheet(title=hoja, rows="1000", cols="10")
            ws.append_row(["Nombre","Fecha","Hora","Tipo"])

        ws.append_row([nombre, fecha, hora, tipo])
        return True

    except:
        return False

# ---------------- PROCESAR COLA ----------------
def procesar_cola():
    registros = q.execute("SELECT * FROM cola").fetchall()

    for r in registros:
        ok = enviar_a_sheets(r[1], r[2], r[3], r[4])
        if ok:
            q.execute("DELETE FROM cola WHERE id=?", (r[0],))
            q_conn.commit()

# Ejecutar al inicio
procesar_cola()

# ---------------- UI ----------------
st.title("📸 Control Personal MTE")
st.caption(f"🕒 {ahora().strftime('%H:%M:%S')}")

empleados = c.execute("SELECT * FROM empleados").fetchall()

if not empleados:
    st.warning("No hay empleados cargados")
    st.stop()

nombre = st.selectbox("Empleado", [e[1] for e in empleados])
tipo = st.radio("Tipo", ["Entrada","Salida"])

foto = st.camera_input("Selfie")

if foto:
    now = ahora()
    fecha = now.strftime("%Y-%m-%d")
    hora = now.strftime("%H:%M:%S")

    # Intentar enviar
    ok = enviar_a_sheets(nombre, tipo, fecha, hora)

    if not ok:
        # guardar en cola
        q.execute("INSERT INTO cola VALUES (?,?,?,?,?)",
                  (str(uuid.uuid4()), nombre, tipo, fecha, hora))
        q_conn.commit()
        st.warning("Guardado en cola (sin internet)")

    else:
        st.success("Guardado en Google Sheets")

    st.markdown(f"<div class='big-title'>✅ BIENVENIDO {nombre.upper()}</div>", unsafe_allow_html=True)

    st.info(noticia())

    st.rerun()
