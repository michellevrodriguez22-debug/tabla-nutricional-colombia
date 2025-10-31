# app.py
# ============================================================
# Generador de Tabla Nutricional Colombia (PNG export)
# Cumple con Res. 810/2021, 2492/2022 y 254/2023 (formato visual)
# Soporta Fig.1 (vertical estándar), Fig.3 (simplificado),
# Fig.4 (tabular) y Fig.5 (lineal), exportando imagen sin título extra.
# Cambios solicitados (Oct 2025):
# - Solo ingreso "por 100 g / 100 mL" (se elimina el modo "por porción").
# - El título "Información Nutricional" va centrado y más grande.
# - Etiquetas en negrilla (grasa saturada, trans, azúcares añadidos, sodio) más grandes.
# - En la fila de Calorías: mostrar "Calorías (kcal)" y, dentro de la misma fila,
#   los subtítulos "por 100 g/mL" y "por porción" con sus valores debajo.
# - Las líneas gruesas: arriba/abajo de Calorías y entre nutrientes y micronutrientes.
# - Micronutrientes ligeramente más pequeños que macronutrientes.
# - Medida casera primero y gramaje entre paréntesis en el tamaño de porción.
# - Encabezado de columnas usa "por 100 g/mL" y "por porción" (sin el tamaño).
# - "Número de porciones por envase" (no "Porciones por envase").
# - Ajustes de estética para formato Tabular (Fig.4) respetando norma visual.
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
        if x is None or (isinstance(x, str) and x.strip() == ""):
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

# ============================================================
# TIPOGRAFÍA Y DIBUJO
# ============================================================
def get_font(size, bold=False):
    try:
        if bold:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except:
        return ImageFont.load_default()

def text_size(draw, text, font):
    bbox = draw.textbbox((0,0), text, font=font)
    return (bbox[2]-bbox[0], bbox[3]-bbox[1])

def draw_hline(draw, x0, x1, y, color, width):
    draw.line((x0, y, x1, y), fill=color, width=width)

def draw_vline(draw, x, y0, y1, color, width):
    draw.line((x, y0, x, y1), fill=color, width=width)

# ============================================================
# ENCABEZADO UI
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

st.sidebar.subheader("Tamaño de porción")
household_measure = st.sidebar.text_input("Medida casera (p. ej., taza, cucharada, unidad)", value="taza")
household_qty = as_num(st.sidebar.text_input("Cantidad de medida casera", value="1"))
portion_weight = as_num(st.sidebar.text_input("Gramaje/peso de la porción (en g o mL)", value="50"))

is_liquid = ("Líquido" in physical_state)
per100_label = "por 100 mL" if is_liquid else "por 100 g"
perportion_label = "por porción"

product_name = st.sidebar.text_input("Nombre del producto (opcional)", value="")
brand_name = st.sidebar.text_input("Marca (opcional)", value="")
provider = st.sidebar.text_input("Proveedor/Fabricante (opcional)", value="")

include_kj = st.sidebar.checkbox("Mostrar también kJ junto a kcal", value=True)

st.sidebar.header("Micronutrientes (opcional)")
vm_options = [
    "Vitamina A (µg ER)",
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
footnote_ns = f"{footnote_base}{'' if footnote_tail.strip().startswith(' ') else ' '}{footnote_tail.strip()}"

st.header("Ingreso de información nutricional (por 100 g/mL)")
st.caption("Ingresa valores **por 100 g** (sólidos) o **por 100 mL** (líquidos).")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Macronutrientes (por 100)")
    fat_total_100 = as_num(st.text_input("Grasa total (g)", value="5"))
    sat_fat_100   = as_num(st.text_input("Grasa saturada (g)", value="2"))
    trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg)", value="0"))
    carb_100      = as_num(st.text_input("Carbohidratos totales (g)", value="20"))
    sugars_total_100  = as_num(st.text_input("Azúcares totales (g)", value="10"))
    sugars_added_100  = as_num(st.text_input("Azúcares añadidos (g)", value="8"))
    fiber_100     = as_num(st.text_input("Fibra dietaria (g)", value="2"))
    protein_100   = as_num(st.text_input("Proteína (g)", value="3"))
    sodium_100_mg = as_num(st.text_input("Sodio (mg)", value="150"))

with c2:
    st.subheader("Micronutrientes (por 100)")
    vm_values_100 = {}
    for vm in selected_vm:
        vm_values_100[vm] = as_num(st.text_input(vm, value="0"))

portion_unit = "mL" if is_liquid else "g"
trans_fat_100_g = (trans_fat_100_mg or 0.0) / 1000.0

fat_total_pp = portion_from_per100(fat_total_100, portion_weight)
sat_fat_pp   = portion_from_per100(sat_fat_100, portion_weight)
trans_fat_pp_mg = portion_from_per100(trans_fat_100_mg, portion_weight)
trans_fat_pp_g  = trans_fat_pp_mg / 1000.0
carb_pp      = portion_from_per100(carb_100, portion_weight)
sugars_total_pp = portion_from_per100(sugars_total_100, portion_weight)
sugars_added_pp = portion_from_per100(sugars_added_100, portion_weight)
fiber_pp     = portion_from_per100(fiber_100, portion_weight)
protein_pp   = portion_from_per100(protein_100, portion_weight)
sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_weight)

vm_pp = {vm: portion_from_per100(v100, portion_weight) for vm, v100 in vm_values_100.items()}

kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp  = kcal_from_macros(fat_total_pp,  carb_pp,  protein_pp)

kj_100 = round(kcal_100 * 4.184) if include_kj else None
kj_pp  = round(kcal_pp  * 4.184) if include_kj else None

BORDER_W = 9
GRID_W_THICK = 7
GRID_W = 3

TEXT_COLOR = (0, 0, 0)
BG_WHITE = (255, 255, 255)

FONT_TITLE = get_font(44, bold=True)
FONT_HEADER = get_font(30, bold=False)
FONT_HEADER_B = get_font(30, bold=True)

FONT_CAL_B = get_font(36, bold=True)
FONT_CAL_NUM = get_font(36, bold=True)
FONT_CAL_SUB = get_font(22, bold=True)

FONT_LABEL = get_font(30, bold=False)
FONT_LABEL_B = get_font(30, bold=True)
FONT_VAL = get_font(30, bold=False)
FONT_VAL_B = get_font(30, bold=True)

FONT_MICRO = get_font(26, bold=False)
FONT_MICRO_B = get_font(26, bold=True)

FONT_FOOT = get_font(24, bold=False)

ROW_H = 66
CELL_PAD_X = 24
CELL_PAD_Y = 16
INDENT_STEP = 28

def build_common_rows():
    rows = []
    rows.append(("Grasa total",        f"{fmt_g(fat_total_100,1)} g",  f"{fmt_g(fat_total_pp,1)} g",  0, False, False))
    rows.append(("  Grasa saturada",   f"{fmt_g(sat_fat_100,1)} g",    f"{fmt_g(sat_fat_pp,1)} g",    1, True,  False))
    rows.append(("  Grasas trans",     f"{fmt_mg(trans_fat_100_mg)} mg", f"{fmt_mg(trans_fat_pp_mg)} mg", 1, True, False))
    rows.append(("Carbohidratos",      f"{fmt_g(carb_100,1)} g",       f"{fmt_g(carb_pp,1)} g",       0, False, False))
    rows.append(("  Azúcares totales", f"{fmt_g(sugars_total_100,1)} g", f"{fmt_g(sugars_total_pp,1)} g", 1, False, False))
    rows.append(("  Azúcares añadidos",f"{fmt_g(sugars_added_100,1)} g", f"{fmt_g(sugars_added_pp,1)} g", 1, True,  False))
    rows.append(("  Fibra dietaria",   f"{fmt_g(fiber_100,1)} g",      f"{fmt_g(fiber_pp,1)} g",      1, False, False))
    rows.append(("Proteína",           f"{fmt_g(protein_100,1)} g",    f"{fmt_g(protein_pp,1)} g",    0, False, False))
    rows.append(("Sodio",              f"{fmt_mg(sodium_100_mg)} mg",  f"{fmt_mg(sodium_pp_mg)} mg",  0, True,  False))
    if selected_vm:
        rows.append(("---sep---", "", "", 0, False, False))
        for vm in selected_vm:
            unit = "mg"
            if "µg" in vm: unit = "µg"
            v100 = vm_values_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)
            name = "Vitamina A (µg ER)" if vm.startswith("Vitamina A") else vm
            val100 = f"{fmt_mg(v100)} mg" if unit == "mg" else f"{fmt_g(v100,1)} µg"
            valpp  = f"{fmt_mg(vpp)} mg"  if unit == "mg" else f"{fmt_g(vpp,1)} µg"
            rows.append((name, val100, valpp, 0, False, True))
    return rows

def header_block(draw, img_w, y0):
    title = "Información Nutricional"
    tw, th = text_size(draw, title, FONT_TITLE)
    draw.text(((img_w - tw)//2, y0), title, fill=TEXT_COLOR, font=FONT_TITLE)

    portion_line = f"Tamaño de porción: {int(round(household_qty))} {household_measure} ({int(round(portion_weight))} {('mL' if is_liquid else 'g')})"
    servings_line = f"Número de porciones por envase: {st.session_state.get('servings_per_pack_print', 1)}"

    y = y0 + th + 8
    draw.text((CELL_PAD_X + BORDER_W, y), portion_line, fill=TEXT_COLOR, font=FONT_HEADER)
    y += 38
    draw.text((CELL_PAD_X + BORDER_W, y), servings_line, fill=TEXT_COLOR, font=FONT_HEADER)
    y += 40
    return y

def draw_calories_row(draw, x_left, x_col2, x_col3, y, img_w):
    draw_hline(draw, BORDER_W, img_w - BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 6
    label = "Calorías (kcal)"
    draw.text((x_left + CELL_PAD_X, y + (ROW_H//2) - 14), label, fill=TEXT_COLOR, font=FONT_CAL_B)
    sub1 = per100_label
    sub2 = perportion_label
    kcal_100_txt = fmt_kcal(kcal_100) + (f" ({kj_100} kJ)" if include_kj else "")
    kcal_pp_txt  = fmt_kcal(kcal_pp)  + (f" ({kj_pp} kJ)"  if include_kj else "")
    w_sub1, _ = text_size(draw, sub1, FONT_CAL_SUB)
    w_sub2, _ = text_size(draw, sub2, FONT_CAL_SUB)
    draw.text((x_col2 - CELL_PAD_X - w_sub1, y + 6), sub1, fill=TEXT_COLOR, font=FONT_CAL_SUB)
    draw.text((x_col3 - CELL_PAD_X - w_sub2, y + 6), sub2, fill=TEXT_COLOR, font=FONT_CAL_SUB)
    w_k1, _ = text_size(draw, kcal_100_txt, FONT_CAL_NUM)
    w_k2, _ = text_size(draw, kcal_pp_txt,  FONT_CAL_NUM)
    draw.text((x_col2 - CELL_PAD_X - w_k1, y + 6 + 26), kcal_100_txt, fill=TEXT_COLOR, font=FONT_CAL_NUM)
    draw.text((x_col3 - CELL_PAD_X - w_k2, y + 6 + 26), kcal_pp_txt,  fill=TEXT_COLOR, font=FONT_CAL_NUM)
    row_h = ROW_H + 26
    y += row_h
    draw_hline(draw, BORDER_W, img_w - BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    return y

def draw_column_headers(draw, x_left, x_col2, x_col3, y):
    w_c100, _ = text_size(draw, per100_label, FONT_HEADER_B)
    w_cpp, _  = text_size(draw, perportion_label, FONT_HEADER_B)
    draw.text((x_col2 - CELL_PAD_X - w_c100, y), per100_label, fill=TEXT_COLOR, font=FONT_HEADER_B)
    draw.text((x_col3 - CELL_PAD_X - w_cpp,  y), perportion_label, fill=TEXT_COLOR, font=FONT_HEADER_B)
    return y + 40

def draw_rows_block(draw, rows, x_left, x_col2, x_col3, y, img_w, tabular=False):
    if tabular:
        draw_vline(draw, x_col2, y, img_w - BORDER_W - 120, TEXT_COLOR, GRID_W)
        draw_vline(draw, x_col3, y, img_w - BORDER_W - 120, TEXT_COLOR, GRID_W)
    for label, val100, valpp, indent, bold, is_micro in rows:
        if label == "---sep---":
            draw_hline(draw, BORDER_W, img_w - BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
            continue
        draw_hline(draw, BORDER_W, img_w - BORDER_W, y, TEXT_COLOR, GRID_W)
        if is_micro:
            font_lbl = FONT_MICRO_B if bold else FONT_MICRO
            font_val = FONT_MICRO_B if bold else FONT_MICRO
        else:
            font_lbl = FONT_LABEL_B if bold else FONT_LABEL
            font_val = FONT_VAL_B if bold else FONT_VAL
        x_label = BORDER_W + CELL_PAD_X + (indent * INDENT_STEP)
        y_text = y + (ROW_H//2) - 14
        draw.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100, _ = text_size(draw, val100, font_val)
        wvpp, _  = text_size(draw, valpp,  font_val)
        draw.text((x_col2 - CELL_PAD_X - wv100, y_text), val100, fill=TEXT_COLOR, font=font_val)
        draw.text((x_col3 - CELL_PAD_X - wvpp,  y_text), valpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H
    draw_hline(draw, BORDER_W, img_w - BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    return y

def draw_footer(draw, img_w, y):
    draw.text((BORDER_W + CELL_PAD_X, y + 12), footnote_ns, fill=TEXT_COLOR, font=FONT_FOOT)

def draw_table_fig1_vertical():
    rows = build_common_rows()
    W = 1400
    header_h = 150
    cal_block_h = ROW_H + 32
    colhdr_h = 44
    footer_h = 110
    data_rows = [r for r in rows if r[0] != "---sep---"]
    sep_count = len([r for r in rows if r[0] == "---sep---"])
    H = BORDER_W*2 + header_h + cal_block_h + colhdr_h + len(data_rows)*ROW_H + sep_count*GRID_W_THICK + footer_h + 40
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)
    y = BORDER_W + 6
    y = header_block(draw, W, y)
    y = draw_calories_row(draw, BORDER_W, col_x[2], col_x[3], y, W)
    y = draw_column_headers(draw, BORDER_W, col_x[2], col_x[3], y)
    draw_hline(draw, BORDER_W, W - BORDER_W, y, TEXT_COLOR, GRID_W)
    y += 6
    draw_vline(draw, col_x[2], y, H - BORDER_W - 120, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], y, H - BORDER_W - 120, TEXT_COLOR, GRID_W)
    y = draw_rows_block(draw, rows, BORDER_W, col_x[2], col_x[3], y, W, tabular=False)
    y += 12
    draw_footer(draw, W, y)
    return img

def draw_table_fig3_simple():
    base_rows = [
        ("Grasa total",        f"{fmt_g(fat_total_100,1)} g",  f"{fmt_g(fat_total_pp,1)} g",  0, False, False),
        ("  Grasa saturada",   f"{fmt_g(sat_fat_100,1)} g",    f"{fmt_g(sat_fat_pp,1)} g",    1, True,  False),
        ("  Grasas trans",     f"{fmt_mg(trans_fat_100_mg)} mg", f"{fmt_mg(trans_fat_pp_mg)} mg", 1, True, False),
        ("Carbohidratos",      f"{fmt_g(carb_100,1)} g",       f"{fmt_g(carb_pp,1)} g",       0, False, False),
        ("  Azúcares añadidos",f"{fmt_g(sugars_added_100,1)} g", f"{fmt_g(sugars_added_pp,1)} g", 1, True,  False),
        ("Proteína",           f"{fmt_g(protein_100,1)} g",    f"{fmt_g(protein_pp,1)} g",    0, False, False),
        ("Sodio",              f"{fmt_mg(sodium_100_mg)} mg",  f"{fmt_mg(sodium_pp_mg)} mg",  0, True,  False),
    ]
    rows = base_rows
    W = 1200
    header_h = 150
    cal_block_h = ROW_H + 32
    colhdr_h = 44
    footer_h = 110
    H = BORDER_W*2 + header_h + cal_block_h + colhdr_h + len(rows)*ROW_H + footer_h + 40
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)
    y = BORDER_W + 6
    y = header_block(draw, W, y)
    y = draw_calories_row(draw, BORDER_W, col_x[2], col_x[3], y, W)
    y = draw_column_headers(draw, BORDER_W, col_x[2], col_x[3], y)
    draw_hline(draw, BORDER_W, W - BORDER_W, y, TEXT_COLOR, GRID_W)
    y += 6
    draw_vline(draw, col_x[2], y, H - BORDER_W - 120, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], y, H - BORDER_W - 120, TEXT_COLOR, GRID_W)
    y = draw_rows_block(draw, rows, BORDER_W, col_x[2], col_x[3], y, W, tabular=False)
    y += 12
    draw_footer(draw, W, y)
    return img

def draw_table_fig4_tabular():
    rows = build_common_rows()
    W = 1400
    header_h = 150
    cal_block_h = ROW_H + 32
    colhdr_h = 44
    footer_h = 110
    data_rows = [r for r in rows if r[0] != "---sep---"]
    sep_count = len([r for r in rows if r[0] == "---sep---"])
    H = BORDER_W*2 + header_h + cal_block_h + colhdr_h + len(data_rows)*ROW_H + sep_count*GRID_W_THICK + footer_h + 40
    col_x = [BORDER_W, BORDER_W + int(W*0.50), BORDER_W + int(W*0.74), W - BORDER_W]
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)
    y = BORDER_W + 6
    y = header_block(draw, W, y)
    y = draw_calories_row(draw, BORDER_W, col_x[2], col_x[3], y, W)
    y = draw_column_headers(draw, BORDER_W, col_x[2], col_x[3], y)
    draw_hline(draw, BORDER_W, W - BORDER_W, y, TEXT_COLOR, GRID_W)
    y += 6
    draw_vline(draw, col_x[1], y, H - BORDER_W - 120, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[2], y, H - BORDER_W - 120, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], y, H - BORDER_W - 120, TEXT_COLOR, GRID_W)
    y = draw_rows_block(draw, rows, BORDER_W, col_x[2], col_x[3], y, W, tabular=True)
    y += 12
    draw_footer(draw, W, y)
    return img

def draw_table_fig5_linear():
    items = []
    kcal_txt_pp = f"{fmt_kcal(kcal_pp)} kcal" + (f" ({kj_pp} kJ)" if include_kj else "")
    kcal_txt_100 = f"{fmt_kcal(kcal_100)} kcal" + (f" ({kj_100} kJ)" if include_kj else "")
    def pair(name, vpp_txt, v100_txt):
        items.append(f"{name}: {vpp_txt} (por 100: {v100_txt})")
    pair("Calorías", kcal_txt_pp, kcal_txt_100)
    pair("Grasa total", f"{fmt_g(fat_total_pp,1)} g", f"{fmt_g(fat_total_100,1)} g")
    pair("Grasa saturada", f"{fmt_g(sat_fat_pp,1)} g", f"{fmt_g(sat_fat_100,1)} g")
    pair("Grasas trans", f"{fmt_mg(trans_fat_pp_mg)} mg", f"{fmt_mg(trans_fat_100_mg)} mg")
    pair("Carbohidratos", f"{fmt_g(carb_pp,1)} g", f"{fmt_g(carb_100,1)} g")
    pair("Azúcares totales", f"{fmt_g(sugars_total_pp,1)} g", f"{fmt_g(sugars_total_100,1)} g")
    pair("Azúcares añadidos", f"{fmt_g(sugars_added_pp,1)} g", f"{fmt_g(sugars_added_100,1)} g")
    pair("Fibra dietaria", f"{fmt_g(fiber_pp,1)} g", f"{fmt_g(fiber_100,1)} g")
    pair("Proteína", f"{fmt_g(protein_pp,1)} g", f"{fmt_g(protein_100,1)} g")
    pair("Sodio", f"{fmt_mg(sodium_pp_mg)} mg", f"{fmt_mg(sodium_100_mg)} mg")
    for vm in selected_vm:
        unit = "mg"
        if "µg" in vm: unit = "µg"
        vpp  = vm_pp.get(vm, 0.0)
        v100 = vm_values_100.get(vm, 0.0)
        name = "Vitamina A (µg ER)" if vm.startswith("Vitamina A") else vm
        vpp_txt  = f"{fmt_mg(vpp)} mg" if unit == "mg" else f"{fmt_g(vpp,1)} µg"
        v100_txt = f"{fmt_mg(v100)} mg" if unit == "mg" else f"{fmt_g(v100,1)} µg"
        pair(name, vpp_txt, v100_txt)
    W = 1600
    H = 560 if len(items) <= 8 else 720 if len(items) <= 14 else 900
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)
    y = BORDER_W + 6
    title = "Información Nutricional"
    tw, th = text_size(draw, title, FONT_TITLE)
    draw.text(((W - tw)//2, y), title, fill=TEXT_COLOR, font=FONT_TITLE)
    y += th + 8
    portion_line = f"Tamaño de porción: {int(round(household_qty))} {household_measure} ({int(round(portion_weight))} {('mL' if is_liquid else 'g')})"
    servings_line = f"Número de porciones por envase: {st.session_state.get('servings_per_pack_print', 1)}"
    draw.text((BORDER_W + CELL_PAD_X, y), portion_line, fill=TEXT_COLOR, font=FONT_HEADER)
    y += 38
    draw.text((BORDER_W + CELL_PAD_X, y), servings_line, fill=TEXT_COLOR, font=FONT_HEADER)
    y += 40
    draw_hline(draw, BORDER_W, W - BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 10
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
    if line: lines.append(line)
    for ln in lines:
        draw.text((left_x, y), ln, fill=TEXT_COLOR, font=FONT_LABEL)
        y += 48
    draw_hline(draw, BORDER_W, W - BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 16
    draw.text((BORDER_W + CELL_PAD_X, y + 8), footnote_ns, fill=TEXT_COLOR, font=FONT_FOOT)
    return img

# ============================================================
# PREVISUALIZACIÓN Y EXPORTACIÓN
# ============================================================
servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="1"))
st.session_state['servings_per_pack_print'] = int(round(servings_per_pack))

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

if export_btn:
    buf = BytesIO()
    img_prev.save(buf, format="PNG")
    buf.seek(0)
    fname = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    st.download_button("Descargar imagen PNG", data=buf, file_name=fname, mime="image/png")
