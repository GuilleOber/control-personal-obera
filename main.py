import streamlit as st
import cv2
import numpy as np
import os
import sqlite3
import uuid
from datetime import datetime
from PIL import Image
import face_recognition

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="Control Oberá Cel", page_icon="👤", layout="centered")

st.title("🚀 Centro de Control Cel")
st.info("Sistema Biométrico de Asistencia")

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
    tipo TEXT
)
''')

conn.commit()

# ----------------------------
# CARPETA
# ----------------------------
if not os.path.exists('fotos_db'):
    os.makedirs('fotos_db')

# ----------------------------
# FUNCION FACE RECOGNITION
# ----------------------------
def obtener_encoding(imagen):
    imagen_rgb = cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB)
    encodings = face_recognition.face_encodings(imagen_rgb)

    if len(encodings) > 0:
        return encodings[0]
    return None

# ----------------------------
# SIDEBAR
# ----------------------------
with st.sidebar:
    st.header("⚙️ Administración")
    modo = st.radio("Ir a:", ["Marcado de Asistencia", "Registrar Empleados"])

# ----------------------------
# REGISTRO DE EMPLEADOS
# ----------------------------
if modo == "Registrar Empleados":

    st.subheader("👥 Gestión de Empleados")

    nombre = st.text_input("Nombre")
    foto = st.file_uploader("Foto", type=['jpg', 'png'])

    if st.button("Guardar empleado"):
        if nombre and foto:
            id_emp = str(uuid.uuid4())

            ruta = f"fotos_db/{id_emp}.jpg"

            img = Image.open(foto)
            img = np.array(img)

            cv2.imwrite(ruta, img)

            c.execute("INSERT INTO empleados VALUES (?, ?, ?)", (id_emp, nombre, ruta))
            conn.commit()

            st.success("Empleado guardado correctamente")
            st.rerun()
        else:
            st.error("Completa todos los campos")

    st.divider()

    st.subheader("📋 Empleados registrados")

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    for emp in empleados:
        st.write(f"👤 {emp[1]}")
        st.image(emp[2], width=150)

# ----------------------------
# MARCADO
# ----------------------------
else:

    st.subheader("📸 Registro de Jornada")

    empleados = c.execute("SELECT * FROM empleados").fetchall()

    if not empleados:
        st.warning("No hay empleados registrados")
    else:
        nombres = [emp[1] for emp in empleados]

        nombre_sel = st.selectbox("Selecciona tu nombre", nombres)
        tipo = st.radio("Tipo", ["Entrada", "Salida"])

        foto = st.camera_input("Tomar foto")

        if foto:
            st.info("Procesando...")

            img = Image.open(foto)
            img_np = np.array(img)

            encoding_selfie = obtener_encoding(img_np)

            if encoding_selfie is None:
                st.error("❌ No se detectó rostro")
            else:
                empleado_data = next(emp for emp in empleados if emp[1] == nombre_sel)

                img_ref = cv2.imread(empleado_data[2])
                encoding_ref = obtener_encoding(img_ref)

                if encoding_ref is None:
                    st.error("Error en imagen de referencia")
                else:
                    resultado = face_recognition.compare_faces(
                        [encoding_ref],
                        encoding_selfie,
                        tolerance=0.5
                    )[0]

                    if resultado:
                        ahora = datetime.now()

                        st.success(f"✅ Bienvenido {nombre_sel}")
                        st.write(f"{tipo} a las {ahora.strftime('%H:%M:%S')}")

                        c.execute('''
                            INSERT INTO registros (empleado_id, nombre, fecha, hora, tipo)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            empleado_data[0],
                            nombre_sel,
                            ahora.strftime('%d/%m/%Y'),
                            ahora.strftime('%H:%M'),
                            tipo
                        ))

                        conn.commit()
                    else:
                        st.error("❌ Rostro no coincide")

# ----------------------------
# HISTORIAL
# ----------------------------
st.divider()
st.subheader("📊 Registros")

registros = c.execute("SELECT * FROM registros ORDER BY id DESC").fetchall()

if registros:
    import pandas as pd

    df = pd.DataFrame(registros, columns=[
        "ID", "Empleado ID", "Nombre", "Fecha", "Hora", "Tipo"
    ])

    st.dataframe(df)
else:
    st.info("Sin registros")
