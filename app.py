import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# ------------------------------
# Configuración inicial
# ------------------------------
st.set_page_config(page_title="Generador Tabla Nutricional", layout="centered")
st.title("Generador de Tabla de Información Nutricional (Formato normativo)")

st.write("Ingrese los datos en el orden solicitado. Vit./Minerales: ingresar sólo números; unidades se añadirán automáticamente.")

# ------------------------------
# Selección tipo y formato
# ------------------------------
st.header("Configuración inicial")
tipo = st.selectbox("Tipo de producto (afecta encabezado)", ["Sólido (por 100 g)", "Líquido (por 100 mL)"])
unidad_100 = "g" if tipo.startswith("Sólido") else "mL"

st.markdown("---")

# ------------------------------
# Selección de qué nutrientes principales incluir
# (Calorías siempre incluidas)
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

# Mostrar checkboxes en el orden normativo; Calorías siempre True but no checkbox
st.markdown("**Calorías (kcal)** — siempre declarado (se calcula automáticamente).")
main_selected = ["Calorías (kcal)"]
for nutrient in MAIN_ORDER[1:]:
    if st.checkbox(nutrient, value=True):
        main_selected.append(nutrient)

st.markdown("---")

# ------------------------------
# Entradas: porción y número porciones
# ------------------------------
st.header("Datos de porción")
porcion_text = st.text_input("Texto de tamaño de porción (ej. 1 porción = 30 g)", "1 porción")
porcion_val = st.number_input(f"Tamaño de porción (número en {unidad_100})", min_value=1.0, value=30.0, step=1.0)
num_porciones = st.text_input("Número de porciones por envase (dejar en blanco si variable)", "")

st.markdown("---")

# ------------------------------
# Entradas: valores por 100 g/mL para los nutrientes seleccionados
# (solo pedimos inputs para los seleccionados)
# ------------------------------
st.header("Valores por 100 " + unidad_100 + " (ingrese sólo números)")

# We'll keep a dictionary of inputs for the main nutrients
main_inputs = {}

# For calorías we don't ask input (calculated), but for the rest that are selected, ask numeric input
# Provide sensible defaults 0.0
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
# Micronutrientes: multiselección + custom
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
    # default 0
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
# No es fuente significativa ...
# ------------------------------
st.header("Nota para nutrientes no significativos (pie de tabla)")
no_signif_text = st.text_input("Escriba la frase tal como desea que aparezca (ej.: No es fuente significativa de: vitamina C, potasio).", "")

st.markdown("---")

# ------------------------------
# Cálculos por 100 y por porción
# ------------------------------
factor = porcion_val / 100.0
# Energy: calories calculated from protein and carbohydrates and fat if provided - set defaults if not provided
# Ensure the required values exist or default to 0
fat = main_inputs.get("Grasa total", 0.0)
prot = main_inputs.get("Proteína", 0.0)
cho = main_inputs.get("Carbohidratos totales", 0.0)

energia_100 = round(4 * (prot + cho) + 9 * fat, 0)
energia_por = int(round(energia_100 * factor, 0))

# build dict for display per selected nutrients
def value_str(nutrient, per100, perpor, unit):
    if per100 is None or per100 == "":
        return "", ""
    return f"{per100} {unit}".strip(), f"{perpor} {unit}".strip()

# Main rows in order - only include those selected (calories always included)
rows = []
# Calorías
rows.append(("Calorías (kcal)", f"{energia_100}", f"{energia_por}"))

# Subsequent main nutrients in normative order if selected
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
        # por-porción calc
        if name == "Sodio":
            vpor = int(round(v100 * factor, 0))
        else:
            vpor = round(v100 * factor, 3) if isinstance(v100, float) else v100
        # format strings (remove trailing .0 if integer visually preferable)
        if name == "Sodio":
            rows.append((name, f"{int(v100)} {unit}", f"{vpor} {unit}"))
        else:
            # trim unnecessary zeros
            v100s = f"{v100}".rstrip('0').rstrip('.') if isinstance(v100, float) else str(v100)
            vpars = f"{vpor}".rstrip('0').rstrip('.') if isinstance(vpor, float) else str(vpor)
            rows.append((name, f"{v100s} {unit}", f"{vpars} {unit}"))

# After main macros, add micronutrients in Table9 order (predefs) if selected
for name, unit in PREDEF_MICROS:
    if name in selected_micros:
        v100 = micros_values.get(name, 0.0)
        vpor = round(v100 * factor, 3)
        v100s = f"{v100}".rstrip('0').rstrip('.') if isinstance(v100, float) else str(v100)
        vprs = f"{vpor}".rstrip('0').rstrip('.') if isinstance(vpor, float) else str(vpor)
        rows.append((name, f"{v100s} {unit}" if v100 != 0 else "", f"{vprs} {unit}" if vpor != 0 else ""))

# Append custom micros after predefs
for name, val, unit in custom_micros:
    v100 = val
    vpor = round(v100 * factor, 3)
    v100s = f"{v100}".rstrip('0').rstrip('.') if isinstance(v100, float) else str(v100)
    vprs = f"{vpor}".rstrip('0').rstrip('.') if isinstance(vpor, float) else str(vpor)
    rows.append((name, f"{v100s} {unit}" if v100 != 0 else "", f"{vprs} {unit}" if vpor != 0 else ""))

# ------------------------------
# Preview DataFrame
# ------------------------------
st.subheader("Vista previa")
df_preview = pd.DataFrame([{"Nutriente": r[0], f"Por 100 {unidad_100}": r[1], f"Por porción ({int(porcion_val)} {unidad_100})": r[2]} for r in rows])
st.dataframe(df_preview, use_container_width=True)

# ------------------------------
# Evaluación indicativa sellos frontales (referencial)
# ------------------------------
st.markdown("---")
st.subheader("Evaluación indicativa de sellos frontales")
sellos = []
# Use the 100g references if present
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
# PDF generation: A4 centered, table with width and height dynamic; lines connect to borders
# ------------------------------
def mm_to_pt(x):
    return x * mm

def generar_pdf(rows, no_signif_text, width_table_mm=100, fixed_height=False):
    page_w, page_h = A4
    table_w = mm_to_pt(width_table_mm)

    # constants (mm)
    row_h_mm = 7.0  # adequate readable row height
    title_h_mm = 10
    info_h_mm = 8
    sep_line_h_mm = 2
    footer_h_mm = 8
    n_rows = len(rows)
    content_h_mm = title_h_mm + info_h_mm + sep_line_h_mm + n_rows * row_h_mm + footer_h_mm + 6

    if fixed_height:
        table_h_mm = 85
    else:
        table_h_mm = max(60, content_h_mm)

    table_h = mm_to_pt(table_h_mm)
    # position table centered
    table_x = (page_w - table_w) / 2
    table_y = (page_h - table_h) / 2

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Outer rect (1 pt)
    c.setLineWidth(1)
    c.rect(table_x, table_y, table_w, table_h)

    # Title
    title_font = "Helvetica-Bold"
    normal_font = "Helvetica"
    title_size = 10
    normal_size = 9
    important_size = int(normal_size * 1.3)

    c.setFont(title_font, title_size)
    title_x = table_x + mm_to_pt(6)
    title_y = table_y + table_h - mm_to_pt(6)
    c.drawString(title_x, title_y, "Información Nutricional")

    # portion and count on same line
    c.setFont(normal_font, normal_size)
    info_y = title_y - mm_to_pt(6)
    c.drawString(title_x, info_y, f"Tamaño de porción: {porcion_text} ({int(porcion_val)} {unidad_100})")
    c.drawRightString(table_x + table_w - mm_to_pt(6), info_y, f"Número de porciones por envase: {num_porciones if num_porciones else '-'}")

    # thick separator line between porciones and calories
    line_y = info_y - mm_to_pt(4)
    c.setLineWidth(1)
    c.line(table_x + mm_to_pt(3), line_y, table_x + table_w - mm_to_pt(3), line_y)

    # Header for columns
    header_y = line_y - mm_to_pt(8)
    col_nutr_x = table_x + mm_to_pt(6)
    col_100_x = table_x + table_w * 0.55
    col_por_x = table_x + table_w * 0.85

    c.setFont(title_font, normal_size)
    c.drawString(col_100_x, header_y, f"Por 100 {unidad_100}")
    c.drawString(col_por_x, header_y, f"Por porción ({int(porcion_val)} {unidad_100})")

    # underline header
    head_line_y = header_y - mm_to_pt(2)
    c.setLineWidth(0.75)
    c.line(table_x + mm_to_pt(3), head_line_y, table_x + table_w - mm_to_pt(3), head_line_y)

    # Draw rows
    current_y = head_line_y - mm_to_pt(6)
    row_h = mm_to_pt(row_h_mm)

    # For identifying important labels for bold and larger font
    important_labels = {"Calorías (kcal)", "Grasa saturada", "Grasas trans", "Azúcares añadidos", "Sodio"}

    for name, v100, vpor in rows:
        # set font
        if name in important_labels:
            c.setFont(title_font, important_size)
        else:
            c.setFont(normal_font, normal_size)

        # draw nutrient name (left)
        c.drawString(col_nutr_x, current_y, name)

        # draw values right aligned
        c.setFont(normal_font, normal_size)
        # right align positions slightly inset from column x to ensure alignment with border
        c.drawRightString(col_100_x + mm_to_pt(22), current_y, v100)
        c.drawRightString(col_por_x + mm_to_pt(22), current_y, vpor)

        # draw horizontal separator that spans full width to border
        current_y -= row_h
        c.setLineWidth(0.5)
        c.line(table_x + mm_to_pt(3), current_y + mm_to_pt(3), table_x + table_w - mm_to_pt(3), current_y + mm_to_pt(3))

    # thicker separation line after sodium (macros vs micros)
    idx_sodio = next((i for i, (n, a, b) in enumerate(rows) if n.strip().lower().startswith("sodio")), None)
    if idx_sodio is not None:
        sep_y = head_line_y - mm_to_pt(6) - mm_to_pt(row_h_mm) * (idx_sodio + 1)
        c.setLineWidth(1)
        c.line(table_x + mm_to_pt(3), sep_y, table_x + table_w - mm_to_pt(3), sep_y)

    # Draw vertical separators for columns that connect to borders (drawn last to overlay)
    # left vertical (near nutrient names) and two verticals for column separation
    # use thin lines 0.75 pt
    c.setLineWidth(0.75)
    # first vertical line (left padding)
    x_v1 = table_x + mm_to_pt(3)
    x_v2 = table_x + table_w * 0.52
    x_v3 = table_x + table_w * 0.82
    # draw vertical lines from top to bottom of table
    c.line(x_v1, table_y + table_h - mm_to_pt(2), x_v1, table_y + mm_to_pt(2))
    c.line(x_v2, table_y + table_h - mm_to_pt(2), x_v2, table_y + mm_to_pt(2))
    c.line(x_v3, table_y + table_h - mm_to_pt(2), x_v3, table_y + mm_to_pt(2))

    # "No es fuente significativa..." text under the table content if provided
    if no_signif_text:
        ns_y = table_y + mm_to_pt(4)
        c.setFont(normal_font, 8)
        # wrap if long
        max_chars = 80
        text = no_signif_text
        lines = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
        for i, line in enumerate(lines):
            c.drawString(title_x, ns_y + mm_to_pt(3) + mm_to_pt(4) * i, line)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ------------------------------
# Botón generar y descargar
# ------------------------------
st.markdown("---")
if st.button("Generar tabla y descargar PDF"):
    # generate PDF with fixed height False for automatic height based on rows
    fixed_mode = False
    pdf = generar_pdf(rows, no_signif_text, width_table_mm=100, fixed_height=fixed_mode)
    st.download_button("Descargar tabla nutricional (PDF)", data=pdf, file_name="tabla_nutricional.pdf", mime="application/pdf")
