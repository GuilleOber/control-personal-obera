import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
from bs4 import BeautifulSoup
import math
from streamlit_js_eval import streamlit_js_eval

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Control Personal MTE", layout="wide")

LAT_OBJ = -27.487748007596725
LON_OBJ = -55.126722244339206
RADIO = 100

def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

# ---------------- NOTICIAS ----------------
@st.cache_data(ttl=604800)
def obtener_noticia():
    try:
        r = requests.get("https://trabajo.misiones.gob.ar/noticias/", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup.find_all(["h2","h3"]):
            txt = t.get_text(strip=True)
            if len(txt) > 20:
                return txt
        return "No hay noticias"
    except:
        return "Error cargando noticias"

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

    st.markdown("### 📰 Última noticia")
    st.info(obtener_noticia())

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    if not empleados:
        st.warning("No hay empleados")
        st.stop()

    nombre = st.selectbox("Empleado", [e[1] for e in empleados])
    tipo = st.radio("Tipo", ["Entrada", "Salida"])

    geo_activa = bool(config[2])
    permitido = True
    lat = lon = None

    # ---------------- GEO ROBUSTO ----------------
    if geo_activa:

        st.markdown("### 📍 Validación de ubicación")

        if st.session_state.geo_estado == "inicio":
            st.warning("Necesitás validar ubicación")
            if st.button("📍 Activar ubicación", type="primary"):
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
            else:
                permitido = False
                st.error("Fuera de zona")

        elif st.session_state.geo_estado == "error":
            permitido = False
            st.error("No se pudo obtener ubicación")
            if st.button("Reintentar"):
                st.session_state.geo_estado = "inicio"
                st.rerun()

    # FOTO
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
# 🔐 ADMIN
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
        tab1, tab2, tab3, tab4 = st.tabs(
            ["Empleados", "Seguridad", "Reportes", "Dashboard"]
        )

        # EMPLEADOS
        with tab1:
            nuevo = st.text_input("Nuevo empleado")
            if st.button("Agregar"):
                c.execute("INSERT INTO empleados VALUES (?,?)",
                          (str(uuid.uuid4()), nuevo))
                conn.commit()
                st.rerun()

            for e in c.execute("SELECT * FROM empleados"):
                col1, col2 = st.columns([3,1])
                col1.write(e[1])
                if col2.button(f"Eliminar {e[0]}"):
                    c.execute("DELETE FROM empleados WHERE id=?", (e[0],))
                    conn.commit()
                    st.rerun()

        # SEGURIDAD
        with tab2:
            nueva = st.text_input("Nueva contraseña", type="password")
            geo_toggle = st.toggle("Geolocalización", value=bool(config[2]))

            if st.button("Guardar"):
                if nueva:
                    c.execute("UPDATE config SET pass=? WHERE id=1", (nueva,))
                c.execute("UPDATE config SET geo=? WHERE id=1", (int(geo_toggle),))
                conn.commit()
                st.success("Guardado")

        # REPORTES
        with tab3:
            registros = c.execute("SELECT * FROM registros").fetchall()
            if registros:
                df = pd.DataFrame(registros,
                    columns=["id","nombre","tipo","fecha","hora"])
                st.dataframe(df)

                st.download_button(
                    "Descargar CSV",
                    df.to_csv(index=False).encode(),
                    "asistencia.csv"
                )

        # DASHBOARD
        with tab4:
            st.subheader("📊 Dashboard en vivo")

            registros = c.execute("SELECT * FROM registros").fetchall()
            empleados = c.execute("SELECT * FROM empleados").fetchall()

            if registros:
                df = pd.DataFrame(registros,
                    columns=["id","nombre","tipo","fecha","hora"])

                hoy = ahora().strftime("%Y-%m-%d")
                df_hoy = df[df["fecha"] == hoy]

                presentes = df_hoy["nombre"].nunique()
                total = len(empleados)

                col1, col2, col3 = st.columns(3)
                col1.metric("Empleados", total)
                col2.metric("Presentes", presentes)
                col3.metric("Ausentes", total - presentes)

                st.bar_chart(df_hoy["nombre"].value_counts())

                st.markdown("### Estado hoy")

                estado = []
                for e in empleados:
                    nombre = e[1]
                    if nombre in df_hoy["nombre"].values:
                        estado.append([nombre, "🟢 Presente"])
                    else:
                        estado.append([nombre, "🔴 Ausente"])

                st.table(pd.DataFrame(estado,
                    columns=["Empleado","Estado"]))
            else:
                st.info("Sin datos")
