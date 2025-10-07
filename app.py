import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import textwrap

# ------------------------------
# Helpers
# ------------------------------
def mm_to_pt(x_mm):
    return x_mm * mm

# ------------------------------
# App config
# ------------------------------
st.set_page_config(page_title="Generador Tabla Nutricional", layout="centered")
st.title("Generador de Tabla de Información Nutricional")
st.write("Ingrese los datos en el orden solicitado. Vit./Minerales: ingresar sólo números; unidades se añadirán automáticamente.")

# ------------------------------
# Tipo y modo de tamaño
# ------------------------------
st.header("Configuración inicial")
tipo = st.selectbox("Tipo de producto (afecta encabezado)", ["Sólido (por 100 g)", "Líquido (por 100 mL)"])
unidad_100 = "g" if tipo.startswith("Sólido") else "mL"
tamano_mode = st.selectbox("Modo de tamaño para la tabla en PDF", ["Altura automática según contenido", "Altura fija (aprox. 85 mm)"])

st.markdown("---")

# ------------------------------
# Selección de nutrientes principales
# ------------------------------
st.header("Seleccione los nutrientes principales que desea declarar")
MAIN_ORDER = [
    "Calorías (kcal)",
    "Grasa total",
    "Grasa saturada",
    "Grasas trans",
    "Carbohidratos totales",
    "Fibra dietaria",
    "Azúcares totales",
    "Azúcares añadidos",
    "Proteína",
    "Sodio"
]

st.markdown("**Calorías (kcal)** — siempre declarado (se calcula automáticamente).")
main_selected = ["Calorías (kcal)"]
for nutrient in MAIN_ORDER[1:]:
    if st.checkbox(nutrient, value=True):
        main_selected.append(nutrient)

st.markdown("---")

# ------------------------------
# Porción y número de porciones
# ------------------------------
st.header("Datos de porción")
porcion_text = st.text_input("Texto de tamaño de porción (ej. 1 porción = 30 g)", "1 porción")
porcion_val = st.number_input(f"Tamaño de porción (número en {unidad_100})", min_value=1.0, value=30.0, step=1.0)
num_porciones = st.text_input("Número de porciones por envase (dejar en blanco si variable)", "")

st.markdown("---")

# ------------------------------
# Valores por 100 para nutrientes seleccionados
# ------------------------------
st.header("Valores por 100 " + unidad_100 + " (ingrese sólo números)")

main_inputs = {}
for nutrient in MAIN_ORDER:
    if nutrient == "Calorías (kcal)":
        continue
    if nutrient in main_selected:
        if nutrient == "Sodio":
            val = st.number_input(f"{nutrient} (mg por 100 {unidad_100})", min_value=0.0, value=0.0, step=1.0, key=f"in_{nutrient}")
            main_inputs[nutrient] = val
        else:
            val = st.number_input(f"{nutrient} (g por 100 {unidad_100})", min_value=0.0, value=0.0, step=0.01, key=f"in_{nutrient}")
            main_inputs[nutrient] = val

st.markdown("---")

# ------------------------------
# Micronutrientes predefinidos y personalizados
# ------------------------------
st.header("Vitaminas y minerales (seleccione los que declare)")

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
selected_micros = st.multiselect("Micronutrientes predefinidos:", micro_names)

st.write("Ingrese los valores por 100 " + unidad_100 + " para los micronutrientes seleccionados (sólo números).")
micros_values = {}
for name in selected_micros:
    val = st.number_input(f"{name} (por 100 {unidad_100})", min_value=0.0, value=0.0, step=0.01, key=f"mic_{name}")
    micros_values[name] = val

st.markdown("---")
add_custom = st.checkbox("Añadir micronutrientes personalizados (opcional)")
custom_micros = []
if add_custom:
    st.write("Añada nombre, valor por 100 y unidad para cada micronutriente adicional.")
    n_custom = st.number_input("¿Cuántos micronutrientes personalizados desea añadir?", min_value=1, max_value=10, value=1, step=1)
    for i in range(int(n_custom)):
        cname = st.text_input(f"Nombre micronutriente #{i+1}", key=f"cname_{i}")
        cval = st.number_input(f"Valor por 100 {unidad_100} #{i+1}", min_value=0.0, value=0.0, step=0.01, key=f"cval_{i}")
        cunit = st.selectbox(f"Unidad #{i+1}", ["mg", "µg", "µg ER", "g", "IU"], key=f"cunit_{i}")
        if cname:
            custom_micros.append((cname, cval, cunit))

st.markdown("---")

# ------------------------------
# Frase "no es fuente significativa"
# ------------------------------
st.header("Frase para nutrientes no significativos (pie de tabla)")
no_signif_text = st.text_input("Escriba la frase tal como desea que aparezca (ej.: No es fuente significativa de: vitamina C, potasio).", "")

st.markdown("---")

# ------------------------------
# Cálculos por 100 y por porción
# ------------------------------
factor = porcion_val / 100.0
fat = main_inputs.get("Grasa total", 0.0)
prot = main_inputs.get("Proteína", 0.0)
cho = main_inputs.get("Carbohidratos totales", 0.0)

energia_100 = round(4 * (prot + cho) + 9 * fat, 0)
energia_por = int(round(energia_100 * factor, 0))

# ------------------------------
# Construcción filas (orden normativo)
# ------------------------------
rows = []
rows.append(("Calorías (kcal)", f"{energia_100}", f"{energia_por}"))

order_for_mains = [
    ("Grasa total", "g"),
    ("Grasa saturada", "g"),
    ("Grasas trans", "g"),
    ("Carbohidratos totales", "g"),
    ("Fibra dietaria", "g"),
    ("Azúcares totales", "g"),
    ("Azúcares añadidos", "g"),
    ("Proteína", "g"),
    ("Sodio", "mg")
]

for name, unit in order_for_mains:
    if name in main_selected:
        v100 = main_inputs.get(name, 0.0)
        if name == "Sodio":
            vpor = int(round(v100 * factor, 0))
            rows.append((name, f"{int(v100)} {unit}", f"{vpor} {unit}"))
        else:
            vpor = round(v100 * factor, 3)
            v100s = f"{v100}".rstrip('0').rstrip('.') if isinstance(v100, float) else str(v100)
            vprs = f"{vpor}".rstrip('0').rstrip('.') if isinstance(vpor, float) else str(vpor)
            rows.append((name, f"{v100s} {unit}", f"{vprs} {unit}"))

# Micronutrientes (predefinidos) en orden de PREDEF_MICROS
for name, unit in PREDEF_MICROS:
    if name in selected_micros:
        v100 = micros_values.get(name, 0.0)
        vpor = round(v100 * factor, 3)
        v100s = f"{v100}".rstrip('0').rstrip('.') if isinstance(v100, float) else str(v100)
        vprs = f"{vpor}".rstrip('0').rstrip('.') if isinstance(vpor, float) else str(vpor)
        rows.append((name, f"{v100s} {unit}" if v100 != 0 else "", f"{vprs} {unit}" if vpor != 0 else ""))

# Custom micros appended in order entered
for name, val, unit in custom_micros:
    v100 = val
    vpor = round(v100 * factor, 3)
    v100s = f"{v100}".rstrip('0').rstrip('.') if isinstance(v100, float) else str(v100)
    vprs = f"{vpor}".rstrip('0').rstrip('.') if isinstance(vpor, float) else str(vpor)
    rows.append((name, f"{v100s} {unit}" if v100 != 0 else "", f"{vprs} {unit}" if vpor != 0 else ""))

# ------------------------------
# Vista previa
# ------------------------------
st.subheader("Vista previa")
df_preview = pd.DataFrame([{"Nutriente": r[0], f"Por 100 {unidad_100}": r[1], f"Por porción ({int(porcion_val)} {unidad_100})": r[2]} for r in rows])
st.dataframe(df_preview, use_container_width=True)

st.markdown("---")

# ------------------------------
# Evaluación indicativa de sellos frontales (referencial)
# ------------------------------
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

# ------------------------------
# Función PDF (versión corregida)
# ------------------------------
def generar_pdf(rows, no_signif_text, width_table_mm=100, fixed_height=False):
    page_w, page_h = A4
    table_w = mm_to_pt(width_table_mm)

    # Diseño (mm)
    row_h_mm = 7.0
    margin_sup_mm = 6
    margin_lat_mm = 6
    separacion_mm = 4
    footer_h_mm = 8
    n_rows = len(rows)

    if fixed_height:
        table_h_mm = 85
    else:
        table_h_mm = max(75, 35 + n_rows * row_h_mm + footer_h_mm)
    table_h = mm_to_pt(table_h_mm)

    # Centrado
    table_x = (page_w - table_w) / 2
    table_y = (page_h - table_h) / 2

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Borde exterior
    c.setLineWidth(1)
    c.rect(table_x, table_y, table_w, table_h)

    # Fuentes y tamaños
    font_reg = "Helvetica"
    font_bold = "Helvetica-Bold"
    size_titulo = 10
    size_normal = 9
    size_destacado = int(size_normal * 1.3)

    # Título
    y_actual = table_y + table_h - mm_to_pt(margin_sup_mm)
    c.setFont(font_bold, size_titulo)
    c.drawString(table_x + mm_to_pt(margin_lat_mm), y_actual, "Información Nutricional")

    # Tamaño de porción (línea aparte)
    y_actual -= mm_to_pt(separacion_mm + 4)
    c.setFont(font_reg, size_normal)
    c.drawString(table_x + mm_to_pt(margin_lat_mm), y_actual, f"Tamaño de porción: {porcion_text} ({int(porcion_val)} {unidad_100})")

    # Número de porciones (línea aparte)
    y_actual -= mm_to_pt(separacion_mm + 4)
    c.drawString(table_x + mm_to_pt(margin_lat_mm), y_actual, f"Número de porciones por envase: {num_porciones if num_porciones else '-'}")

    # Línea divisoria gruesa
    y_actual -= mm_to_pt(separacion_mm)
    c.setLineWidth(1)
    c.line(table_x + mm_to_pt(3), y_actual, table_x + table_w - mm_to_pt(3), y_actual)

    # Encabezado columnas
    y_actual -= mm_to_pt(6)
    col_nutr_x = table_x + mm_to_pt(6)
    col_100_x = table_x + table_w * 0.55
    col_por_x = table_x + table_w * 0.85

    c.setFont(font_bold, size_normal)
    c.drawString(col_100_x, y_actual, f"Por 100 {unidad_100}")
    c.drawString(col_por_x, y_actual, f"Por porción ({int(porcion_val)} {unidad_100})")

    # Línea bajo encabezado
    y_actual -= mm_to_pt(3)
    c.setLineWidth(0.75)
    c.line(table_x + mm_to_pt(3), y_actual, table_x + table_w - mm_to_pt(3), y_actual)

    # Filas
    y_actual -= mm_to_pt(5)
    row_h = mm_to_pt(row_h_mm)
    important_labels = {"Calorías (kcal)", "Grasa saturada", "Grasas trans", "Azúcares añadidos", "Sodio"}
    sep_y_for_sodio = None

    for name, v100, vpor in rows:
        if name in important_labels:
            c.setFont(font_bold, size_destacado)
        else:
            c.setFont(font_reg, size_normal)

        c.drawString(col_nutr_x, y_actual, name)
        c.setFont(font_reg, size_normal)
        # Right align values (if empty strings, drawRightString is still OK)
        c.drawRightString(col_100_x + mm_to_pt(22), y_actual, v100)
        c.drawRightString(col_por_x + mm_to_pt(22), y_actual, vpor)

        # Move down and draw thin separator
        y_after = y_actual - row_h
        thin_line_y = y_after + mm_to_pt(2.5)
        c.setLineWidth(0.5)
        c.line(table_x + mm_to_pt(3), thin_line_y, table_x + table_w - mm_to_pt(3), thin_line_y)

        # If this row is Sodio, store separator Y to draw thick later
        if name.strip().lower().startswith("sodio"):
            sep_y_for_sodio = thin_line_y

        y_actual = y_after

    # Thick separator after sodio (macros vs micros)
    if sep_y_for_sodio is not None:
        c.setLineWidth(1)
        c.line(table_x + mm_to_pt(3), sep_y_for_sodio, table_x + table_w - mm_to_pt(3), sep_y_for_sodio)

    # Vertical separators full height
    c.setLineWidth(0.75)
    x_v1 = table_x + mm_to_pt(3)
    x_v2 = table_x + table_w * 0.52
    x_v3 = table_x + table_w * 0.82
    c.line(x_v1, table_y + mm_to_pt(2), x_v1, table_y + table_h - mm_to_pt(2))
    c.line(x_v2, table_y + mm_to_pt(2), x_v2, table_y + table_h - mm_to_pt(2))
    c.line(x_v3, table_y + mm_to_pt(2), x_v3, table_y + table_h - mm_to_pt(2))

    # Pie: "No es fuente significativa..." (si existe)
    if no_signif_text:
        c.setFont(font_reg, 8)
        ns_lines = textwrap.wrap(no_signif_text, width=80)
        ns_y = table_y + mm_to_pt(4)
        for i, line in enumerate(ns_lines):
            c.drawString(table_x + mm_to_pt(margin_lat_mm), ns_y + mm_to_pt(4) * i, line)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ------------------------------
# Botón generar y descargar
# ------------------------------
st.markdown("---")
if st.button("Generar tabla y descargar PDF"):
    fixed_mode = True if tamano_mode == "Altura fija (aprox. 85 mm)" else False
    pdf_buf = generar_pdf(rows, no_signif_text, width_table_mm=100, fixed_height=fixed_mode)
    st.download_button(
        label="Descargar tabla nutricional (PDF)",
        data=pdf_buf,
        file_name="tabla_nutricional.pdf",
        mime="application/pdf"
    )
