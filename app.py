# app.py
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
def mm2pt(x_mm):
    return x_mm * mm

def trim_num_str(x):
    """Return compact string removing trailing .0 where appropriate"""
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
# App config
# -------------------------
st.set_page_config(page_title="Generador Tabla Nutricional", layout="centered")
st.title("Generador de Tabla de Información Nutricional (Resol. 810/2021)")
st.write("Ingrese los datos en el orden solicitado. **No ingrese unidades** en los campos numéricos (el sistema las añade).")

# -------------------------
# Tipo de producto y configuración (solo auto-height)
# -------------------------
st.header("Configuración")
tipo = st.selectbox("Tipo de producto (afecta encabezado)", ["Sólido (por 100 g)", "Líquido (por 100 mL)"])
unidad_100 = "g" if tipo.startswith("Sólido") else "mL"

st.markdown("**Nota:** La tabla se genera con altura automática según el contenido (formato vertical estándar).")

# -------------------------
# Selección de nutrientes principales (orden normativo)
# Calorías siempre se calcula y muestra
# -------------------------
st.header("Nutrientes principales (seleccione los aplicables)")
st.markdown("Calorías (kcal) — siempre se mostrará (calculada automáticamente).")

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
for nut in MAIN_ORDER:
    # default True for most common ones (user can uncheck)
    default = True if nut in ["Grasa total", "Grasa saturada", "Carbohidratos totales", "Proteína", "Sodio"] else False
    if st.checkbox(nut, value=default):
        main_selected.append(nut)

st.markdown("---")

# -------------------------
# Porción y número de porciones (cada uno en su renglón según norma)
# -------------------------
st.header("Datos de porción")
porcion_text = st.text_input("Texto Tamaño de porción (ej.: 1 porción = 30 g)", "1 porción")
porcion_val = st.number_input(f"Tamaño de porción (número en {unidad_100})", min_value=1.0, value=30.0, step=1.0)
num_porciones = st.text_input("Número de porciones por envase (ej.: Aprox. 2)", "")

st.markdown("---")

# -------------------------
# Ingreso de valores por 100 (solo para los seleccionados)
# -------------------------
st.header(f"Valores por 100 {unidad_100} (ingrese solo números)")

main_inputs = {}
for nut in MAIN_ORDER:
    if nut not in main_selected:
        main_inputs[nut] = 0.0
        continue
    if nut == "Sodio":
        v = st.number_input(f"{nut} (mg por 100 {unidad_100})", min_value=0.0, value=0.0, step=1.0, key=f"in_{nut}")
    else:
        v = st.number_input(f"{nut} (g por 100 {unidad_100})", min_value=0.0, value=0.0, step=0.01, key=f"in_{nut}")
    main_inputs[nut] = v

st.markdown("---")

# -------------------------
# Micronutrientes (predefinidos) + posibilidad custom
# -------------------------
st.header("Micronutrientes (seleccione y luego ingrese valores por 100)")
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
    ("Biotina", "µg"),
    ("Ácido pantoténico", "mg"),
    ("Calcio", "mg"),
    ("Hierro", "mg"),
    ("Magnesio", "mg"),
    ("Zinc", "mg"),
    ("Selenio", "µg"),
    ("Cobre", "mg"),
    ("Manganeso", "mg"),
    ("Yodo", "µg"),
    ("Potasio", "mg")
]
micro_names = [m[0] for m in PREDEF_MICROS]
selected_micros = st.multiselect("Micronutrientes predefinidos (Tabla 9):", micro_names)

micros_values = {}
if selected_micros:
    st.write("Ingrese valores por 100 (solo números). Unidades se muestran en la tabla.")
    for name in selected_micros:
        default = 0.0
        micros_values[name] = st.number_input(f"{name} (por 100 {unidad_100})", min_value=0.0, value=default, step=0.01, key=f"mic_{name}")

st.markdown("---")
add_custom = st.checkbox("Añadir micronutrientes personalizados (opcional)")
custom_micros = []
if add_custom:
    st.write("Añada nombre, valor por 100 y unidad para cada micronutriente adicional.")
    count = st.number_input("¿Cuántos micronutrientes personalizados desea añadir?", min_value=1, max_value=10, value=1, step=1)
    for i in range(int(count)):
        cname = st.text_input(f"Nombre micronutriente #{i+1}", key=f"cname_{i}")
        cval = st.number_input(f"Valor por 100 {unidad_100} #{i+1}", min_value=0.0, value=0.0, step=0.01, key=f"cval_{i}")
        cunit = st.selectbox(f"Unidad #{i+1}", ["mg", "µg", "µg ER", "g", "IU"], key=f"cunit_{i}")
        if cname:
            custom_micros.append((cname, cval, cunit))

st.markdown("---")

# -------------------------
# Frase "No es fuente significativa..." (dentro del recuadro)
# -------------------------
st.header("Frase para nutrientes no significativos (se imprimirá dentro del recuadro)")
no_signif_text = st.text_input("Escriba la frase como desea que aparezca (ej.: No es fuente significativa de: vitamina C, potasio).", "")

st.markdown("---")

# -------------------------
# Cálculos (energía y por porción)
# -------------------------
factor = porcion_val / 100.0
fat = main_inputs.get("Grasa total", 0.0)
prot = main_inputs.get("Proteína", 0.0)
cho = main_inputs.get("Carbohidratos totales", 0.0)
energia_100 = round(4 * (prot + cho) + 9 * fat, 0)
energia_por = int(round(energia_100 * factor, 0))

# build rows in normative order; only include those selected
rows = []
# Calories always first
rows.append(("Calorías (kcal)", str(energia_100), str(energia_por)))

# fats subgroup order
fat_order = [
    ("Grasa total", "g"),
    ("Grasa poliinsaturada", "g"),
    ("Grasa monoinsaturada", "g"),
    ("Grasa saturada", "g"),
    ("Grasas trans", "g")
]
for name, unit in fat_order:
    if name in main_selected:
        v100 = main_inputs.get(name, 0.0)
        vpor = int(round(v100 * factor, 0)) if name == "Sodio" else round(v100 * factor, 3)
        rows.append((("  " + name) if name != "Grasa total" else name, f"{trim_num_str(v100)} {unit}" if v100 != 0 else "0", f"{trim_num_str(round(v100 * factor, 3))} {unit}" if v100 != 0 else "0"))

# carbohydrates subgroup
carb_order = [
    ("Carbohidratos totales", "g"),
    ("Fibra dietaria", "g"),
    ("Azúcares totales", "g"),
    ("Azúcares añadidos", "g")
]
for name, unit in carb_order:
    if name in main_selected:
        v100 = main_inputs.get(name, 0.0)
        vpor = round(v100 * factor, 3)
        rows.append((("  " + name) if name != "Carbohidratos totales" else name, f"{trim_num_str(v100)} {unit}" if v100 != 0 else "0", f"{trim_num_str(vpor)} {unit}" if v100 != 0 else "0"))

# protein and sodium
if "Proteína" in main_selected:
    v100 = main_inputs.get("Proteína", 0.0)
    rows.append(("Proteína", f"{trim_num_str(v100)} g" if v100 != 0 else "0", f"{trim_num_str(round(v100*factor,3))} g" if v100 != 0 else "0"))
if "Sodio" in main_selected:
    v100 = main_inputs.get("Sodio", 0.0)
    rows.append(("Sodio", f"{int(v100)} mg" if v100 != 0 else "0", f"{int(round(v100*factor,0))} mg" if v100 != 0 else "0"))

# micronutrients in PREDEF order if selected
for name, unit in PREDEF_MICROS:
    if name in selected_micros:
        v100 = micros_values.get(name, 0.0)
        vpor = round(v100 * factor, 3)
        rows.append((name, f"{trim_num_str(v100)} {unit}" if v100 != 0 else "", f"{trim_num_str(vpor)} {unit}" if vpor != 0 else ""))

# custom micros appended
for name, val, unit in custom_micros:
    v100 = val
    vpor = round(v100 * factor, 3)
    rows.append((name, f"{trim_num_str(v100)} {unit}" if v100 != 0 else "", f"{trim_num_str(vpor)} {unit}" if vpor != 0 else ""))

# -------------------------
# Preview
# -------------------------
st.subheader("Vista previa de la tabla (por 100 / por porción)")
df_preview = pd.DataFrame([{"Nutriente": r[0], f"Por 100 {unidad_100}": r[1], f"Por porción ({int(porcion_val)} {unidad_100})": r[2]} for r in rows])
st.dataframe(df_preview, use_container_width=True)

# -------------------------
# Indicative front-of-pack evaluation (referential)
# -------------------------
st.markdown("---")
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

st.markdown("---")

# -------------------------
# PDF generation (complete, auto-height)
# -------------------------
def generar_pdf(rows, no_signif_text, table_width_mm=100):
    # A4 page
    page_w, page_h = A4
    table_w = mm2pt(table_width_mm)

    # layout params (mm)
    top_margin_mm = 6
    left_margin_mm = 6
    right_margin_mm = 6
    title_h_mm = 8
    line_after_info_mm = 3
    header_h_mm = 6
    row_h_mm = 7.0  # height per row
    footer_h_mm = 8
    n_rows = len(rows)

    # compute table height dynamically
    content_h_mm = title_h_mm + line_after_info_mm*2 + header_h_mm + n_rows * row_h_mm + footer_h_mm + 8
    table_h_mm = max(75, content_h_mm)
    table_h = mm2pt(table_h_mm)

    # center table on A4
    table_x = (page_w - table_w) / 2
    table_y = (page_h - table_h) / 2

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # outer rectangle
    c.setLineWidth(1)
    c.rect(table_x, table_y, table_w, table_h)

    # fonts and sizes
    font_reg = "Helvetica"
    font_bold = "Helvetica-Bold"
    sz_title = 10
    sz_normal = 9
    sz_important = int(sz_normal * 1.3)

    # title position
    y = table_y + table_h - mm2pt(top_margin_mm)
    c.setFont(font_bold, sz_title)
    c.drawString(table_x + mm2pt(left_margin_mm), y, "Información Nutricional")

    # tamaño de porción (línea aparte)
    y -= mm2pt(line_after_info_mm + 2)
    c.setFont(font_reg, sz_normal)
    c.drawString(table_x + mm2pt(left_margin_mm), y, f"Tamaño de porción: {porcion_text} ({int(porcion_val)} {unidad_100})")

    # número de porciones (línea aparte)
    y -= mm2pt(line_after_info_mm + 2)
    c.drawString(table_x + mm2pt(left_margin_mm), y, f"Número de porciones por envase: {num_porciones if num_porciones else '-'}")

    # thick line under info
    y -= mm2pt(line_after_info_mm + 1)
    c.setLineWidth(1)
    c.line(table_x + mm2pt(3), y, table_x + table_w - mm2pt(3), y)

    # header columns
    y -= mm2pt(7)
    col_n_x = table_x + mm2pt(left_margin_mm)
    col_100_x = table_x + table_w * 0.55
    col_por_x = table_x + table_w * 0.85
    c.setFont(font_bold, sz_normal)
    c.drawString(col_100_x, y, f"Por 100 {unidad_100}")
    c.drawString(col_por_x, y, f"Por porción ({int(porcion_val)} {unidad_100})")

    # underline header
    y -= mm2pt(3)
    c.setLineWidth(0.75)
    c.line(table_x + mm2pt(3), y, table_x + table_w - mm2pt(3), y)

    # rows start
    y -= mm2pt(6)
    row_h = mm2pt(row_h_mm)
    thin_y_for_sodio = None
    important_set = {"Calorías (kcal)", "  Grasa saturada", "  Grasas trans", "  Azúcares añadidos", "Sodio"}

    for name, v100, vpor in rows:
        # font
        # note: rows may have leading two spaces for indentation "  " set earlier
        display_name = name
        if display_name.strip() in {"Grasa saturada", "Grasas trans", "Azúcares añadidos", "Sodio", "Calorías (kcal)"}:
            # use bold + larger for highlighted nutrients
            c.setFont(font_bold, sz_important)
        else:
            c.setFont(font_reg, sz_normal)

        # draw name
        c.drawString(col_n_x, y, display_name)

        # values (right aligned)
        c.setFont(font_reg, sz_normal)
        c.drawRightString(col_100_x + mm2pt(22), y, v100)
        c.drawRightString(col_por_x + mm2pt(22), y, vpor)

        # after row: thin separator
        y_after = y - row_h
        thin_line_y = y_after + mm2pt(2.5)
        c.setLineWidth(0.5)
        c.line(table_x + mm2pt(3), thin_line_y, table_x + table_w - mm2pt(3), thin_line_y)

        # store position after sodium for thick separator
        if display_name.strip().lower().startswith("sodio"):
            thin_y_for_sodio = thin_line_y

        y = y_after

    # thick separator after sodium (if found) - draw at stored thin_y_for_sodio
    if thin_y_for_sodio:
        c.setLineWidth(1)
        c.line(table_x + mm2pt(3), thin_y_for_sodio, table_x + table_w - mm2pt(3), thin_y_for_sodio)

    # vertical separators full height, drawn last
    c.setLineWidth(0.75)
    x_v1 = table_x + mm2pt(3)
    x_v2 = table_x + table_w * 0.52
    x_v3 = table_x + table_w * 0.82
    c.line(x_v1, table_y + mm2pt(2), x_v1, table_y + table_h - mm2pt(2))
    c.line(x_v2, table_y + mm2pt(2), x_v2, table_y + table_h - mm2pt(2))
    c.line(x_v3, table_y + mm2pt(2), x_v3, table_y + table_h - mm2pt(2))

    # No es fuente significativa... inside recuadro under rows (wrap if needed)
    if no_signif_text:
        wrap_width_chars = 80
        lines = textwrap.wrap(no_signif_text, width=wrap_width_chars)
        ns_y = table_y + mm2pt(4)
        c.setFont(font_reg, 8)
        for i, line in enumerate(lines):
            c.drawString(table_x + mm2pt(left_margin_mm), ns_y + mm2pt(4) * i, line)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# -------------------------
# Generate and download PDF
# -------------------------
st.markdown("---")
if st.button("Generar tabla y descargar PDF"):
    pdf = generar_pdf(rows, no_signif_text, table_width_mm=100)
    st.download_button(
        label="Descargar tabla nutricional (PDF)",
        data=pdf,
        file_name="tabla_nutricional.pdf",
        mime="application/pdf"
    )

