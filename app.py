import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from io import BytesIO

# -------------------------------------------------------
# CONFIGURACIÓN INICIAL
# -------------------------------------------------------
st.set_page_config(page_title="Generador Tabla Nutricional - Colombia", layout="centered")

st.title("🇨🇴 Generador de Tabla Nutricional (Resolución 810/2021 y 2492/2022)")
st.write("""
Esta herramienta genera la tabla nutricional con el formato oficial colombiano. 
Calcula automáticamente las **calorías (kcal)** según los factores de Atwater.
""")

# -------------------------------------------------------
# ENTRADAS DEL USUARIO
# -------------------------------------------------------
st.header("Datos del producto")

col1, col2 = st.columns(2)
with col1:
    nombre_producto = st.text_input("Nombre del producto", "")
    porcion_texto = st.text_input("Tamaño de porción (texto en etiqueta)", "1 unidad")
    porcion_g = st.number_input("Tamaño de porción (g o ml)", min_value=1.0, value=15.0)
    num_porciones = st.text_input("Número de porciones por envase", "")
with col2:
    proteinas_100 = st.number_input("Proteína (g por 100 g)", 0.0, 1000.0, 5.5)
    grasa_total_100 = st.number_input("Grasa total (g por 100 g)", 0.0, 1000.0, 27.0)
    grasa_sat_100 = st.number_input("Grasa saturada (g por 100 g)", 0.0, 1000.0, 15.0)
    grasa_trans_100 = st.number_input("Grasa trans (mg por 100 g)", 0.0, 10000.0, 1617.0)
    carbohidratos_100 = st.number_input("Carbohidratos totales (g por 100 g)", 0.0, 1000.0, 2.1)
    fibra_100 = st.number_input("Fibra dietaria (g por 100 g)", 0.0, 1000.0, 0.0)
    azucares_100 = st.number_input("Azúcares totales (g por 100 g)", 0.0, 1000.0, 2.0)
    azucares_anadidos_100 = st.number_input("Azúcares añadidos (g por 100 g)", 0.0, 1000.0, 2.0)
    sodio_100 = st.number_input("Sodio (mg por 100 g)", 0.0, 10000.0, 364.0)

st.markdown("### Micronutrientes (opcional)")
colA, colB, colC = st.columns(3)
with colA:
    vitA = st.text_input("Vitamina A", "226 µg ER")
with colB:
    vitD = st.text_input("Vitamina D", "0.2 µg")
with colC:
    hierro = st.text_input("Hierro", "0 mg")
calcio = st.text_input("Calcio", "80 mg")
zinc = st.text_input("Zinc", "0,54 mg")

st.markdown("---")

# -------------------------------------------------------
# CÁLCULOS AUTOMÁTICOS
# -------------------------------------------------------
energia_100 = round(4 * (proteinas_100 + carbohidratos_100) + 9 * grasa_total_100, 0)
factor = porcion_g / 100

def calc_porcion(valor):
    return round(valor * factor, 2)

# Calcular valores por porción
energia_porcion = round(energia_100 * factor, 0)
proteinas_porcion = calc_porcion(proteinas_100)
grasa_total_porcion = calc_porcion(grasa_total_100)
grasa_sat_porcion = calc_porcion(grasa_sat_100)
grasa_trans_porcion = round(grasa_trans_100 * factor, 0)
carbohidratos_porcion = calc_porcion(carbohidratos_100)
fibra_porcion = calc_porcion(fibra_100)
azucares_porcion = calc_porcion(azucares_100)
azucares_anadidos_porcion = calc_porcion(azucares_anadidos_100)
sodio_porcion = round(sodio_100 * factor, 0)

# -------------------------------------------------------
# CREACIÓN DE LA TABLA
# -------------------------------------------------------
datos = {
    "Nutriente": [
        "Calorías (kcal)", "Grasa total", "Grasa saturada", "Grasa Trans",
        "Carbohidratos totales", "Fibra dietaria", "Azúcares totales", "Az. añadidos",
        "Proteína", "Sodio", "Vitamina A", "Vitamina D", "Hierro", "Calcio", "Zinc"
    ],
    "Por 100 g": [
        f"{energia_100}", f"{grasa_total_100} g", f"{grasa_sat_100} g", f"{int(grasa_trans_100)} mg",
        f"{carbohidratos_100} g", f"{fibra_100} g", f"{azucares_100} g", f"{azucares_anadidos_100} g",
        f"{proteinas_100} g", f"{int(sodio_100)} mg", vitA, vitD, hierro, calcio, zinc
    ],
    f"Por porción de {int(porcion_g)} g": [
        f"{energia_porcion}", f"{grasa_total_porcion} g", f"{grasa_sat_porcion} g", f"{int(grasa_trans_porcion)} mg",
        f"{carbohidratos_porcion} g", f"{fibra_porcion} g", f"{azucares_porcion} g", f"{azucares_anadidos_porcion} g",
        f"{proteinas_porcion} g", f"{int(sodio_porcion)} mg", vitA, vitD, hierro, calcio, zinc
    ]
}

df = pd.DataFrame(datos)
st.dataframe(df, use_container_width=True)

# -------------------------------------------------------
# EVALUACIÓN DE SELLOS FRONTALES (referencial)
# -------------------------------------------------------
st.subheader("Evaluación de sellos frontales (referencial)")
sellos = []
if energia_100 >= 275:
    sellos.append("EXCESO EN CALORÍAS")
if grasa_sat_100 >= 4:
    sellos.append("EXCESO EN GRASA SATURADA")
if azucares_100 >= 10:
    sellos.append("EXCESO EN AZÚCARES")
if sodio_100 >= 300:
    sellos.append("EXCESO EN SODIO")

if sellos:
    for s in sellos:
        st.error(s)
else:
    st.success("No requiere sellos frontales (según valores de referencia).")

st.markdown("---")

# -------------------------------------------------------
# FUNCIÓN PARA CREAR PDF
# -------------------------------------------------------
def generar_pdf():
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    left = 20 * mm
    top = height - 20 * mm

    c.setFont("Helvetica-Bold", 14)
    c.rect(left - 4*mm, top - 8*mm, 170*mm, 14*mm)
    c.drawString(left + 35*mm, top - 6*mm, "Información Nutricional")

    c.setFont("Helvetica", 9)
    c.drawString(left, top - 26*mm, f"Tamaño de porción: {porcion_texto} ({int(porcion_g)} g)")
    c.drawString(left + 120*mm, top - 26*mm, f"Número de porciones por envase: {num_porciones}")

    # Encabezado de tabla
    y = top - 38*mm
    c.setFont("Helvetica-Bold", 9)
    c.rect(left, y, 170*mm, 8*mm)
    c.drawString(left + 72*mm, y + 2*mm, "Por 100 g")
    c.drawString(left + 122*mm, y + 2*mm, f"por porción de {int(porcion_g)} g")

    # Cuerpo de la tabla
    c.setFont("Helvetica", 8)
    y -= 8*mm
    for i in range(len(df)):
        nutr = df["Nutriente"][i]
        v1 = df["Por 100 g"][i]
        v2 = df[f"Por porción de {int(porcion_g)} g"][i]
        # Fondo
        c.setFillColorRGB(0.95, 0.87, 0.84)
        c.rect(left + 70*mm, y, 50*mm, 8*mm, fill=1, stroke=1)
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(left + 120*mm, y, 50*mm, 8*mm, fill=1, stroke=1)
        c.setFillColor(colors.black)

        c.setFont("Helvetica-Bold" if nutr in ["Calorías (kcal)", "Grasa saturada", "Grasa Trans", "Sodio"] else "Helvetica", 8)
        c.drawString(left + 2*mm, y + 2*mm, nutr)
        c.drawCentredString(left + 95*mm, y + 2*mm, v1)
        c.drawCentredString(left + 145*mm, y + 2*mm, v2)
        y -= 8*mm

    c.setFont("Helvetica", 7)
    c.drawString(left, y - 6*mm, "Generado conforme a la Resolución 810 de 2021 y 2492 de 2022.")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# -------------------------------------------------------
# BOTÓN DE DESCARGA
# -------------------------------------------------------
if st.button("📄 Generar PDF"):
    pdf_buffer = generar_pdf()
    st.download_button(
        label="Descargar Tabla Nutricional (PDF)",
        data=pdf_buffer,
        file_name=f"tabla_nutricional_{nombre_producto.replace(' ', '_')}.pdf",
        mime="application/pdf"
    )
