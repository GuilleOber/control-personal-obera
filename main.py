import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
import requests
from bs4 import BeautifulSoup
import math

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
    background-attachment: fixed;
}

.card {
    background-color: rgba(255,255,255,0.92);
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0px 4px 15px rgba(0,0,0,0.2);
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

# TABLAS LIMPIAS Y CONSISTENTES
c.execute("""
CREATE TABLE IF NOT EXISTS empleados (
    id TEXT,
    nombre TEXT,
    foto TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS config (
    id INTEGER,
    pass TEXT,
    geo INTEGER,
    radio INTEGER
)
""")

conn.commit()

# INIT CONFIG
if not c.execute("SELECT * FROM config").fetchone():
    c.execute("INSERT INTO config VALUES (1,'admin',1,100)")
    conn.commit()

config = c.execute("SELECT * FROM config").fetchone()

# ---------------- NOTICIAS CACHE ----------------
@st.cache_data(ttl=604800)  # 7 días
def obtener_noticia():
    try:
        url = "https://trabajo.misiones.gob.ar/noticias/"
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        titulo = soup.find("h2")
        return titulo.text.strip() if titulo else "No disponible"
    except:
        return "No se pudo cargar noticias"

# ---------------- GEO ----------------
LAT_REF = -27.487735745039803
LON_REF = -55.126748202517426

def distancia(lat, lon):
    R = 6371000
    phi1 = math.radians(lat)
    phi2 = math.radians(LAT_REF)
    dphi = math.radians(LAT_REF - lat)
    dlambda = math.radians(LON_REF - lon)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ---------------- SESIÓN ----------------
if "admin" not in st.session_state:
    st.session_state.admin = False

# ---------------- SIDEBAR ----------------
st.sidebar.title("Control MTE")
menu = st.sidebar.radio("Menú", ["Asistencia", "Admin"])

# =========================================================
# 📸 ASISTENCIA
# =========================================================
if menu == "Asistencia":

    col1, col2 = st.columns([2,1])

    # ---------- PANEL IZQUIERDO ----------
    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)

        st.subheader("📸 Marcar asistencia")
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

            draw.text((10,10), f"{nombre} {fecha} {hora}", fill=(255,0,0))

            img.save(f"{uuid.uuid4()}.jpg")

            st.markdown(f"<div class='big-title'>✅ BIENVENIDO {nombre.upper()}</div>", unsafe_allow_html=True)
            st.success("Registro OK")

            st.markdown("### 📰 Información")
            st.info(obtener_noticia())

            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- PANEL DERECHO ----------
    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)

        st.subheader("📍 Ubicación")
        if config[2]:
            st.success(f"Geolocalización activa (radio {config[3]}m)")
        else:
            st.warning("Geolocalización desactivada")

        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("<div class='card'>", unsafe_allow_html=True)

        st.subheader("📰 Última noticia")
        st.write(obtener_noticia())

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
        tab1, tab2, tab3 = st.tabs(["👥 Empleados","📍 Geo","🔐 Seguridad"])

        # -------- EMPLEADOS --------
        with tab1:
            st.subheader("Gestión de empleados")

            nuevo = st.text_input("Nombre")

            if st.button("Agregar"):
                if nuevo:
                    c.execute(
                        "INSERT INTO empleados (id, nombre, foto) VALUES (?,?,?)",
                        (str(uuid.uuid4()), nuevo, "")
                    )
                    conn.commit()
                    st.rerun()

            empleados = c.execute("SELECT * FROM empleados").fetchall()

            for e in empleados:
                colA, colB = st.columns([3,1])
                colA.write(e[1])
                if colB.button(f"Eliminar {e[0]}"):
                    c.execute("DELETE FROM empleados WHERE id=?", (e[0],))
                    conn.commit()
                    st.rerun()

        # -------- GEO --------
        with tab2:
            geo = st.toggle("Activar geolocalización", value=bool(config[2]))
            radio = st.slider("Radio permitido (m)", 50, 300, config[3])

            if st.button("Guardar configuración"):
                c.execute(
                    "UPDATE config SET geo=?, radio=? WHERE id=1",
                    (int(geo), radio)
                )
                conn.commit()
                st.success("Configuración guardada")
                st.rerun()

        # -------- SEGURIDAD --------
        with tab3:
            nueva = st.text_input("Nueva contraseña", type="password")

            if st.button("Cambiar contraseña"):
                if nueva:
                    c.execute("UPDATE config SET pass=? WHERE id=1", (nueva,))
                    conn.commit()
                    st.success("Contraseña actualizada")
