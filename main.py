import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from PIL import Image, ImageDraw
import random
import requests
from bs4 import BeautifulSoup

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Control de Personal MTE", layout="centered")

def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

# ---------------- DB ----------------
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS empleados (id TEXT, nombre TEXT, foto TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY,
    admin_pass TEXT
)''')

conn.commit()

if not c.execute("SELECT * FROM config").fetchone():
    c.execute("INSERT INTO config VALUES (1, 'admin')")
    conn.commit()

admin_pass = c.execute("SELECT admin_pass FROM config").fetchone()[0]

# ---------------- NOTICIAS ----------------
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

# ---------------- SESIÓN ----------------
if "admin" not in st.session_state:
    st.session_state.admin = False

# ---------------- MENÚ ----------------
menu = st.sidebar.radio("Menú", ["📸 Asistencia", "🔐 Admin"])

# =========================================================
# 📸 ASISTENCIA
# =========================================================
if menu == "📸 Asistencia":

    st.title("📸 Control de Personal MTE")
    st.caption(f"🕒 {ahora().strftime('%H:%M:%S')}")

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    if not empleados:
        st.warning("No hay empleados cargados")
        st.stop()

    nombre = st.selectbox("Empleado", [e[1] for e in empleados])
    tipo = st.radio("Tipo", ["Entrada", "Salida"])

    foto = st.camera_input("Tomar selfie")

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
        <h1 style='text-align:center; color:green;'>
        ✅ BIENVENIDO {nombre.upper()}
        </h1>
        """, unsafe_allow_html=True)

        st.markdown("### 📰 Última noticia")

        noticia = obtener_noticia()
        st.info(noticia)

        # RESET
        st.rerun()

# =========================================================
# 🔐 ADMIN
# =========================================================
else:

    if not st.session_state.admin:

        st.subheader("Login Admin")

        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")

        if st.button("Ingresar"):
            if user == "admin" and pwd == admin_pass:
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

    else:

        tab1, tab2 = st.tabs(["👥 Empleados", "🔐 Seguridad"])

        # ---------------- EMPLEADOS ----------------
        with tab1:
            st.subheader("Gestión de empleados")

            nombre = st.text_input("Nombre nuevo")
            foto = st.file_uploader("Foto")

            if st.button("Agregar"):
                if nombre and foto:
                    path = f"{uuid.uuid4()}.jpg"
                    Image.open(foto).save(path)

                    c.execute("INSERT INTO empleados VALUES (?, ?, ?)",
                              (str(uuid.uuid4()), nombre, path))
                    conn.commit()
                    st.rerun()

            empleados = c.execute("SELECT * FROM empleados").fetchall()

            for emp in empleados:
                col1, col2 = st.columns([3,1])
                col1.write(emp[1])
                if col2.button(f"Eliminar {emp[0]}"):
                    c.execute("DELETE FROM empleados WHERE id=?", (emp[0],))
                    conn.commit()
                    st.rerun()

        # ---------------- SEGURIDAD ----------------
        with tab2:
            st.subheader("Cambiar contraseña")

            nueva = st.text_input("Nueva contraseña", type="password")

            if st.button("Guardar contraseña"):
                c.execute("UPDATE config SET admin_pass=? WHERE id=1", (nueva,))
                conn.commit()
                st.success("Contraseña actualizada")
