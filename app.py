# app.py
# ============================================================
# Generador de Tabla Nutricional Colombia (PNG export)
# Cumple con Res. 810/2021, 2492/2022 y 254/2023 (formato visual)
# Soporta Fig.1 (vertical estándar), Fig.3 (simplificado),
# Fig.4 (tabular) y Fig.5 (lineal), exportando imagen sin título.
# Ajustes finales solicitados por el usuario (nov-2025).
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
        if nd == 0:
            return f"{int(round(x,0))}"
        return f"{x:.{nd}f}".rstrip('0').rstrip('.')
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
# ESTILO DE DIBUJO (tipos, grosores, helpers)
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

def draw_hline(draw, x0, x1, y, color, width):
    draw.line((x0, y, x1, y), fill=color, width=width)

def draw_vline(draw, x, y0, y1, color, width):
    draw.line((x, y0, x, y1), fill=color, width=width)

# ============================================================
# BARRA LATERAL (CONFIG)
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

physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])
# Solo ingreso por 100 g / 100 mL (se quita modo por porción)
input_basis = "Por 100 g/mL"

product_name = st.sidebar.text_input("Nombre del producto (opcional, no se imprime en PNG)")

# Tamaño de porción: medida casera + cantidad, y entre paréntesis el gramaje/volumen
st.sidebar.subheader("Porciones (para impresión)")
portion_household_name = st.sidebar.text_input("Medida casera (ej. taza, cucharada, unidad)", value="taza")
portion_household_qty  = st.sidebar.text_input("Cantidad (ej. 1/2, 1, 3)", value="1")
portion_unit = "g" if "Sólido" in physical_state else "mL"
portion_mass_val = as_num(st.sidebar.text_input(f"Peso de porción en {portion_unit}", value="50"))
servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="1"))

# Vitaminas/minerales (multi-selección) — unidades se ponen junto al valor, no al nombre
st.sidebar.header("Micronutrientes (opcional)")
vm_options = [
    "Vitamina A",
    "Vitamina D",
    "Calcio",
    "Hierro",
    "Zinc",
    "Potasio",
    "Vitamina C",
    "Vitamina E",
    "Vitamina B12",
    "Ácido fólico",
]
selected_vm = st.sidebar.multiselect(
    "Selecciona micronutrientes a incluir",
    vm_options,
    default=["Vitamina A", "Vitamina D", "Calcio", "Hierro", "Zinc"]
)

# Pie: “No es fuente significativa de …” SIEMPRE aparece
st.sidebar.header("Texto al pie")
footnote_base = "No es fuente significativa de"
footnote_tail = st.sidebar.text_input("Completa la frase", value=" _____.")
footnote_ns = f"{footnote_base}{'' if footnote_tail.strip().startswith(' ') else ' '}{footnote_tail.strip()}"

# ============================================================
# INGRESO DE NUTRIENTES (SOLO POR 100 g/mL)
# ============================================================
st.header("Ingreso de información nutricional **por 100 g / 100 mL** (solo números)")
c1, c2 = st.columns(2)
with c1:
    st.subheader("Macronutrientes")
    fat_total_100 = as_num(st.text_input("Grasa total (g / 100 g o mL)", value="5"))
    sat_fat_100   = as_num(st.text_input("Grasa saturada (g / 100 g o mL)", value="2"))
    # Grasa trans se ingresa en mg / 100 g (o mL)
    trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg / 100 g o mL)", value="0"))

    carb_100      = as_num(st.text_input("Carbohidratos totales (g / 100 g o mL)", value="20"))
    sugars_total_100  = as_num(st.text_input("Azúcares totales (g / 100 g o mL)", value="10"))
    sugars_added_100  = as_num(st.text_input("Azúcares añadidos (g / 100 g o mL)", value="8"))
    fiber_100     = as_num(st.text_input("Fibra dietaria (g / 100 g o mL)", value="2"))
    protein_100   = as_num(st.text_input("Proteína (g / 100 g o mL)", value="3"))
    sodium_100_mg = as_num(st.text_input("Sodio (mg / 100 g o mL)", value="150"))

with c2:
    st.subheader("Micronutrientes (por 100 g / 100 mL)")
    vm_values_100 = {}
    for vm in selected_vm:
        vm_values_100[vm] = as_num(st.text_input(vm, value="0"))

# ============================================================
# CÁLCULO POR PORCIÓN (derivado del peso/volumen)
# ============================================================
# Convertir trans g para energía
trans_fat_100_g = (trans_fat_100_mg or 0.0) / 1000.0

# Derivar por porción a partir del peso/volumen de la porción
portion_size = portion_mass_val  # en g o mL
fat_total_pp = portion_from_per100(fat_total_100, portion_size)
sat_fat_pp   = portion_from_per100(sat_fat_100, portion_size)
trans_fat_pp_g = portion_from_per100(trans_fat_100_g, portion_size)

carb_pp      = portion_from_per100(carb_100, portion_size)
sugars_total_pp = portion_from_per100(sugars_total_100, portion_size)
sugars_added_pp = portion_from_per100(sugars_added_100, portion_size)
fiber_pp     = portion_from_per100(fiber_100, portion_size)
protein_pp   = portion_from_per100(protein_100, portion_size)
sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_size)

# Micronutrientes por porción
vm_values_pp = {}
for vm, v100 in vm_values_100.items():
    vm_values_pp[vm] = portion_from_per100(v100, portion_size)

# ============================================================
# ENERGÍA Y FOP (informativo dentro del app)
# ============================================================
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp  = kcal_from_macros(fat_total_pp,  carb_pp,  protein_pp)

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

# Config visual general (mismos grosores/ancho acordados)
BORDER_W = 6                 # marco externo
GRID_W_THICK = 5             # separadores principales
GRID_W = 3                   # líneas normales
TEXT_COLOR = (0, 0, 0)
BG_WHITE = (255, 255, 255)

# Tipografías (mismas escalas; título un poco más grande)
FONT_TITLE = get_font(40, bold=True)     # más grande y centrado
FONT_LABEL = get_font(30, bold=False)
FONT_LABEL_B = get_font(30, bold=True)
FONT_SMALL = get_font(26, bold=False)
FONT_SMALL_B = get_font(26, bold=True)
FONT_MICRO = get_font(24, bold=False)       # micronutrientes más pequeño
FONT_MICRO_B = get_font(24, bold=True)

ROW_H = 64
CELL_PAD_X = 22
CELL_PAD_Y = 18

def build_portion_text():
    # “Tamaño de porción: <cantidad> <medida> (<gramaje> g/mL)”
    qty = portion_household_qty.strip()
    meas = portion_household_name.strip()
    gramaje = f"{int(round(portion_size))} {portion_unit}"
    porc1 = f"Tamaño de porción: {qty} {meas} ({gramaje})"
    porc2 = f"Número de porciones por envase: {int(round(servings_per_pack))}"
    return porc1, porc2

def macros_rows_common():
    """
    Devuelve la lista base (Fig.1/Fig.4) de nutrientes (tuplas)
    (label, v100_str, vpp_str, unit, indent, bold, is_sep, is_micro)
    """
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"

    rows = [
        # Macros
        ("Grasa total",        f"{fmt_g(fat_total_100,1)} g",              f"{fmt_g(fat_total_pp,1)} g",            "g", 0, False, False, False),
        ("  Grasa saturada",   f"{fmt_g(sat_fat_100,1)} g",                f"{fmt_g(sat_fat_pp,1)} g",              "g", 1, True,  False, False),
        ("  Grasas trans",     f"{fmt_mg(trans_fat_100_g*1000)} mg",       f"{fmt_mg(trans_fat_pp_g*1000)} mg",     "mg",1, True,  False, False),
        ("Carbohidratos",      f"{fmt_g(carb_100,1)} g",                   f"{fmt_g(carb_pp,1)} g",                 "g", 0, False, False, False),
        ("  Azúcares totales", f"{fmt_g(sugars_total_100,1)} g",           f"{fmt_g(sugars_total_pp,1)} g",         "g", 1, False, False, False),
        ("  Azúcares añadidos",f"{fmt_g(sugars_added_100,1)} g",           f"{fmt_g(sugars_added_pp,1)} g",         "g", 1, True,  False, False),
        ("  Fibra dietaria",   f"{fmt_g(fiber_100,1)} g",                  f"{fmt_g(fiber_pp,1)} g",                "g", 1, False, False, False),
        ("Proteína",           f"{fmt_g(protein_100,1)} g",                f"{fmt_g(protein_pp,1)} g",              "g", 0, False, False, False),
        ("Sodio",              f"{fmt_mg(sodium_100_mg)} mg",              f"{fmt_mg(sodium_pp_mg)} mg",            "mg",0, True,  False, False),
    ]
    # Micronutrientes (más pequeños; nombre sin unidades, unidades junto al valor)
    if selected_vm:
        rows.append(("---sep---", "", "", "", 0, False, True, False))  # separador grueso
        for vm in selected_vm:
            v100 = vm_values_100.get(vm, 0.0)
            vpp  = vm_values_pp.get(vm, 0.0)
            # Heurística de unidad: mg para minerales comunes; µg para Vit A, D, B12, Ácido fólico
            unit = "mg"
            if vm in ["Vitamina A", "Vitamina D", "Vitamina B12", "Ácido fólico"]:
                unit = "µg"
            if vm == "Vitamina E":
                unit = "mg"
            if vm == "Vitamina C":
                unit = "mg"
            if vm == "Potasio":
                unit = "mg"
            # valores con unidad al lado del valor (no del nombre)
            val100 = f"{fmt_mg(v100)} {unit}" if unit == "mg" else f"{fmt_g(v100,1)} {unit}"
            valpp  = f"{fmt_mg(vpp)} {unit}"  if unit == "mg" else f"{fmt_g(vpp,1)} {unit}"
            rows.append((vm, val100, valpp, unit, 0, False, False, True))
    return rows

def draw_title_and_portions(draw, W, H, start_y):
    """
    Dibuja el título centrado (“Información Nutricional”) y debajo
    (alineado a la izquierda) ‘Tamaño de porción’ y ‘Número de porciones…’.
    Entre el título y esas dos líneas va una línea gruesa (según pedido).
    Retorna el nuevo y (posición siguiente).
    """
    # Marco externo ya se dibuja en cada figura
    # Título centrado
    title = "Información Nutricional"
    tw, th = text_size(draw, title, FONT_TITLE)
    cx = W // 2
    tx = cx - tw//2
    y = start_y
    draw.text((tx, y), title, fill=TEXT_COLOR, font=FONT_TITLE)
    y += th + 12

    # Línea gruesa que separa el título del bloque de porciones
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 12

    # Porciones (izquierda)
    p1, p2 = build_portion_text()
    draw.text((BORDER_W + CELL_PAD_X, y + 8),  p1, fill=TEXT_COLOR, font=FONT_SMALL)
    draw.text((BORDER_W + CELL_PAD_X, y + 8 + 34), p2, fill=TEXT_COLOR, font=FONT_SMALL)
    y += 80

    return y

def draw_calories_block(draw, W, cur_y):
    """
    Bloque de Calorías (kcal) con:
    - Línea gruesa arriba
    - Una “fila” con cuatro celdas:
        [ Calorías (kcal) | Por 100 g/mL | Por porción ]
        [       (vacío)   |   valor 100  |   valor porción ]
      * separadas con líneas verticales y horizontales internas
      * línea gruesa abajo
    Retorna y final.
    """
    # Línea gruesa arriba
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
    cur_y += 4

    # Definir columnas de la rejilla de calorías (3 celdas de ancho similar):
    # Col0: etiqueta “Calorías (kcal)”
    # Col1: subcolumna “Por 100 g/mL” (encabezado) + valor debajo
    # Col2: subcolumna “Por porción”  (encabezado) + valor debajo
    # Mismo ancho total usado en las figuras previas
    col_x = [BORDER_W, BORDER_W + int(W*0.50), BORDER_W + int(W*0.75), W - BORDER_W]
    row_h_header = 48  # encabezados “Por 100 … / Por porción”
    row_h_values = 64  # fila de valores
    total_h = row_h_header + row_h_values + 16

    # Marco interno vertical (para no cruzar título/porciones)
    # Títulos de subcolumnas (centrados en sus celdas)
    # Col0: “Calorías (kcal)”
    label = "Calorías (kcal)"
    lw, lh = text_size(draw, label, FONT_LABEL_B)
    # Centrar verticalmente en el bloque total
    label_y = cur_y + (total_h//2) - (lh//2)
    draw.text((BORDER_W + CELL_PAD_X, label_y), label, fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Encabezados subcolumnas
    per100_label = "Por 100 g" if "g" in portion_unit else "Por 100 mL"
    perportion_label = "Por porción"  # sin cantidad (pedido)

    # texto centrado en Col1 encabezado
    h1_w, h1_h = text_size(draw, per100_label, FONT_SMALL_B)
    h2_w, h2_h = text_size(draw, perportion_label, FONT_SMALL_B)

    # Centro de col1 (col_x[1]..col_x[2]) y col2 (col_x[2]..col_x[3])
    col1_center = (col_x[1] + col_x[2]) // 2
    col2_center = (col_x[2] + col_x[3]) // 2

    # Encabezados
    draw.text((col1_center - h1_w//2, cur_y + 6), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col2_center - h2_w//2, cur_y + 6), perportion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)

    # Línea horizontal que divide encabezados y valores
    mid_y = cur_y + row_h_header + 4
    draw_hline(draw, col_x[1], W-BORDER_W, mid_y, TEXT_COLOR, GRID_W)

    # Valores (centrados en su celda)
    txt_100 = f"{fmt_kcal(kcal_100)}"
    txt_pp  = f"{fmt_kcal(kcal_pp)}"
    v1_w, v1_h = text_size(draw, txt_100, FONT_LABEL_B)
    v2_w, v2_h = text_size(draw, txt_pp,  FONT_LABEL_B)

    v_y = mid_y + 12
    draw.text((col1_center - v1_w//2, v_y), txt_100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    draw.text((col2_center - v2_w//2, v_y), txt_pp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Separadores verticales internos (desde arriba del bloque hasta abajo)
    draw_vline(draw, col_x[1], cur_y, cur_y + total_h, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[2], cur_y, cur_y + total_h, TEXT_COLOR, GRID_W)

    # Línea gruesa abajo
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y + total_h, TEXT_COLOR, GRID_W_THICK)

    return cur_y + total_h + 8

def draw_rows_grid(draw, W, start_y, rows, footer_text, micronutrient_smaller=True):
    """
    Dibuja todas las filas de nutrientes con:
    - línea fina arriba de cada fila
    - dos columnas de valores a la derecha (por 100 y por porción)
    - separador vertical entre columnas de valores
    - línea gruesa entre macros y micronutrientes (si ‘---sep---’)
    - pie al final
    """
    # Columnas (3 columnas: label | por 100 | por porción)
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]
    y = start_y

    # Línea fina inicial (para cerrar caja)
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    for tup in rows:
        label, v100, vpp, unit, indent, bold, is_sep, is_micro = tup

        if is_sep:
            # línea gruesa separando macros de micronutrientes
            draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
            continue

        font_lbl = FONT_LABEL_B if bold else (FONT_MICRO if is_micro and micronutrient_smaller else FONT_LABEL)
        font_val = FONT_LABEL_B if bold else (FONT_MICRO_B if is_micro and micronutrient_smaller else FONT_LABEL)

        # línea superior de la fila
        draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

        # label
        x_label = BORDER_W + CELL_PAD_X + (indent * 28)
        y_label = y + (ROW_H//2) - 14
        draw.text((x_label, y_label), label, fill=TEXT_COLOR, font=font_lbl)

        # valores a la derecha (alineados a derecha)
        wv100, _ = text_size(draw, v100, font_val)
        wvpp,  _ = text_size(draw, vpp,  font_val)
        draw.text((col_x[2] - CELL_PAD_X - wv100, y_label), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((col_x[3] - CELL_PAD_X - wvpp,  y_label), vpp,  fill=TEXT_COLOR, font=font_val)

        y += ROW_H

    # línea base antes del pie
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # pie
    y += 16
    draw.text((BORDER_W + CELL_PAD_X, y + 12), footer_text, fill=TEXT_COLOR, font=FONT_SMALL)
    return y + 60

# ================== Figuras ==================

def draw_table_fig1_vertical():
    """
    Fig. 1 — Vertical estándar
    - Título centrado (grande) + línea gruesa
    - Porción y número de porciones (izquierda)
    - Bloque Calorías (rejilla en la MISMA fila, con encabezados y valores)
    - Resto de nutrientes con columnas por 100 y por porción
    - Línea gruesa entre macros y micronutrientes
    """
    rows = macros_rows_common()

    # Dimensiones
    W = 1400
    # estimar altura
    base_h = 220  # título + porciones
    cal_h  = 48 + 64 + 24  # bloque calorías
    num_rows = sum(1 for r in rows if r[0] != "---sep---")
    sep_count = sum(1 for r in rows if r[0] == "---sep---")
    footer_h = 110
    H = BORDER_W*2 + base_h + cal_h + num_rows*ROW_H + sep_count*GRID_W_THICK + footer_h + 40

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # marco
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    y = BORDER_W + 8
    y = draw_title_and_portions(draw, W, H, y)

    # bloque calorías
    y = draw_calories_block(draw, W, y)

    # columnas de valores (verticales)
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]
    # Encabezados de columnas por 100 / porción (arriba de la primera fila de nutrientes)
    per100_label = "por 100 g" if "g" in portion_unit else "por 100 mL"
    perportion_label = "por porción"

    # encabezados (alineados derecha en sus columnas)
    w_c100, _ = text_size(draw, per100_label, FONT_SMALL_B)
    w_cpp, _  = text_size(draw, perportion_label, FONT_SMALL_B)
    draw.text((col_x[2] - CELL_PAD_X - w_c100, y + 6), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col_x[3] - CELL_PAD_X - w_cpp,  y + 6), perportion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    # línea fina bajo encabezados
    draw_hline(draw, BORDER_W, W-BORDER_W, y + 46, TEXT_COLOR, GRID_W)
    y += 50

    # verticales (desde aquí para no cruzar encabezados)
    draw_vline(draw, col_x[2], y, H-BORDER_W-110, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], y, H-BORDER_W-110, TEXT_COLOR, GRID_W)

    y = draw_rows_grid(draw, W, y, rows, footnote_ns)
    return img

def draw_table_fig3_simple():
    """
    Fig. 3 — Simplificado (menos filas)
    Mantiene estética y bloque de calorías con la misma rejilla.
    """
    # filas reducidas
    rows_all = macros_rows_common()
    # seleccionar simplificado: total, saturada, trans, carbohidratos, azúcares añadidos, proteína, sodio
    keep = {"Grasa total", "  Grasa saturada", "  Grasas trans", "Carbohidratos", "  Azúcares añadidos", "Proteína", "Sodio"}
    rows = []
    had_sep = False
    for r in rows_all:
        if r[0] == "---sep---":
            had_sep = True
            continue
        if r[0] in keep:
            # (label, v100, vpp, unit, indent, bold, is_sep, is_micro)
            rows.append(r)
    # Dimensiones
    W = 1400
    base_h = 220
    cal_h  = 48 + 64 + 24
    num_rows = len(rows)
    footer_h = 110
    H = BORDER_W*2 + base_h + cal_h + num_rows*ROW_H + footer_h + 40

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # marco
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    y = BORDER_W + 8
    y = draw_title_and_portions(draw, W, H, y)
    y = draw_calories_block(draw, W, y)

    # Encabezados columnas antes de las filas
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]
    per100_label = "por 100 g" if "g" in portion_unit else "por 100 mL"
    perportion_label = "por porción"
    w_c100, _ = text_size(draw, per100_label, FONT_SMALL_B)
    w_cpp, _  = text_size(draw, perportion_label, FONT_SMALL_B)
    draw.text((col_x[2] - CELL_PAD_X - w_c100, y + 6), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col_x[3] - CELL_PAD_X - w_cpp,  y + 6), perportion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw_hline(draw, BORDER_W, W-BORDER_W, y + 46, TEXT_COLOR, GRID_W)
    y += 50
    draw_vline(draw, col_x[2], y, H-BORDER_W-110, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], y, H-BORDER_W-110, TEXT_COLOR, GRID_W)

    y = draw_rows_grid(draw, W, y, rows, footnote_ns)
    return img

def draw_table_fig4_tabular():
    """
    Fig. 4 — Tabular
    Estructura de malla completa, celdas bien definidas, con negrillas según norma.
    Mantiene el bloque de calorías en rejilla en la misma fila (como las otras figuras).
    """
    rows = macros_rows_common()

    # Dimensiones
    W = 1400
    base_h = 220
    cal_h  = 48 + 64 + 24
    num_rows = sum(1 for r in rows if r[0] != "---sep---")
    sep_count = sum(1 for r in rows if r[0] == "---sep---")
    footer_h = 110
    H = BORDER_W*2 + base_h + cal_h + num_rows*ROW_H + sep_count*GRID_W_THICK + footer_h + 40

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # marco
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    y = BORDER_W + 8
    y = draw_title_and_portions(draw, W, H, y)
    y = draw_calories_block(draw, W, y)

    # En tabular, todo en malla: encabezados columnas + filas
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]
    per100_label = "por 100 g" if "g" in portion_unit else "por 100 mL"
    perportion_label = "por porción"

    # Encabezados centrados en celdas de sus columnas
    w_c100, _ = text_size(draw, per100_label, FONT_SMALL_B)
    w_cpp, _  = text_size(draw, perportion_label, FONT_SMALL_B)
    # Dibujar casilla de encabezado como una “fila tabular”: línea superior fina
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
    # Etiquetas centradas en su celda (pero para Col0 no hay etiqueta; está vacío)
    c1_center = (col_x[1] + col_x[2]) // 2
    c2_center = (col_x[2] + col_x[3]) // 2
    draw.text((c1_center - w_c100//2, y + CELL_PAD_Y), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((c2_center - w_cpp//2,  y + CELL_PAD_Y), perportion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)

    # verticales
    draw_vline(draw, col_x[1], y, H-BORDER_W-110, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[2], y, H-BORDER_W-110, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], y, H-BORDER_W-110, TEXT_COLOR, GRID_W)

    # línea inferior de la fila de encabezados
    draw_hline(draw, BORDER_W, W-BORDER_W, y + 46, TEXT_COLOR, GRID_W)
    y += 50

    # Fila por fila en malla
    for r in rows:
        label, v100, vpp, unit, indent, bold, is_sep, is_micro = r
        if is_sep:
            draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
            continue

        # línea superior de fila
        draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

        font_lbl = FONT_LABEL_B if bold else (FONT_MICRO if is_micro else FONT_LABEL)
        font_val = FONT_LABEL_B if bold else (FONT_MICRO_B if is_micro else FONT_LABEL)

        # Col0 (label) — en tabular no “indentamos” con espacios, sino con alineación visual
        x_label = BORDER_W + CELL_PAD_X + (indent * 28)
        y_text = y + (ROW_H//2) - 14
        draw.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)

        # Col1 (por 100)
        wv100, _ = text_size(draw, v100, font_val)
        draw.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)

        # Col2 (por porción)
        wvpp, _ = text_size(draw, vpp, font_val)
        draw.text((col_x[3] - CELL_PAD_X - wvpp, y_text), vpp, fill=TEXT_COLOR, font=font_val)

        y += ROW_H

    # línea base antes del pie
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 16
    draw.text((BORDER_W + CELL_PAD_X, y + 12), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

def draw_table_fig5_linear():
    """
    Fig. 5 — Lineal (en 1-2 líneas con separadores)
    Ahora muestra “Calorías (kcal): valor por porción (por 100 …)” etc.
    """
    items = []

    # Calorías
    kcal_pp_txt  = f"{fmt_kcal(kcal_pp)} kcal"
    kcal_100_txt = f"{fmt_kcal(kcal_100)} kcal"
    items.append(f"Calorías (kcal): {kcal_pp_txt} (por 100: {kcal_100_txt})")

    def pair(name, vpp_txt, v100_txt):
        items.append(f"{name}: {vpp_txt} (por 100: {v100_txt})")

    pair("Grasa total", f"{fmt_g(fat_total_pp,1)} g",         f"{fmt_g(fat_total_100,1)} g")
    pair("Grasa saturada", f"{fmt_g(sat_fat_pp,1)} g",        f"{fmt_g(sat_fat_100,1)} g")
    pair("Grasas trans", f"{fmt_mg(trans_fat_pp_g*1000)} mg", f"{fmt_mg(trans_fat_100_g*1000)} mg")
    pair("Carbohidratos", f"{fmt_g(carb_pp,1)} g",            f"{fmt_g(carb_100,1)} g")
    pair("Azúcares totales", f"{fmt_g(sugars_total_pp,1)} g", f"{fmt_g(sugars_total_100,1)} g")
    pair("Azúcares añadidos", f"{fmt_g(sugars_added_pp,1)} g",f"{fmt_g(sugars_added_100,1)} g")
    pair("Fibra dietaria", f"{fmt_g(fiber_pp,1)} g",          f"{fmt_g(fiber_100,1)} g")
    pair("Proteína", f"{fmt_g(protein_pp,1)} g",              f"{fmt_g(protein_100,1)} g")
    pair("Sodio", f"{fmt_mg(sodium_pp_mg)} mg",               f"{fmt_mg(sodium_100_mg)} mg")

    # Micronutrientes
    for vm in selected_vm:
        vpp  = vm_values_pp.get(vm, 0.0)
        v100 = vm_values_100.get(vm, 0.0)
        unit = "mg"
        if vm in ["Vitamina A", "Vitamina D", "Vitamina B12", "Ácido fólico"]:
            unit = "µg"
        vpp_txt  = f"{fmt_mg(vpp)} {unit}" if unit == "mg" else f"{fmt_g(vpp,1)} {unit}"
        v100_txt = f"{fmt_mg(v100)} {unit}" if unit == "mg" else f"{fmt_g(v100,1)} {unit}"
        pair(vm, vpp_txt, v100_txt)

    # Imagen
    W = 1600
    H = 560 if len(items) <= 8 else 720 if len(items) <= 14 else 900
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # marco
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    y = BORDER_W + 8
    # título centrado + línea gruesa + porciones izquierda
    y = draw_title_and_portions(draw, W, H, y)

    # texto lineal con puntos medios
    left_x = BORDER_W + 28
    line_items = "  •  ".join(items)
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

    # pie
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
