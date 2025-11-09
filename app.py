# ============================================================
# app_810_2492_full.py
# Generador de Tabla Nutricional (Colombia) -> PNG (solo PNG)
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Fig.1 (Vertical estándar), Fig.3 (Simplificado), Fig.5 (Lineal/Tabular)
# Entradas por 100 g / 100 mL. Cálculo por porción y kcal.
# ============================================================

from io import BytesIO
from datetime import datetime
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ------------------------------------------------------------
# Helpers de líneas
# ------------------------------------------------------------
def draw_hline(draw, x0, x1, y, color, width):
    draw.line((x0, y, x1, y), fill=color, width=width)

def draw_vline(draw, x, y0, y1, color, width):
    draw.line((x, y0, x, y1), fill=color, width=width)

# ------------------------------------------------------------
# Fuentes
# ------------------------------------------------------------
def get_font(size, bold=False):
    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.load_default()

# ------------------------------------------------------------
# CONFIG Streamlit
# ------------------------------------------------------------
st.set_page_config(page_title="Generador de Tabla Nutricional (Colombia)", layout="wide")
st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

# ------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------
def as_num(x):
    try:
        if x is None or str(x).strip() == "":
            return 0.0
        return float(x)
    except Exception:
        return 0.0

def kcal_from_macros(fat_g, carb_g, protein_g, organic_acids_g=0.0, alcohol_g=0.0):
    return float(9*(fat_g or 0) + 4*(carb_g or 0) + 4*(protein_g or 0) + 7*(alcohol_g or 0) + 3*(organic_acids_g or 0))

def portion_from_per100(value_per100, portion_size):
    if portion_size and portion_size > 0:
        return (value_per100 * portion_size) / 100.0
    return 0.0

def round_kcal(v):
    if v < 5: return 0
    return int(round(v))

def round_g(v):
    av = abs(v)
    if av >= 100: return float(int(round(v, 0)))
    return float(round(v, 1))

def round_mg(v_mg):
    if v_mg < 5: return 0
    return int(round(v_mg))

def fmt_one_decimal(v):
    try: return f"{float(v):.1f}"
    except Exception: return "0.0"

def fmt_carbs_rule(v):
    try: v = float(v)
    except Exception: return "0"
    av = abs(v)
    if av < 10:
        return f"{v:.1f}".rstrip('0').rstrip('.') if v % 1 != 0 else f"{v:.1f}"
    if av < 100: return f"{int(round(v))}"
    return f"{int(round(v))}"

def fmt_int(v):
    try: return f"{int(round(float(v)))}"
    except Exception: return "0"

def fmt_default_g(x):
    try: x = float(x)
    except Exception: return "0"
    if float(x).is_integer(): return f"{int(x)}"
    return f"{x:.1f}".rstrip('0').rstrip('.')

def fmt_micro_value(name, unit, v):
    """
    Formateo de micronutrientes según 810:
    <1 → 2 decimales; 1-10 → 1 decimal; >=100 → entero.
    Vitamina A en µg ER, Vitamina D en µg.
    """
    try:
        v = float(v)
    except Exception:
        return f"0 {unit}"
    if name == "Vitamina A":
        unit = "µg ER"
    elif name == "Vitamina D":
        unit = "µg"
    if abs(v) < 1:   return f"{v:.2f} {unit}"
    if abs(v) < 10:  return f"{v:.1f} {unit}"
    if abs(v) >= 100: return f"{int(round(v))} {unit}"
    return f"{int(round(v))} {unit}"

# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------
st.sidebar.header("Configuración")

format_choice = st.sidebar.selectbox(
    "Formato a exportar",
    ["Fig. 1 — Vertical estándar", "Fig. 3 — Simplificado", "Fig. 5 — Lineal"],
    index=0
)

physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])
portion_unit = "g" if "Sólido" in physical_state else "mL"

st.sidebar.subheader("Porción")
household_name = st.sidebar.text_input("Medida casera (p. ej. 1 unidad, 1 taza)", value="1 unidad")
household_mass = as_num(st.sidebar.text_input(f"Equivalencia en {portion_unit} (número)", value="40"))
servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="2"))

st.sidebar.subheader("Micronutrientes a declarar")
vm_options = ["Vitamina A","Vitamina D","Hierro","Calcio","Zinc"]
selected_vm = st.sidebar.multiselect("Selecciona los que declararás", vm_options, default=["Vitamina A","Vitamina D","Hierro","Calcio","Zinc"])

st.sidebar.subheader("Polialcoholes")
include_poly = st.sidebar.checkbox("Incluir polialcoholes", value=False)
poly_100 = as_num(st.sidebar.text_input("Polialcoholes (g/100)", value="0")) if include_poly else 0.0

st.sidebar.subheader("Texto al pie")
footnote_tail = st.sidebar.text_input("Completa: No es fuente significativa de ...", value="")

# ------------------------------------------------------------
# ENTRADAS PRINCIPALES (por 100 g/mL)
# ------------------------------------------------------------
st.header("Ingreso de datos por 100 g / 100 mL")

c1, c2, c3 = st.columns([0.33, 0.33, 0.34])
with c1:
    st.subheader("Macronutrientes (por 100)")
    fat_total_100    = as_num(st.text_input("Grasa total (g/100)", value="13"))
    sat_fat_100      = as_num(st.text_input("Grasa saturada (g/100)", value="6"))
    trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg/100)", value="820"))
with c2:
    carb_100       = as_num(st.text_input("Carbohidratos totales (g/100)", value="31"))
    sug_total_100  = as_num(st.text_input("Azúcares totales (g/100)", value="5"))
    sug_added_100  = as_num(st.text_input("Azúcares añadidos (g/100)", value="2"))
with c3:
    fiber_100      = as_num(st.text_input("Fibra dietaria (g/100)", value="0.8"))
    protein_100    = as_num(st.text_input("Proteína (g/100)", value="5"))
    sodium_100_mg  = as_num(st.text_input("Sodio (mg/100)", value="560"))

st.markdown("---")
st.subheader("Valores de micronutrientes seleccionados (por 100)")
vm_values = {}
vm_col1, vm_col2 = st.columns([0.5, 0.5])
def vm_unit(name):
    return "µg ER" if name == "Vitamina A" else ("µg" if name == "Vitamina D" else "mg")
with vm_col1:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 0:
            vm_values[(vm, vm_unit(vm))] = as_num(st.text_input(f"{vm} ({vm_unit(vm)}/100)", value="0"))
with vm_col2:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 1:
            vm_values[(vm, vm_unit(vm))] = as_num(st.text_input(f"{vm} ({vm_unit(vm)}/100)", value="0"))

# ------------------------------------------------------------
# CÁLCULOS
# ------------------------------------------------------------
portion_size = household_mass
is_liquid = "Líquido" in physical_state

# Por porción (sin redondear)
fat_total_pp    = portion_from_per100(fat_total_100, portion_size)
sat_fat_pp      = portion_from_per100(sat_fat_100, portion_size)
trans_fat_pp_mg = portion_from_per100(trans_fat_100_mg, portion_size)
carb_pp         = portion_from_per100(carb_100, portion_size)
sug_total_pp    = portion_from_per100(sug_total_100, portion_size)
sug_added_pp    = portion_from_per100(sug_added_100, portion_size)
fiber_pp        = portion_from_per100(fiber_100, portion_size)
protein_pp      = portion_from_per100(protein_100, portion_size)
sodium_pp_mg    = portion_from_per100(sodium_100_mg, portion_size)
poly_pp         = portion_from_per100(poly_100, portion_size) if include_poly else 0.0

# Energía (antes de redondear)
kcal_100_raw = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp_raw  = kcal_from_macros(fat_total_pp,  carb_pp,  protein_pp)
kcal_100 = round_kcal(kcal_100_raw)
kcal_pp  = round_kcal(kcal_pp_raw)

# Redondeos y no significativas
def nonsig_zero_g(name, v):
    if name == "Grasa total" and v < 0.5: return 0.0
    if name in ("Grasa saturada","Grasas trans") and v < 0.1: return 0.0
    return v

def nonsig_zero_mg(name, vmg):
    if name == "Sodio" and vmg < 5: return 0
    return vmg

# Por 100
fat_total_100_r     = round_g(nonsig_zero_g("Grasa total",       fat_total_100))
sat_fat_100_r       = round_g(nonsig_zero_g("Grasa saturada",    sat_fat_100))
carb_100_r          = round_g(carb_100)
sug_total_100_r     = round_g(sug_total_100)
sug_added_100_r     = round_g(sug_added_100)
fiber_100_r         = round_g(fiber_100)
protein_100_r       = round_g(protein_100)
sodium_100_mg_r     = round_mg(sodium_100_mg)
poly_100_r          = round_g(poly_100) if include_poly else 0.0
_trans_g_100        = (trans_fat_100_mg or 0.0)/1000.0
_trans_g_100        = nonsig_zero_g("Grasas trans", _trans_g_100)
trans_fat_100_mg_r  = round_mg(_trans_g_100*1000.0)

# Por porción
fat_total_pp_r     = round_g(nonsig_zero_g("Grasa total",       fat_total_pp))
sat_fat_pp_r       = round_g(nonsig_zero_g("Grasa saturada",    sat_fat_pp))
carb_pp_r          = round_g(carb_pp)
sug_total_pp_r     = round_g(sug_total_pp)
sug_added_pp_r     = round_g(sug_added_pp)
fiber_pp_r         = round_g(fiber_pp)
protein_pp_r       = round_g(protein_pp)
sodium_pp_mg_r     = round_mg(sodium_pp_mg)
poly_pp_r          = round_g(poly_pp) if include_poly else 0.0
_trans_g_pp        = (trans_fat_pp_mg or 0.0)/1000.0
_trans_g_pp        = nonsig_zero_g("Grasas trans", _trans_g_pp)
trans_fat_pp_mg_r  = round_mg(_trans_g_pp*1000.0)

# Micronutrientes por porción
vm_pp = {}
vm_values_rounded = {}
for (name, unit), v100 in vm_values.items():
    vpp = portion_from_per100(v100, portion_size)
    vm_values_rounded[(name, unit)] = v100
    vm_pp[(name, unit)] = vpp

# ------------------------------------------------------------
# ESTILO
# ------------------------------------------------------------
BORDER_W       = 6
GRID_W         = 3
GRID_W_THICK   = 9
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

def column_labels():
    return ("Por 100 g" if not is_liquid else "Por 100 mL", "Por porción")

# Medición
def measure_text(draw, text, font):
    bbox = draw.textbbox((0,0), text, font=font)
    return bbox[2]-bbox[0], bbox[3]-bbox[1]

def compute_cols_vertical(draw, labels, v100_list, vpp_list, W):
    name_w_max = 0
    for t in labels:
        w,_ = measure_text(draw, t, FONT_LABEL)
        if w > name_w_max: name_w_max = w

    v100_w_max = 0
    for t in v100_list:
        w,_ = measure_text(draw, t, FONT_LABEL)
        if w > v100_w_max: v100_w_max = w

    vpp_w_max = 0
    for t in vpp_list:
        w,_ = measure_text(draw, t, FONT_LABEL)
        if w > vpp_w_max: vpp_w_max = w

    col100_label, colpp_label = column_labels()
    col100_w, _ = measure_text(draw, col100_label, FONT_SMALL_B)
    colpp_w, _ = measure_text(draw, colpp_label, FONT_SMALL_B)

    azucares_added_width, _ = measure_text(draw, "  Azúcares añadidos", FONT_LABEL)
    final_name_width = max(name_w_max, azucares_added_width) + 15

    name_to_values_gap = 35
    values_gap = 20
    right_margin = 15

    x0 = BORDER_W + CELL_PAD_X
    x1 = x0 + final_name_width + name_to_values_gap
    col100_width = max(v100_w_max, col100_w) + 15
    x2 = x1 + col100_width + values_gap
    colpp_width = max(vpp_w_max, colpp_w) + 4
    x3 = x2 + colpp_width + right_margin

    total_width_needed = x3
    if total_width_needed > W:
        W = total_width_needed + BORDER_W * 2

    return [x0, x1, x2, x3], W

# ------------------------------------------------------------
# FILAS
# ------------------------------------------------------------
def common_rows():
    rows = [
        ("Grasa total",            f"{fmt_one_decimal(fat_total_100_r)} g",     f"{fmt_one_decimal(fat_total_pp_r)} g",       0, False, False),
        ("  Grasa saturada",       f"{fmt_one_decimal(sat_fat_100_r)} g",       f"{fmt_one_decimal(sat_fat_pp_r)} g",         1, True,  False),
        ("  Grasas trans",         f"{fmt_int(trans_fat_100_mg_r)} mg",         f"{fmt_int(trans_fat_pp_mg_r)} mg",           1, True,  False),
        ("Carbohidratos totales",  f"{fmt_carbs_rule(carb_100_r)} g",           f"{fmt_carbs_rule(carb_pp_r)} g",             0, False, False),
        ("  Fibra dietaria",       f"{fmt_one_decimal(fiber_100_r)} g",         f"{fmt_one_decimal(fiber_pp_r)} g",           1, False, False),
        ("Azúcares totales",       f"{fmt_one_decimal(sug_total_100_r)} g",     f"{fmt_one_decimal(sug_total_pp_r)} g",       0, False, False),
        ("  Azúcares añadidos",    f"{fmt_one_decimal(sug_added_100_r)} g",     f"{fmt_one_decimal(sug_added_pp_r)} g",       1, True,  False),
        ("Proteína",               f"{fmt_one_decimal(protein_100_r)} g",       f"{fmt_one_decimal(protein_pp_r)} g",         0, False, False),
        ("Sodio",                  f"{fmt_int(sodium_100_mg_r)} mg",            f"{fmt_int(sodium_pp_mg_r)} mg",              0, True,  False),
    ]
    if include_poly:
        # Insertarlo después de Fibra y antes de Azúcares totales
        try:
            idx_azuc_tot = next(i for i, r in enumerate(rows) if r[0].strip() == "Azúcares totales")
            rows.insert(idx_azuc_tot, ("  Polialcoholes", f"{fmt_one_decimal(poly_100_r)} g", f"{fmt_one_decimal(poly_pp_r)} g", 1, False, False))
        except StopIteration:
            pass
    return rows

def micro_rows():
    # Orden oficial: Vitamina A, Vitamina D, Hierro, Calcio, Zinc
    order = ["Vitamina A","Vitamina D","Hierro","Calcio","Zinc"]
    selected = [(n,u) for (n,u) in vm_values_rounded.keys()]
    ordered = []
    for name in order:
        for (n,u) in selected:
            if n == name:
                ordered.append((n,u))

    rows = []
    for (name, unit) in ordered:
        v100 = vm_values_rounded[(name, unit)]
        vpp  = vm_pp[(name, unit)]
        v100_txt = fmt_micro_value(name, unit, v100)
        vpp_txt  = fmt_micro_value(name, unit, vpp)
        rows.append((name, v100_txt, vpp_txt, 0, False, True))
    return rows

# ------------------------------------------------------------
# BLOQUE CALORÍAS (2 filas combinadas)
# ------------------------------------------------------------
def draw_calories_combined_row(d, W, y, col_x, kcal_100_txt, kcal_pp_txt):
    row_h = ROW_H * 2
    y_text_title = y + (ROW_H // 2) - 14
    d.text((BORDER_W + CELL_PAD_X, y_text_title), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)

    c100, cpp = column_labels()
    w_c100, _ = measure_text(d, c100, FONT_SMALL_B)
    w_cpp, _ = measure_text(d, cpp, FONT_SMALL_B)
    d.text((col_x[2] - 15 - w_c100, y_text_title), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - 15 - w_cpp,  y_text_title), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    draw_hline(d, col_x[1], W-BORDER_W, y + ROW_H, TEXT_COLOR, GRID_W)

    y_text_values = y + ROW_H + (ROW_H // 2) - 14
    w100, _ = measure_text(d, kcal_100_txt, FONT_LABEL_B)
    wpp, _  = measure_text(d, kcal_pp_txt,  FONT_LABEL_B)
    d.text((col_x[2] - 15 - w100, y_text_values), kcal_100_txt, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - 15 - wpp,  y_text_values), kcal_pp_txt,  fill=TEXT_COLOR, font=FONT_LABEL_B)
    return y + row_h

# ------------------------------------------------------------
# FIGURA 1 — VERTICAL ESTÁNDAR
# ------------------------------------------------------------
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 580
    header_h = 130
    gap_after_title = 5
    foot_h = 90 if footnote_tail.strip() else 20

    body_rows_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)

    H_temp = 100
    img_temp = Image.new("RGB", (W, H_temp), BG_WHITE)
    d_temp = ImageDraw.Draw(img_temp)

    labels_all = [r[0] for r in rows_nutri] + ([r[0] for r in rows_micro] if show_micro else [])
    v100_all   = [r[1] for r in rows_nutri] + ([r[1] for r in rows_micro] if show_micro else [])
    vpp_all    = [r[2] for r in rows_nutri] + ([r[2] for r in rows_micro] if show_micro else [])
    col_x, W = compute_cols_vertical(d_temp, labels_all, v100_all, vpp_all, W)

    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         (ROW_H * 2) + GRID_W_THICK + body_rows_h + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # Marco y título
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)
    title = "Información Nutricional"
    tw, th = measure_text(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 15), title, fill=TEXT_COLOR, font=FONT_TITLE)

    # porciones
    y0 = BORDER_W + 15 + th + 12
    d.text((BORDER_W + CELL_PAD_X, y0),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, y0 + 35),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y_header_bottom = BORDER_W + header_h
    draw_hline(d, BORDER_W, W-BORDER_W, y_header_bottom, TEXT_COLOR, GRID_W_THICK)

    kcal_100_txt = f"{fmt_int(kcal_100)}"
    kcal_pp_txt  = f"{fmt_int(kcal_pp)}"
    y = draw_calories_combined_row(d, W, y_header_bottom+1, col_x, kcal_100_txt, kcal_pp_txt)

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Filas macronutrientes
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text  = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = measure_text(d, v100, font_val)
        wvpp,_  = measure_text(d, vpp,  font_val)
        d.text((col_x[2]-15-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-15-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    if show_micro:
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    if show_micro:
        for label, v100, vpp, indent, _, _ in rows_micro:
            y += 1
            draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
            x_label = BORDER_W + CELL_PAD_X + indent*28
            y_text  = y + (ROW_H_MICRO//2) - 12
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100,_ = measure_text(d, v100, FONT_MICRO)
            wvpp,_  = measure_text(d, vpp,  FONT_MICRO)
            d.text((col_x[2]-15-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-15-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Líneas verticales hasta la segunda gruesa (fin de datos)
    draw_vline(d, col_x[1], y_header_bottom, y, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], y_header_bottom, y, TEXT_COLOR, GRID_W)

    # Pie multilínea
    if footnote_tail.strip():
        base_text = f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}"
        max_line_width = W - 2*BORDER_W - 2*CELL_PAD_X
        words = base_text.split(' ')
        lines, current_line = [], []
        for word in words:
            test_line = ' '.join(current_line + [word])
            test_width, _ = measure_text(d, test_line, FONT_SMALL)
            if test_width <= max_line_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))

        current_y = y + 15
        for line in lines:
            d.text((BORDER_W + CELL_PAD_X, current_y), line, fill=TEXT_COLOR, font=FONT_SMALL)
            current_y += FONT_SMALL.size + 6

    return img

# ------------------------------------------------------------
# FIGURA 3 — SIMPLIFICADO (sin micronutrientes)
# ------------------------------------------------------------
def draw_fig3():
    rows_nutri = common_rows()
    rows_micro = []  # sin micronutrientes
    show_micro = False

    W = 580
    header_h = 130
    gap_after_title = 5
    foot_h = 90 if footnote_tail.strip() else 20
    body_rows_h = len(rows_nutri)*ROW_H

    H_temp = 100
    img_temp = Image.new("RGB", (W, H_temp), BG_WHITE)
    d_temp = ImageDraw.Draw(img_temp)

    labels_all = [r[0] for r in rows_nutri]
    v100_all   = [r[1] for r in rows_nutri]
    vpp_all    = [r[2] for r in rows_nutri]
    col_x, W = compute_cols_vertical(d_temp, labels_all, v100_all, vpp_all, W)

    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         (ROW_H * 2) + GRID_W_THICK + body_rows_h + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)
    title = "Información Nutricional"
    tw, th = measure_text(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 15), title, fill=TEXT_COLOR, font=FONT_TITLE)

    y0 = BORDER_W + 15 + th + 12
    d.text((BORDER_W + CELL_PAD_X, y0),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, y0 + 35),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y_header_bottom = BORDER_W + header_h
    draw_hline(d, BORDER_W, W-BORDER_W, y_header_bottom, TEXT_COLOR, GRID_W_THICK)

    kcal_100_txt = f"{fmt_int(kcal_100)}"
    kcal_pp_txt  = f"{fmt_int(kcal_pp)}"
    y = draw_calories_combined_row(d, W, y_header_bottom+1, col_x, kcal_100_txt, kcal_pp_txt)

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Filas macronutrientes
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text  = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = measure_text(d, v100, font_val)
        wvpp,_  = measure_text(d, vpp,  font_val)
        d.text((col_x[2]-15-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-15-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Líneas verticales hasta la segunda gruesa (fin de datos)
    draw_vline(d, col_x[1], y_header_bottom, y, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], y_header_bottom, y, TEXT_COLOR, GRID_W)

    # Pie multilínea
    if footnote_tail.strip():
        base_text = f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}"
        max_line_width = W - 2*BORDER_W - 2*CELL_PAD_X
        words = base_text.split(' ')
        lines, current_line = [], []
        for word in words:
            test_line = ' '.join(current_line + [word])
            test_width, _ = measure_text(d, test_line, FONT_SMALL)
            if test_width <= max_line_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))

        current_y = y + 15
        for line in lines:
            d.text((BORDER_W + CELL_PAD_X, current_y), line, fill=TEXT_COLOR, font=FONT_SMALL)
            current_y += FONT_SMALL.size + 6

    return img

# ------------------------------------------------------------
# FIGURA 5 — LINEAL / TABULAR
# ------------------------------------------------------------
def draw_fig5():
    """
    Formato lineal/tabular (diseño ancho).
    Fondo blanco, dos bloques corridos (100 g/mL y por porción), y pie multilínea.
    """
    W, H = 1700, 460
    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    x = BORDER_W + CELL_PAD_X
    y = BORDER_W + 20
    line_space = 42
    max_line_width = W - 2 * BORDER_W - 2 * CELL_PAD_X

    # Encabezado (100 g o 100 mL)
    header_100 = f"Información nutricional ({'100 mL' if is_liquid else '100 g'}): "
    d.text((x, y), header_100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    y += line_space

    # Texto (por 100)
    parts_100 = [
        f"Calorías {fmt_int(kcal_100)}",
        f"Grasa total {fmt_one_decimal(fat_total_100_r)} g",
        f"Grasa saturada {fmt_one_decimal(sat_fat_100_r)} g",
        f"Grasas trans {fmt_int(trans_fat_100_mg_r)} mg",
        f"Sodio {fmt_int(sodium_100_mg_r)} mg",
        f"Carbohidratos totales {fmt_carbs_rule(carb_100_r)} g",
        f"Fibra dietaria {fmt_one_decimal(fiber_100_r)} g"
    ]
    if include_poly:
        parts_100.append(f"Polialcoholes {fmt_one_decimal(poly_100_r)} g")
    parts_100 += [
        f"Azúcares totales {fmt_one_decimal(sug_total_100_r)} g",
        f"Azúcares añadidos {fmt_one_decimal(sug_added_100_r)} g",
        f"Proteína {fmt_one_decimal(protein_100_r)} g",
        f"Vitamina A {fmt_micro_value('Vitamina A','µg ER',vm_values_rounded.get(('Vitamina A','µg ER'),0))}",
        f"Vitamina D {fmt_micro_value('Vitamina D','µg',vm_values_rounded.get(('Vitamina D','µg'),0))}",
        f"Hierro {fmt_micro_value('Hierro','mg',vm_values_rounded.get(('Hierro','mg'),0))}",
        f"Calcio {fmt_micro_value('Calcio','mg',vm_values_rounded.get(('Calcio','mg'),0))}",
        f"Zinc {fmt_micro_value('Zinc','mg',vm_values_rounded.get(('Zinc','mg'),0))}."
    ]
    text_100 = ", ".join(parts_100)

    # Salto automático por ancho
    words = text_100.split(" ")
    lines, current = [], []
    for word in words:
        test_line = " ".join(current + [word])
        w, _ = measure_text(d, test_line, FONT_SMALL)
        if w <= max_line_width:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    for line in lines:
        d.text((x, y), line, fill=TEXT_COLOR, font=FONT_SMALL)
        y += FONT_SMALL.size + 4

    # Encabezado por porción
    y += line_space
    header_pp = "Información nutricional (porción): "
    d.text((x, y), header_pp, fill=TEXT_COLOR, font=FONT_SMALL_B)
    y += line_space

    # Texto (por porción)
    parts_pp = [
        f"Tamaño de porción: {household_name} ({int(round(portion_size))} {portion_unit})",
        f"Número de porciones por envase: {int(round(servings_per_pack))}",
        f"Calorías {fmt_int(kcal_pp)}",
        f"Grasa total {fmt_one_decimal(fat_total_pp_r)} g",
        f"Grasa saturada {fmt_one_decimal(sat_fat_pp_r)} g",
        f"Grasas trans {fmt_int(trans_fat_pp_mg_r)} mg",
        f"Sodio {fmt_int(sodium_pp_mg_r)} mg",
        f"Carbohidratos totales {fmt_carbs_rule(carb_pp_r)} g",
        f"Fibra dietaria {fmt_one_decimal(fiber_pp_r)} g"
    ]
    if include_poly:
        parts_pp.append(f"Polialcoholes {fmt_one_decimal(poly_pp_r)} g")
    parts_pp += [
        f"Azúcares totales {fmt_one_decimal(sug_total_pp_r)} g",
        f"Azúcares añadidos {fmt_one_decimal(sug_added_pp_r)} g",
        f"Proteína {fmt_one_decimal(protein_pp_r)} g",
        f"Vitamina A {fmt_micro_value('Vitamina A','µg ER',vm_pp.get(('Vitamina A','µg ER'),0))}",
        f"Vitamina D {fmt_micro_value('Vitamina D','µg',vm_pp.get(('Vitamina D','µg'),0))}",
        f"Hierro {fmt_micro_value('Hierro','mg',vm_pp.get(('Hierro','mg'),0))}",
        f"Calcio {fmt_micro_value('Calcio','mg',vm_pp.get(('Calcio','mg'),0))}",
        f"Zinc {fmt_micro_value('Zinc','mg',vm_pp.get(('Zinc','mg'),0))}."
    ]
    text_pp = ", ".join(parts_pp)

    # Salto automático por ancho (porción)
    words = text_pp.split(" ")
    lines, current = [], []
    for word in words:
        test_line = " ".join(current + [word])
        w, _ = measure_text(d, test_line, FONT_SMALL)
        if w <= max_line_width:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    for line in lines:
        d.text((x, y), line, fill=TEXT_COLOR, font=FONT_SMALL)
        y += FONT_SMALL.size + 4

    # Pie multilínea
    if footnote_tail.strip():
        base_text = f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}"
        words = base_text.split(" ")
        lines, current_line = [], []
        for word in words:
            test_line = " ".join(current_line + [word])
            w, _ = measure_text(d, test_line, FONT_SMALL)
            if w <= max_line_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
        # margen inferior
        y += line_space
        for line in lines:
            d.text((x, y), line, fill=TEXT_COLOR, font=FONT_SMALL)
            y += FONT_SMALL.size + 4

    d.rectangle([0, 0, W-1, H-1], outline=TEXT_COLOR, width=BORDER_W)
    return img

# ------------------------------------------------------------
# PREVISUALIZACIÓN + EXPORTACIÓN
# ------------------------------------------------------------
st.header("Previsualización")
left, right = st.columns([0.72, 0.28])
with right:
    export_btn = st.button("Generar PNG", use_container_width=True)

with left:
    if format_choice.startswith("Fig. 1"):
        img_prev = draw_fig1()
    elif format_choice.startswith("Fig. 3"):
        img_prev = draw_fig3()
    else:
        img_prev = draw_fig5()
    st.image(img_prev, caption="Vista previa (PNG)", use_column_width=True)

if export_btn:
    buf = BytesIO()
    img_prev.save(buf, format="PNG")
    buf.seek(0)
    fname = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    st.download_button("Descargar PNG", data=buf, file_name=fname, mime="image/png")
