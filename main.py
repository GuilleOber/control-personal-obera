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

# Crear carpeta
if not os.path.exists('fotos_db'):
    os.makedirs('fotos_db')

# ----------------------------
# FUNCION MEJORADA
# ----------------------------
def comparar_imagenes(img1, img2):
    img1 = cv2.resize(img1, (200, 200))
    img2 = cv2.resize(img2, (200, 200))

    img1 = cv2.GaussianBlur(img1, (5,5), 0)
    img2 = cv2.GaussianBlur(img2, (5,5), 0)

    score = cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)[0][0]
    return score

# ----------------------------
# SIDEBAR
# ----------------------------
with st.sidebar:
    st.header("⚙️ Administración")
    modo = st.radio("Ir a:", ["Marcado de Asistencia", "Registrar / Editar Empleados"])

# ----------------------------
# GESTIÓN DE EMPLEADOS
# ----------------------------
if modo == "Registrar / Editar Empleados":

    st.subheader("👥 Gestión de Empleados")

    # -------- REGISTRAR --------
    st.markdown("### ➕ Nuevo empleado")
    nuevo_nombre = st.text_input("Nombre")
    foto_perfil = st.file_uploader("Foto", type=['jpg', 'png'])

    if st.button("Guardar empleado"):
        if nuevo_nombre and foto_perfil:
            ruta = f"fotos_db/{nuevo_nombre}.jpg"
            img = Image.open(foto_perfil).convert('L').resize((200, 200))
            img.save(ruta)

            if os.path.exists(ruta):
                st.success("Empleado guardado")
                st.rerun()
            else:
                st.error("Error al guardar")
        else:
            st.error("Completa todos los campos")

    st.divider()

    # -------- LISTA --------
    archivos = [f for f in os.listdir("fotos_db") if f.endswith(".jpg")]

    if archivos:
        nombres = [f.split('.')[0] for f in archivos]

        st.markdown("### ✏️ Editar / Eliminar")

        empleado_sel = st.selectbox("Empleado", nombres)

        # EDITAR
        nuevo_nombre_edit = st.text_input("Nuevo nombre", value=empleado_sel)

        if st.button("Actualizar nombre"):
            if nuevo_nombre_edit:
                old_path = f"fotos_db/{empleado_sel}.jpg"
                new_path = f"fotos_db/{nuevo_nombre_edit}.jpg"

                os.rename(old_path, new_path)
                st.success("Nombre actualizado")
                st.rerun()

        # BORRAR
        if st.button("Eliminar empleado"):
            path = f"fotos_db/{empleado_sel}.jpg"
            os.remove(path)
            st.warning("Empleado eliminado")
            st.rerun()

    else:
        st.info("No hay empleados registrados")

# ----------------------------
# MARCADO
# ----------------------------
else:

    st.subheader("📸 Registro de Jornada")

    empleados = [f.split('.')[0] for f in os.listdir('fotos_db') if f.endswith('.jpg')]

    if not empleados:
        st.warning("No hay empleados")
    else:
        empleado_sel = st.selectbox("Selecciona tu nombre", empleados)
        tipo_marca = st.radio("Tipo", ["Entrada", "Salida"])

        foto_selfie = st.camera_input("Tomar foto")

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

                st.write(f"🔍 Similitud: {round(score,2)}")

                if score > 0.5:
                    ahora = datetime.now()

                    st.success(f"✅ Bienvenido {empleado_sel}")
                    st.write(f"{tipo_marca} a las {ahora.strftime('%H:%M:%S')}")

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
    st.info("Sin registros")
