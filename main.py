import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Control Personal MTE", layout="wide")

def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

# ---------------- NOTICIA CACHEADA ----------------
@st.cache_data(ttl=604800)  # 1 semana
def obtener_noticia():
    try:
        url = "https://trabajo.misiones.gob.ar/noticias/"
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        titulo = soup.find("h2")
        if not titulo:
            titulo = soup.find("h3")

        return titulo.text.strip() if titulo else "No hay noticias disponibles"
    except:
        return "No se pudo cargar la noticia"

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
    pass TEXT
)
""")

conn.commit()

if not c.execute("SELECT * FROM config").fetchone():
    c.execute("INSERT INTO config VALUES (1,'admin')")
    conn.commit()

config = c.execute("SELECT * FROM config").fetchone()

# ---------------- SESION ----------------
if "admin" not in st.session_state:
    st.session_state.admin = False

# ---------------- MENU ----------------
menu = st.sidebar.radio("Menú", ["Asistencia","Admin"])

# =========================================================
# 📸 ASISTENCIA
# =========================================================
if menu == "Asistencia":

    st.subheader("📸 Control de Asistencia")
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

        c.execute("INSERT INTO registros VALUES (?,?,?,?,?)",
                  (str(uuid.uuid4()), nombre, tipo, fecha, hora))
        conn.commit()

        st.success(f"✅ Bienvenido {nombre}")

        # 📰 NOTICIA
        st.markdown("### 📰 Última noticia")
        st.info(obtener_noticia())

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
        tab1, tab2, tab3 = st.tabs(["Empleados","Seguridad","Reportes"])

        # EMPLEADOS
        with tab1:
            nuevo = st.text_input("Nuevo empleado")

            if st.button("Agregar"):
                if nuevo:
                    c.execute("INSERT INTO empleados VALUES (?,?)",
                              (str(uuid.uuid4()), nuevo))
                    conn.commit()
                    st.rerun()

            empleados = c.execute("SELECT * FROM empleados").fetchall()

            for e in empleados:
                col1,col2 = st.columns([3,1])
                col1.write(e[1])
                if col2.button(f"Eliminar {e[0]}"):
                    c.execute("DELETE FROM empleados WHERE id=?", (e[0],))
                    conn.commit()
                    st.rerun()

        # SEGURIDAD
        with tab2:
            nueva = st.text_input("Nueva contraseña", type="password")

            if st.button("Cambiar contraseña"):
                if nueva:
                    c.execute("UPDATE config SET pass=? WHERE id=1",(nueva,))
                    conn.commit()
                    st.success("Contraseña actualizada")

        # REPORTES
        with tab3:
            st.subheader("📊 Reporte mensual")

            registros = c.execute("SELECT * FROM registros").fetchall()

            if not registros:
                st.warning("No hay datos")
            else:
                df = pd.DataFrame(registros, columns=["id","nombre","tipo","fecha","hora"])

                df["fecha"] = pd.to_datetime(df["fecha"])

                resumen = df.groupby("nombre").agg({
                    "fecha": "nunique",
                    "id": "count"
                }).reset_index()

                resumen.columns = ["Empleado","Días trabajados","Registros"]

                st.dataframe(resumen)

                # DESCARGA CSV
                csv = df.to_csv(index=False).encode('utf-8')

                st.download_button(
                    "⬇️ Descargar registros (CSV)",
                    csv,
                    "asistencia.csv",
                    "text/csv"
                )
                )
