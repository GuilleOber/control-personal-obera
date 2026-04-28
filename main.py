import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
import requests
from bs4 import BeautifulSoup

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Control Personal MTE", layout="wide")

def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

# ---------------- DB ----------------
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS empleados (id TEXT, nombre TEXT, foto TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS config (id INTEGER, pass TEXT, geo INTEGER, radio INTEGER)")
conn.commit()

if not c.execute("SELECT * FROM config").fetchone():
    c.execute("INSERT INTO config VALUES (1,'admin',1,100)")
    conn.commit()

config = c.execute("SELECT * FROM config").fetchone()

# ---------------- COLA ----------------
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
        except Exception as e:
            st.warning(f"Creando archivo: {e}")
            ss = client.create(archivo)

        try:
            ws = ss.worksheet(hoja)
        except Exception as e:
            st.warning(f"Creando hoja: {e}")
            ws = ss.add_worksheet(title=hoja, rows="1000", cols="10")
            ws.append_row(["Nombre","Fecha","Hora","Tipo"])

        ws.append_row([nombre, fecha, hora, tipo])

        return True

    except Exception as e:
        st.error(f"❌ Error Sheets: {e}")
        return False

def procesar_cola():
    registros = q.execute("SELECT * FROM cola").fetchall()

    for r in registros:
        ok = enviar_a_sheets(r[1], r[2], r[3], r[4])
        if ok:
            q.execute("DELETE FROM cola WHERE id=?", (r[0],))
            q_conn.commit()

procesar_cola()

# ---------------- REPORTE ----------------
def generar_reporte_mensual():
    try:
        client = conectar()
        now = ahora()

        archivo = f"Asistencia_{now.strftime('%Y_%m')}"
        spreadsheet = client.open(archivo)

        hojas = spreadsheet.worksheets()
        resumen = {}

        for hoja in hojas:
            if hoja.title == "Resumen_Mensual":
                continue

            datos = hoja.get_all_values()

            for fila in datos[1:]:
                nombre = fila[0]

                if nombre not in resumen:
                    resumen[nombre] = {"dias": set(), "registros": 0}

                resumen[nombre]["registros"] += 1
                resumen[nombre]["dias"].add(hoja.title)

        try:
            ws = spreadsheet.worksheet("Resumen_Mensual")
            ws.clear()
        except:
            ws = spreadsheet.add_worksheet(title="Resumen_Mensual", rows="100", cols="10")

        ws.append_row(["Empleado", "Días", "Registros"])

        for nombre, data in resumen.items():
            ws.append_row([nombre, len(data["dias"]), data["registros"]])

        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}/edit#gid={ws.id}"

        st.success("Reporte generado")
        st.markdown(f"[Abrir reporte]({url})")

    except Exception as e:
        st.error(f"Error reporte: {e}")

# ---------------- SESIÓN ----------------
if "admin" not in st.session_state:
    st.session_state.admin = False

# ---------------- SIDEBAR ----------------
menu = st.sidebar.radio("Menú", ["Asistencia","Admin"])

# =========================================================
# 📸 ASISTENCIA
# =========================================================
if menu == "Asistencia":

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    if not empleados:
        st.warning("No hay empleados")
        st.stop()

    st.subheader("📸 Asistencia")
    st.caption(f"🕒 {ahora().strftime('%H:%M:%S')}")

    nombre = st.selectbox("Empleado", [e[1] for e in empleados])
    tipo = st.radio("Tipo", ["Entrada","Salida"])

    foto = st.camera_input("Selfie")

    if foto:
        now = ahora()
        fecha = now.strftime("%Y-%m-%d")
        hora = now.strftime("%H:%M:%S")

        ok = enviar_a_sheets(nombre, tipo, fecha, hora)

        if not ok:
            q.execute("INSERT INTO cola VALUES (?,?,?,?,?)",
                      (str(uuid.uuid4()), nombre, tipo, fecha, hora))
            q_conn.commit()
            st.warning("Guardado en cola")
        else:
            st.success("Guardado en Sheets")

        st.success(f"Bienvenido {nombre}")
        st.info(noticia())

        st.rerun()

    pendientes = q.execute("SELECT COUNT(*) FROM cola").fetchone()[0]
    st.info(f"Pendientes: {pendientes}")

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
                st.error("Error login")

    else:
        tab1, tab2, tab3, tab4 = st.tabs(["Empleados","Config","Seguridad","Reportes"])

        with tab1:
            nuevo = st.text_input("Nuevo empleado")
            if st.button("Agregar"):
                c.execute("INSERT INTO empleados VALUES (?,?,?)",
                          (str(uuid.uuid4()), nuevo, ""))
                conn.commit()
                st.rerun()

            for e in c.execute("SELECT * FROM empleados"):
                if st.button(f"Eliminar {e[1]}"):
                    c.execute("DELETE FROM empleados WHERE id=?", (e[0],))
                    conn.commit()
                    st.rerun()

        with tab2:
            st.write("Config básica")

        with tab3:
            nueva = st.text_input("Nueva contraseña", type="password")
            if st.button("Guardar"):
                c.execute("UPDATE config SET pass=? WHERE id=1",(nueva,))
                conn.commit()
                st.success("OK")

        with tab4:
            if st.button("Generar reporte mensual"):
                generar_reporte_mensual()
