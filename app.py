# app.py
import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import textwrap

# -------------------------
# Funciones auxiliares
# -------------------------
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
# Configuración base
# -------------------------
st.set_page_config(page_title="Generador de Tabla Nutricional", layout="centered")
st.title("Generador de Tabla de Información Nutricional (Resolución 810 de 2021)")

# -------------------------
# Tipo de producto
# -------------------------
tipo = st.selectbox("Tipo de producto", ["Sólido (por 100 g)", "Líquido (por 100 mL)"])
unidad_100 = "g" if tipo.startswith("Sólido") else "mL"

# -------------------------
# Nutrientes principales
# -------------------------
st.header("Nutrientes principales")
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
main_selected = [n for n in MAIN_ORDER if st.checkbox(n, value=n in ["Grasa total","Carbohidratos totales","Proteína","Sodio"])]

# -------------------------
# Porciones
# -------------------------
st.header("Datos de porción")
porcion_text = st.text_input("Texto de tamaño de porción (ejemplo: 1 porción = 30 g)", "1 porción")
porcion_val = st.number_input(f"Tamaño de porción ({unidad_100})", min_value=1.0, value=30.0, step=1.0)
num_porciones = st.text_input("Número de porciones por envase", "")

# -------------------------
# Ingreso de valores por 100
# -------------------------
st.header(f"Valores por 100 {unidad_100}")
main_inputs = {}
for nut in MAIN_ORDER:
    if nut not in main_selected:
        main_inputs[nut] = 0.0
        continue
    if nut == "Sodio":
        main_inputs[nut] = st.number_input(f"{nut} (mg por 100 {unidad_100})", min_value=0.0, value=0.0, step=1.0)
    else:
        main_inputs[nut] = st.number_input(f"{nut} (g por 100 {unidad_100})", min_value=0.0, value=0.0, step=0.01)

# -------------------------
# Micronutrientes
# -------------------------
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
selected_micros = st.multiselect("Seleccione los micronutrientes que aplica:", micro_names)
micros_values = {}
for name in selected_micros:
    micros_values[name] = st.number_input(f"{name} (por 100 {unidad_100})", min_value=0.0, value=0.0, step=0.01)

# -------------------------
# Frase de no significativos
# -------------------------
st.header("Frase de nutrientes no significativos")
no_signif_text = st.text_input("Ejemplo: No es fuente significativa de vitamina C, potasio.", "")

# -------------------------
# Cálculos
# -------------------------
factor = porcion_val / 100.0
fat = main_inputs.get("Grasa total", 0.0)
prot = main_inputs.get("Proteína", 0.0)
cho = main_inputs.get("Carbohidratos totales", 0.0)
energia_100 = round(4 * (prot + cho) + 9 * fat, 0)
energia_por = int(round(energia_100 * factor, 0))

rows = []
rows.append(("Calorías (kcal)", str(energia_100), str(energia_por)))

# Grasa
fat_group = ["Grasa total","Grasa poliinsaturada","Grasa monoinsaturada","Grasa saturada","Grasas trans"]
for name in fat_group:
    if name in main_selected:
        v100 = main_inputs[name]
        vpor = round(v100 * factor, 3)
        indent = "  " if name != "Grasa total" else ""
        rows.append((f"{indent}{name}", f"{trim_num_str(v100)} g", f"{trim_num_str(vpor)} g"))

# Espacio entre grupos
rows.append(("", "", ""))

# Carbohidratos
carb_group = ["Carbohidratos totales","Fibra dietaria","Azúcares totales","Azúcares añadidos"]
for name in carb_group:
    if name in main_selected:
        v100 = main_inputs[name]
        vpor = round(v100 * factor, 3)
        indent = "  " if name != "Carbohidratos totales" else ""
        rows.append((f"{indent}{name}", f"{trim_num_str(v100)} g", f"{trim_num_str(vpor)} g"))

# Proteína y sodio
for name, unit in [("Proteína","g"),("Sodio","mg")]:
    if name in main_selected:
        v100 = main_inputs[name]
        vpor = round(v100 * factor, 1)
        rows.append((name, f"{trim_num_str(v100)} {unit}", f"{trim_num_str(vpor)} {unit}"))

# Micronutrientes
for name, unit in PREDEF_MICROS:
    if name in selected_micros:
        v100 = micros_values[name]
        vpor = round(v100 * factor, 3)
        rows.append((name, f"{trim_num_str(v100)} {unit}", f"{trim_num_str(vpor)} {unit}"))

# -------------------------
# Vista previa
# -------------------------
df_preview = pd.DataFrame(rows, columns=["Nutriente", f"Por 100 {unidad_100}", f"Por porción ({int(porcion_val)} {unidad_100})"])
st.dataframe(df_preview, use_container_width=True)

# -------------------------
# Función de PDF
# -------------------------
def generar_pdf(rows, no_signif_text, table_width_mm=100):
    page_w, page_h = A4
    table_w = table_width_mm * mm
    row_h_mm = 7.0
    top_margin_mm = 6
    left_margin_mm = 6
    n_rows = len(rows)
    table_h_mm = 45 + n_rows * row_h_mm + 8
    table_h = table_h_mm * mm
    table_x = (page_w - table_w) / 2
    table_y = (page_h - table_h) / 2

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    font_reg = "Helvetica"
    font_bold = "Helvetica-Bold"
    sz_title = 10
    sz_header = 8
    sz_text = 9
    sz_highlight = int(sz_text * 1.3)

    # Recuadro
    c.setLineWidth(1)
    c.rect(table_x, table_y, table_w, table_h)

    y = table_y + table_h - top_margin_mm * mm
    c.setFont(font_bold, sz_title)
    c.drawString(table_x + left_margin_mm * mm, y, "Información Nutricional")

    # Tamaño de porción
    y -= 5 * mm
    c.setFont(font_reg, sz_text)
    c.drawString(table_x + left_margin_mm * mm, y, f"Tamaño de porción: {porcion_text} ({int(porcion_val)} {unidad_100})")

    # Número de porciones
    y -= 5 * mm
    c.drawString(table_x + left_margin_mm * mm, y, f"Número de porciones por envase: {num_porciones if num_porciones else '-'}")

    # Línea gruesa
    y -= 3.5 * mm
    c.setLineWidth(1)
    c.line(table_x + 3 * mm, y, table_x + table_w - 3 * mm, y)

    # Encabezado
    y -= 6 * mm
    c.setFont(font_bold, sz_header)
    col_name_x = table_x + left_margin_mm * mm
    col_100_x = table_x + table_w * 0.58
    col_portion_x = col_100_x + 38 * mm
    c.drawString(col_100_x, y, f"Por 100 {unidad_100}")
    c.drawString(col_portion_x, y, f"Por porción ({int(porcion_val)} {unidad_100})")

    y -= 2.8 * mm
    c.setLineWidth(0.75)
    c.line(table_x + 3 * mm, y, table_x + table_w - 3 * mm, y)

    # Filas
    y -= 6 * mm
    row_h = row_h_mm * mm
    important = {"Calorías (kcal)", "Grasa saturada", "Grasas trans", "Azúcares añadidos", "Sodio"}

    for name, v100, vpor in rows:
        display_name = name.strip()
        if display_name in important:
            c.setFont(font_bold, sz_highlight)
        else:
            c.setFont(font_reg, sz_text)

        c.drawString(col_name_x, y, name)
        if display_name in important:
            c.setFont(font_bold, sz_highlight)
        else:
            c.setFont(font_reg, sz_text)
        c.drawRightString(col_100_x + 22 * mm, y, v100)
        c.drawRightString(col_portion_x + 22 * mm, y, vpor)

        y -= row_h
        c.setLineWidth(0.5)
        c.line(table_x + 3 * mm, y + 2.5 * mm, table_x + table_w - 3 * mm, y + 2.5 * mm)
        if display_name.lower().startswith("sodio"):
            c.setLineWidth(1)
            c.line(table_x + 3 * mm, y + 2.5 * mm, table_x + table_w - 3 * mm, y + 2.5 * mm)

    # Líneas verticales exactas
    c.setLineWidth(0.75)
    x_v1 = table_x + 3 * mm
    x_v2 = col_100_x - 3 * mm
    x_v3 = col_portion_x - 3 * mm
    for xv in [x_v1, x_v2, x_v3]:
        c.line(xv, table_y + 2 * mm, xv, table_y + table_h - 2 * mm)

    # Frase dentro del recuadro
    if no_signif_text:
        c.setFont(font_reg, 8)
        ns_y = table_y + 5 * mm
        for i, line in enumerate(textwrap.wrap(no_signif_text, width=85)):
            c.drawString(table_x + left_margin_mm * mm, ns_y + i * 4.2, line)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# -------------------------
# Botón de PDF
# -------------------------
if st.button("Generar y descargar PDF"):
    pdf = generar_pdf(rows, no_signif_text)
    st.download_button("Descargar tabla nutricional (PDF)", data=pdf, file_name="tabla_nutricional.pdf", mime="application/pdf")

