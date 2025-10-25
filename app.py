# app.py (versión corregida - error de sintaxis arreglado)
import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import textwrap

# -------------------------
# Helpers
# -------------------------
def mm2pt(x):
    return x * mm

def trim_num_str(x):
    if x is None:
        return ""
    try:
        if isinstance(x, float):
            s = f"{x:.3f}".rstrip('0').rstrip('.')
        else:
            s = str(x)
        return s
    except Exception:
        return str(x)

# -------------------------
# App UI
# -------------------------
st.set_page_config(page_title="Generador Tabla Nutricional", layout="centered")
st.title("Generador de Tabla de Información Nutricional (Resol. 810/2021)")

# Tipo de producto
tipo = st.selectbox("Tipo de producto", ["Sólido (por 100 g)", "Líquido (por 100 mL)"])
unidad_100 = "g" if tipo.startswith("Sólido") else "mL"

# Nutrientes principales (orden normativo, usuario selecciona los que aplican)
st.header("Nutrientes principales (seleccione los que aplican)")
MAIN_ORDER = [
    "Grasa total",
    "Grasa poliinsaturada",
    "Grasa monoinsaturada",
    "Grasa saturada",
    "Grasas trans",
    "Carbohidratos totales",
    "Fibra dietaria",
    "Azúcares totales",
    "Azúcares añadidos",
    "Proteína",
    "Sodio"
]
main_selected = []
st.markdown("**Calorías (kcal)** se calcula automáticamente y siempre aparece.")
for nut in MAIN_ORDER:
    default = True if nut in ["Grasa total", "Grasa saturada", "Carbohidratos totales", "Proteína", "Sodio"] else False
    if st.checkbox(nut, value=default):
        main_selected.append(nut)

st.markdown("---")

# Porciones (cada en su renglón según norma)
st.header("Datos de porción")
porcion_text = st.text_input("Texto tamaño de porción (ej.: 1 porción = 30 g)", "1 porción")
porcion_val = st.number_input(f"Tamaño de porción (número en {unidad_100})", min_value=1.0, value=30.0, step=1.0)
num_porciones = st.text_input("Número de porciones por envase", "")

st.markdown("---")

# Ingresos por 100
st.header(f"Valores por 100 {unidad_100} (ingrese sólo números)")
main_inputs = {}
for nut in MAIN_ORDER:
    if nut not in main_selected:
        main_inputs[nut] = 0.0
        continue
    if nut == "Sodio":
        main_inputs[nut] = st.number_input(f"{nut} (mg por 100 {unidad_100})", min_value=0.0, value=0.0, step=1.0, key=f"in_{nut}")
    else:
        main_inputs[nut] = st.number_input(f"{nut} (g por 100 {unidad_100})", min_value=0.0, value=0.0, step=0.01, key=f"in_{nut}")

st.markdown("---")

# Micronutrientes (predefinidos + custom)
st.header("Micronutrientes (Tabla 9)")
PREDEF_MICROS = [
    ("Vitamina A", "µg ER"),
    ("Vitamina D", "µg"),
    ("Vitamina E", "mg"),
    ("Vitamina K", "µg"),
    ("Vitamina C", "mg"),
    ("Tiamina (B1)", "mg"),
    ("Riboflavina (B2)", "mg"),
    ("Niacina (B3)", "mg"),
    ("Vitamina B6", "mg"),
    ("Folato (B9)", "µg"),
    ("Vitamina B12", "µg"),
    ("Calcio", "mg"),
    ("Hierro", "mg"),
    ("Zinc", "mg"),
    ("Potasio", "mg")
]
micro_names = [m[0] for m in PREDEF_MICROS]
selected_micros = st.multiselect("Micronutrientes predefinidos:", micro_names)
micros_values = {}
if selected_micros:
    for name in selected_micros:
        micros_values[name] = st.number_input(f"{name} (por 100 {unidad_100})", min_value=0.0, value=0.0, step=0.01, key=f"mic_{name}")

add_custom = st.checkbox("Añadir micronutrientes personalizados (opcional)")
custom_micros = []
if add_custom:
    st.markdown("Añada cada micronutriente personalizado (nombre, valor por 100, unidad)")
    n_custom = st.number_input("¿Cuántos personalizados desea añadir?", min_value=1, max_value=10, value=1)
    for i in range(int(n_custom)):
        cname = st.text_input(f"Nombre micronutriente #{i+1}", key=f"cname_{i}")
        cval = st.number_input(f"Valor por 100 {unidad_100} #{i+1}", min_value=0.0, value=0.0, step=0.01, key=f"cval_{i}")
        cunit = st.selectbox(f"Unidad #{i+1}", ["mg", "µg", "µg ER", "g", "IU"], key=f"cunit_{i}")
        if cname:
            custom_micros.append((cname, cval, cunit))

st.markdown("---")

# Frase "No es fuente significativa..." dentro del recuadro
st.header("Frase de nutrientes no significativos (se imprimirá dentro del recuadro)")
no_signif_text = st.text_input("Ej.: No es fuente significativa de: vitamina C, potasio.", "")

st.markdown("---")

# Cálculos
factor = porcion_val / 100.0
fat = main_inputs.get("Grasa total", 0.0)
prot = main_inputs.get("Proteína", 0.0)
cho = main_inputs.get("Carbohidratos totales", 0.0)
energia_100 = round(4 * (prot + cho) + 9 * fat, 0)
energia_por = int(round(energia_100 * factor, 0))

# Construir filas en orden normativo, insertando un spacer entre grupos
rows = []
rows.append(("Calorías (kcal)", str(energia_100), str(energia_por)))

# Fat group
fat_group = ["Grasa total", "Grasa poliinsaturada", "Grasa monoinsaturada", "Grasa saturada", "Grasas trans"]
fat_included = [n for n in fat_group if n in main_selected]
for idx, name in enumerate(fat_group):
    if name in main_selected:
        v100 = main_inputs.get(name, 0.0)
        vpor = round(v100 * factor, 3)
        indent = "" if name == "Grasa total" else "  "
        rows.append((f"{indent}{name}", f"{trim_num_str(v100)} g" if v100 != 0 else "0", f"{trim_num_str(vpor)} g" if v100 != 0 else "0"))

# If both fat and carb groups exist, add spacer
carb_group = ["Carbohidratos totales", "Fibra dietaria", "Azúcares totales", "Azúcares añadidos"]
if any(n in main_selected for n in fat_group) and any(n in main_selected for n in carb_group):
    rows.append(("", "", ""))  # spacer row

# Carb group
for name in carb_group:
    if name in main_selected:
        v100 = main_inputs.get(name, 0.0)
        vpor = round(v100 * factor, 3)
        indent = "" if name == "Carbohidratos totales" else "  "
        rows.append((f"{indent}{name}", f"{trim_num_str(v100)} g" if v100 != 0 else "0", f"{trim_num_str(vpor)} g" if v100 != 0 else "0"))

# Protein and Sodium
if "Proteína" in main_selected:
    v100 = main_inputs.get("Proteína", 0.0)
    vpor = round(v100 * factor, 3)
    rows.append(("Proteína", f"{trim_num_str(v100)} g" if v100 != 0 else "0", f"{trim_num_str(vpor)} g" if v100 != 0 else "0"))
if "Sodio" in main_selected:
    v100 = main_inputs.get("Sodio", 0.0)
    vpor = int(round(v100 * factor, 0))
    rows.append(("Sodio", f"{int(v100)} mg" if v100 != 0 else "0", f"{vpor} mg" if v100 != 0 else "0"))

# Micronutrientes predefinidos (en orden PREDEF_MICROS)
for name, unit in PREDEF_MICROS:
    if name in selected_micros:
        v100 = micros_values.get(name, 0.0)
        vpor = round(v100 * factor, 3)
        rows.append((name, f"{trim_num_str(v100)} {unit}" if v100 != 0 else "", f"{trim_num_str(vpor)} {unit}" if vpor != 0 else ""))

# Custom micros
for name, val, unit in custom_micros:
    v100 = val
    vpor = round(v100 * factor, 3)
    rows.append((name, f"{trim_num_str(v100)} {unit}" if v100 != 0 else "", f"{trim_num_str(vpor)} {unit}" if vpor != 0 else ""))

# Preview
st.subheader("Vista previa")
df_preview = pd.DataFrame(rows, columns=["Nutriente", f"Por 100 {unidad_100}", f"Por porción ({int(porcion_val)} {unidad_100})"])
st.dataframe(df_preview, use_container_width=True)

st.markdown("---")

# Evaluación indicativa sellos frontales
st.subheader("Evaluación indicativa de sellos frontales")
sellos = []
if energia_100 >= 275:
    sellos.append("EXCESO EN CALORÍAS")
if main_inputs.get("Grasa saturada", 0) >= 4:
    sellos.append("EXCESO EN GRASA SATURADA")
if main_inputs.get("Azúcares totales", 0) >= 10:
    sellos.append("EXCESO EN AZÚCARES")
if main_inputs.get("Sodio", 0) >= 300:
    sellos.append("EXCESO EN SODIO")

if sellos:
    for s in sellos:
        st.error(s)
else:
    st.success("No requiere sellos frontales (evaluación indicativa).")

# -------------------------
# Generación de PDF (COMPLETAMENTE CORREGIDA)
# -------------------------
def generar_pdf(rows, no_signif_text, table_width_mm=100):
    page_w, page_h = A4
    table_w = table_width_mm * mm

    # Layout params (mm) - AJUSTADOS PARA MEJOR ESPACIADO
    top_margin_mm = 8
    left_inner_margin_mm = 6
    right_inner_margin_mm = 6
    name_col_w_mm = 52
    value_col_w_mm = (table_width_mm - left_inner_margin_mm - right_inner_margin_mm - name_col_w_mm) / 2.0

    # CÁLCULO DINÁMICO DE ALTURA BASADO EN CONTENIDO REAL
    row_h_mm = 6.5  # Reducido ligeramente para mejor ajuste
    
    # Contar filas reales (excluyendo espacios)
    n_real_rows = sum(1 for row in rows if row[0] != "" or row[1] != "" or row[2] != "")
    
    # Altura base + espacio para header + espacio para footer + espacio para frase final
    header_height_mm = 28  # Aumentado para mejor espaciado
    footer_height_mm = 12 if no_signif_text else 8
    content_height_mm = n_real_rows * row_h_mm
    table_h_mm = header_height_mm + content_height_mm + footer_height_mm
    
    # Asegurar altura mínima
    table_h_mm = max(80, table_h_mm)
    table_h = table_h_mm * mm

    # Centrar tabla
    table_x = (page_w - table_w) / 2
    table_y = (page_h - table_h) / 2

    # Posiciones de columnas
    left_inner_x = table_x + left_inner_margin_mm * mm
    name_col_right_x = left_inner_x + name_col_w_mm * mm
    col100_left_x = name_col_right_x
    col100_right_x = col100_left_x + value_col_w_mm * mm
    colpor_left_x = col100_right_x
    colpor_right_x = colpor_left_x + value_col_w_mm * mm

    # Crear PDF
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Fuentes y tamaños
    f_reg = "Helvetica"
    f_bold = "Helvetica-Bold"
    sz_title = 10
    sz_header = 8
    sz_text = 8
    sz_high = 9

    # Dibujar rectángulo exterior
    c.setLineWidth(1)
    c.rect(table_x, table_y, table_w, table_h)

    # TÍTULO Y ENCABEZADOS CON MEJOR ESPACIADO
    y = table_y + table_h - mm2pt(top_margin_mm)
    
    # Título principal
    c.setFont(f_bold, sz_title)
    c.drawString(table_x + left_inner_margin_mm * mm, y, "Información Nutricional")
    
    # Tamaño de porción
    y -= 7 * mm
    c.setFont(f_reg, sz_text)
    c.drawString(table_x + left_inner_margin_mm * mm, y, f"Tamaño de porción: {porcion_text} ({int(porcion_val)} {unidad_100})")
    
    # Número de porciones
    y -= 6 * mm
    c.drawString(table_x + left_inner_margin_mm * mm, y, f"Número de porciones por envase: {num_porciones if num_porciones else '-'}")

    # LÍNEA GRUESA después del encabezado (según norma)
    y -= 5 * mm
    c.setLineWidth(1.2)  # Más gruesa
    c.line(table_x + 3 * mm, y, table_x + table_w - 3 * mm, y)

    # Encabezados de columnas (SIN NEGRILLA)
    y -= 7 * mm
    c.setFont(f_reg, sz_header)
    c.drawString(col100_left_x + 2 * mm, y, f"Por 100 {unidad_100}")
    c.drawString(colpor_left_x + 2 * mm, y, f"Por porción ({int(porcion_val)} {unidad_100})")

    # Subrayado de encabezados
    y -= 3 * mm
    c.setLineWidth(0.75)
    c.line(table_x + 3 * mm, y, table_x + table_w - 3 * mm, y)

    # POSICIÓN INICIAL PARA FILAS
    y -= 6 * mm
    row_h_pt = row_h_mm * mm

    # Nutrientes que van en negrilla y con indentación según resoluciones
    highlighted_bold = {"Calorías (kcal)", "Grasa total", "Grasa saturada", "Grasas trans", 
                       "Carbohidratos totales", "Azúcares añadidos", "Sodio", "Proteína"}
    
    # Nutrientes con indentación
    indented_nutrients = {"Grasa poliinsaturada", "Grasa monoinsaturada", "Grasa saturada", 
                         "Grasas trans", "Fibra dietaria", "Azúcares totales", "Azúcares añadidos"}

    # DIBUJAR LÍNEAS VERTICALES COMPLETAS PRIMERO
    c.setLineWidth(0.75)
    y_top_vertical = table_y + table_h - 3 * mm
    y_bottom_vertical = table_y + 3 * mm
    
    # Línea izquierda
    x_left_v = table_x + 3 * mm
    c.line(x_left_v, y_bottom_vertical, x_left_v, y_top_vertical)
    
    # Línea entre nombre y valores
    x_name_right_v = name_col_right_x
    c.line(x_name_right_v, y_bottom_vertical, x_name_right_v, y_top_vertical)
    
    # Línea entre columnas de valores
    x_col100_right_v = col100_right_x
    c.line(x_col100_right_v, y_bottom_vertical, x_col100_right_v, y_top_vertical)

    # VARIABLE PARA CONTROLAR LÍNEAS GRUESAS
    last_was_sodium = False

    # DIBUJAR FILAS DE CONTENIDO
    for i, (name, v100, vpor) in enumerate(rows):
        # Manejar filas espaciadoras
        if name == "" and v100 == "" and vpor == "":
            y -= row_h_pt
            continue

        display_name = name
        indent_amount = 4 if name.strip() in indented_nutrients else 0

        # Aplicar formato según nutriente
        if name.strip() in highlighted_bold:
            c.setFont(f_bold, sz_high)
            text_y_offset = 1  # Pequeño ajuste para mejor alineación
        else:
            c.setFont(f_reg, sz_text)
            text_y_offset = 0

        # Dibujar nombre del nutriente (con indentación si aplica)
        name_x = table_x + left_inner_margin_mm * mm + 1 * mm + mm2pt(indent_amount)
        c.drawString(name_x, y + text_y_offset, display_name.strip())

        # Dibujar valores (mismo formato que el nombre)
        pad_right = 2 * mm
        x_right_100 = col100_right_x - pad_right
        x_right_por = colpor_right_x - pad_right

        # CORRECCIÓN: Variables sin espacios en los nombres
        v100s = v100 if v100 is not None else ""
        vpors = vpor if vpor is not None else ""

        if v100s != "":
            c.drawRightString(x_right_100, y + text_y_offset, v100s)
        if vpors != "":
            c.drawRightString(x_right_por, y + text_y_offset, vpors)

        # AVANZAR posición Y
        y -= row_h_pt

        # DIBUJAR LÍNEAS HORIZONTALES CON GROSOR DIFERENCIADO
        if i < len(rows) - 1:  # No dibujar después de la última fila
            if name.strip().lower() == "sodio":
                # LÍNEA GRUESA después de sodio
                c.setLineWidth(1.2)
                last_was_sodium = True
            elif last_was_sodium:
                # LÍNEA GRUESA después de micronutrientes (si sigue después de sodio)
                c.setLineWidth(1.2)
                last_was_sodium = False
            else:
                # Línea normal para separación entre filas
                c.setLineWidth(0.5)
            
            # Posición de la línea (ligeramente arriba del texto siguiente)
            line_y = y + mm2pt(2)
            c.line(table_x + 3 * mm, line_y, table_x + table_w - 3 * mm, line_y)

    # FRASE "No es fuente significativa..." en la parte inferior
    if no_signif_text:
        ns_y = table_y + 8 * mm
        c.setFont(f_reg, 7)
        ns_wrap = textwrap.wrap(no_signif_text, width=80)
        for i, line in enumerate(ns_wrap):
            c.drawString(table_x + left_inner_margin_mm * mm, ns_y - (i * 3.5 * mm), line)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# -------------------------
# Generate button
# -------------------------
st.markdown("---")
if st.button("Generar y descargar PDF"):
    if not main_selected:
        st.error("Debe seleccionar al menos un nutriente principal.")
    else:
        with st.spinner("Generando PDF..."):
            pdfbuf = generar_pdf(rows, no_signif_text, table_width_mm=100)
            st.success("PDF generado correctamente!")
            st.download_button(
                "Descargar tabla nutricional (PDF)", 
                data=pdfbuf, 
                file_name="tabla_nutricional.pdf", 
                mime="application/pdf"
            )
