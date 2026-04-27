import streamlit as st
import sqlite3
import uuid
from datetime import datetime
import pandas as pd
import qrcode
import os
from PIL import Image
import numpy as np
import cv2
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="Control Personal PRO", page_icon="👤")

st.title("🏢 Control de Personal PRO")
st.info("QR + Foto + Auditoría + Reportes")

# ----------------------------
# GOOGLE SHEETS
# ----------------------------
SHEET_ID = "1rtduRSVLvJk1381A4PZ_ALELRmg_behDl9d_jimr4GA"

def conectar_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )

    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def guardar_en_sheets(nombre, fecha, hora, tipo):
    try:
        sheet = conectar_sheets()

        # hoja del día
        hoja_nombre = fecha

        try:
            ws = sheet.worksheet(hoja_nombre)
        except:
            ws = sheet.add_worksheet(title=hoja_nombre, rows="1000", cols="10")
            ws.append_row(["Nombre", "Fecha", "Hora", "Tipo"])

        ws.append_row([nombre, fecha, hora, tipo])

    except Exception as e:
        st.warning(f"Error Google Sheets: {e}")

# ----------------------------
# DB
# ----------------------------
conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS empleados (
    id TEXT PRIMARY KEY,
    nombre TEXT,
    qr TEXT
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
os.makedirs("qr_codes", exist_ok=True)
os.makedirs("fotos_registros", exist_ok=True)

# ----------------------------
# SIDEBAR
# ----------------------------
with st.sidebar:
    modo = st.radio("Menú", ["Registrar Empleado", "Marcar Asistencia", "Auditoría"])

# ----------------------------
# REGISTRO EMPLEADO
# ----------------------------
if modo == "Registrar Empleado":

    st.subheader("➕ Nuevo Empleado")

    nombre = st.text_input("Nombre")

    if st.button("Crear empleado"):
        if nombre:
            emp_id = str(uuid.uuid4())

            qr_img = qrcode.make(emp_id)
            qr_path = f"qr_codes/{emp_id}.png"
            qr_img.save(qr_path)

            c.execute("INSERT INTO empleados VALUES (?, ?, ?)", (emp_id, nombre, qr_path))
            conn.commit()

            st.success("Empleado creado")
            st.image(qr_path)

# ----------------------------
# MARCAR
# ----------------------------
elif modo == "Marcar Asistencia":

    st.subheader("📸 Escanear QR")

    foto_qr = st.camera_input("Escanea el QR")

    if foto_qr:
        img = Image.open(foto_qr)
        img_np = np.array(img)

        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img_np)

        if data:
            emp_id = data
            empleado = c.execute("SELECT * FROM empleados WHERE id=?", (emp_id,)).fetchone()

            if empleado:
                st.success(f"Empleado: {empleado[1]}")

                tipo = st.radio("Tipo", ["Entrada", "Salida"])
                foto = st.camera_input("📸 Foto obligatoria")

                if foto:
                    img_foto = Image.open(foto)
                    img_np2 = np.array(img_foto)

                    foto_path = f"fotos_registros/{uuid.uuid4()}.jpg"
                    cv2.imwrite(foto_path, img_np2)

                    ahora = datetime.now()
                    fecha = ahora.strftime('%d-%m-%Y')
                    hora = ahora.strftime('%H:%M')

                    # guardar local
                    c.execute('''
                        INSERT INTO registros (empleado_id, nombre, fecha, hora, tipo, foto)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        emp_id,
                        empleado[1],
                        fecha,
                        hora,
                        tipo,
                        foto_path
                    ))
                    conn.commit()

                    # guardar en Google Sheets
                    guardar_en_sheets(empleado[1], fecha, hora, tipo)

                    st.success("✅ Registro guardado + enviado a Google Sheets")

            else:
                st.error("Empleado no encontrado")
        else:
            st.error("No se detectó QR")

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
