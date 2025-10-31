# app.py
# ============================================================
# Generador de Tabla Nutricional Colombia (PNG export)
# Cumple con Res. 810/2021, 2492/2022 y 254/2023 (formato visual)
# Soporta Fig.1 (vertical estándar), Fig.3 (simplificado),
# Fig.4 (tabular) y Fig.5 (lineal), exportando imagen sin título.
# ============================================================

import math
from io import BytesIO
from datetime import datetime

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# CONFIG STREAMLIT
# ============================================================
st.set_page_config(page_title="Generador de Tabla Nutricional (Colombia)", layout="wide")

# ============================================================
# UTILIDADES NUMÉRICAS
# ============================================================
def as_num(x):
    try:
        if x is None or x == "":
            return 0.0
        return float(x)
    except:
        return 0.0

def kcal_from_macros(fat_g, carb_g, protein_g, organic_acids_g=0.0, alcohol_g=0.0):
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9*fat_g + 4*carb_g + 4*protein_g + 7*alcohol_g + 3*organic_acids_g
    return float(round(kcal, 0))

def per100_from_portion(value_per_portion, portion_size):
    if portion_size and portion_size > 0:
        return float(round((value_per_portion / portion_size) * 100.0, 2))
    return 0.0

def portion_from_per100(value_per100, portion_size):
    if portion_size and portion_size > 0:
        return float(round((value_per100 * portion_size) / 100.0, 2))
    return 0.0

def pct_energy_from_nutrient_kcal(nutrient_kcal, total_kcal):
    if total_kcal and total_kcal > 0:
        return round((nutrient_kcal / total_kcal) * 100.0, 1)
    return 0.0

def fmt_g(x, nd=1):
    try:
        x = float(x)
        return f"{x:.{nd}f}".rstrip('0').rstrip('.') if nd > 0 else f"{int(round(x,0))}"
    except:
        return "0"

def fmt_mg(x):
    try:
        return f"{int(round(float(x)))}"
    except:
        return "0"

def fmt_kcal(x):
    try:
        return f"{int(round(float(x)))}"
    except:
        return "0"

# ============================================================
# ESTILO DE DIBUJO
# ============================================================
def get_font(size, bold=False):
    """
    Intenta cargar DejaVu Sans (estándar en la mayoría de entornos Streamlit).
    Si no está disponible, usa la fuente por defecto de PIL.
    """
    try:
        if bold:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except:
        return ImageFont.load_default()

def text_size(draw, text, font):
    bbox = draw.textbbox((0,0), text, font=font)
    w = bbox[2]-bbox[0]
    h = bbox[3]-bbox[1]
    return w, h

# Dibujo de líneas con grosor controlado
def draw_hline(draw, x0, x1, y, color, width):
    draw.line((x0, y, x1, y), fill=color, width=width)

def draw_vline(draw, x, y0, y1, color, width):
    draw.line((x, y0, x, y1), fill=color, width=width)

# ============================================================
# LOGICA DE BARRA LATERAL
# ============================================================
st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

st.sidebar.header("Configuración general")
format_choice = st.sidebar.selectbox(
    "Formato a exportar",
    [
        "Fig. 1 — Vertical estándar",
        "Fig. 3 — Simplificado",
        "Fig. 4 — Tabular",
        "Fig. 5 — Lineal"
    ],
    index=0
)

product_type = st.sidebar.selectbox("Tipo de producto", ["Producto terminado", "Materia prima"])
physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])
input_basis = st.sidebar.radio("Modo de ingreso de datos", ["Por porción", "Por 100 g/mL"], index=0)

product_name = st.sidebar.text_input("Nombre del producto")
brand_name = st.sidebar.text_input("Marca (opcional)")
provider = st.sidebar.text_input("Proveedor/Fabricante (opcional)")

col_ps1, col_ps2 = st.sidebar.columns(2)
with col_ps1:
    portion_size = as_num(st.text_input("Tamaño de porción (solo número)", value="50"))
with col_ps2:
    portion_unit = "g" if "Sólido" in physical_state else "mL"
    st.text_input("Unidad de porción", value=portion_unit, disabled=True)

servings_per_pack = as_num(st.sidebar.text_input("Porciones por envase (número)", value="1"))

include_kj = st.sidebar.checkbox("Mostrar también kJ junto a kcal", value=True)

st.sidebar.header("Micronutrientes (opcional)")
vm_options = [
    "Vitamina A (µg ER)",  # µg ER debe respetarse en la imagen
    "Vitamina D (µg)",
    "Calcio (mg)",
    "Hierro (mg)",
    "Zinc (mg)",
    "Potasio (mg)",
    "Vitamina C (mg)",
    "Vitamina E (mg)",
    "Vitamina B12 (µg)",
    "Ácido fólico (µg)",
]
selected_vm = st.sidebar.multiselect(
    "Selecciona micronutrientes a incluir",
    vm_options,
    default=["Vitamina A (µg ER)", "Vitamina D (µg)", "Calcio (mg)", "Hierro (mg)", "Zinc (mg)"]
)

st.sidebar.header("Texto al pie")
footnote_base = "No es fuente significativa de"
footnote_tail = st.sidebar.text_input("Completa la frase (aparecerá siempre)", value=" _____.")
# Siempre incluir “No es fuente significativa de” más lo que el usuario ponga:
footnote_ns = f"{footnote_base}{'' if footnote_tail.strip().startswith(' ') else ' '}{footnote_tail.strip()}"

# ============================================================
# INGRESO DE NUTRIENTES
# ============================================================
st.header("Ingreso de información nutricional (sin unidades)")
st.caption("Ingresa solo números. El sistema calcula automáticamente por 100 g/mL y por porción.")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Macronutrientes")
    fat_total_input = as_num(st.text_input("Grasa total (g)", value="5"))
    sat_fat_input   = as_num(st.text_input("Grasa saturada (g)", value="2"))

    # Grasa trans se ingresa en mg (como pediste)
    trans_fat_input_mg = as_num(st.text_input("Grasas trans (mg)", value="0"))
    # Para cálculos energéticos, convertir a g:
    trans_fat_input_g = trans_fat_input_mg / 1000.0

    carb_input      = as_num(st.text_input("Carbohidratos totales (g)", value="20"))
    sugars_total_input  = as_num(st.text_input("Azúcares totales (g)", value="10"))
    sugars_added_input  = as_num(st.text_input("Azúcares añadidos (g)", value="8"))
    fiber_input     = as_num(st.text_input("Fibra dietaria (g)", value="2"))
    protein_input   = as_num(st.text_input("Proteína (g)", value="3"))
    sodium_input_mg = as_num(st.text_input("Sodio (mg)", value="150"))

with c2:
    st.subheader("Micronutrientes seleccionados")
    vm_values = {}
    for vm in selected_vm:
        vm_values[vm] = as_num(st.text_input(vm, value="0"))

# ============================================================
# NORMALIZACIÓN POR 100 vs PORCIÓN
# ============================================================
if input_basis == "Por porción":
    fat_total_pp = fat_total_input
    sat_fat_pp   = sat_fat_input
    trans_fat_pp_g = trans_fat_input_g
    carb_pp      = carb_input
    sugars_total_pp = sugars_total_input
    sugars_added_pp = sugars_added_input
    fiber_pp     = fiber_input
    protein_pp   = protein_input
    sodium_pp_mg = sodium_input_mg

    fat_total_100 = per100_from_portion(fat_total_pp, portion_size)
    sat_fat_100   = per100_from_portion(sat_fat_pp, portion_size)
    trans_fat_100_g = per100_from_portion(trans_fat_pp_g, portion_size)
    carb_100      = per100_from_portion(carb_pp, portion_size)
    sugars_total_100 = per100_from_portion(sugars_total_pp, portion_size)
    sugars_added_100 = per100_from_portion(sugars_added_pp, portion_size)
    fiber_100     = per100_from_portion(fiber_pp, portion_size)
    protein_100   = per100_from_portion(protein_pp, portion_size)
    sodium_100_mg = per100_from_portion(sodium_pp_mg, portion_size)
else:
    fat_total_100 = fat_total_input
    sat_fat_100   = sat_fat_input
    trans_fat_100_g = trans_fat_input_g
    carb_100      = carb_input
    sugars_total_100 = sugars_total_input
    sugars_added_100 = sugars_added_input
    fiber_100     = fiber_input
    protein_100   = protein_input
    sodium_100_mg = sodium_input_mg

    fat_total_pp = portion_from_per100(fat_total_100, portion_size)
    sat_fat_pp   = portion_from_per100(sat_fat_100, portion_size)
    trans_fat_pp_g = portion_from_per100(trans_fat_100_g, portion_size)
    carb_pp      = portion_from_per100(carb_100, portion_size)
    sugars_total_pp = portion_from_per100(sugars_total_100, portion_size)
    sugars_added_pp = portion_from_per100(sugars_added_100, portion_size)
    fiber_pp     = portion_from_per100(fiber_100, portion_size)
    protein_pp   = portion_from_per100(protein_100, portion_size)
    sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_size)

# Micronutrientes normalizados
vm_pp = {}
vm_100 = {}
for vm, val in vm_values.items():
    if input_basis == "Por porción":
        vm_pp[vm] = val
        vm_100[vm] = per100_from_portion(val, portion_size)
    else:
        vm_100[vm] = val
        vm_pp[vm] = portion_from_per100(val, portion_size)

# ============================================================
# ENERGÍA Y FOP
# ============================================================
kcal_pp = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)

kj_pp = round(kcal_pp * 4.184) if include_kj else None
kj_100 = round(kcal_100 * 4.184) if include_kj else None

is_liquid = ("Líquido" in physical_state)

# Sellos (informativo)
pct_kcal_sug_add_pp = pct_energy_from_nutrient_kcal(4*sugars_added_pp, kcal_pp)
pct_kcal_sat_fat_pp = pct_energy_from_nutrient_kcal(9*sat_fat_pp, kcal_pp)
pct_kcal_trans_pp   = pct_energy_from_nutrient_kcal(9*trans_fat_pp_g, kcal_pp)

fop_sugar = pct_kcal_sug_add_pp >= 10.0
fop_sat   = pct_kcal_sat_fat_pp >= 10.0
fop_trans = pct_kcal_trans_pp >= 1.0

if is_liquid and kcal_100 == 0:
    fop_sodium = sodium_100_mg >= 40.0
else:
    fop_sodium = (sodium_100_mg >= 300.0) or ((sodium_pp_mg / max(kcal_pp, 1)) >= 1.0)

with st.expander("Resultado de validación informativa (Sellos de advertencia posibles)", expanded=False):
    colf1, colf2, colf3, colf4 = st.columns(4)
    with colf1:
        st.write(f"Azúcares añadidos ≥10% kcal: **{'Sí' if fop_sugar else 'No'}**")
    with colf2:
        st.write(f"Grasa saturada ≥10% kcal: **{'Sí' if fop_sat else 'No'}**")
    with colf3:
        st.write(f"Grasas trans ≥1% kcal: **{'Sí' if fop_trans else 'No'}**")
    with colf4:
        st.write(f"Sodio criterio aplicable: **{'Sí' if fop_sodium else 'No'}**")

# ============================================================
# BLOQUE DE RENDERIZADO PNG (TABLAS)
# ============================================================

# Config visual general
BORDER_W = 6                 # grosor del marco externo
GRID_W_THICK = 5             # línea gruesa (separadores principales)
GRID_W = 3                   # línea normal
TEXT_COLOR = (0, 0, 0)
BG_WHITE = (255, 255, 255)

# Tipografías
FONT_HEADER = get_font(36, bold=True)
FONT_LABEL = get_font(30, bold=False)
FONT_LABEL_B = get_font(30, bold=True)
FONT_SMALL = get_font(26, bold=False)
FONT_SMALL_B = get_font(26, bold=True)

ROW_H = 64                  # altura de fila para evitar solapes
CELL_PAD_X = 22             # padding lateral dentro de celdas
CELL_PAD_Y = 18             # padding vertical

def nutrient_rows_common():
    """
    Devuelve la lista base (Fig.1/Fig.4) de nutrientes (tuplas)
    con estructura: (label, v100_str, vpp_str, unit, indent, bold)
    """
    # Calorías arriba, aparte (se dibuja diferente)
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    perportion_label = f"por porción ({fmt_mg(portion_size) if portion_unit=='mL' else fmt_mg(portion_size)} {portion_unit})"

    kcal_100_txt = fmt_kcal(kcal_100) + (" ("+str(int(round(kj_100)))+" kJ)" if include_kj else "")
    kcal_pp_txt  = fmt_kcal(kcal_pp) + (" ("+str(int(round(kj_pp)))+" kJ)" if include_kj else "")

    # Macros y Sodio
    rows = [
        # header de columnas (fila de títulos de columnas)
        ("", per100_label, perportion_label, "", 0, False, True),  # flag 'True' final = fila de header columnas
        ("Grasa total",        f"{fmt_g(fat_total_100,1)} g",  f"{fmt_g(fat_total_pp,1)} g",  "g", 0, False, False),
        ("  Grasa saturada",   f"{fmt_g(sat_fat_100,1)} g",    f"{fmt_g(sat_fat_pp,1)} g",    "g", 1, True,  False),
        ("  Grasas trans",     f"{fmt_mg(trans_fat_100_g*1000)} mg", f"{fmt_mg(trans_fat_pp_g*1000)} mg", "mg", 1, True, False),
        ("Carbohidratos",      f"{fmt_g(carb_100,1)} g",       f"{fmt_g(carb_pp,1)} g",       "g", 0, False, False),
        ("  Azúcares totales", f"{fmt_g(sugars_total_100,1)} g", f"{fmt_g(sugars_total_pp,1)} g", "g", 1, False, False),
        ("  Azúcares añadidos",f"{fmt_g(sugars_added_100,1)} g", f"{fmt_g(sugars_added_pp,1)} g", "g", 1, True,  False),
        ("  Fibra dietaria",   f"{fmt_g(fiber_100,1)} g",      f"{fmt_g(fiber_pp,1)} g",      "g", 1, False, False),
        ("Proteína",           f"{fmt_g(protein_100,1)} g",    f"{fmt_g(protein_pp,1)} g",    "g", 0, False, False),
        ("Sodio",              f"{fmt_mg(sodium_100_mg)} mg",  f"{fmt_mg(sodium_pp_mg)} mg",  "mg",0, True,  False),
    ]
    # Micronutrientes seleccionados
    if selected_vm:
        rows.append(("---sep---", "", "", "", 0, False, False))  # separador grueso

        for vm in selected_vm:
            unit = "mg"
            if "µg" in vm:
                unit = "µg"
            v100 = vm_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)

            # Etiqueta limpia para nombre (respetando Vitamina A µg ER)
            if vm.startswith("Vitamina A"):
                display_name = "Vitamina A (µg ER)"  # mantener explícito en imagen
            else:
                display_name = vm  # incluye (mg)/(µg) y es claro al usuario

            val100 = f"{fmt_mg(v100)} {unit}" if unit == "mg" else f"{fmt_g(v100,1)} {unit}" if unit == "µg" else f"{fmt_g(v100,1)} {unit}"
            valpp  = f"{fmt_mg(vpp)} {unit}"  if unit == "mg" else f"{fmt_g(vpp,1)} {unit}"  if unit == "µg" else f"{fmt_g(vpp,1)} {unit}"

            rows.append((display_name, val100, valpp, unit, 0, False, False))

    return kcal_100_txt, kcal_pp_txt, rows

def draw_table_fig1_vertical():
    """
    Dibuja Fig. 1 (vertical estándar) como una imagen PNG con fondo blanco,
    sin título dentro de la imagen. Líneas y tipografía ajustadas.
    """
    kcal_100_txt, kcal_pp_txt, rows = nutrient_rows_common()

    # Dimensiones base
    W = 1400
    # Altura dinámica según filas
    num_rows = len(rows)
    header_h = 120     # Encabezado "Información Nutricional" + tamaño porción/porciones
    kcal_h   = 90      # Fila de calorías grande
    colhdr_h = 70      # Fila de cabeceras columnas
    footer_h = 110     # Pie de "No es fuente significativa de..."
    H = BORDER_W*2 + header_h + kcal_h + (num_rows-1)*ROW_H + footer_h + 40

    # Columnas (3 columnas)
    col_x = [BORDER_W, BORDER_W + int(W*0.5), BORDER_W + int(W*0.82), W - BORDER_W]  # 0..3 puntos verticales
    # Ajuste de anchos: 50% / 32% / 18% aprox

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco externo
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    cur_y = BORDER_W

    # Encabezado interno (sin cruzar verticales)
    # Línea bajo el encabezado
    # Título
    title_font = FONT_LABEL_B
    title = "Información Nutricional"
    tw, th = text_size(draw, title, title_font)
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 8), title, fill=TEXT_COLOR, font=title_font)

    # Tamaño de porción / Porciones por envase (debajo del título)
    sub1 = f"Tamaño de porción: {int(round(portion_size))} {portion_unit}"
    sub2 = f"Porciones por envase: {int(round(servings_per_pack))}"
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 8 + th + 8), sub1, fill=TEXT_COLOR, font=FONT_SMALL)
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 8 + th + 8 + 34), sub2, fill=TEXT_COLOR, font=FONT_SMALL)

    # Línea gruesa debajo encabezado
    cur_y += header_h
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)

    # Fila Calorías (en negrilla y grande)
    # Texto izquierda: "Calorías"
    draw.text((BORDER_W + CELL_PAD_X, cur_y + (ROW_H//2) - 10), "Calorías", fill=TEXT_COLOR, font=FONT_LABEL_B)
    # Valores por 100 / por porción alineados a la derecha de sus columnas
    txt_100 = kcal_100_txt
    txt_pp  = kcal_pp_txt
    w1, _ = text_size(draw, txt_100, FONT_LABEL_B)
    w2, _ = text_size(draw, txt_pp, FONT_LABEL_B)
    draw.text((col_x[2] - CELL_PAD_X - w1, cur_y + (ROW_H//2) - 10), txt_100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    draw.text((col_x[3] - CELL_PAD_X - w2, cur_y + (ROW_H//2) - 10), txt_pp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Línea gruesa bajo Calorías
    cur_y += ROW_H
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)

    # Fila cabeceras columnas
    # (Nota: no dibujar verticales antes de esta fila, para no cruzar encabezados)
    # Cabeceras ya están en rows[0] con flag header=True
    _, c100, cpp, _, _, _, _ = rows[0]
    draw.text((BORDER_W + CELL_PAD_X, cur_y + CELL_PAD_Y), " ", fill=TEXT_COLOR, font=FONT_SMALL_B)
    # Texto de columnas alineado a derecha en bordes col_x[2] y col_x[3]
    w_c100, _ = text_size(draw, c100, FONT_SMALL_B)
    w_cpp, _  = text_size(draw, cpp,  FONT_SMALL_B)
    draw.text((col_x[2] - CELL_PAD_X - w_c100, cur_y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col_x[3] - CELL_PAD_X - w_cpp,  cur_y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    # Línea fina debajo cabeceras
    cur_y += colhdr_h
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W)

    # Ahora sí, verticales internas desde acá (no atraviesan encabezado)
    # Tres columnas visibles: | label | col_x[2] | col_x[3] |
    draw_vline(draw, col_x[2], cur_y, H-BORDER_W-footer_h-40, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], cur_y, H-BORDER_W-footer_h-40, TEXT_COLOR, GRID_W)

    # Filas de nutrientes
    for i, tup in enumerate(rows[1:], start=1):
        label, v100, vpp, unit, indent, bold, is_colhdr = tup
        if label == "---sep---":
            draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
            continue

        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL

        # Línea superior de cada fila
        draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W)

        # Columna izquierda (label)
        x_label = BORDER_W + CELL_PAD_X + (indent * 28)
        y_label = cur_y + (ROW_H//2) - 14
        draw.text((x_label, y_label), label, fill=TEXT_COLOR, font=font_lbl)

        # Valores alineados a la derecha de sus columnas
        wv100, _ = text_size(draw, v100, font_val)
        wvpp,  _ = text_size(draw, vpp,  font_val)
        draw.text((col_x[2] - CELL_PAD_X - wv100, y_label), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((col_x[3] - CELL_PAD_X - wvpp,  y_label), vpp,  fill=TEXT_COLOR, font=font_val)

        cur_y += ROW_H

    # Línea base antes del pie
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)

    # Pie: "No es fuente significativa de ..."
    cur_y += 16
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 12), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

def draw_table_fig3_simple():
    """
    Dibuja Fig. 3 (simplificado) como imagen.
    Menor cantidad de filas. Mantiene reglas de negrilla.
    """
    # Selección reducida: Calorías, Grasa total, Saturada, Trans, Carbohidratos,
    # Azúcares añadidos, Proteína, Sodio. (Coherente con simplificado)
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    perportion_label = f"por porción ({int(round(portion_size))} {portion_unit})"

    kcal_100_txt = fmt_kcal(kcal_100) + (f" ({int(round(kj_100))} kJ)" if include_kj else "")
    kcal_pp_txt  = fmt_kcal(kcal_pp)  + (f" ({int(round(kj_pp))} kJ)"  if include_kj else "")

    rows = [
        ("", per100_label, perportion_label, "", 0, False, True),
        ("Grasa total",        f"{fmt_g(fat_total_100,1)} g",  f"{fmt_g(fat_total_pp,1)} g",  "g", 0, False, False),
        ("  Grasa saturada",   f"{fmt_g(sat_fat_100,1)} g",    f"{fmt_g(sat_fat_pp,1)} g",    "g", 1, True,  False),
        ("  Grasas trans",     f"{fmt_mg(trans_fat_100_g*1000)} mg", f"{fmt_mg(trans_fat_pp_g*1000)} mg", "mg", 1, True, False),
        ("Carbohidratos",      f"{fmt_g(carb_100,1)} g",       f"{fmt_g(carb_pp,1)} g",       "g", 0, False, False),
        ("  Azúcares añadidos",f"{fmt_g(sugars_added_100,1)} g", f"{fmt_g(sugars_added_pp,1)} g", "g", 1, True,  False),
        ("Proteína",           f"{fmt_g(protein_100,1)} g",    f"{fmt_g(protein_pp,1)} g",    "g", 0, False, False),
        ("Sodio",              f"{fmt_mg(sodium_100_mg)} mg",  f"{fmt_mg(sodium_pp_mg)} mg",  "mg",0, True,  False),
    ]

    # Dimensiones
    W = 1200
    header_h = 120
    kcal_h = 90
    colhdr_h = 70
    footer_h = 110
    H = BORDER_W*2 + header_h + kcal_h + (len(rows)-1)*ROW_H + footer_h + 40

    col_x = [BORDER_W, BORDER_W + int(W*0.5), BORDER_W + int(W*0.82), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    cur_y = BORDER_W

    # Encabezado
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 8), "Información Nutricional", fill=TEXT_COLOR, font=FONT_LABEL_B)
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 52), f"Tamaño de porción: {int(round(portion_size))} {portion_unit}", fill=TEXT_COLOR, font=FONT_SMALL)
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 86), f"Porciones por envase: {int(round(servings_per_pack))}", fill=TEXT_COLOR, font=FONT_SMALL)
    cur_y += header_h
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)

    # Calorías
    draw.text((BORDER_W + CELL_PAD_X, cur_y + (ROW_H//2) - 10), "Calorías", fill=TEXT_COLOR, font=FONT_LABEL_B)
    w1, _ = text_size(draw, kcal_100_txt, FONT_LABEL_B)
    w2, _ = text_size(draw, kcal_pp_txt,  FONT_LABEL_B)
    draw.text((col_x[2] - CELL_PAD_X - w1, cur_y + (ROW_H//2) - 10), kcal_100_txt, fill=TEXT_COLOR, font=FONT_LABEL_B)
    draw.text((col_x[3] - CELL_PAD_X - w2, cur_y + (ROW_H//2) - 10), kcal_pp_txt,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    cur_y += ROW_H
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)

    # Cabeceras
    _, c100, cpp, _, _, _, _ = rows[0]
    w_c100, _ = text_size(draw, c100, FONT_SMALL_B)
    w_cpp, _  = text_size(draw, cpp,  FONT_SMALL_B)
    draw.text((col_x[2] - CELL_PAD_X - w_c100, cur_y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col_x[3] - CELL_PAD_X - w_cpp,  cur_y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    cur_y += 70
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[2], cur_y, H-BORDER_W-footer_h-40, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], cur_y, H-BORDER_W-footer_h-40, TEXT_COLOR, GRID_W)

    # Filas
    for tup in rows[1:]:
        label, v100, vpp, unit, indent, bold, _ = tup
        draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + (indent * 28)
        y_label = cur_y + (ROW_H//2) - 14
        draw.text((x_label, y_label), label, fill=TEXT_COLOR, font=font_lbl)

        wv100, _ = text_size(draw, v100, font_val)
        wvpp, _  = text_size(draw, vpp,  font_val)
        draw.text((col_x[2] - CELL_PAD_X - wv100, y_label), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((col_x[3] - CELL_PAD_X - wvpp,  y_label), vpp,  fill=TEXT_COLOR, font=font_val)

        cur_y += ROW_H

    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
    cur_y += 16
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 12), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)
    return img

def draw_table_fig4_tabular():
    """
    Dibuja Fig. 4 (tabular) como imagen.
    Tabla con celdas más “grid” e indicadores en negrilla (810).
    """
    kcal_100_txt, kcal_pp_txt, rows = nutrient_rows_common()

    # Para tabular, alineamos en una malla regular con celdas completas
    W = 1400
    header_h = 120
    kcal_h = 90
    colhdr_h = 70
    footer_h = 110

    # Contemos filas visuales reales (incluye separadores)
    data_rows = [r for r in rows if r[0] != "---sep---"]
    sep_count = len([r for r in rows if r[0] == "---sep---"])
    H = BORDER_W*2 + header_h + kcal_h + colhdr_h + (len(data_rows))*ROW_H + sep_count*GRID_W_THICK + footer_h + 40

    # Columnas (3 col + marco)
    # En tabular, dejamos más espacio para la primera col y equilibramos las otras dos
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco externo
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)
    cur_y = BORDER_W

    # Encabezado
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 8), "Información Nutricional", fill=TEXT_COLOR, font=FONT_LABEL_B)
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 52), f"Tamaño de porción: {int(round(portion_size))} {portion_unit}", fill=TEXT_COLOR, font=FONT_SMALL)
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 86), f"Porciones por envase: {int(round(servings_per_pack))}", fill=TEXT_COLOR, font=FONT_SMALL)

    cur_y += header_h
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)

    # Calorías (negrita)
    draw.text((BORDER_W + CELL_PAD_X, cur_y + (ROW_H//2) - 10), "Calorías", fill=TEXT_COLOR, font=FONT_LABEL_B)
    w1, _ = text_size(draw, kcal_100_txt, FONT_LABEL_B)
    w2, _ = text_size(draw, kcal_pp_txt,  FONT_LABEL_B)
    draw.text((col_x[2] - CELL_PAD_X - w1, cur_y + (ROW_H//2) - 10), kcal_100_txt, fill=TEXT_COLOR, font=FONT_LABEL_B)
    draw.text((col_x[3] - CELL_PAD_X - w2, cur_y + (ROW_H//2) - 10), kcal_pp_txt,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    cur_y += ROW_H
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)

    # Cabecera de columnas
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    perportion_label = f"por porción ({int(round(portion_size))} {portion_unit})"
    w_c100, _ = text_size(draw, per100_label, FONT_SMALL_B)
    w_cpp, _  = text_size(draw, perportion_label, FONT_SMALL_B)
    draw.text((col_x[2] - CELL_PAD_X - w_c100, cur_y + CELL_PAD_Y), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col_x[3] - CELL_PAD_X - w_cpp,  cur_y + CELL_PAD_Y), perportion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)

    cur_y += colhdr_h
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W)

    # Verticales internas (desde aquí, para no cruzar encabezados)
    draw_vline(draw, col_x[1], cur_y, H-BORDER_W-footer_h-40, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[2], cur_y, H-BORDER_W-footer_h-40, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], cur_y, H-BORDER_W-footer_h-40, TEXT_COLOR, GRID_W)

    # Ahora iterar filas con estética tabular: cada fila parece una "celda"
    for tup in rows[1:]:
        if tup[0] == "---sep---":
            draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
            continue

        label, v100, vpp, unit, indent, bold, _ = tup
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL

        # línea superior de la fila
        draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W)

        # “celdas”:
        # Col 1 (label)
        x_label = BORDER_W + CELL_PAD_X + (indent * 28)
        y_text = cur_y + (ROW_H//2) - 14
        draw.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)

        # Col 2 (por 100)
        wv100, _ = text_size(draw, v100, font_val)
        draw.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)

        # Col 3 (por porción)
        wvpp, _ = text_size(draw, vpp, font_val)
        draw.text((col_x[3] - CELL_PAD_X - wvpp, y_text), vpp, fill=TEXT_COLOR, font=font_val)

        cur_y += ROW_H

    # Base antes del pie
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
    cur_y += 16
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 12), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

def draw_table_fig5_linear():
    """
    Dibuja Fig. 5 (lineal). Presentación en una o dos líneas con separadores.
    Se prioriza por porción; por 100 g/mL se muestra entre paréntesis.
    """
    # Preparar pares "Nombre: valor por porción (por 100 …)"
    items = []

    kcal_txt_pp = f"{fmt_kcal(kcal_pp)} kcal" + (f" ({int(round(kj_pp))} kJ)" if include_kj else "")
    kcal_txt_100 = f"{fmt_kcal(kcal_100)} kcal" + (f" ({int(round(kj_100))} kJ)" if include_kj else "")

    def pair(name, vpp_txt, v100_txt):
        items.append(f"{name}: {vpp_txt} (por 100: {v100_txt})")

    pair("Calorías", kcal_txt_pp, kcal_txt_100)
    pair("Grasa total", f"{fmt_g(fat_total_pp,1)} g", f"{fmt_g(fat_total_100,1)} g")
    pair("Grasa saturada", f"{fmt_g(sat_fat_pp,1)} g", f"{fmt_g(sat_fat_100,1)} g")
    pair("Grasas trans", f"{fmt_mg(trans_fat_pp_g*1000)} mg", f"{fmt_mg(trans_fat_100_g*1000)} mg")
    pair("Carbohidratos", f"{fmt_g(carb_pp,1)} g", f"{fmt_g(carb_100,1)} g")
    pair("Azúcares totales", f"{fmt_g(sugars_total_pp,1)} g", f"{fmt_g(sugars_total_100,1)} g")
    pair("Azúcares añadidos", f"{fmt_g(sugars_added_pp,1)} g", f"{fmt_g(sugars_added_100,1)} g")
    pair("Fibra dietaria", f"{fmt_g(fiber_pp,1)} g", f"{fmt_g(fiber_100,1)} g")
    pair("Proteína", f"{fmt_g(protein_pp,1)} g", f"{fmt_g(protein_100,1)} g")
    pair("Sodio", f"{fmt_mg(sodium_pp_mg)} mg", f"{fmt_mg(sodium_100_mg)} mg")

    # Micronutrientes
    for vm in selected_vm:
        unit = "mg"
        if "µg" in vm:
            unit = "µg"
        vpp  = vm_pp.get(vm, 0.0)
        v100 = vm_100.get(vm, 0.0)
        name = "Vitamina A (µg ER)" if vm.startswith("Vitamina A") else vm
        vpp_txt  = f"{fmt_mg(vpp)} {unit}" if unit == "mg" else f"{fmt_g(vpp,1)} {unit}"
        v100_txt = f"{fmt_mg(v100)} {unit}" if unit == "mg" else f"{fmt_g(v100,1)} {unit}"
        pair(name, vpp_txt, v100_txt)

    # Imágen
    W = 1600
    H = 560 if len(items) <= 8 else 720 if len(items) <= 14 else 900
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco y título de bloque (sin texto “Información Nutricional” dentro)
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Texto lineal
    left_x = BORDER_W + 28
    y = BORDER_W + 40

    # Primera línea “porción”
    porcion = f"Tamaño de porción: {int(round(portion_size))} {portion_unit}    •    Porciones por envase: {int(round(servings_per_pack))}"
    draw.text((left_x, y), porcion, fill=TEXT_COLOR, font=FONT_SMALL_B)
    y += 60

    # Cadenas separadas por "  •  "
    line_items = "  •  ".join(items)
    # Hacer wrap manual para no salirnos
    max_width = W - left_x - 30
    words = line_items.split(" ")
    line = ""
    lines = []
    for w in words:
        tmp = (line + " " + w).strip()
        if text_size(draw, tmp, FONT_LABEL)[0] <= max_width:
            line = tmp
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)

    for ln in lines:
        draw.text((left_x, y), ln, fill=TEXT_COLOR, font=FONT_LABEL)
        y += 48

    # Pie
    y += 10
    draw.text((left_x, y), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ============================================================
# PREVISUALIZACIÓN Y EXPORTACIÓN
# ============================================================
st.header("Previsualización")
preview_col, controls_col = st.columns([0.7, 0.3])

with controls_col:
    st.caption("Elige el formato y luego exporta la imagen.")
    export_btn = st.button("Generar PNG con fondo blanco")

with preview_col:
    if format_choice.startswith("Fig. 1"):
        img_prev = draw_table_fig1_vertical()
    elif format_choice.startswith("Fig. 3"):
        img_prev = draw_table_fig3_simple()
    elif format_choice.startswith("Fig. 4"):
        img_prev = draw_table_fig4_tabular()
    else:
        img_prev = draw_table_fig5_linear()

    st.image(img_prev, caption="Vista previa (escala reducida)", use_column_width=True)

# Exportar
if export_btn:
    buf = BytesIO()
    img_prev.save(buf, format="PNG")
    buf.seek(0)
    fname = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    st.download_button("Descargar imagen PNG", data=buf, file_name=fname, mime="image/png")
