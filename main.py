import streamlit as st
import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import os
from PIL import Image, ImageDraw
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_js_eval import streamlit_js_eval
import math

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="Control Personal", page_icon="👤", layout="centered")

def ahora():
    return datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))

st.title("🏢 Control de Personal")
st.caption(f"🕒 Hora actual: {ahora().strftime('%H:%M:%S')}")

# ----------------------------
# FRASES
# ----------------------------
frases = [
    "El trabajo en equipo hace que el sueño funcione.",
    "Juntos logramos más.",
    "La unión hace la fuerza.",
    "Nadie es tan bueno como todos juntos.",
    "El éxito es mejor cuando se comparte."
]

# ----------------------------
# GOOGLE SHEETS
# ----------------------------
SHEET_ID = "1rtduRSVLvJk1381A4PZ_ALELRmg_behDl9d_jimr4GA"

def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def guardar_en_sheets(nombre, fecha, hora, tipo):
    try:
        sheet = conectar_sheets()
        try:
            ws = sheet.worksheet(fecha)
        except:
            ws = sheet.add_worksheet(title=fecha, rows="1000", cols="10")
            ws.append_row(["Nombre", "Fecha", "Hora", "Tipo"])

        ws.append_row([nombre, fecha, hora, tipo])
    except Exception as e:
        st.warning(f"Error Sheets: {e}")

# ----------------------------
# DB
# ----------------------------
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS empleados (id TEXT, nombre TEXT, foto TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empleado_id TEXT,
    nombre TEXT,
    fecha TEXT,
    hora TEXT,
    tipo TEXT,
    foto TEXT
)''')
conn.commit()

os.makedirs("fotos_empleados", exist_ok=True)
os.makedirs("fotos_registros", exist_ok=True)

# ----------------------------
# GEO (100 metros)
# ----------------------------
def obtener_coords():
    return streamlit_js_eval(
        js_expressions="""
        new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(
                (pos) => resolve([pos.coords.latitude, pos.coords.longitude]),
                (err) => reject(err)
            );
        })
        """,
        key="geo"
    )

def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

# Coordenadas base (Oberá)
LAT_REF = -27.487
LON_REF = -55.119
RADIO_METROS = 100

# ----------------------------
# MENU
# ----------------------------
modo = st.sidebar.radio("Menú", ["Empleados", "Marcar Asistencia", "Auditoría"], index=1)

# ----------------------------
# EMPLEADOS
# ----------------------------
if modo == "Empleados":

    st.subheader("👥 Empleados")

    nombre = st.text_input("Nombre")
    foto = st.file_uploader("Foto base")

    if st.button("Guardar"):
        if nombre and foto:
            emp_id = str(uuid.uuid4())
            path = f"fotos_empleados/{emp_id}.jpg"
            Image.open(foto).save(path)

            c.execute("INSERT INTO empleados VALUES (?, ?, ?)", (emp_id, nombre, path))
            conn.commit()
            st.success("Guardado")
            st.rerun()

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    for emp in empleados:
        st.image(emp[2], width=100)
        nuevo = st.text_input(f"Editar {emp[0]}", value=emp[1])

        col1, col2 = st.columns(2)

        if col1.button(f"Actualizar {emp[0]}"):
            c.execute("UPDATE empleados SET nombre=? WHERE id=?", (nuevo, emp[0]))
            conn.commit()
            st.rerun()

        if col2.button(f"Eliminar {emp[0]}"):
            c.execute("DELETE FROM empleados WHERE id=?", (emp[0],))
            conn.commit()
            st.rerun()

# ----------------------------
# MARCAR
# ----------------------------
elif modo == "Marcar Asistencia":

    st.subheader("📸 Registro con ubicación")

    coords = obtener_coords()

    if coords is None:
        st.warning("📍 Debes permitir la ubicación en tu dispositivo")
        st.stop()

    lat, lon = coords
    dist = distancia_metros(lat, lon, LAT_REF, LON_REF)

    st.caption(f"📍 Distancia al punto: {int(dist)} m")

    if dist > RADIO_METROS:
        st.error("🚫 Fuera del área permitida (100m)")
        st.stop()

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    if empleados:
        nombres = [e[1] for e in empleados]
        nombre_sel = st.selectbox("Selecciona tu nombre", nombres)
        tipo = st.radio("Tipo", ["Entrada", "Salida"])

        foto = st.camera_input("Tomar selfie")

        if foto:
            img = Image.open(foto)

            ahora_dt = ahora()
            fecha = ahora_dt.strftime("%d-%m-%Y")
            hora = ahora_dt.strftime("%H:%M")

            draw = ImageDraw.Draw(img)
            draw.text((10, 10), f"{nombre_sel} {fecha} {hora}", fill=(255, 0, 0))

            path = f"fotos_registros/{uuid.uuid4()}.jpg"
            img.save(path)

            emp = next(e for e in empleados if e[1] == nombre_sel)

            c.execute('''
                INSERT INTO registros (empleado_id, nombre, fecha, hora, tipo, foto)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (emp[0], nombre_sel, fecha, hora, tipo, path))
            conn.commit()

            guardar_en_sheets(nombre_sel, fecha, hora, tipo)

            st.success(f"✅ Bienvenido {nombre_sel}")
            st.info(random.choice(frases))
            st.image(path)

# ----------------------------
# AUDITORIA
# ----------------------------
else:

    st.subheader("📊 Auditoría")

    registros = c.execute("SELECT * FROM registros ORDER BY id DESC").fetchall()

    if registros:
        df = pd.DataFrame(registros, columns=[
            "ID", "EmpID", "Nombre", "Fecha", "Hora", "Tipo", "Foto"
        ])

        st.dataframe(df.drop(columns=["Foto"]))

        for _, row in df.head(10).iterrows():
            st.image(row["Foto"], width=200)
    else:
        st.info("Sin registros")
