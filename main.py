import streamlit as st
import cv2
from PIL import Image
import numpy as np
import os
from datetime import datetime
import pandas as pd

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(page_title="Control Oberá Cel", page_icon="👤", layout="centered")

st.title("🚀 Centro de Control Cel")
st.info("Sistema Biométrico de Asistencia")

# Crear carpeta si no existe
if not os.path.exists('fotos_db'):
    os.makedirs('fotos_db')

# ----------------------------
# FUNCION COMPARACION
# ----------------------------
def comparar_imagenes(img1, img2):
    img1 = cv2.resize(img1, (200, 200))
    img2 = cv2.resize(img2, (200, 200))

    img1 = cv2.equalizeHist(img1)
    img2 = cv2.equalizeHist(img2)

    diff = cv2.absdiff(img1, img2)
    return np.mean(diff)

# ----------------------------
# SIDEBAR
# ----------------------------
with st.sidebar:
    st.header("⚙️ Administración")
    modo = st.radio("Ir a:", ["Marcado de Asistencia", "Registrar Nuevo Empleado"])

# ----------------------------
# REGISTRAR EMPLEADO
# ----------------------------
if modo == "Registrar Nuevo Empleado":

    st.subheader("📝 Alta de Personal")

    nuevo_nombre = st.text_input("Nombre del trabajador")
    foto_perfil = st.file_uploader("Subir foto", type=['jpg', 'png'])

    if st.button("Guardar Empleado"):
        if nuevo_nombre and foto_perfil:

            ruta = f"fotos_db/{nuevo_nombre}.jpg"

            img = Image.open(foto_perfil).convert('L').resize((200, 200))
            img.save(ruta)

            # Verificación
            if os.path.exists(ruta):
                st.success(f"✅ {nuevo_nombre} registrado correctamente")
                st.rerun()
            else:
                st.error("❌ Error al guardar la imagen")

        else:
            st.error("Completa todos los campos")

    # Mostrar empleados actuales
    st.divider()
    st.subheader("👥 Empleados registrados")

    archivos = [f for f in os.listdir("fotos_db") if f.endswith(".jpg")]

    if archivos:
        nombres = [f.split('.')[0] for f in archivos]
        st.write(nombres)
    else:
        st.info("Aún no hay empleados")

# ----------------------------
# MARCADO
# ----------------------------
else:

    st.subheader("📸 Registro de Jornada")

    empleados = [f.split('.')[0] for f in os.listdir('fotos_db') if f.endswith('.jpg')]

    if not empleados:
        st.warning("No hay empleados registrados")
    else:
        empleado_sel = st.selectbox("Selecciona tu nombre", empleados)
        tipo_marca = st.radio("Tipo", ["Entrada", "Salida"])

        foto_selfie = st.camera_input("Tómate una foto")

        if foto_selfie:
            st.info("Procesando...")

            img_selfie = Image.open(foto_selfie).convert('L')
            img_np = np.array(img_selfie)

            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )

            faces = face_cascade.detectMultiScale(img_np, 1.3, 5)

            if len(faces) == 0:
                st.error("❌ No se detectó rostro")
            else:
                x, y, w, h = faces[0]
                rostro = img_np[y:y+h, x:x+w]

                ref_path = f"fotos_db/{empleado_sel}.jpg"
                img_ref = cv2.imread(ref_path, 0)

                score = comparar_imagenes(rostro, img_ref)

                if score < 50:
                    ahora = datetime.now()

                    st.success(f"✅ Bienvenido {empleado_sel}")
                    st.write(f"{tipo_marca} registrada a las {ahora.strftime('%H:%M:%S')}")

                    df_nuevo = pd.DataFrame([{
                        "Nombre": empleado_sel,
                        "Fecha": ahora.strftime('%d/%m/%Y'),
                        "Hora": ahora.strftime('%H:%M'),
                        "Tipo": tipo_marca
                    }])

                    archivo = "registros.csv"

                    if os.path.exists(archivo):
                        df_existente = pd.read_csv(archivo)
                        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
                    else:
                        df_final = df_nuevo

                    df_final.to_csv(archivo, index=False)

                else:
                    st.error("❌ Rostro no coincide")

# ----------------------------
# HISTORIAL
# ----------------------------
st.divider()
st.subheader("📊 Registros")

archivo = "registros.csv"

if os.path.exists(archivo):
    df = pd.read_csv(archivo)
    st.dataframe(df)
else:
    st.info("Aún no hay registros")
