import streamlit as st
import pandas as pd
import numpy as np

# -------------------------------------------------------
# CONFIGURACIÓN INICIAL DEL APLICATIVO
# -------------------------------------------------------
st.set_page_config(page_title="Generador de Tabla Nutricional - Colombia", layout="centered")

st.title("🇨🇴 Generador de Tabla Nutricional según Resolución 810 de 2021 y 2492 de 2022")
st.write("Este aplicativo permite calcular automáticamente la información nutricional **por 100 g** y **por porción**, "
         "de acuerdo con la normativa colombiana vigente del Ministerio de Salud y Protección Social.")

st.markdown("---")

# -------------------------------------------------------
# ENTRADAS DEL USUARIO
# -------------------------------------------------------
st.header("🔢 Datos del producto")

col1, col2 = st.columns(2)
with col1:
    nombre_producto = st.text_input("Nombre del producto", "")
    porcion = st.number_input("Tamaño de la porción (g o ml)", min_value=1.0, value=30.0, step=1.0)
with col2:
    energia_100g = st.number_input("Energía (kcal por 100 g)", min_value=0.0, value=200.0)
    proteinas_100g = st.number_input("Proteínas (g por 100 g)", min_value=0.0, value=3.0)

grasa_total_100g = st.number_input("Grasa total (g por 100 g)", min_value=0.0, value=10.0)
grasa_sat_100g = st.number_input("Grasa saturada (g por 100 g)", min_value=0.0, value=4.0)
grasa_trans_100g = st.number_input("Grasa trans (g por 100 g)", min_value=0.0, value=0.1)
carbohidratos_100g = st.number_input("Carbohidratos (g por 100 g)", min_value=0.0, value=25.0)
azucares_100g = st.number_input("Azúcares totales (g por 100 g)", min_value=0.0, value=12.0)
fibra_100g = st.number_input("Fibra dietaria (g por 100 g)", min_value=0.0, value=2.0)
sodio_100g = st.number_input("Sodio (mg por 100 g)", min_value=0.0, value=150.0)

st.markdown("---")

# -------------------------------------------------------
# CÁLCULOS AUTOMÁTICOS
# -------------------------------------------------------
st.header("🧮 Resultados calculados")

factor = porcion / 100

datos = {
    "Nutriente": ["Energía (kcal)", "Proteínas (g)", "Grasa total (g)",
                   "Grasa saturada (g)", "Grasa trans (g)", "Carbohidratos (g)",
                   "Azúcares totales (g)", "Fibra dietaria (g)", "Sodio (mg)"],
    "Por 100 g": [energia_100g, proteinas_100g, grasa_total_100g,
                  grasa_sat_100g, grasa_trans_100g, carbohidratos_100g,
                  azucares_100g, fibra_100g, sodio_100g],
    f"Por porción ({porcion} g)": [
        round(energia_100g * factor, 2),
        round(proteinas_100g * factor, 2),
        round(grasa_total_100g * factor, 2),
        round(grasa_sat_100g * factor, 2),
        round(grasa_trans_100g * factor, 2),
        round(carbohidratos_100g * factor, 2),
        round(azucares_100g * factor, 2),
        round(fibra_100g * factor, 2),
        round(sodio_100g * factor, 2)
    ]
}

tabla = pd.DataFrame(datos)
st.dataframe(tabla, use_container_width=True)

st.markdown("---")

# -------------------------------------------------------
# ALERTAS DE SELLOS FRONTALES SEGÚN RESOLUCIÓN 2492/2022
# -------------------------------------------------------
st.header("⚠️ Evaluación de sellos frontales de advertencia")

exceso = []

if energia_100g >= 275:
    exceso.append("EXCESO EN CALORÍAS")
if grasa_sat_100g >= 4:
    exceso.append("EXCESO EN GRASA SATURADA")
if azucares_100g >= 10:
    exceso.append("EXCESO EN AZÚCARES")
if sodio_100g >= 300:
    exceso.append("EXCESO EN SODIO")

if exceso:
    st.error("El producto requiere los siguientes sellos frontales:")
    for e in exceso:
        st.write(f"- 🟥 {e}")
else:
    st.success("✅ El producto NO requiere sellos frontales según la Resolución 2492 de 2022.")

st.markdown("---")
st.caption("Desarrollado como proyecto académico basado en la Resolución 810 de 2021 y su modificación 2492 de 2022 (Ministerio de Salud y Protección Social de Colombia).")
