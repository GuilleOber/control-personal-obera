import streamlit as st
import cv2
from deepface import DeepFace
from PIL import Image
import numpy as np
import os
from datetime import datetime
import pandas as pd

from streamlit_gsheets import GSheetsConnection

# Crear conexión
conn = st.connection("gsheets", type=GSheetsConnection)

# Ejemplo de cómo guardar un registro
if st.button("Confirmar Registro"):
    df_nuevo = pd.DataFrame([{"Nombre": empleado_sel, "Fecha": ahora.strftime('%d/%m/%Y'), "Hora": ahora.strftime('%H:%M'), "Tipo": tipo_marca}])
    # Aquí se envía a la nube
    conn.create(data=df_nuevo) 
    st.success("Guardado en Google Sheets")

# Configuración visual de la App
st.set_page_config(page_title="Control Oberá Cel", page_icon="👤", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 Centro de Control Cel")
st.info("Sistema Biométrico de Asistencia")

# --- Gestión de Empleados (Carga de fotos de referencia) ---
if not os.path.exists('fotos_db'):
    os.makedirs('fotos_db')

# Menú lateral para administración
with st.sidebar:
    st.header("⚙️ Administración")
    modo = st.radio("Ir a:", ["Marcado de Asistencia", "Registrar Nuevo Empleado"])

# --- LÓGICA: REGISTRAR NUEVO ---
if modo == "Registrar Nuevo Empleado":
    st.subheader("📝 Alta de Personal")
    nuevo_nombre = st.text_input("Nombre del trabajador")
    foto_perfil = st.file_uploader("Subir foto de referencia", type=['jpg', 'png'])
    
    if st.button("Guardar Empleado"):
        if nuevo_nombre and foto_perfil:
            img = Image.open(foto_perfil)
            img.save(f"fotos_db/{nuevo_nombre}.jpg")
            st.success(f"Empleado {nuevo_nombre} registrado con éxito.")
        else:
            st.error("Por favor, completa el nombre y la foto.")

# --- LÓGICA: MARCADO (PWA) ---
else:
    st.subheader("📸 Registro de Jornada")
    empleados = [f.split('.')[0] for f in os.listdir('fotos_db') if f.endswith(('.jpg', '.png'))]
    
    if not empleados:
        st.warning("No hay empleados en la base de datos.")
    else:
        empleado_sel = st.selectbox("Selecciona tu nombre", empleados)
        tipo_marca = st.radio("Tipo de registro", ["Entrada", "Salida"], horizontal=True)
        
        # Activa la cámara del celular
        foto_selfie = st.camera_input("Tómate una foto para verificar")

        if foto_selfie:
            with st.spinner("Procesando reconocimiento..."):
                # Guardar captura temporal
                img_selfie = Image.open(foto_selfie)
                img_selfie.save("temp_cel.jpg")
                
                foto_referencia = f"fotos_db/{empleado_sel}.jpg"

                try:
                    # Comparación Biométrica
                    resultado = DeepFace.verify(
                        img1_path=foto_referencia, 
                        img2_path="temp_cel.jpg",
                        model_name="VGG-Face",
                        detector_backend="opencv",
                        enforce_detection=True
                    )

                    if resultado['verified']:
                        ahora = datetime.now()
                        st.balloons()
                        st.success(f"✅ ¡Identidad Confirmada! {empleado_sel}")
                        st.write(f"Registro de **{tipo_marca}** exitoso a las {ahora.strftime('%H:%M:%S')}")
                        
                        # AQUÍ SE CONECTARÍA CON GOOGLE SHEETS PARA GUARDAR EL DATO
                        # Por ahora lo mostramos en pantalla
                    else:
                        st.error("❌ La cara no coincide. Intenta con mejor luz.")
                
                except Exception as e:
                    st.error("No se pudo detectar un rostro claro.")
                
                if os.path.exists("temp_cel.jpg"):
                    os.remove("temp_cel.jpg")
