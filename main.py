import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from PIL import Image, ImageDraw
import random
import math

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
    admin_pass TEXT,
    geo_activa INTEGER,
    radio INTEGER
)''')

conn.commit()

# INIT CONFIG
if not c.execute("SELECT * FROM config").fetchone():
    c.execute("INSERT INTO config VALUES (1, 'admin', 1, 100)")
    conn.commit()

# ---------------- CONFIG LOAD ----------------
config = c.execute("SELECT * FROM config").fetchone()
admin_pass = config[1]
geo_activa = config[2]
radio = config[3]

# ---------------- FRASES ----------------
frases = [
    "El trabajo en equipo hace la diferencia",
    "Juntos logramos más",
    "La unión hace la fuerza",
    "Cada esfuerzo cuenta"
]

# ---------------- GEO ----------------
LAT_REF = -27.487735745039803
LON_REF = -55.126748202517426

def distancia(lat1, lon1):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(LAT_REF)
    dphi = math.radians(LAT_REF - lat1)
    dlambda = math.radians(LON_REF - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ---------------- SESIÓN ----------------
if "admin" not in st.session_state:
    st.session_state.admin = False

# ---------------- MENÚ ----------------
menu = st.sidebar.radio("Menú", ["📸 Asistencia", "🔐 Admin", "📥 Instalar App"])

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

        st.success(f"✅ Bienvenido {nombre}")
        st.info(random.choice(frases))
        st.image(path)

        # RESET AUTOMÁTICO
        st.rerun()

# =========================================================
# 🔐 ADMIN
# =========================================================
elif menu == "🔐 Admin":

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

        tab1, tab2, tab3 = st.tabs(["👥 Empleados", "⚙️ Config", "🔐 Seguridad"])

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

        # ---------------- CONFIG ----------------
        with tab2:
            st.subheader("Configuración")

            geo = st.toggle("Geolocalización obligatoria", value=bool(geo_activa))
            rad = st.slider("Radio permitido (metros)", 50, 300, radio)

            if st.button("Guardar configuración"):
                c.execute("UPDATE config SET geo_activa=?, radio=? WHERE id=1",
                          (int(geo), rad))
                conn.commit()
                st.success("Guardado")
                st.rerun()

        # ---------------- SEGURIDAD ----------------
        with tab3:
            st.subheader("Cambiar contraseña")

            nueva = st.text_input("Nueva contraseña", type="password")

            if st.button("Guardar contraseña"):
                c.execute("UPDATE config SET admin_pass=? WHERE id=1", (nueva,))
                conn.commit()
                st.success("Contraseña actualizada")

# =========================================================
# 📥 INSTALAR
# =========================================================
else:
    st.subheader("Instalar aplicación")

    st.markdown("""
### 📱 Cómo instalar

**Android:**
1. Abrir menú ⋮
2. "Agregar a pantalla de inicio"

**iPhone:**
1. Botón compartir
2. "Añadir a inicio"
""")
