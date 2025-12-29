# ============================================================
# app_810_2492_full_negrilla.py
# Generador de Tabla Nutricional (Colombia) -> PNG (solo PNG)
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Fig.1 (Vertical estándar), Fig.3 (Simplificado), Fig.5 (Lineal/Tabular)
# Entradas por 100 g / 100 mL. Cálculo por porción y kcal.
# - Polialcoholes opcional (entre Fibra y Azúcares totales)
# - Orden de micronutrientes: Vitamina A, Vitamina D, Hierro, Calcio, Zinc
# - Pie "No es fuente significativa de ..." con salto de línea automático
# - Formato lineal con salto de línea automático y negrillas específicas
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

def fmt_int(v):
    try: return f"{int(round(float(v)))}"
    except Exception: return "0"

def fmt_default_g(x):
    try: x = float(x)
    except Exception: return "0"
    if float(x).is_integer(): return f"{int(x)}"
    return f"{x:.1f}".rstrip('0').rstrip('.')

def fmt_one_decimal(v):
    """
    Para tabla lineal:
    - Enteros → sin decimales
    - Decimales → 1 decimal
    """
    try:
        v = float(v)
    except Exception:
        return "0"
    if v.is_integer():
        return f"{int(v)}"
    return f"{v:.1f}"

def fmt_carbs_rule(v):
    """
    Regla visual para carbohidratos en formato lineal:
    - Enteros → sin decimales
    - Decimales → 1 decimal
    (no altera el redondeo normativo previo)
    """
    try:
        v = float(v)
    except Exception:
        return "0"
    if v.is_integer():
        return f"{int(v)}"
    return f"{v:.1f}"

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

def fmt_art9(value, is_micro=False):
    """
    Formato según Artículo 9 – Resolución 810 de 2021
    is_micro = True para vitaminas y minerales
    """
    try:
        v = float(value)
    except Exception:
        return "0"

    av = abs(v)

    if av >= 1000:
        return f"{int(round(v))}"
    if av >= 100:
        return f"{int(round(v))}"
    if av >= 10:
        return f"{int(round(v))}"
    if av >= 1:
        return f"{v:.1f}".rstrip('0').rstrip('.')
    # av < 1
    if is_micro:
        return f"{v:.2f}"   # 👈 SIN rstrip
    return f"{v:.1f}"      # 👈 SIN rstrip

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
    limits = {
        "Carbohidratos totales": 0.5,
        "Azúcares totales": 0.5,
        "Proteína": 0.5,
        "Grasa total": 0.5,
        "Fibra dietaria": 0.5,
        "Grasa saturada": 0.1,
    }
    return 0.0 if v <= limits.get(name, -1) else v


def nonsig_zero_mg(name, v):
    limits = {
        "Grasas trans": 100,
        "Sodio": 5,
    }
    return 0 if v <= limits.get(name, -1) else v


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
trans_fat_100_mg_r  = round_mg(_trans_g_100 * 1000.0)

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
# PARA GRASAS TRANS POR PORCIÓN: NO APLICAR CRITERIO DE "NO SIGNIFICATIVO"
_trans_g_pp        = (trans_fat_pp_mg or 0.0)/1000.0
# ELIMINAR ESTA LÍNEA: _trans_g_pp = nonsig_zero_g("Grasas trans", _trans_g_pp)
trans_fat_pp_mg_r  = round_mg(_trans_g_pp * 1000.0)

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
FONT_LABEL_EMPH     = get_font(int(30 * 1.3), bold=False)
FONT_LABEL_EMPH_B   = get_font(int(30 * 1.3), bold=True)
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

def compute_cols_vertical(draw, labels_with_indent, v100_list, vpp_list, W):
    name_w_max = 0
    INDENT_PX = 28  # mismo valor que usas al dibujar
    
    for label, indent in labels_with_indent:
        # usar fuente grande solo si es un nutriente enfatizado
        font = FONT_LABEL_EMPH_B if label.strip() in [
            "Grasa saturada",
            "Grasas trans",
            "Azúcares añadidos",
            "Sodio"
        ] else FONT_LABEL

        w, _ = measure_text(draw, label.strip(), font)
        total_w = w + indent * INDENT_PX
        if total_w > name_w_max:
            name_w_max = total_w

    v100_w_max = 0
    for t in v100_list:
        w, _ = measure_text(draw, t, FONT_LABEL)
        if w > v100_w_max:
            v100_w_max = w

    vpp_w_max = 0
    for t in vpp_list:
        w, _ = measure_text(draw, t, FONT_LABEL)
        if w > vpp_w_max:
            vpp_w_max = w

    col100_label, colpp_label = column_labels()
    col100_w, _ = measure_text(draw, col100_label, FONT_SMALL_B)
    colpp_w, _ = measure_text(draw, colpp_label, FONT_SMALL_B)

    final_name_width = name_w_max + 15 + GRID_W

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
        ("Grasa total",            f"{fmt_art9(fat_total_100_r)} g",     f"{fmt_art9(fat_total_pp_r)} g",       0, False, False),
        ("Grasa saturada",       f"{fmt_art9(sat_fat_100_r)} g", f"{fmt_art9(sat_fat_pp_r)} g", 1, True, False),
        ("Grasas trans",         f"{fmt_art9(trans_fat_100_mg_r)} mg", f"{fmt_art9(trans_fat_pp_mg_r)} mg", 1, True, False),
        ("Carbohidratos totales",  f"{fmt_art9(carb_100_r)} g",           f"{fmt_art9(carb_pp_r)} g",             0, False, False),
        ("Fibra dietaria",       f"{fmt_art9(fiber_100_r)} g",         f"{fmt_art9(fiber_pp_r)} g",           1, False, False),
        ("Azúcares totales",     f"{fmt_art9(sug_total_100_r)} g",
                            f"{fmt_art9(sug_total_pp_r)} g", 1, False, False),
        ("Azúcares añadidos",  f"{fmt_art9(sug_added_100_r)} g",
                            f"{fmt_art9(sug_added_pp_r)} g", 2, True, False),
        ("Proteína",               f"{fmt_art9(protein_100_r)} g",       f"{fmt_art9(protein_pp_r)} g",         0, False, False),
        ("Sodio",                  f"{fmt_art9(sodium_100_mg_r)} mg",            f"{fmt_art9(sodium_pp_mg_r)} mg",              0, True,  False),
    ]
    if include_poly:
        # Insertarlo después de Fibra y antes de Azúcares totales
        try:
            idx_azuc_tot = next(i for i, r in enumerate(rows) if r[0].strip() == "Azúcares totales")
            rows.insert(idx_azuc_tot, ("  Polialcoholes", f"{fmt_art9(poly_100_r)} g", f"{fmt_art9(poly_pp_r)} g", 1, False, False))
        except StopIteration:
            pass
    return rows

def micro_rows():
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

        rows.append((
    name,
    f"{fmt_art9(v100, is_micro=True)} {unit}",
    f"{fmt_art9(vpp,  is_micro=True)} {unit}",
    0, False, True
))

    return rows

# ------------------------------------------------------------
# BLOQUE CALORÍAS (2 filas combinadas)
# ------------------------------------------------------------
def draw_calories_combined_row(d, W, y, col_x, kcal_100_txt, kcal_pp_txt):
    row_h = ROW_H * 2
    y_text_title = y + (ROW_H // 2) - 14
    d.text((BORDER_W + CELL_PAD_X, y_text_title), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_EMPH_B)

    c100, cpp = column_labels()
    w_c100, _ = measure_text(d, c100, FONT_SMALL_B)
    w_cpp, _ = measure_text(d, cpp, FONT_SMALL_B)
    x100_center = (col_x[1] + col_x[2]) // 2
    xpp_center  = (col_x[2] + col_x[3]) // 2
    
    d.text((x100_center - w_c100//2, y_text_title), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((xpp_center  - w_cpp//2,  y_text_title), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)


    draw_hline(d, col_x[1], W-BORDER_W, y + ROW_H, TEXT_COLOR, GRID_W)
    
    y_text_values = y + ROW_H + (ROW_H // 2) - 14
    w100, _ = measure_text(d, kcal_100_txt, FONT_LABEL_EMPH_B)
    wpp, _  = measure_text(d, kcal_pp_txt,  FONT_LABEL_EMPH_B)
    
    x100_center = (col_x[1] + col_x[2]) // 2
    xpp_center  = (col_x[2] + col_x[3]) // 2
    
    d.text((x100_center - w100//2, y_text_values),
       kcal_100_txt,
       fill=TEXT_COLOR,
       font=FONT_LABEL_EMPH_B)
    d.text((xpp_center - wpp//2, y_text_values),
       kcal_pp_txt,
       fill=TEXT_COLOR,
       font=FONT_LABEL_EMPH_B)

    return y + row_h

# ------------------------------------------------------------
# Helper: renderizado rich text con negrilla parcial + salto de línea
# ------------------------------------------------------------

def draw_rich_wrapped_text(d, x, y, tokens, font_reg, font_bold, max_w, line_gap=4, first_line_x=None):
    """tokens = [(text, is_bold), ...]"""
    lines = []
    current = []

    def measure_tokens(tokens_list):
        w_total = 0
        for t, b in tokens_list:
            w, _ = measure_text(d, t, font_bold if b else font_reg)
            w_total += w
        return w_total

    # Construir líneas
    for t, b in tokens:
        if t == "":
            continue
        tentative = current + [(t, b)]
        if measure_tokens(tentative) <= max_w:
            current = tentative
        else:
            if current:
                lines.append(current)
                current = [(t, b)]
            else:
                lines.append([(t, b)])
                current = []

    if current:
        lines.append(current)

    # Dibujar líneas
def draw_rich_wrapped_text(d, x, y, tokens, font_reg, font_bold, max_w, line_gap=4, first_line_x=None):
    lines = []
    current = []

def measure_tokens(tokens_list, is_first_line=False):
    w_total = 0
    for t, b in tokens_list:
        w, _ = measure_text(d, t, font_bold if b else font_reg)
        w_total += w
            
    if is_first_line and first_line_x is not None:
        w_total += (first_line_x - x)
            
    return w_total


    # Construcción de líneas
    for t, b in tokens:
        if not t:
            continue
            is_first = len(lines) == 0
            tentative = current + [(t, b)]
            
            if measure_tokens(tentative, is_first_line=is_first) <= max_w:
                current = tentative
            else:
                if current:
                    lines.append(current)
                current = [(t, b)]


    # Renderizado
    for i, line in enumerate(lines):
        cx = first_line_x if (i == 0 and first_line_x is not None) else x
        for t, b in line:
            f = font_bold if b else font_reg
            d.text((cx, y), t, fill=TEXT_COLOR, font=f)
            w, _ = measure_text(d, t, f)
            cx += w
        y += font_reg.size + line_gap

    return y


# ------------------------------------------------------------
# FIGURA 1 — VERTICAL ESTÁNDAR
# ------------------------------------------------------------
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 580
    header_h = 165
    gap_after_title = 5
    foot_h = 90 if footnote_tail.strip() else 20

    body_rows_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)

    H_temp = 100
    img_temp = Image.new("RGB", (W, H_temp), BG_WHITE)
    d_temp = ImageDraw.Draw(img_temp)
    
    labels_all = [(r[0], r[3]) for r in rows_nutri] + \
             ([(r[0], r[3]) for r in rows_micro] if show_micro else [])
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
    
    # Línea delgada bajo el título 
    y_line_title = BORDER_W + 15 + th + 22
    draw_hline(
    d,
    BORDER_W,
    W - BORDER_W,
    y_line_title,
    TEXT_COLOR,
    GRID_W
)

    # porciones
    y0 = y_line_title + 20
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
        if bold:
            font_lbl = FONT_LABEL_EMPH_B
            font_val = FONT_LABEL_EMPH_B
        else:
            font_lbl = FONT_LABEL
            font_val = FONT_LABEL

        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text  = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        
        wv100, _ = measure_text(d, v100, font_val)
        wvpp,  _ = measure_text(d, vpp,  font_val)
        
        x100_center = (col_x[1] + col_x[2]) // 2
        xpp_center  = (col_x[2] + col_x[3]) // 2
        
        d.text((x100_center - wv100//2, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((xpp_center  - wvpp//2,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)


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
            x100_center = (col_x[1] + col_x[2]) // 2
            xpp_center  = (col_x[2] + col_x[3]) // 2
            
            d.text((x100_center - wv100//2, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((xpp_center  - wvpp//2,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)

            y += ROW_H_MICRO

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    
    # Líneas verticales hasta la segunda gruesa (fin de datos)
    draw_vline(d, col_x[1] + GRID_W//2, y_header_bottom, y, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2] + GRID_W//2, y_header_bottom, y, TEXT_COLOR, GRID_W)

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
    header_h = 165
    gap_after_title = 5
    foot_h = 90 if footnote_tail.strip() else 20
    body_rows_h = len(rows_nutri)*ROW_H

    H_temp = 100
    img_temp = Image.new("RGB", (W, H_temp), BG_WHITE)
    d_temp = ImageDraw.Draw(img_temp)
    
    labels_all = [(r[0], r[3]) for r in rows_nutri]
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
    
    # Línea delgada bajo el título
    y_line_title = BORDER_W + 15 + th + 22
    draw_hline(d, BORDER_W, W - BORDER_W, y_line_title, TEXT_COLOR, GRID_W)

    y0 = y_line_title + 20
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
        if bold:
            font_lbl = FONT_LABEL_EMPH_B
            font_val = FONT_LABEL_EMPH_B
        else:
            font_lbl = FONT_LABEL
            font_val = FONT_LABEL

        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text  = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = measure_text(d, v100, font_val)
        wvpp,_  = measure_text(d, vpp,  font_val)
        
        x100_center = (col_x[1] + col_x[2]) // 2
        xpp_center  = (col_x[2] + (W - BORDER_W)) // 2
        
        d.text((x100_center - wv100//2, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((xpp_center  - wvpp//2,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)

        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Líneas verticales hasta la segunda gruesa (fin de datos)
    draw_vline(d, col_x[1] + GRID_W//2, y_header_bottom, y, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2] + GRID_W//2, y_header_bottom, y, TEXT_COLOR, GRID_W)

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
# FIGURA 5 — LINEAL / TABULAR (con negrillas específicas)
# ------------------------------------------------------------
def draw_fig5():
    """
    Formato lineal/tabular (diseño ancho) con salto de línea automático.
    Negrilla para: Información nutricional (ambos encabezados), Calorías + valor,
    Sodio + valor, Azúcares añadidos + valor, y títulos de Tamaño de porción / Número de porciones.
    """
    W, H = 1700, 520
    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    x = BORDER_W + CELL_PAD_X
    y = BORDER_W + 20
    line_space = 42
    max_line_width = W - 2 * BORDER_W - 2 * CELL_PAD_X

    # Encabezado 100 g / 100 mL (inline con contenido)
    label_main = "Información nutricional"
    label_unit = f" ({'100 mL' if is_liquid else '100 g'}):"

    # Dibujar encabezado
    d.text((x, y), label_main, fill=TEXT_COLOR, font=FONT_SMALL_B)
    w_main, _ = measure_text(d, label_main, FONT_SMALL_B)
    d.text((x + w_main, y), label_unit, fill=TEXT_COLOR, font=FONT_SMALL)

    # Nuevo punto de inicio para el contenido
    w_unit, _ = measure_text(d, label_unit, FONT_SMALL)
    x_content = x + w_main + w_unit + 10  # 10 px de aire visual


    # Partes por 100 -> tokens con negrilla en Calorías, Sodio, Azúcares añadidos (título y valor)
    def tokens_item(label, value, unit="", bold=False):
        toks = [(label, bold), (" ", bold), (value, bold)]
        if unit:
            toks.append((" " + unit, bold))
        return toks

    tokens_100 = []
    tokens_100 += tokens_item("Calorías", f"{fmt_int(kcal_100)}", bold=True) + [(", ", False)]
    tokens_100 += tokens_item("Grasa total", f"{fmt_one_decimal(fat_total_100_r)}", "g", bold=False) + [(", ", False)]
    tokens_100 += tokens_item("Grasa saturada", f"{fmt_one_decimal(sat_fat_100_r)}", "g", bold=False) + [(", ", False)]
    tokens_100 += tokens_item("Grasas trans", f"{fmt_int(trans_fat_100_mg_r)}", "mg", bold=False) + [(", ", False)]
    tokens_100 += tokens_item("Sodio", f"{fmt_int(sodium_100_mg_r)}", "mg", bold=True) + [(", ", False)]
    tokens_100 += tokens_item("Carbohidratos totales", f"{fmt_carbs_rule(carb_100_r)}", "g", bold=False) + [(", ", False)]
    tokens_100 += tokens_item("Fibra dietaria", f"{fmt_one_decimal(fiber_100_r)}", "g", bold=False) + [(", ", False)]
    if include_poly:
        tokens_100 += tokens_item("Polialcoholes", f"{fmt_one_decimal(poly_100_r)}", "g", bold=False) + [(", ", False)]
        
    tokens_100 += tokens_item("Azúcares totales", f"{fmt_one_decimal(sug_total_100_r)}", "g", bold=False) + [(", ", False)]
    tokens_100 += tokens_item("Azúcares añadidos", f"{fmt_one_decimal(sug_added_100_r)}", "g", bold=True) + [(", ", False)]
    tokens_100 += tokens_item("Proteína", f"{fmt_one_decimal(protein_100_r)}", "g", bold=False) + [(", ", False)]

    # Micronutrientes (mantener formato descriptivo simple, sin negrilla)
    def vm_or_zero(name, unit_key):
        return fmt_micro_value(name, unit_key, vm_values_rounded.get((name, unit_key), 0))
    micro_texts = [
        f"Vitamina A {vm_or_zero('Vitamina A','µg ER')}",
        f"Vitamina D {vm_or_zero('Vitamina D','µg')}",
        f"Hierro {vm_or_zero('Hierro','mg')}",
        f"Calcio {vm_or_zero('Calcio','mg')}",
        f"Zinc {vm_or_zero('Zinc','mg')}"
    ]
    for i, mt in enumerate(micro_texts):
        tokens_100 += [(mt, False)]
        tokens_100 += [(", ", False)] if i < len(micro_texts)-1 else [(".", False)]

    # Render envuelto
    y = draw_rich_wrapped_text(
        d,
        x,                    
        y,
        tokens_100,
        FONT_SMALL,
        FONT_SMALL_B,
        max_line_width,
        line_gap=4,
        first_line_x=x_content
    )

    # Encabezado por porción en negrilla
    y += line_space
    label_main = "Información nutricional"
    label_unit = " (porción):"
    
    d.text((x, y), label_main, fill=TEXT_COLOR, font=FONT_SMALL_B)
    w_main, _ = measure_text(d, label_main, FONT_SMALL_B)
    d.text((x + w_main, y), label_unit, fill=TEXT_COLOR, font=FONT_SMALL)

    w_unit, _ = measure_text(d, label_unit, FONT_SMALL)
    x_content_pp = x + w_main + w_unit + 10

    tokens_pp = []
    # Tamaño de porción (negrilla solo título)
    tokens_pp += [("Tamaño de porción:", True), (" ", False), (f"{household_name} ({int(round(portion_size))} {portion_unit})", False), (", ", False)]
    # Número de porciones (negrilla solo título)
    tokens_pp += [("Número de porciones por envase:", True), (" ", False), (f"{int(round(servings_per_pack))}", False), (", ", False)]
    # Calorías (bold + valor)
    tokens_pp += tokens_item("Calorías", f"{fmt_int(kcal_pp)}", bold=True) + [(", ", False)]
    # Grasa total
    tokens_pp += tokens_item("Grasa total", f"{fmt_one_decimal(fat_total_pp_r)}", "g", bold=False) + [(", ", False)]
    # Grasa saturada
    tokens_pp += tokens_item("Grasa saturada", f"{fmt_one_decimal(sat_fat_pp_r)}", "g", bold=False) + [(", ", False)]
    # Grasas trans
    tokens_pp += tokens_item("Grasas trans", f"{fmt_int(trans_fat_pp_mg_r)}", "mg", bold=False) + [(", ", False)]
    # Sodio (bold + valor)
    tokens_pp += tokens_item("Sodio", f"{fmt_int(sodium_pp_mg_r)}", "mg", bold=True) + [(", ", False)]
    # Carbohidratos totales
    tokens_pp += tokens_item("Carbohidratos totales", f"{fmt_carbs_rule(carb_pp_r)}", "g", bold=False) + [(", ", False)]
    # Fibra
    tokens_pp += tokens_item("Fibra dietaria", f"{fmt_one_decimal(fiber_pp_r)}", "g", bold=False) + [(", ", False)]
    # Polialcoholes
    if include_poly:
        tokens_pp += tokens_item("Polialcoholes", f"{fmt_one_decimal(poly_pp_r)}", "g", bold=False) + [(", ", False)]
    # Azúcares totales
    tokens_pp += tokens_item("Azúcares totales", f"{fmt_one_decimal(sug_total_pp_r)}", "g", bold=False) + [(", ", False)]
    # Azúcares añadidos (bold + valor)
    tokens_pp += tokens_item("Azúcares añadidos", f"{fmt_one_decimal(sug_added_pp_r)}", "g", bold=True) + [(", ", False)]
    # Proteína
    tokens_pp += tokens_item("Proteína", f"{fmt_one_decimal(protein_pp_r)}", "g", bold=False) + [(", ", False)]

    # Micros por porción (sin negrilla)
    micro_pp_texts = [
        f"Vitamina A {fmt_micro_value('Vitamina A','µg ER',vm_pp.get(('Vitamina A','µg ER'),0))}",
        f"Vitamina D {fmt_micro_value('Vitamina D','µg',vm_pp.get(('Vitamina D','µg'),0))}",
        f"Hierro {fmt_micro_value('Hierro','mg',vm_pp.get(('Hierro','mg'),0))}",
        f"Calcio {fmt_micro_value('Calcio','mg',vm_pp.get(('Calcio','mg'),0))}",
        f"Zinc {fmt_micro_value('Zinc','mg',vm_pp.get(('Zinc','mg'),0))}"
    ]
    for i, mt in enumerate(micro_pp_texts):
        tokens_pp += [(mt, False)]
        tokens_pp += [(", ", False)] if i < len(micro_pp_texts)-1 else [(".", False)]

    y = draw_rich_wrapped_text(
    d,
    x,                       # margen izquierdo
    y,                       # 👈 MISMO y del encabezado
    tokens_pp,
    FONT_SMALL,
    FONT_SMALL_B,
    max_line_width,
    line_gap=4,
    first_line_x=x_content_pp
)


    # Pie multilínea (regular)
    if footnote_tail.strip():
        base_text = f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}"
        # Partir por palabras en tokens regulares
        words = base_text.split(" ")
        foot_tokens = []
        for i, w in enumerate(words):
            foot_tokens.append((w + (" " if i < len(words)-1 else ""), False))
        y += line_space
        y = draw_rich_wrapped_text(d, x, y, foot_tokens, FONT_SMALL, FONT_SMALL_B, max_line_width, line_gap=4)

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
