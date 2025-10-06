import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import portrait
from io import BytesIO

# -----------------------------
# Configuración de la app
# -----------------------------
st.set_page_config(page_title="Generador Tabla Nutricional", layout="centered")
st.title("Generador de Tabla Nutricional")
st.write("Ingrese los datos obtenidos en los bromatológicos.")

# -----------------------------
# Elección de tipo de producto
# -----------------------------
st.header("Configuración del formato")
col_type, col_sizeopt = st.columns(2)

with col_type:
    tipo_producto = st.selectbox("Tipo de producto (afecta encabezado)", ["Sólido (g)", "Líquido (mL)"])

with col_sizeopt:
    tamaño_opción = st.selectbox("Generar tamaño", ["Tamaño fijo (100 mm × 85 mm)", "Tamaño automático (según contenido)"])

# -----------------------------
# Entradas en el orden de la tabla
# (No pedimos calorías: se calculan automáticamente)
# Orden según Art. 28.4
# -----------------------------
st.header("Datos de porción")
porcion_text = st.text_input("Tamaño de porción (texto en etiqueta)", "1 porción")
porcion_g = st.number_input("Tamaño de porción en (g o mL) — ingresar número", min_value=1.0, value=15.0, step=1.0)
num_porciones = st.text_input("Número de porciones por envase (dejar en blanco si variable)", "")

st.markdown("---")
st.header("Valores por 100 " + ("g" if tipo_producto.startswith("Sólido") else "mL") )
st.write("Ingrese solo números. Unidades mostradas automáticamente en la tabla.")

# 1. Grasa total
grasa_total_100 = st.number_input("Grasa total (g por 100)", min_value=0.0, value=0.0, step=0.1)

# 2. Grasa saturada (sangría debajo de grasa total)
grasa_sat_100 = st.number_input("  - Grasa saturada (g por 100)", min_value=0.0, value=0.0, step=0.1)

# 3. Grasa trans (g por 100)
grasa_trans_100 = st.number_input("  - Grasa trans (g por 100)", min_value=0.0, value=0.0, step=0.01)

# 4. Carbohidratos totales
carbohidratos_100 = st.number_input("Carbohidratos totales (g por 100)", min_value=0.0, value=0.0, step=0.1)

# 5. Fibra dietaria (sangría)
fibra_100 = st.number_input("  - Fibra dietaria (g por 100)", min_value=0.0, value=0.0, step=0.1)

# 6. Azúcares totales (sangría)
azucares_100 = st.number_input("  - Azúcares totales (g por 100)", min_value=0.0, value=0.0, step=0.1)

# 7. Azúcares añadidos (sangría, en negrita en la tabla)
azucares_anadidos_100 = st.number_input("  - Azúcares añadidos (g por 100)", min_value=0.0, value=0.0, step=0.1)

# 8. Proteína
proteina_100 = st.number_input("Proteína (g por 100)", min_value=0.0, value=0.0, step=0.1)

# 9. Sodio (mg por 100)
sodio_100 = st.number_input("Sodio (mg por 100)", min_value=0.0, value=0.0, step=1.0)

st.markdown("---")
st.header("Vitaminas y minerales (ingresar solo valores numéricos)")
st.write("Se agregarán automáticamente las unidades requeridas en la tabla: Vitamina A (µg ER), Vitamina D (µg), Hierro (mg), Calcio (mg), Zinc (mg).")

vitA_val = st.number_input("Vitamina A (valor numérico)", min_value=0.0, value=0.0, step=0.1)
vitD_val = st.number_input("Vitamina D (valor numérico)", min_value=0.0, value=0.0, step=0.01)
hierro_val = st.number_input("Hierro (valor numérico)", min_value=0.0, value=0.0, step=0.01)
calcio_val = st.number_input("Calcio (valor numérico)", min_value=0.0, value=0.0, step=0.1)
zinc_val = st.number_input("Zinc (valor numérico)", min_value=0.0, value=0.0, step=0.01)

# -----------------------------
# Cálculos de energía y por porción
# -----------------------------
# Energía (kcal) según Atwater: 4*(proteína + carbohidratos) + 9*(grasa total)
energia_100 = round(4 * (proteina_100 + carbohidratos_100) + 9 * grasa_total_100, 0)
factor = porcion_g / 100.0

# Valores por porción (redondeo práctico para etiqueta)
energia_porcion = int(round(energia_100 * factor, 0))
grasa_total_por = round(grasa_total_100 * factor, 2)
grasa_sat_por = round(grasa_sat_100 * factor, 2)
grasa_trans_por = round(grasa_trans_100 * factor, 3)
carbohidratos_por = round(carbohidratos_100 * factor, 2)
fibra_por = round(fibra_100 * factor, 2)
azucares_por = round(azucares_100 * factor, 2)
azucares_anadidos_por = round(azucares_anadidos_100 * factor, 2)
proteina_por = round(proteina_100 * factor, 2)
sodio_por = int(round(sodio_100 * factor, 0))

vitA_por = round(vitA_val * factor, 2)
vitD_por = round(vitD_val * factor, 3)
hierro_por = round(hierro_val * factor, 2)
calcio_por = round(calcio_val * factor, 1)
zinc_por = round(zinc_val * factor, 2)

# -----------------------------
# Construcción del DataFrame para vista en la app (opcional)
# -----------------------------
nombres = [
    "Calorías (kcal)",
    "Grasa total",
    "  Grasa saturada",
    "  Grasa trans",
    "Carbohidratos totales",
    "  Fibra dietaria",
    "  Azúcares totales",
    "  Azúcares añadidos",
    "Proteína",
    "Sodio",
    # separador visual en DataFrame no obligatorio
    "Vitamina A",
    "Vitamina D",
    "Hierro",
    "Calcio",
    "Zinc"
]

por100_vals = [
    str(energia_100),
    f"{grasa_total_100} g",
    f"{grasa_sat_100} g",
    f"{grasa_trans_100} g",
    f"{carbohidratos_100} g",
    f"{fibra_100} g",
    f"{azucares_100} g",
    f"{azucares_anadidos_100} g",
    f"{proteina_100} g",
    f"{int(sodio_100)} mg",
    f"{int(vitA_val)} µg ER" if vitA_val else "",
    f"{vitD_val} µg" if vitD_val else "",
    f"{hierro_val} mg" if hierro_val else "",
    f"{calcio_val} mg" if calcio_val else "",
    f"{zinc_val} mg" if zinc_val else ""
]

porporcion_vals = [
    str(energia_porcion),
    f"{grasa_total_por} g",
    f"{grasa_sat_por} g",
    f"{grasa_trans_por} g",
    f"{carbohidratos_por} g",
    f"{fibra_por} g",
    f"{azucares_por} g",
    f"{azucares_anadidos_por} g",
    f"{proteina_por} g",
    f"{sodio_por} mg",
    f"{vitA_por} µg ER" if vitA_val else "",
    f"{vitD_por} µg" if vitD_val else "",
    f"{hierro_por} mg" if hierro_val else "",
    f"{calcio_por} mg" if calcio_val else "",
    f"{zinc_por} mg" if zinc_val else ""
]

df_preview = pd.DataFrame({
    "Nutriente": nombres,
    f"Por 100 {'g' if tipo_producto.startswith('Sólido') else 'mL'}": por100_vals,
    f"Por porción ({int(porcion_g)} {'g' if tipo_producto.startswith('Sólido') else 'mL'})": porporcion_vals
})

st.markdown("---")
st.subheader("Vista previa (establecimiento de valores)")
st.dataframe(df_preview, use_container_width=True)

# -----------------------------
# Evaluación indicativa de sellos frontales (referencial)
# -----------------------------
st.markdown("---")
st.subheader("Evaluación de sellos frontales (indicativa)")
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
    st.success("No requiere sellos frontales (evaluación indicativa).")

# -----------------------------
# Función para generar PDF de solo la tabla (tamaño real)
# -----------------------------
def mm_to_pts(x_mm):
    return x_mm * mm

def generar_pdf_tabla(width_mm=100, base_row_height_mm=6.5):
    """
    Genera un PDF en memoria que contiene únicamente el recuadro de la tabla en blanco y negro.
    Si el tamaño es automático, la altura se ajusta según el número de filas.
    """
    # Contar filas: nutriente rows (15 en total: 10 macronutrientes + 5 micronutrientes)
    filas = len(nombres)
    # Espacios: encabezado title + porción/num porciones + separador + filas + pie nota
    header_h = 14  # mm (título + espacio)
    top_info_h = 10  # mm para "Tamaño porción" y "N° porciones"
    separator_h = 2  # mm (línea gruesa entre porciones y calorías)
    footer_h = 6  # mm
    row_h = base_row_height_mm  # mm por fila

    content_h_mm = header_h + top_info_h + separator_h + filas * row_h + footer_h

    # Si el usuario escogió tamaño fijo, usamos altura fija; si automático, ajustamos
    if tamaño_opción == "Tamaño fijo (100 mm × 85 mm)":
        height_mm = 85
    else:
        # añadir pequeño margen
        height_mm = max(60, content_h_mm + 6)

    # Crear canvas con tamaño exacto en puntos (reportlab usa puntos)
    width_pts = mm_to_pts(width_mm)
    height_pts = mm_to_pts(height_mm)
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pts, height_pts))

    # Márgenes internos
    left_margin = mm_to_pts(6)
    right_margin = mm_to_pts(6)
    top_margin = mm_to_pts(6)
    # coordenadas de inicio (origen abajo en reportlab)
    x0 = left_margin
    y0 = height_pts - top_margin  # punto Y superior

    # Dibujar recuadro exterior (grosor 1 pt)
    c.setLineWidth(1)
    c.rect(x0 - mm_to_pts(2), y0 - mm_to_pts(2) - mm_to_pts(height_mm - 4), width_pts - left_margin - right_margin + mm_to_pts(4), height_pts - mm_to_pts(4), stroke=1, fill=0)

    # Título: "Información Nutricional" -- Helvetica Bold 10pt (mínimo)
    title_font = "Helvetica-Bold"
    title_size = 10
    c.setFont(title_font, title_size)
    title_y = y0 - mm_to_pts(4)
    c.drawString(x0 + mm_to_pts(20), title_y, "Información Nutricional")

    # Tamaño de porción y número de porciones: Arial/Helvetica 10pt
    info_font = "Helvetica"
    info_size = 10
    c.setFont(info_font, info_size)
    info_y = title_y - mm_to_pts(6)
    c.drawString(x0, info_y, f"Tamaño de porción: {porcion_text} ({int(porcion_g)} {'g' if tipo_producto.startswith('Sólido') else 'mL'})")
    c.drawRightString(width_pts - right_margin, info_y, f"Número de porciones por envase: {num_porciones if num_porciones else '-'}")

    # Línea negra gruesa (1 pt) entre número de porciones y calorías (según tu requerimiento)
    line_y = info_y - mm_to_pts(4)
    c.setLineWidth(1)
    c.line(x0, line_y, width_pts - right_margin, line_y)

    # Espacio antes de la tabla
    table_start_y = line_y - mm_to_pts(4)

    # Columnas: nombres | por 100 | por porción
    col_nutriente_x = x0 + mm_to_pts(2)
    col_100_x = x0 + mm_to_pts(60)  # ajustar según ancho
    col_porcion_x = x0 + mm_to_pts(85)

    # Encabezados de columna
    header_font = "Helvetica-Bold"
    header_size = 9
    c.setFont(header_font, header_size)
    c.drawString(col_nutriente_x, table_start_y, "")
    c.drawString(col_100_x, table_start_y, f"Por 100 {'g' if tipo_producto.startswith('Sólido') else 'mL'}")
    c.drawString(col_porcion_x, table_start_y, f"Por porción ({int(porcion_g)} {'g' if tipo_producto.startswith('Sólido') else 'mL'})")

    # Línea inferior del encabezado (0.75 pt)
    head_line_y = table_start_y - mm_to_pts(1.5)
    c.setLineWidth(0.75)
    c.line(x0, head_line_y, width_pts - right_margin, head_line_y)

    # Iterar filas y dibujar
    current_y = head_line_y - mm_to_pts(3)
    # tamaños
    normal_font = "Helvetica"
    normal_size = 10
    bold_font = "Helvetica-Bold"
    bold_size = int(normal_size * 1.3)  # para los nutrientes indicados

    # Nutrientes que deben estar en negrita y 1.3× (según resolución): Calorías, Gr. Saturada, Gr. Trans, Az. añadidos, Sodio
    important_labels = {"Calorías (kcal)", "  Grasa saturada", "  Grasa trans", "  Azúcares añadidos", "Sodio"}

    # Dibujar cada fila
    for idx, name in enumerate(nombres):
        # Select font size and style
        if name in important_labels:
            c.setFont(bold_font, bold_size)
        else:
            # Use regular for indented nutrient names too
            c.setFont(normal_font, normal_size)

        # Escribir nombre (respetando sangrías)
        # left align
        c.drawString(col_nutriente_x, current_y, name)

        # Escribir valores centrados en sus columnas (usar fuente negrita para valores principales como calorías)
        # Por 100
        c.setFont(normal_font, normal_size)
        val100 = por100_vals[idx]
        valpor = porporcion_vals[idx]
        # Ajuste: centrar aproximado en la columna
        c.drawRightString(col_100_x + mm_to_pts(20), current_y, val100)
        c.drawRightString(col_porcion_x + mm_to_pts(20), current_y, valpor)

        # Línea separadora fina entre filas (0.5 pt)
        current_y -= mm_to_pts(base_row_height_mm)
        c.setLineWidth(0.5)
        c.line(x0, current_y + mm_to_pts(1.5), width_pts - right_margin, current_y + mm_to_pts(1.5))

    # Línea separadora más gruesa entre macros y vitaminas/minerales (1 pt)
    # Calcular Y de la línea: después de la fila "Sodio" (fila 10, índice 9)
    separator_after_index = 10  # después de Sodio (índice 9)
    # compute y position for that separator
    sep_y = head_line_y - mm_to_pts(3) - mm_to_pts(base_row_height_mm) * (separator_after_index - 1) - mm_to_pts(base_row_height_mm)
    c.setLineWidth(1)
    c.line(x0, sep_y, width_pts - right_margin, sep_y)

    # Nota legal / fuente en el pie (pequeño)
    c.setFont("Helvetica", 6)
    c.drawString(x0, sep_y - mm_to_pts(6), "Tabla generada conforme a las especificaciones de la Resolución 810/2021 y 2492/2022 (blanco y negro).")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# -----------------------------
# Botón para generar y descargar PDF
# -----------------------------
st.markdown("---")
if st.button("Generar y descargar tabla (PDF)"):
    # Determinar anchura fija (100 mm) y fila base 6.5 mm típicamente
    width_mm = 100
    base_row_mm = 6.5
    pdf_buffer = generar_pdf_tabla(width_mm=width_mm, base_row_height_mm=base_row_mm)
    st.download_button(
        label="Descargar tabla nutricional (PDF)",
        data=pdf_buffer,
        file_name=f"tabla_nutricional_{('producto').replace(' ', '_')}.pdf",
        mime="application/pdf"
    )
