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
RADIO = 100  # metros

def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

# ---------------- NOTICIA CACHEADA ----------------
@st.cache_data(ttl=604800)
def obtener_noticia():
    try:
        url = "https://trabajo.misiones.gob.ar/noticias/"
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        titulos = soup.find_all(["h2","h3"])
        for t in titulos:
            texto = t.get_text(strip=True)
            if len(texto) > 20:
                return texto

        return "No se encontró noticia"
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

c.execute("""
CREATE TABLE IF NOT EXISTS empleados (
    id TEXT,
    nombre TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS registros (
    id TEXT,
    nombre TEXT,
    tipo TEXT,
    fecha TEXT,
    hora TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS config (
    id INTEGER,
    pass TEXT,
    geo INTEGER
)
""")

conn.commit()

if not c.execute("SELECT * FROM config").fetchone():
    c.execute("INSERT INTO config VALUES (1,'admin',1)")
    conn.commit()

config = c.execute("SELECT * FROM config").fetchone()

# ---------------- SESION ----------------
if "admin" not in st.session_state:
    st.session_state.admin = False

# ---------------- MENU ----------------
menu = st.sidebar.radio("Menú", ["Asistencia", "Admin"])

# =========================================================
# 📸 ASISTENCIA
# =========================================================
if menu == "Asistencia":

    st.subheader("📸 Control de Asistencia")
    st.caption(f"🕒 {ahora().strftime('%H:%M:%S')}")

    # 📰 noticia arriba
    st.markdown("### 📰 Última noticia")
    st.info(obtener_noticia())

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    if not empleados:
        st.warning("No hay empleados cargados")
        st.stop()

    nombre = st.selectbox("Empleado", [e[1] for e in empleados])
    tipo = st.radio("Tipo", ["Entrada", "Salida"])

    geo_activa = bool(config[2])

    permitido = True
    lat = None
    lon = None

    if geo_activa:
        lat = streamlit_js_eval(
            js_expressions="navigator.geolocation.getCurrentPosition((p)=>p.coords.latitude)"
        )
        lon = streamlit_js_eval(
            js_expressions="navigator.geolocation.getCurrentPosition((p)=>p.coords.longitude)"
        )

        if lat and lon:
            dist = distancia_metros(LAT_OBJ, LON_OBJ, lat, lon)
            st.write(f"📍 Distancia: {int(dist)} m")

            if dist > RADIO:
                permitido = False
                st.error("❌ Fuera de zona permitida")
        else:
            permitido = False
            st.warning("⚠️ Activá la ubicación del dispositivo")

    foto = st.camera_input("Selfie") if permitido else None

    if foto:
        now = ahora()
        fecha = now.strftime("%Y-%m-%d")
        hora = now.strftime("%H:%M:%S")

        c.execute(
            "INSERT INTO registros VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), nombre, tipo, fecha, hora)
        )
        conn.commit()

        st.success(f"✅ Bienvenido {nombre}")
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
                st.error("Credenciales incorrectas")

    else:
        tab1, tab2, tab3 = st.tabs(["Empleados", "Seguridad", "Reportes"])

        # EMPLEADOS
        with tab1:
            nuevo = st.text_input("Nuevo empleado")

            if st.button("Agregar"):
                if nuevo:
                    c.execute(
                        "INSERT INTO empleados VALUES (?,?)",
                        (str(uuid.uuid4()), nuevo)
                    )
                    conn.commit()
                    st.rerun()

            empleados = c.execute("SELECT * FROM empleados").fetchall()

            for e in empleados:
                col1, col2 = st.columns([3, 1])
                col1.write(e[1])
                if col2.button(f"Eliminar {e[0]}"):
                    c.execute("DELETE FROM empleados WHERE id=?", (e[0],))
                    conn.commit()
                    st.rerun()

        # SEGURIDAD + GEO
        with tab2:
            nueva = st.text_input("Nueva contraseña", type="password")

            geo_toggle = st.toggle(
                "Requerir geolocalización",
                value=bool(config[2])
            )

            if st.button("Guardar cambios"):
                if nueva:
                    c.execute("UPDATE config SET pass=? WHERE id=1", (nueva,))
                c.execute("UPDATE config SET geo=? WHERE id=1", (int(geo_toggle),))
                conn.commit()
                st.success("Configuración actualizada")

        # REPORTES
        with tab3:
            st.subheader("📊 Reporte mensual")

            registros = c.execute("SELECT * FROM registros").fetchall()

            if not registros:
                st.warning("No hay datos")
            else:
                df = pd.DataFrame(
                    registros,
                    columns=["id", "nombre", "tipo", "fecha", "hora"]
                )

                df["fecha"] = pd.to_datetime(df["fecha"])

                resumen = df.groupby("nombre").agg({
                    "fecha": "nunique",
                    "id": "count"
                }).reset_index()

                resumen.columns = ["Empleado", "Días trabajados", "Registros"]

                st.dataframe(resumen)

                csv = df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    label="⬇️ Descargar registros (CSV)",
                    data=csv,
                    file_name="asistencia.csv",
                    mime="text/csv"
                )
