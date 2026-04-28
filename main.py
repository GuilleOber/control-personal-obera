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

        ws.append_row(["Empleado", "Días trabajados", "Registros"])

        for nombre, data in resumen.items():
            ws.append_row([nombre, len(data["dias"]), data["registros"]])

        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}/edit#gid={ws.id}"

        st.success("Reporte generado ✅")
        st.markdown(f"👉 [Abrir reporte]({url})")

    except Exception as e:
        st.error(f"Error reporte: {e}")

# ---------------- SESIÓN ----------------
if "admin" not in st.session_state:
    st.session_state.admin = False

# ---------------- SIDEBAR ----------------
st.sidebar.title("Control MTE")
menu = st.sidebar.radio("Menú", ["Asistencia","Admin"])

# =========================================================
# 📸 ASISTENCIA
# =========================================================
if menu == "Asistencia":

    col1, col2 = st.columns([2,1])

    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)

        st.subheader("📸 Asistencia")
        st.caption(f"🕒 {ahora().strftime('%H:%M:%S')}")

        empleados = c.execute("SELECT * FROM empleados").fetchall()

        if not empleados:
            st.warning("No hay empleados")
            st.stop()

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
                st.warning("Sin conexión → guardado en cola")
            else:
                st.success("Guardado en Sheets")

            st.markdown(f"<div class='big-title'>✅ {nombre.upper()}</div>", unsafe_allow_html=True)
            st.info(noticia())

            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📦 Cola pendiente")

        pendientes = q.execute("SELECT COUNT(*) FROM cola").fetchone()[0]
        st.write(f"Registros pendientes: {pendientes}")

        if st.button("Sincronizar ahora"):
            procesar_cola()
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# 🔐 ADMIN
# =========================================================
else:

    if not st.session_state.admin:
        st.subheader("Login Admin")

        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")

        if st.button("Ingresar"):
            if user == "admin" and pwd == config[1]:
                st.session_state.admin = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

    else:
        tab1, tab2, tab3, tab4 = st.tabs(["Empleados","Config","Seguridad","Reportes"])

        # EMPLEADOS
        with tab1:
            nuevo = st.text_input("Nuevo empleado")

            if st.button("Agregar"):
                if nuevo:
                    c.execute(
                        "INSERT INTO empleados (id, nombre, foto) VALUES (?,?,?)",
                        (str(uuid.uuid4()), nuevo, "")
                    )
                    conn.commit()
                    st.rerun()

            for e in c.execute("SELECT * FROM empleados"):
                colA,colB = st.columns([3,1])
                colA.write(e[1])
                if colB.button(f"Eliminar {e[0]}"):
                    c.execute("DELETE FROM empleados WHERE id=?", (e[0],))
                    conn.commit()
                    st.rerun()

        # CONFIG
        with tab2:
            geo = st.toggle("Geolocalización", value=bool(config[2]))
            radio = st.slider("Radio (m)", 50, 300, config[3])

            if st.button("Guardar configuración"):
                c.execute("UPDATE config SET geo=?, radio=? WHERE id=1",(int(geo),radio))
                conn.commit()
                st.success("Guardado")

        # SEGURIDAD
        with tab3:
            nueva = st.text_input("Nueva contraseña", type="password")

            if st.button("Cambiar contraseña"):
                if nueva:
                    c.execute("UPDATE config SET pass=? WHERE id=1",(nueva,))
                    conn.commit()
                    st.success("Actualizada")

        # REPORTES
        with tab4:
            st.subheader("📊 Reporte mensual")

            if st.button("Generar reporte mensual"):
                generar_reporte_mensual()
