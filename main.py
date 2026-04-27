import streamlit as st
import sqlite3
import uuid
from datetime import datetime
import pandas as pd
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="Control Personal PRO", page_icon="👤")

st.title("🏢 Control de Personal")
st.caption("🕒 Hora actual: " + datetime.now().strftime("%H:%M:%S"))

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
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def guardar_en_sheets(nombre, fecha, hora, tipo):
    try:
        sheet = conectar_sheets()
        hoja_nombre = fecha

        try:
            ws = sheet.worksheet(hoja_nombre)
        except:
            ws = sheet.add_worksheet(title=hoja_nombre, rows="1000", cols="10")
            ws.append_row(["Nombre", "Fecha", "Hora", "Tipo"])

        ws.append_row([nombre, fecha, hora, tipo])

    except Exception as e:
        st.warning(f"Sheets error: {e}")

# ----------------------------
# DB
# ----------------------------
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS empleados (
    id TEXT PRIMARY KEY,
    nombre TEXT,
    foto TEXT
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empleado_id TEXT,
    nombre TEXT,
    fecha TEXT,
    hora TEXT,
    tipo TEXT,
    foto TEXT
)
''')

conn.commit()

# ----------------------------
# CARPETAS
# ----------------------------
os.makedirs("fotos_empleados", exist_ok=True)
os.makedirs("fotos_registros", exist_ok=True)

# ----------------------------
# SIDEBAR
# ----------------------------
with st.sidebar:
    modo = st.radio("Menú", ["Empleados", "Marcar Asistencia", "Auditoría"])

# ----------------------------
# EMPLEADOS
# ----------------------------
if modo == "Empleados":

    st.subheader("👥 Gestión de Empleados")

    nombre = st.text_input("Nombre")
    foto = st.file_uploader("Foto base", type=["jpg", "png"])

    if st.button("Guardar empleado"):
        if nombre and foto:
            emp_id = str(uuid.uuid4())
            path = f"fotos_empleados/{emp_id}.jpg"

            img = Image.open(foto)
            img.save(path)

            c.execute("INSERT INTO empleados VALUES (?, ?, ?)", (emp_id, nombre, path))
            conn.commit()

            st.success("Empleado guardado")
            st.rerun()

    st.divider()

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    for emp in empleados:
        st.write(f"👤 {emp[1]}")
        st.image(emp[2], width=120)

        col1, col2 = st.columns(2)

        with col1:
            nuevo_nombre = st.text_input(f"Editar {emp[0]}", value=emp[1])
            if st.button(f"Actualizar {emp[0]}"):
                c.execute("UPDATE empleados SET nombre=? WHERE id=?", (nuevo_nombre, emp[0]))
                conn.commit()
                st.rerun()

        with col2:
            if st.button(f"Eliminar {emp[0]}"):
                c.execute("DELETE FROM empleados WHERE id=?", (emp[0],))
                conn.commit()
                st.rerun()

# ----------------------------
# MARCAR
# ----------------------------
elif modo == "Marcar Asistencia":

    st.subheader("📸 Registro con Selfie")

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    if empleados:
        nombres = [emp[1] for emp in empleados]
        nombre_sel = st.selectbox("¿Quién sos?", nombres)

        tipo = st.radio("Tipo", ["Entrada", "Salida"])

        foto = st.camera_input("Tomar foto")

        if foto:
            img = Image.open(foto)

            ahora = datetime.now()
            fecha = ahora.strftime("%d-%m-%Y")
            hora = ahora.strftime("%H:%M")

            # dibujar texto en imagen
            draw = ImageDraw.Draw(img)
            texto = f"{nombre_sel} - {fecha} {hora}"
            draw.text((10, 10), texto, fill=(255, 0, 0))

            path = f"fotos_registros/{uuid.uuid4()}.jpg"
            img.save(path)

            emp = next(e for e in empleados if e[1] == nombre_sel)

            c.execute('''
                INSERT INTO registros (empleado_id, nombre, fecha, hora, tipo, foto)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (emp[0], nombre_sel, fecha, hora, tipo, path))

            conn.commit()

            guardar_en_sheets(nombre_sel, fecha, hora, tipo)

            frase = random.choice(frases)

            st.success(f"✅ Bienvenido {nombre_sel}")
            st.info(frase)
            st.image(path)

# ----------------------------
# AUDITORÍA
# ----------------------------
else:

    st.subheader("🧾 Auditoría")

    registros = c.execute("SELECT * FROM registros ORDER BY id DESC").fetchall()

    if registros:
        df = pd.DataFrame(registros, columns=[
            "ID", "Empleado ID", "Nombre", "Fecha", "Hora", "Tipo", "Foto"
        ])

        st.dataframe(df.drop(columns=["Foto"]))

        st.divider()

        for _, row in df.head(10).iterrows():
            st.write(f"{row['Nombre']} - {row['Fecha']} {row['Hora']}")
            st.image(row["Foto"], width=200)
    else:
        st.info("Sin registros")
