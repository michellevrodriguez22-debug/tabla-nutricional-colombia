import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# ---------------------
# Configuración Streamlit
# ---------------------
st.set_page_config(page_title="Generador Tabla Nutricional (Normativa)", layout="centered")
st.title("Generador de Tabla de Información Nutricional")
st.write("Ingrese los datos en el orden solicitado. Vitaminas y minerales (predefinidos) -> ingresar solo valores numéricos (sin unidades).")

# ---------------------
# Selección tipo y formato
# ---------------------
st.header("Configuración inicial")
col1, col2 = st.columns(2)
with col1:
    tipo = st.selectbox("Tipo de producto (afecta encabezado)", ["Sólido (por 100 g)", "Líquido (por 100 mL)"])
with col2:
    tamaño_mode = st.selectbox("Modo de tamaño para la tabla en PDF", ["Altura automática según contenido", "Altura fija (aprox. 85 mm)"])

unidad_100 = "g" if tipo.startswith("Sólido") else "mL"

st.markdown("---")

# ---------------------
# Entradas: porción y número porciones
# ---------------------
st.header("Datos de porción")
porcion_text = st.text_input("Texto de tamaño de porción (ej. 1 porción = 30 g)", "1 porción")
porcion_val = st.number_input(f"Tamaño de porción (número en {unidad_100})", min_value=1.0, value=30.0, step=1.0)
num_porciones = st.text_input("Número de porciones por envase (dejar en blanco si variable)", "")

st.markdown("---")

# ---------------------
# Entradas: nutrientes principales (orden obligatorio)
# No pedimos kcal; se calcula
# ---------------------
st.header("Nutrientes (valores por 100 " + unidad_100 + ") — ingresar solo números")
# 1) Grasa total
grasa_total_100 = st.number_input("Grasa total (g por 100)", min_value=0.0, value=0.0, step=0.1)
# 2) Grasa saturada (sangría)
grasa_sat_100 = st.number_input("  - Grasa saturada (g por 100)", min_value=0.0, value=0.0, step=0.1)
# 3) Grasas trans
grasa_trans_100 = st.number_input("  - Grasas trans (g por 100)", min_value=0.0, value=0.0, step=0.01)
# 4) Carbohidratos totales
carbo_100 = st.number_input("Carbohidratos totales (g por 100)", min_value=0.0, value=0.0, step=0.1)
# 5) Fibra dietaria
fibra_100 = st.number_input("  - Fibra dietaria (g por 100)", min_value=0.0, value=0.0, step=0.1)
# 6) Azúcares totales
azucares_100 = st.number_input("  - Azúcares totales (g por 100)", min_value=0.0, value=0.0, step=0.1)
# 7) Azúcares añadidos
azucares_anad_100 = st.number_input("  - Azúcares añadidos (g por 100)", min_value=0.0, value=0.0, step=0.1)
# 8) Proteína
proteina_100 = st.number_input("Proteína (g por 100)", min_value=0.0, value=0.0, step=0.1)
# 9) Sodio
sodio_100 = st.number_input("Sodio (mg por 100)", min_value=0.0, value=0.0, step=1.0)

st.markdown("---")

# ---------------------
# Micronutrientes: selección múltiple + posibilidad añadir custom
# Predefinidos (orden según Tabla 9 parcialmente): A,D,E,K,C,B1,B2,B3,B6,Folato,B12,Biotina,Pantoténico,
# Calcio, Hierro, Magnesio, Zinc, Selenio, Cobre, Manganeso, Yodo, Potasio
# ---------------------
st.header("Vitaminas y minerales (seleccione los que declare y escriba sus valores numéricos)")

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
selected_micros = st.multiselect("Micronutrientes (seleccione varios):", micro_names)

# Inputs para los micronutrientes seleccionados: enteros/decimales sin unidad
micros_values = {}
st.markdown("**Ingrese solo el valor numérico** (las unidades se añadirán automáticamente según la lista oficial).")
for name in selected_micros:
    default_val = 0.0
    val = st.number_input(f"{name} (valor por 100 {unidad_100})", min_value=0.0, value=default_val, step=0.01, key=f"mic_{name}")
    micros_values[name] = val

st.markdown("**Agregar micronutrientes personalizados** (opcional). Si añade alguno, indique unidad en el campo correspondiente.")
add_custom = st.checkbox("Agregar micronutrientes personalizados")

custom_micros = []
if add_custom:
    with st.expander("Añadir micronutriente personalizado (puede añadir varios)"):
        add_more = True
        counter = 0
        while add_more:
            counter += 1
            coln, colv, colu = st.columns([3,2,2])
            with coln:
                cname = st.text_input(f"Nombre micronutriente #{counter}", key=f"cname_{counter}")
            with colv:
                cval = st.number_input(f"Valor por 100 {unidad_100} #{counter}", min_value=0.0, value=0.0, key=f"cval_{counter}")
            with colu:
                cunit = st.selectbox(f"Unidad #{counter}", ["mg", "µg", "µg ER", "g", "IU"], key=f"cunit_{counter}")
            if cname:
                custom_micros.append((cname, cval, cunit))
            add_more = st.checkbox(f"Añadir otro micronutriente (#{counter+1})", key=f"more_{counter}")
            # break loop if user doesn't check add_more; streamlit will re-render so this simplistic loop works as input area

st.markdown("---")

# ---------------------
# "No es fuente significativa de ..." — campo libre
# ---------------------
st.header("Frase para nutrientes no significativos")
no_signif_text = st.text_input("Escriba la frase tal como desea que aparezca (ej. No es fuente significativa de: vitamina C, potasio).", "")

st.markdown("---")

# ---------------------
# Cálculos: energía y por porción
# ---------------------
factor = porcion_val / 100.0
energia_100 = round(4 * (proteina_100 + carbo_100) + 9 * grasa_total_100, 0)
energia_por = int(round(energia_100 * factor, 0))

# cálculos por porción para macros
grasa_total_por = round(grasa_total_100 * factor, 2)
grasa_sat_por = round(grasa_sat_100 * factor, 2)
grasa_trans_por = round(grasa_trans_100 * factor, 3)
carbo_por = round(carbo_100 * factor, 2)
fibra_por = round(fibra_100 * factor, 2)
azucares_por = round(azucares_100 * factor, 2)
azucares_anad_por = round(azucares_anad_100 * factor, 2)
proteina_por = round(proteina_100 * factor, 2)
sodio_por = int(round(sodio_100 * factor, 0))

# micros por porción
micros_por_values = {name: round(val * factor, 3) for name, val in micros_values.items()}
custom_micros_por = [(name, round(val * factor, 3), unit) for (name, val, unit) in custom_micros]

# ---------------------
# Construcción del listado final (orden obligatorio)
# ---------------------
# Order main nutrients as required
main_labels = [
    ("Calorías (kcal)", str(energia_100), str(energia_por)),
    ("Grasa total", f"{grasa_total_100} g", f"{grasa_total_por} g"),
    ("  Grasa saturada", f"{grasa_sat_100} g", f"{grasa_sat_por} g"),
    ("  Grasas trans", f"{grasa_trans_100} g", f"{grasa_trans_por} g"),
    ("Carbohidratos totales", f"{carbo_100} g", f"{carbo_por} g"),
    ("  Fibra dietaria", f"{fibra_100} g", f"{fibra_por} g"),
    ("  Azúcares totales", f"{azucares_100} g", f"{azucares_por} g"),
    ("  Azúcares añadidos", f"{azucares_anad_100} g", f"{azucares_anad_por} g"),
    ("Proteína", f"{proteina_100} g", f"{proteina_por} g"),
    ("Sodio", f"{int(sodio_100)} mg", f"{sodio_por} mg")
]

# Micronutrients: follow the order of PREDEF_MICROS if selected
micros_ordered = []
for name, unit in PREDEF_MICROS:
    if name in selected_micros:
        val100 = f"{micros_values.get(name, 0)} {unit}" if micros_values.get(name, None) != 0 else ""
        valpor = f"{micros_por_values.get(name, 0)} {unit}" if micros_values.get(name, None) != 0 else ""
        micros_ordered.append((name, val100, valpor))

# Custom micros appended after predefs (user provided order preserved)
for name, val, unit in custom_micros:
    val100 = f"{val} {unit}" if val != 0 else ""
    valpor = f"{round(val * factor, 3)} {unit}" if val != 0 else ""
    micros_ordered.append((name, val100, valpor))

# If no micronutrients selected, but user still wants to declare only mandatory, follow instruction:
# If only micronutrients declared are the five obligatory, the order should be A, D, Iron, Calcium, Zinc (we already included those in PREDEF order)

# Build final rows list
rows = main_labels + micros_ordered

# ---------------------
# Preview table in Streamlit
# ---------------------
st.subheader("Vista previa de la tabla (por 100 " + unidad_100 + " / por porción)")
df_preview = pd.DataFrame([{"Nutriente": r[0], f"Por 100 {unidad_100}": r[1], f"Por porción ({int(porcion_val)} {unidad_100})": r[2]} for r in rows])
st.dataframe(df_preview, use_container_width=True)

# ---------------------
# Evaluación indicativa etiquetas frontales (referencial)
# ---------------------
st.markdown("---")
st.subheader("Evaluación indicativa de sellos frontales")
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

st.markdown("---")

# ---------------------
# Generación del PDF (centrado en A4, tabla con altura dinámica)
# ---------------------
def mm_to_pt(mm_val):
    return mm_val * mm

def generar_pdf(rows, no_significant_text, width_table_mm=100, fixed_height_mode=False):
    # Page setup: A4 portrait
    page_w, page_h = A4  # in points
    # Table width in points
    table_w = mm_to_pt(width_table_mm)

    # Visual row height (mm) - depend on font size; choose 6.5 mm default
    row_h_mm = 6.5
    header_h_mm = 12
    info_h_mm = 8
    separating_line_mm = 2
    footer_h_mm = 6

    # compute content height based on rows
    n_rows = len(rows)
    content_h_mm = header_h_mm + info_h_mm + separating_line_mm + n_rows * row_h_mm + footer_h_mm + 8  # extra padding

    if fixed_height_mode:
        table_h_mm = 85  # fixed ~85mm
    else:
        table_h_mm = content_h_mm

    # position table centered on A4
    table_h = mm_to_pt(table_h_mm)
    table_x = (page_w - table_w) / 2
    table_y = (page_h - table_h) / 2

    # Create PDF in memory
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Draw outer rectangle (1 pt)
    c.setLineWidth(1)
    c.rect(table_x, table_y, table_w, table_h)

    # Fonts sizes (points)
    title_font = "Helvetica-Bold"
    normal_font = "Helvetica"
    title_size = 10  # for "Información Nutricional"
    normal_size = 9  # general
    important_size = normal_size * 1.3  # for emphasized nutrients

    # Draw title
    c.setFont(title_font, title_size)
    title_x = table_x + mm_to_pt(6)
    title_y = table_y + table_h - mm_to_pt(8)
    c.drawString(title_x, title_y, "Información Nutricional")

    # Draw porción / num porciones line
    c.setFont(normal_font, normal_size)
    info_y = title_y - mm_to_pt(6)
    c.drawString(title_x, info_y, f"Tamaño de porción: {porcion_text} ({int(porcion_val)} {unidad_100})")
    c.drawRightString(table_x + table_w - mm_to_pt(6), info_y, f"Número de porciones por envase: {num_porciones if num_porciones else '-'}")

    # Draw thick line between porciones y calorías (1 pt)
    line_y = info_y - mm_to_pt(4)
    c.setLineWidth(1)
    c.line(table_x + mm_to_pt(3), line_y, table_x + table_w - mm_to_pt(3), line_y)

    # Table header (Por 100 / Por porción)
    header_y = line_y - mm_to_pt(6)
    col_nutr_x = table_x + mm_to_pt(6)
    col_100_x = table_x + table_w * 0.55  # approx position for "por 100"
    col_por_x = table_x + table_w * 0.85

    c.setFont(title_font, normal_size)
    c.drawString(col_100_x, header_y, f"Por 100 {unidad_100}")
    c.drawString(col_por_x, header_y, f"Por porción ({int(porcion_val)} {unidad_100})")

    # Draw line under header (0.75 pt)
    head_line_y = header_y - mm_to_pt(2)
    c.setLineWidth(0.75)
    c.line(table_x + mm_to_pt(3), head_line_y, table_x + table_w - mm_to_pt(3), head_line_y)

    # Rows: start below head_line_y
    current_y = head_line_y - mm_to_pt(4)
    row_h = mm_to_pt(row_h_mm)

    important_set = {"Calorías (kcal)", "  Grasa saturada", "  Grasas trans", "  Azúcares añadidos", "Sodio"}

    for name, val100, valpor in rows:
        # choose font & size
        if name in important_set:
            c.setFont(title_font, int(important_size))
        else:
            c.setFont(normal_font, normal_size)

        # nutrient name (left)
        c.drawString(col_nutr_x, current_y, name)

        # values right aligned in their columns
        c.setFont(normal_font, normal_size)
        c.drawRightString(col_100_x + mm_to_pt(22), current_y, val100)
        c.drawRightString(col_por_x + mm_to_pt(22), current_y, valpor)

        # thin separator after row (0.5 pt)
        current_y -= row_h
        c.setLineWidth(0.5)
        c.line(table_x + mm_to_pt(3), current_y + mm_to_pt(3), table_x + table_w - mm_to_pt(3), current_y + mm_to_pt(3))

    # Draw thicker separation line between macros and micros:
    # find index of "Sodio" in rows and compute y position
    idx_sodio = None
    for idx, (n, v1, v2) in enumerate(rows):
        if n.strip().lower().startswith("sodio"):
            idx_sodio = idx
            break
    if idx_sodio is not None:
        sep_after = header_y - mm_to_pt(2) - mm_to_pt(4) - mm_to_pt(row_h_mm) * (idx_sodio + 1)
        c.setLineWidth(1)
        c.line(table_x + mm_to_pt(3), sep_after, table_x + table_w - mm_to_pt(3), sep_after)

    # Add the "No es fuente significativa..." text if provided (directly under table content)
    if no_significant_text:
        ns_y = current_y - mm_to_pt(6)
        c.setFont(normal_font, 8)
        # wrap text if too long: simple split
        max_chars = 80
        text = no_significant_text
        if len(text) <= max_chars:
            c.drawString(col_nutr_x, ns_y, text)
        else:
            # split into chunks
            parts = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
            for i, part in enumerate(parts):
                c.drawString(col_nutr_x, ns_y - mm_to_pt(4) * i, part)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ---------------------
# Botón generar / descargar
# ---------------------
st.markdown("---")
if st.button("Generar tabla y preparar PDF"):
    fixed_mode = True if tamaño_mode == "Altura fija (aprox. 85 mm)" else False
    pdf_buf = generar_pdf(rows, no_signif_text, width_table_mm=100, fixed_height_mode=fixed_mode)
    st.download_button(
        label="Descargar tabla nutricional (PDF)",
        data=pdf_buf,
        file_name="tabla_nutricional.pdf",
        mime="application/pdf"
    )
