# ============================================================
# app.py — Generador de Tabla Nutricional (Colombia)
# Cumple con Resoluciones 810/2021, 2492/2022 y 254/2023
# Soporta Fig.1 (Vertical), Fig.3 (Simplificada), Fig.4 (Tabular), Fig.5 (Lineal)
# Modo de entrada: sólo por 100 g o 100 mL
# Exportación directa a PNG con fondo blanco y proporciones normativas
# ============================================================

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import datetime

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
st.set_page_config(
    page_title="Generador Tabla Nutricional (Colombia)",
    layout="wide"
)
st.title("🧾 Generador de Tabla de Información Nutricional — Colombia")

# ============================================================
# FUNCIONES UTILITARIAS
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

def portion_from_per100(value_per100, portion_size):
    if portion_size and portion_size > 0:
        return float(round((value_per100 * portion_size) / 100.0, 2))
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

def get_font(size, bold=False):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size)
    except:
        return ImageFont.load_default()

def text_size(draw, text, font):
    bbox = draw.textbbox((0,0), text, font=font)
    return bbox[2]-bbox[0], bbox[3]-bbox[1]

def draw_hline(draw, x0, x1, y, color, width):
    draw.line((x0, y, x1, y), fill=color, width=width)

def draw_vline(draw, x, y0, y1, color, width):
    draw.line((x, y0, x, y1), fill=color, width=width)

# ============================================================
# SIDEBAR CONFIGURACIÓN
# ============================================================
st.sidebar.header("⚙️ Configuración del formato")
format_choice = st.sidebar.selectbox(
    "Selecciona el formato de tabla:",
    [
        "Fig. 1 — Vertical estándar",
        "Fig. 3 — Simplificado",
        "Fig. 4 — Tabular",
        "Fig. 5 — Lineal"
    ],
    index=0
)

physical_state = st.sidebar.selectbox("Estado físico del producto", ["Sólido (g)", "Líquido (mL)"])
portion_unit = "g" if "Sólido" in physical_state else "mL"

# Porciones
st.sidebar.subheader("🍽️ Porción")
household_name = st.sidebar.text_input("Medida casera (ejemplo: 1 unidad, 1 taza)", value="1 unidad")
household_mass = as_num(st.sidebar.text_input(f"Equivalencia en {portion_unit}", value="40"))
servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="2"))

# Micronutrientes
st.sidebar.subheader("💊 Micronutrientes (por 100 g / 100 mL)")
vm_options = [
    "Vitamina A", "Vitamina D", "Vitamina B12", "Ácido fólico",
    "Vitamina C", "Vitamina E", "Calcio", "Hierro", "Zinc", "Potasio"
]
selected_vm = st.sidebar.multiselect(
    "Selecciona los que incluirás:",
    vm_options,
    default=["Vitamina A","Calcio","Hierro","Vitamina D","Zinc"]
)

# Pie
st.sidebar.subheader("📝 Texto al pie")
footnote_tail = st.sidebar.text_input(
    "Completa el texto: No es fuente significativa de ...",
    value="Proteína, Vitamina D, Hierro, Calcio, Zinc, Vitamina A y fibra."
)

# ============================================================
# INGRESO DE DATOS PRINCIPALES
# ============================================================
st.header("🧮 Ingreso de información nutricional por 100 g / 100 mL")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Macronutrientes")
    fat_total_100    = as_num(st.text_input("Grasa total (g)", value="13"))
    sat_fat_100      = as_num(st.text_input("Grasa saturada (g)", value="6"))
    trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg)", value="820"))
    carb_100         = as_num(st.text_input("Carbohidratos totales (g)", value="31"))
    sug_total_100    = as_num(st.text_input("Azúcares totales (g)", value="5"))
    sug_added_100    = as_num(st.text_input("Azúcares añadidos (g)", value="2"))
    fiber_100        = as_num(st.text_input("Fibra dietaria (g)", value="0.8"))
    protein_100      = as_num(st.text_input("Proteína (g)", value="5"))
    sodium_100_mg    = as_num(st.text_input("Sodio (mg)", value="560"))

with col2:
    st.subheader("Micronutrientes seleccionados (por 100)")
    vm_values_100 = {}
    for vm in selected_vm:
        vm_values_100[vm] = as_num(st.text_input(vm, value="0"))

# ============================================================
# CÁLCULOS
# ============================================================
portion_size = household_mass
is_liquid = "Líquido" in physical_state

# grasas trans pasan a g
trans_fat_100_g = (trans_fat_100_mg or 0.0) / 1000.0

# porciones
fat_total_pp    = portion_from_per100(fat_total_100, portion_size)
sat_fat_pp      = portion_from_per100(sat_fat_100, portion_size)
trans_fat_pp_mg = portion_from_per100(trans_fat_100_mg, portion_size)
carb_pp         = portion_from_per100(carb_100, portion_size)
sug_total_pp    = portion_from_per100(sug_total_100, portion_size)
sug_added_pp    = portion_from_per100(sug_added_100, portion_size)
fiber_pp        = portion_from_per100(fiber_100, portion_size)
protein_pp      = portion_from_per100(protein_100, portion_size)
sodium_pp_mg    = portion_from_per100(sodium_100_mg, portion_size)

vm_pp = {}
for name, v100 in vm_values_100.items():
    vm_pp[name] = portion_from_per100(v100, portion_size)

kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp  = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)

# ============================================================
# PARÁMETROS DE DISEÑO
# ============================================================
BORDER_W       = 6
GRID_W         = 3
GRID_W_THICK   = 9  # triple grosor en líneas gruesas
TEXT_COLOR     = (0,0,0)
BG_WHITE       = (255,255,255)

FONT_TITLE     = get_font(46, bold=True)
FONT_LABEL     = get_font(30, bold=False)
FONT_LABEL_B   = get_font(30, bold=True)
FONT_SMALL     = get_font(26, bold=False)
FONT_SMALL_B   = get_font(26, bold=True)
FONT_MICRO     = get_font(24, bold=False)
FONT_MICRO_B   = get_font(24, bold=True)

ROW_H          = 64
ROW_H_MICRO    = 54
CELL_PAD_X     = 22
CELL_PAD_Y     = 18
# ============================================================
# BLOQUES DE TEXTO Y FILAS
# ============================================================
def build_portion_text(portion_unit, portion_size, household_name, servings_per_pack):
    # “Tamaño de porción: <medida casera> (<gramaje>)”
    gramaje = f"{int(round(portion_size))} {portion_unit}"
    p1 = f"Tamaño de porción: {household_name} ({gramaje})"
    p2 = f"Número de porciones por envase: {fmt_g(servings_per_pack,0)}"
    return p1, p2

def macros_rows_common(
    fat_total_100, fat_total_pp,
    sat_fat_100, sat_fat_pp,
    trans_fat_100_mg, trans_fat_pp_mg,
    carb_100, carb_pp,
    sug_total_100, sug_total_pp,
    sug_added_100, sug_added_pp,
    fiber_100, fiber_pp,
    protein_100, protein_pp,
    sodium_100_mg, sodium_pp_mg,
    selected_vm, vm_values_100, vm_pp
):
    """
    Retorna lista de tuplas:
    (label, v100_str, vpp_str, indent, bold, is_micro, is_separator)
    * NOTA: Unidades aparecen junto a los valores, no en los nombres (como pediste).
    * Negrillas en: Grasa saturada, Grasas trans, Azúcares añadidos, Sodio (según norma).
    """
    rows = [
        ("Grasa total",            f"{fmt_g(fat_total_100,1)} g",          f"{fmt_g(fat_total_pp,1)} g",            0, False, False, False),
        ("  Grasa saturada",       f"{fmt_g(sat_fat_100,1)} g",            f"{fmt_g(sat_fat_pp,1)} g",              1, True,  False, False),
        ("  Grasas trans",         f"{fmt_mg(trans_fat_100_mg)} mg",       f"{fmt_mg(trans_fat_pp_mg)} mg",         1, True,  False, False),
        ("Carbohidratos totales",  f"{fmt_g(carb_100,1)} g",               f"{fmt_g(carb_pp,1)} g",                 0, False, False, False),
        ("  Fibra dietaria",       f"{fmt_g(fiber_100,1)} g",              f"{fmt_g(fiber_pp,1)} g",                1, False, False, False),
        ("  Azúcares totales",     f"{fmt_g(sug_total_100,1)} g",          f"{fmt_g(sug_total_pp,1)} g",            1, False, False, False),
        ("  Azúcares añadidos",    f"{fmt_g(sug_added_100,1)} g",          f"{fmt_g(sug_added_pp,1)} g",            1, True,  False, False),
        ("Proteína",               f"{fmt_g(protein_100,1)} g",            f"{fmt_g(protein_pp,1)} g",              0, False, False, False),
        ("Sodio",                  f"{fmt_mg(sodium_100_mg)} mg",          f"{fmt_mg(sodium_pp_mg)} mg",            0, True,  False, False),
    ]

    # Micronutrientes como bloque aparte, más pequeños, unidades junto al valor
    if selected_vm:
        rows.append(("", "", "", 0, False, False, True))  # separador grueso
        for name in selected_vm:
            v100 = vm_values_100.get(name, 0.0)
            vpp  = vm_pp.get(name, 0.0)
            # Regla de unidad:
            unit = "mg"
            if name in ("Vitamina A", "Vitamina D", "Vitamina B12", "Ácido fólico"):
                unit = "µg"
            v100_txt = f"{fmt_mg(v100)} {unit}" if unit=="mg" else f"{fmt_g(v100,1)} {unit}"
            vpp_txt  = f"{fmt_mg(vpp)} {unit}"  if unit=="mg" else f"{fmt_g(vpp,1)} {unit}"
            rows.append((name, v100_txt, vpp_txt, 0, False, True, False))
    return rows

# ============================================================
# DIBUJO: TÍTULO + PORCIONES
# ============================================================
def draw_title_and_portions(draw, W, start_y, portion_unit, portion_size, household_name, servings_per_pack):
    """
    - Título centrado: “Información Nutricional” (más grande)
    - Línea gruesa bajo el título
    - Debajo, pegado a la izquierda: tamaño por porción y número de porciones
    - Retorna y siguiente
    """
    title = "Información Nutricional"
    tw, th = text_size(draw, title, FONT_TITLE)
    tx = (W - tw)//2
    y  = start_y
    draw.text((tx, y), title, fill=TEXT_COLOR, font=FONT_TITLE)
    y += th + 10

    # Línea gruesa separadora (entre título y bloque porciones)
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 12

    # Porciones (alineado a la izquierda)
    p1, p2 = build_portion_text(portion_unit, portion_size, household_name, servings_per_pack)
    draw.text((BORDER_W + CELL_PAD_X, y + 6), p1, fill=TEXT_COLOR, font=FONT_SMALL)
    draw.text((BORDER_W + CELL_PAD_X, y + 6 + 34), p2, fill=TEXT_COLOR, font=FONT_SMALL)
    y += 80
    return y

# ============================================================
# DIBUJO: BLOQUE DE CALORÍAS (rejilla en una sola fila)
# ============================================================
def draw_calories_block(draw, W, cur_y, portion_unit, kcal_100, kcal_pp):
    """
    - Línea gruesa arriba y abajo
    - Rejilla con 3 columnas: [Calorías (kcal)] | [Por 100 … -> valor] | [Por porción -> valor]
    - Con líneas verticales entre las tres columnas
    - Retorna (y_fin_bloque, y_top_for_verticals, y_bottom_for_verticals)
    """
    # Línea gruesa arriba
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
    y_top = cur_y  # para verticales extendidas

    cur_y += 4
    # Columnas del bloque de calorías
    col_x = [BORDER_W, BORDER_W + int(W*0.50), BORDER_W + int(W*0.75), W - BORDER_W]
    header_h = 50
    values_h = 62
    total_h  = header_h + values_h + 12

    # Col 0: etiqueta
    label = "Calorías (kcal)"
    lw, lh = text_size(draw, label, FONT_LABEL_B)
    # centrado vertical del label respecto al bloque total
    ly = cur_y + (total_h//2) - (lh//2)
    draw.text((BORDER_W + CELL_PAD_X, ly), label, fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Col 1 y 2: encabezados
    per100_label = "Por 100 g" if portion_unit == "g" else "Por 100 mL"
    porcion_label = "Por porción"
    h1w, h1h = text_size(draw, per100_label, FONT_SMALL_B)
    h2w, h2h = text_size(draw, porcion_label, FONT_SMALL_B)

    c1_center = (col_x[1] + col_x[2]) // 2
    c2_center = (col_x[2] + col_x[3]) // 2

    draw.text((c1_center - h1w//2, cur_y + 6), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((c2_center - h2w//2, cur_y + 6), porcion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)

    # Línea que separa encabezados y valores
    mid_y = cur_y + header_h
    draw_hline(draw, col_x[1], W-BORDER_W, mid_y, TEXT_COLOR, GRID_W)

    # Valores centrados en su celda
    v100 = fmt_kcal(kcal_100)
    vpp  = fmt_kcal(kcal_pp)
    v1w, v1h = text_size(draw, v100, FONT_LABEL_B)
    v2w, v2h = text_size(draw, vpp,  FONT_LABEL_B)

    vy = mid_y + 10
    draw.text((c1_center - v1w//2, vy), v100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    draw.text((c2_center - v2w//2, vy), vpp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Verticales internas del bloque
    draw_vline(draw, col_x[1], cur_y, cur_y + total_h, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[2], cur_y, cur_y + total_h, TEXT_COLOR, GRID_W)

    # Línea gruesa abajo
    y_end = cur_y + total_h
    draw_hline(draw, BORDER_W, W-BORDER_W, y_end, TEXT_COLOR, GRID_W_THICK)

    # devolvemos también el rango vertical deseado para extender las líneas
    return y_end + 6, y_top, y_end

# ============================================================
# DIBUJO: FILAS (con línea vertical entre nombre y valores)
# ============================================================
def draw_rows_with_headers_and_grid(
    draw, W, start_y, rows, portion_unit, footer_text,
    extend_verticals_from=None
):
    """
    - Encabezados de columnas ("Por 100 g/mL" y "Por porción") una sola vez
    - Línea vertical entre nombre y valores (columna de corte)
    - Verticales de columnas de valores (dos)
    - Líneas gruesas donde corresponden (separador entre macros y micros)
    - Si extend_verticals_from=(y_top, y_bottom) se prolongan verticales desde
      la línea gruesa superior de calorías hasta la línea antes del pie.
    """
    # Definir columnas: label | (corte) | por100 | porción
    col_label_right = BORDER_W + int(W*0.56)     # corte vertical después del nombre
    col_100_left    = col_label_right
    col_100_right   = BORDER_W + int(W*0.80)
    col_portion_right = W - BORDER_W

    y = start_y

    # Encabezados de columnas (alineados derecha en cada columna de valores)
    per100_label = "Por 100 g" if portion_unit == "g" else "Por 100 mL"
    porcion_label = "Por porción"
    w1, _ = text_size(draw, per100_label, FONT_SMALL_B)
    w2, _ = text_size(draw, porcion_label, FONT_SMALL_B)

    draw.text((col_100_right - CELL_PAD_X - w1, y + CELL_PAD_Y - 4), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col_portion_right - CELL_PAD_X - w2, y + CELL_PAD_Y - 4), porcion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)

    # Línea fina bajo los encabezados
    y += 46
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    # Guardar y_top para verticales largas
    y_top_for_verticals = extend_verticals_from[0] if extend_verticals_from else y
    # Arrancamos filas
    for (label, v100, vpp, indent, bold, is_micro, is_sep) in rows:
        if is_sep:
            # separador grueso entre macros y micros
            draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
            continue

        # línea superior de fila
        draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

        # fuentes
        if is_micro:
            font_lbl = FONT_MICRO
            font_val = FONT_MICRO_B  # pequeños, pero con mismo contraste
        else:
            font_lbl = FONT_LABEL_B if bold else FONT_LABEL
            font_val = FONT_LABEL_B if bold else FONT_LABEL

        # label (con indent)
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text  = y + (ROW_H//2) - 14
        draw.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)

        # valores
        wv100,_ = text_size(draw, v100, font_val)
        wvpp,_  = text_size(draw, vpp,  font_val)
        draw.text((col_100_right  - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((col_portion_right - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)

        y += ROW_H

    # Base antes del pie (línea gruesa)
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Extender verticales (tres): corte, 100, porción.
    # Queremos que vayan desde la primera línea gruesa (calorías top) hasta antes del pie.
    y_bottom_for_verticals = y
    if extend_verticals_from is not None:
        y_top = extend_verticals_from[0]
        # Corte entre nombre y valores
        draw_vline(draw, col_label_right, y_top, y_bottom_for_verticals, TEXT_COLOR, GRID_W)
        # Separador entre 100 y porción
        draw_vline(draw, col_100_right, y_top, y_bottom_for_verticals, TEXT_COLOR, GRID_W)
        # Borde de porción (derecha interna)
        draw_vline(draw, col_portion_right, y_top, y_bottom_for_verticals, TEXT_COLOR, GRID_W)

    # Pie
    draw.text((BORDER_W + CELL_PAD_X, y + 16), footer_text, fill=TEXT_COLOR, font=FONT_SMALL)
    return y + 60  # y final

# ============================================================
# FIGURA 1 — VERTICAL ESTÁNDAR
# ============================================================
def draw_fig1_vertical(
    portion_unit, portion_size, household_name, servings_per_pack,
    kcal_100, kcal_pp,
    rows, footnote_ns
):
    # Dimensiones base
    W = 1400
    H_est = 220 + (50 + 62 + 20) + (len(rows)+6)*ROW_H + 200
    img = Image.new("RGB", (W, H_est), BG_WHITE)
    d = ImageDraw.Draw(img)

    # Marco
    d.rectangle([0,0,W-1,H_est-1], outline=TEXT_COLOR, width=BORDER_W)

    # Título + porciones
    y = BORDER_W + 8
    y = draw_title_and_portions(d, W, y, portion_unit, portion_size, household_name, servings_per_pack)

    # Bloque calorías
    y, y_top_cal, y_bottom_cal = draw_calories_block(d, W, y, portion_unit, kcal_100, kcal_pp)

    # Filas (con vertical extendida desde el top grueso de calorías)
    y = draw_rows_with_headers_and_grid(
        d, W, y, rows, portion_unit, footnote_ns,
        extend_verticals_from=(y_top_cal, None)
    )

    # Crop al contenido real
    img = img.crop((0, 0, W, int(y + 40)))
    return img

# ============================================================
# FIGURA 3 — SIMPLIFICADA
# ============================================================
def draw_fig3_simple(
    portion_unit, portion_size, household_name, servings_per_pack,
    kcal_100, kcal_pp,
    rows_all, footnote_ns
):
    # Selección de filas simplificadas
    keep = {
        "Grasa total",
        "  Grasa saturada",
        "  Grasas trans",
        "Carbohidratos totales",
        "  Azúcares añadidos",
        "Proteína",
        "Sodio",
    }
    rows = [r for r in rows_all if (not r[6]) and (r[0] in keep)]  # omitir separadores y micros

    W = 1400
    H_est = 200 + (50 + 62 + 20) + (len(rows)+6)*ROW_H + 200
    img = Image.new("RGB", (W, H_est), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H_est-1], outline=TEXT_COLOR, width=BORDER_W)

    y = BORDER_W + 8
    y = draw_title_and_portions(d, W, y, portion_unit, portion_size, household_name, servings_per_pack)
    y, y_top_cal, y_bottom_cal = draw_calories_block(d, W, y, portion_unit, kcal_100, kcal_pp)

    y = draw_rows_with_headers_and_grid(
        d, W, y, rows, portion_unit, footnote_ns,
        extend_verticals_from=(y_top_cal, None)
    )

    img = img.crop((0, 0, W, int(y + 40)))
    return img

# ============================================================
# FIGURA 4 — TABULAR
# ============================================================
def draw_fig4_tabular(
    portion_unit, portion_size, household_name, servings_per_pack,
    kcal_100, kcal_pp,
    rows, footnote_ns
):
    # Tabular con misma rejilla y verticales extendidas
    W = 1500
    H_est = 240 + (50 + 62 + 20) + (len(rows)+6)*ROW_H + 220
    img = Image.new("RGB", (W, H_est), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H_est-1], outline=TEXT_COLOR, width=BORDER_W)

    y = BORDER_W + 8
    y = draw_title_and_portions(d, W, y, portion_unit, portion_size, household_name, servings_per_pack)
    y, y_top_cal, y_bottom_cal = draw_calories_block(d, W, y, portion_unit, kcal_100, kcal_pp)

    # En tabular, usamos la misma función de filas (ya crea verticales y encabezados)
    y = draw_rows_with_headers_and_grid(
        d, W, y, rows, portion_unit, footnote_ns,
        extend_verticals_from=(y_top_cal, None)
    )

    img = img.crop((0, 0, W, int(y + 40)))
    return img

# ============================================================
# FIGURA 5 — LINEAL
# ============================================================
def draw_fig5_linear(
    portion_unit, portion_size, household_name, servings_per_pack,
    kcal_100, kcal_pp,
    selected_vm, vm_values_100, vm_pp,
    fat_total_100, fat_total_pp,
    sat_fat_100, sat_fat_pp,
    trans_fat_100_mg, trans_fat_pp_mg,
    carb_100, carb_pp,
    sug_total_100, sug_total_pp,
    sug_added_100, sug_added_pp,
    fiber_100, fiber_pp,
    protein_100, protein_pp,
    sodium_100_mg, sodium_pp_mg,
    footnote_ns
):
    # Construimos frase corrido con •
    items = []
    items.append(f"Calorías (kcal): {fmt_kcal(kcal_pp)} (por 100: {fmt_kcal(kcal_100)})")
    items.append(f"Grasa total: {fmt_g(fat_total_pp,1)} g (por 100: {fmt_g(fat_total_100,1)} g)")
    items.append(f"Grasa saturada: {fmt_g(sat_fat_pp,1)} g (por 100: {fmt_g(sat_fat_100,1)} g)")
    items.append(f"Grasas trans: {fmt_mg(trans_fat_pp_mg)} mg (por 100: {fmt_mg(trans_fat_100_mg)} mg)")
    items.append(f"Carbohidratos totales: {fmt_g(carb_pp,1)} g (por 100: {fmt_g(carb_100,1)} g)")
    items.append(f"Azúcares totales: {fmt_g(sug_total_pp,1)} g (por 100: {fmt_g(sug_total_100,1)} g)")
    items.append(f"Azúcares añadidos: {fmt_g(sug_added_pp,1)} g (por 100: {fmt_g(sug_added_100,1)} g)")
    items.append(f"Fibra dietaria: {fmt_g(fiber_pp,1)} g (por 100: {fmt_g(fiber_100,1)} g)")
    items.append(f"Proteína: {fmt_g(protein_pp,1)} g (por 100: {fmt_g(protein_100,1)} g)")
    items.append(f"Sodio: {fmt_mg(sodium_pp_mg)} mg (por 100: {fmt_mg(sodium_100_mg)} mg)")

    for name in selected_vm:
        v100 = vm_values_100.get(name, 0.0)
        vpp  = vm_pp.get(name, 0.0)
        unit = "mg"
        if name in ("Vitamina A", "Vitamina D", "Vitamina B12", "Ácido fólico"):
            unit = "µg"
        vpp_txt  = f"{fmt_mg(vpp)} {unit}" if unit=="mg" else f"{fmt_g(vpp,1)} {unit}"
        v100_txt = f"{fmt_mg(v100)} {unit}" if unit=="mg" else f"{fmt_g(v100,1)} {unit}"
        items.append(f"{name}: {vpp_txt} (por 100: {v100_txt})")

    W = 1600
    H = 640
    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Título + porciones
    y = BORDER_W + 8
    y = draw_title_and_portions(d, W, y, portion_unit, portion_size, household_name, servings_per_pack)

    # Texto corrido con saltos de línea automáticos
    left_x = BORDER_W + 28
    maxw = W - left_x - 30
    s = "  •  ".join(items)
    words = s.split(" ")
    line = ""
    lines = []
    for w in words:
        t = (line + " " + w).strip()
        if text_size(d, t, FONT_LABEL)[0] <= maxw:
            line = t
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)

    for ln in lines:
        d.text((left_x, y), ln, fill=TEXT_COLOR, font=FONT_LABEL)
        y += 48

    # Pie
    d.text((left_x, y + 12), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    # Crop
    img = img.crop((0, 0, W, int(y + 80)))
    return img
# ============================================================
# PREVISUALIZACIÓN Y EXPORTACIÓN PNG
# ============================================================

st.header("🖼️ Previsualización y Exportación")

preview_col, controls_col = st.columns([0.7, 0.3])

with controls_col:
    st.caption("Selecciona el formato y genera la imagen PNG con fondo blanco.")
    export_btn = st.button("📤 Generar imagen PNG")

# Construcción de filas comunes
rows_all = macros_rows_common(
    fat_total_100, fat_total_pp,
    sat_fat_100, sat_fat_pp,
    trans_fat_100_mg, trans_fat_pp_mg,
    carb_100, carb_pp,
    sug_total_100, sug_total_pp,
    sug_added_100, sug_added_pp,
    fiber_100, fiber_pp,
    protein_100, protein_pp,
    sodium_100_mg, sodium_pp_mg,
    selected_vm, vm_values_100, vm_pp
)

footnote_ns = f"No es fuente significativa de {footnote_tail.strip()}"

with preview_col:
    if format_choice.startswith("Fig. 1"):
        img_prev = draw_fig1_vertical(
            portion_unit, portion_size, household_name, servings_per_pack,
            kcal_100, kcal_pp, rows_all, footnote_ns
        )
    elif format_choice.startswith("Fig. 3"):
        img_prev = draw_fig3_simple(
            portion_unit, portion_size, household_name, servings_per_pack,
            kcal_100, kcal_pp, rows_all, footnote_ns
        )
    elif format_choice.startswith("Fig. 4"):
        img_prev = draw_fig4_tabular(
            portion_unit, portion_size, household_name, servings_per_pack,
            kcal_100, kcal_pp, rows_all, footnote_ns
        )
    else:
        img_prev = draw_fig5_linear(
            portion_unit, portion_size, household_name, servings_per_pack,
            kcal_100, kcal_pp,
            selected_vm, vm_values_100, vm_pp,
            fat_total_100, fat_total_pp,
            sat_fat_100, sat_fat_pp,
            trans_fat_100_mg, trans_fat_pp_mg,
            carb_100, carb_pp,
            sug_total_100, sug_total_pp,
            sug_added_100, sug_added_pp,
            fiber_100, fiber_pp,
            protein_100, protein_pp,
            sodium_100_mg, sodium_pp_mg,
            footnote_ns
        )

    # Mostrar previsualización
    st.image(img_prev, caption="Vista previa (escala reducida)", use_column_width=True)

# Botón de descarga PNG
if export_btn:
    buf = BytesIO()
    img_prev.save(buf, format="PNG")
    buf.seek(0)
    fname = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    st.download_button(
        label="⬇️ Descargar imagen PNG",
        data=buf,
        file_name=fname,
        mime="image/png"
    )
