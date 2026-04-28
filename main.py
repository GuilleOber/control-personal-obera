import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
from bs4 import BeautifulSoup
import math
import random
from streamlit_js_eval import streamlit_js_eval

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Control Personal MTE", layout="wide")

LAT_OBJ = -27.487748007596725
LON_OBJ = -55.126722244339206
RADIO = 100

def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

# ---------------- ARTICULOS LEY ----------------
articulos_ley = [
    "Art. 14: El trabajo es protegido por la ley.",
    "Art. 21: Existe contrato de trabajo cuando una persona realiza actos a favor de otra.",
    "Art. 62: Las partes deben obrar con buena fe.",
    "Art. 74: El empleador debe garantizar condiciones dignas.",
    "Art. 84: El trabajador debe cumplir con diligencia.",
    "Art. 103: Se considera remuneración todo ingreso del trabajador.",
    "Art. 197: Jornada máxima 8 horas diarias.",
]

def articulo_del_dia():
    dia = ahora().timetuple().tm_yday
    return articulos_ley[dia % len(articulos_ley)]

# ---------------- NOTICIA ----------------
@st.cache_data(ttl=604800)
def obtener_noticia():
    try:
        r = requests.get("https://trabajo.misiones.gob.ar/noticias/", timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")

        for t in soup.find_all(["h2","h3"]):
            txt = t.get_text(strip=True)
            if len(txt) > 20:
                return txt

        return articulo_del_dia()
    except:
        return articulo_del_dia()

# ---------------- DISTANCIA ----------------
def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ---------------- DB ----------------
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS empleados (id TEXT, nombre TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS registros (id TEXT, nombre TEXT, tipo TEXT, fecha TEXT, hora TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS config (id INTEGER, pass TEXT, geo INTEGER)")
conn.commit()

if not c.execute("SELECT * FROM config").fetchone():
    c.execute("INSERT INTO config VALUES (1,'admin',1)")
    conn.commit()

config = c.execute("SELECT * FROM config").fetchone()

# ---------------- SESION ----------------
if "admin" not in st.session_state:
    st.session_state.admin = False
if "geo_estado" not in st.session_state:
    st.session_state.geo_estado = "inicio"

# ---------------- MENU ----------------
menu = st.sidebar.radio("Menú", ["Asistencia", "Admin"])

# =========================================================
# 📸 ASISTENCIA
# =========================================================
if menu == "Asistencia":

    st.subheader("📸 Control de Asistencia")
    st.caption(f"🕒 {ahora().strftime('%H:%M:%S')}")

    st.markdown("### 📰 Información")
    st.info(obtener_noticia())

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    if not empleados:
        st.warning("No hay empleados")
        st.stop()

    nombre = st.selectbox("Empleado", [e[1] for e in empleados])
    tipo = st.radio("Tipo", ["Entrada", "Salida"])

    geo_activa = bool(config[2])

    # 👇 CLAVE: SI GEO DESACTIVADA → PERMITIR DIRECTO
    permitido = not geo_activa

    lat = lon = None

    if geo_activa:

        st.markdown("### 📍 Validación de ubicación")

        if st.session_state.geo_estado == "inicio":
            st.warning("Validar ubicación")
            if st.button("📍 Activar ubicación"):
                st.session_state.geo_estado = "obteniendo"
                st.rerun()
            permitido = False

        elif st.session_state.geo_estado == "obteniendo":
            lat = streamlit_js_eval(js_expressions="navigator.geolocation.getCurrentPosition((p)=>p.coords.latitude)")
            lon = streamlit_js_eval(js_expressions="navigator.geolocation.getCurrentPosition((p)=>p.coords.longitude)")

            if lat and lon:
                st.session_state.geo_estado = "validando"
            else:
                st.session_state.geo_estado = "error"

            st.rerun()
            permitido = False

        elif st.session_state.geo_estado == "validando":
            dist = distancia_metros(LAT_OBJ, LON_OBJ, lat, lon)

            if dist <= RADIO:
                st.success(f"Ubicación válida ({int(dist)} m)")
                permitido = True
            else:
                permitido = False
                st.error("Fuera de zona")

        elif st.session_state.geo_estado == "error":
            permitido = False
            st.error("No se pudo obtener ubicación")

            if st.button("Reintentar"):
                st.session_state.geo_estado = "inicio"
                st.rerun()

    # 📸 FOTO (ya no depende de geo si está desactivada)
    foto = st.camera_input("Selfie") if permitido else None

    if foto:
        now = ahora()

        c.execute("INSERT INTO registros VALUES (?,?,?,?,?)",
                  (str(uuid.uuid4()), nombre, tipo,
                   now.strftime("%Y-%m-%d"),
                   now.strftime("%H:%M:%S")))
        conn.commit()

        st.success(f"Bienvenido {nombre}")
        st.session_state.geo_estado = "inicio"
        st.rerun()

# =========================================================
# 🔐 ADMIN (igual que antes)
# =========================================================
else:

    if not st.session_state.admin:
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")

        if st.button("Ingresar"):
            if user == "admin" and pwd == config[1]:
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Error")

    else:
        tab1, tab2 = st.tabs(["Empleados", "Seguridad"])

        with tab1:
            nuevo = st.text_input("Nuevo empleado")
            if st.button("Agregar"):
                c.execute("INSERT INTO empleados VALUES (?,?)",
                          (str(uuid.uuid4()), nuevo))
                conn.commit()
                st.rerun()

        with tab2:
            geo_toggle = st.toggle("Geolocalización", value=bool(config[2]))

            if st.button("Guardar"):
                c.execute("UPDATE config SET geo=? WHERE id=1", (int(geo_toggle),))
                conn.commit()
                st.success("Guardado")
