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
    """
    Tabla 2 – Cantidades no significativas (Res. 810/2021)
    Calorías:
    ≤ 4 kcal → 0
    > 4 kcal → se declara el valor REAL (sin aproximar)
    """
    try:
        v = float(v)
    except Exception:
        return 0

    if v <= 4:
        return 0

    return v   

def fmt_kcal(v):
    if v == 0:
        return "0"
    return f"{v:.1f}".rstrip("0").rstrip(".")

    # No aproximar, no redondear
    return v


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

household_name = st.sidebar.text_input(
    "Medida casera (p. ej. 1 unidad, 1 taza)",
    value="1 unidad"
)

household_mass = as_num(
    st.sidebar.text_input(
        f"Equivalencia en {portion_unit} (número)",
        value="40"
    )
)

st.sidebar.markdown("**Número de porciones por envase**")

servings_value = as_num(
    st.sidebar.text_input(
        "Valor numérico (para cálculos)",
        value=""
    )
)

servings_label = st.sidebar.text_input(
    "Texto a mostrar (solo si aplica, ej. 'aprox. 4')",
    value=""
)


st.sidebar.subheader("Macronutrientes a declarar")
macro_order = [
    "Grasa total",
    "Grasa saturada",
    "Grasas trans",
    "Carbohidratos totales",
    "Fibra dietaria",
    "Azúcares totales",
    "Azúcares añadidos",
    "Proteína",
    "Sodio",
]

selected_macros = st.sidebar.multiselect(
    "Selecciona los macronutrientes que se declararán en la tabla",
    macro_order,
    default=macro_order
)

st.sidebar.subheader("Grasas opcionales")

selected_optional_fats = st.sidebar.multiselect(
    "Selecciona las grasas que deseas declarar",
    ["Grasa monoinsaturada", "Grasa poliinsaturada"],
    default=[]
)

st.sidebar.subheader("Micronutrientes a declarar")
vm_options = [
    # Micronutrientes base
    "Vitamina A",
    "Vitamina D",
    "Hierro",
    "Calcio",
    "Zinc",

    # Micronutrientes voluntarios
    "Vitamina C",
    "Vitamina B1",
    "Vitamina E",
    "Fósforo",
    "Vitamina K",
    "Yodo",
    "Magnesio",
    "Niacina",
    "Ácido pantoténico",
    "Selenio",
    "Vitamina B6",
    "Cobre",
    "Riboflavina",
    "Manganeso",
    "Tiamina",
    "Cromo",
    "Folato",
    "Molibdeno",
    "Biotina",
    "Cloruro",
    "Vitamina B12"
]
selected_vm = st.sidebar.multiselect(
    "Selecciona los que declararás",
    vm_options,
    default=["Vitamina A","Vitamina D","Hierro","Calcio","Zinc"]
)


# ------------------------------------------------------------
# Construcción automática del texto
# "No es fuente significativa de ..."
# ------------------------------------------------------------
micro_order = ["Vitamina A", "Vitamina D", "Hierro", "Calcio", "Zinc"]

mandatory_micros = [
    "Vitamina A",
    "Vitamina D",
    "Hierro",
    "Calcio",
    "Zinc"
]

macros_not_declared = [
    m for m in macro_order if m not in selected_macros
]

micros_not_declared = [
    m for m in mandatory_micros if m not in selected_vm
]


footnote_items = macros_not_declared + micros_not_declared

footnote_text = (
    "No es fuente significativa de " + ", ".join(footnote_items)
    if footnote_items else ""
)



st.sidebar.subheader("Polialcoholes")
include_poly = st.sidebar.checkbox("Incluir polialcoholes", value=False)
poly_100 = as_num(st.sidebar.text_input("Polialcoholes (g/100)", value="0")) if include_poly else 0.0


# ------------------------------------------------------------
# Texto final a mostrar para número de porciones
# ------------------------------------------------------------
servings_display = (
    servings_label.strip()
    if servings_label.strip()
    else (
        str(int(round(servings_value)))
        if servings_value > 0
        else "0"
    )
)


# ------------------------------------------------------------
# ENTRADAS PRINCIPALES (por 100 g/mL)
# ------------------------------------------------------------
st.header("Ingreso de datos por 100 g / 100 mL")

c1, c2, c3 = st.columns([0.33, 0.33, 0.34])
with c1:
    st.subheader("Macronutrientes (por 100)")

    if "Grasa total" in selected_macros:
        fat_total_100 = as_num(st.text_input("Grasa total (g/100)", value="13"))
    else:
        fat_total_100 = 0.0

    if "Grasa saturada" in selected_macros:
        sat_fat_100 = as_num(st.text_input("Grasa saturada (g/100)", value="6"))
    else:
        sat_fat_100 = 0.0

    if "Grasas trans" in selected_macros:
        trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg/100)", value="820"))
    else:
        trans_fat_100_mg = 0.0

    if "Grasa monoinsaturada" in selected_optional_fats:
        mono_fat_100 = as_num(st.text_input("Grasa monoinsaturada (g/100)", value="0"))
    else:
        mono_fat_100 = 0.0

    if "Grasa poliinsaturada" in selected_optional_fats:
        poly_fat_100 = as_num(st.text_input("Grasa poliinsaturada (g/100)", value="0"))
    else:
        poly_fat_100 = 0.0
    
with c2:
    if "Carbohidratos totales" in selected_macros:
        carb_100 = as_num(st.text_input("Carbohidratos totales (g/100)", value="31"))
    else:
        carb_100 = 0.0

    if "Azúcares totales" in selected_macros:
        sug_total_100 = as_num(st.text_input("Azúcares totales (g/100)", value="5"))
    else:
        sug_total_100 = 0.0

    if "Azúcares añadidos" in selected_macros:
        sug_added_100 = as_num(st.text_input("Azúcares añadidos (g/100)", value="2"))
    else:
        sug_added_100 = 0.0
        
with c3:
    if "Fibra dietaria" in selected_macros:
        fiber_100 = as_num(st.text_input("Fibra dietaria (g/100)", value="0.8"))
    else:
        fiber_100 = 0.0

    if "Proteína" in selected_macros:
        protein_100 = as_num(st.text_input("Proteína (g/100)", value="5"))
    else:
        protein_100 = 0.0

    if "Sodio" in selected_macros:
        sodium_100_mg = as_num(st.text_input("Sodio (mg/100)", value="560"))
    else:
        sodium_100_mg = 0.0

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
mono_fat_pp = portion_from_per100(mono_fat_100, portion_size)
poly_fat_pp = portion_from_per100(poly_fat_100, portion_size)

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
mono_fat_100_r = round_g(mono_fat_100)
poly_fat_100_r = round_g(poly_fat_100)
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
mono_fat_pp_r = round_g(mono_fat_pp)
poly_fat_pp_r = round_g(poly_fat_pp)
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
FONT_SMALL_EMPH_B = get_font(int(26 * 1.3), bold=True)
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
    rows = []
    if "Grasa total" in selected_macros:
        rows.append(("Grasa total",
            f"{fmt_art9(fat_total_100_r)} g",
            f"{fmt_art9(fat_total_pp_r)} g",
            0, False, False))

    if "Grasa monoinsaturada" in selected_optional_fats:
        rows.append(("Grasa monoinsaturada",
            f"{fmt_art9(mono_fat_100_r)} g",
            f"{fmt_art9(mono_fat_pp_r)} g",
            1, False, False))

    if "Grasa poliinsaturada" in selected_optional_fats:
        rows.append(("Grasa poliinsaturada",
            f"{fmt_art9(poly_fat_100_r)} g",
            f"{fmt_art9(poly_fat_pp_r)} g",
            1, False, False))

    if "Grasa saturada" in selected_macros:
        rows.append(("Grasa saturada",
            f"{fmt_art9(sat_fat_100_r)} g",
            f"{fmt_art9(sat_fat_pp_r)} g",
            1, True, False))

    if "Grasas trans" in selected_macros:
        rows.append(("Grasas trans",
            f"{fmt_art9(trans_fat_100_mg_r)} mg",
            f"{fmt_art9(trans_fat_pp_mg_r)} mg",
            1, True, False))

    if "Carbohidratos totales" in selected_macros:
        rows.append(("Carbohidratos totales",
            f"{fmt_art9(carb_100_r)} g",
            f"{fmt_art9(carb_pp_r)} g",
            0, False, False))

    if "Fibra dietaria" in selected_macros:
        rows.append(("Fibra dietaria",
            f"{fmt_art9(fiber_100_r)} g",
            f"{fmt_art9(fiber_pp_r)} g",
            1, False, False))

    if "Azúcares totales" in selected_macros:
        rows.append(("Azúcares totales",
            f"{fmt_art9(sug_total_100_r)} g",
            f"{fmt_art9(sug_total_pp_r)} g",
            1, False, False))

    if "Azúcares añadidos" in selected_macros:
        rows.append(("Azúcares añadidos",
            f"{fmt_art9(sug_added_100_r)} g",
            f"{fmt_art9(sug_added_pp_r)} g",
            2, True, False))

    if "Proteína" in selected_macros:
        rows.append(("Proteína",
            f"{fmt_art9(protein_100_r)} g",
            f"{fmt_art9(protein_pp_r)} g",
            0, False, False))

    if "Sodio" in selected_macros:
        rows.append(("Sodio",
            f"{fmt_art9(sodium_100_mg_r)} mg",
            f"{fmt_art9(sodium_pp_mg_r)} mg",
            0, True, False))

    return rows

def micro_rows():
    mandatory = ["Vitamina A","Vitamina D","Hierro","Calcio","Zinc"]

    # Orden final:
    # 1) obligatorios (en orden fijo)
    # 2) voluntarios (en el orden en que el usuario los seleccionó)
    ordered = []

    # obligatorios
    for m in mandatory:
        for (n, u) in vm_values_rounded.keys():
            if n == m:
                ordered.append((n, u))

    # voluntarios
    for (n, u) in vm_values_rounded.keys():
        if n not in mandatory:
            ordered.append((n, u))

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

    if current:
        lines.append(current)

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
            if b == "emph":
                f = FONT_SMALL_EMPH_B
            elif b == "bold":
                f = FONT_SMALL_B
            else:
                f = FONT_SMALL
            w, _ = measure_text(d, t, f)
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

    if current:
        lines.append(current)

    # Renderizado
    for i, line in enumerate(lines):
        cx = first_line_x if (i == 0 and first_line_x is not None) else x
        for t, b in line:
            if b == "emph":
                f = FONT_SMALL_EMPH_B      # 👈 1.3x
            elif b == "bold":
                f = FONT_SMALL_B
            else:
                f = FONT_SMALL

            d.text((cx, y), t, fill=TEXT_COLOR, font=f)
            w, _ = measure_text(d, t, f)
            cx += w

        y += FONT_SMALL.size + line_gap

    return y


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
            if b == "emph":
                f = FONT_SMALL_EMPH_B      # negrilla + 1.3x
            elif b == "bold":
                f = FONT_SMALL_B           # negrilla normal
            else:
                f = FONT_SMALL             # texto normal

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
    foot_h = 90 if footnote_text.strip() else 20

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
           f"Número de porciones por envase: {servings_display}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y_header_bottom = BORDER_W + header_h
    draw_hline(d, BORDER_W, W-BORDER_W, y_header_bottom, TEXT_COLOR, GRID_W_THICK)
    
    kcal_100_txt = fmt_kcal(kcal_100)
    kcal_pp_txt  = fmt_kcal(kcal_pp)
    
    y = draw_calories_combined_row(
        d,
        W,
        y_header_bottom + 1,
        col_x,
        kcal_100_txt,
        kcal_pp_txt
    )

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
    if footnote_text:
        base_text = footnote_text
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
    foot_h = 90 if footnote_text.strip() else 20
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
           f"Número de porciones por envase: {servings_display}",
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
    if footnote_text:
        base_text = footnote_text
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
    W = 1700
    H = 400  # altura inicial mínima
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
    def tokens_item(label, value, unit="", bold=False, emph=False):
        flag = "emph" if emph else ("bold" if bold else None)
        toks = [(label, flag), (" ", flag), (value, flag)]
        if unit:
            toks.append((" " + unit, flag))
        return toks

        
    tokens_100 = []
    tokens_100 += tokens_item("Calorías", fmt_kcal(kcal_100), "kcal", emph=True) + [(", ", False)]
    
    if "Grasa total" in selected_macros:
        tokens_100 += tokens_item("Grasa total", f"{fmt_one_decimal(fat_total_100_r)}", "g") + [(", ", False)]
        
    if "Grasa saturada" in selected_macros:
        tokens_100 += tokens_item("Grasa saturada", f"{fmt_one_decimal(sat_fat_100_r)}", "g", emph=True) + [(", ", False)]
        
    if "Grasas trans" in selected_macros:
        tokens_100 += tokens_item("Grasas trans", f"{fmt_int(trans_fat_100_mg_r)}", "mg", emph=True) + [(", ", False)]
        
    if "Carbohidratos totales" in selected_macros:
        tokens_100 += tokens_item("Carbohidratos totales", f"{fmt_carbs_rule(carb_100_r)}", "g") + [(", ", False)]
        
    if "Fibra dietaria" in selected_macros:
        tokens_100 += tokens_item("Fibra dietaria", f"{fmt_one_decimal(fiber_100_r)}", "g") + [(", ", False)]
        
    if include_poly:
        tokens_100 += tokens_item("Polialcoholes", f"{fmt_one_decimal(poly_100_r)}", "g") + [(", ", False)]
        
    if "Azúcares totales" in selected_macros:
        tokens_100 += tokens_item("Azúcares totales", f"{fmt_one_decimal(sug_total_100_r)}", "g") + [(", ", False)]
        
    if "Azúcares añadidos" in selected_macros:
        tokens_100 += tokens_item("Azúcares añadidos", f"{fmt_one_decimal(sug_added_100_r)}", "g", emph=True) + [(", ", False)]
        
    if "Proteína" in selected_macros:
        tokens_100 += tokens_item("Proteína", f"{fmt_one_decimal(protein_100_r)}", "g") + [(", ", False)]
        
    if "Sodio" in selected_macros:
        tokens_100 += tokens_item("Sodio", f"{fmt_int(sodium_100_mg_r)}", "mg", emph=True) + [(", ", False)]

    # Micronutrientes (mantener formato descriptivo simple, sin negrilla)
    def vm_or_zero(name, unit_key):
        return fmt_micro_value(name, unit_key, vm_values_rounded.get((name, unit_key), 0))
    for name in ["Vitamina A","Vitamina D","Hierro","Calcio","Zinc"]:
        if name in selected_vm:
            unit = "µg ER" if name == "Vitamina A" else ("µg" if name == "Vitamina D" else "mg")
            value = vm_values_rounded.get((name, unit), 0)
            tokens_100 += [(f"{name} {fmt_micro_value(name, unit, value)}", False), (", ", False)]


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
    label_main = "Información nutricional"
    label_unit = " (porción):"
    
    d.text((x, y), label_main, fill=TEXT_COLOR, font=FONT_SMALL_B)
    w_main, _ = measure_text(d, label_main, FONT_SMALL_B)
    d.text((x + w_main, y), label_unit, fill=TEXT_COLOR, font=FONT_SMALL)

    w_unit, _ = measure_text(d, label_unit, FONT_SMALL)
    x_content_pp = x + w_main + w_unit + 10

    tokens_pp = []
    
    tokens_pp += [
        ("Tamaño de porción:", True),
        (" ", False),
        (f"{household_name} ({int(round(portion_size))} {portion_unit})", False),
        (", ", False)
    ]

# Número de porciones por envase
    tokens_pp += [
        ("Número de porciones por envase:", True),
        (" ", False),
        (servings_display, False),
        (", ", False)
    ]

# Calorías
    tokens_pp += tokens_item("Calorías", fmt_kcal(kcal_pp), "kcal", emph=True) + [(", ", False)]
    
# Grasa total
    if "Grasa total" in selected_macros:
        tokens_pp += tokens_item("Grasa total", f"{fmt_one_decimal(fat_total_pp_r)}", "g") + [(", ", False)]

# Grasa saturada
    if "Grasa saturada" in selected_macros:
        tokens_pp  += tokens_item("Grasa saturada", f"{fmt_one_decimal(sat_fat_pp_r)}", "g", emph=True) + [(", ", False)]

# Grasas trans
    if "Grasas trans" in selected_macros:
        tokens_pp  += tokens_item("Grasas trans", f"{fmt_int(trans_fat_pp_mg_r)}", "mg", emph=True) + [(", ", False)]

# Carbohidratos
    if "Carbohidratos totales" in selected_macros:
        tokens_pp += tokens_item("Carbohidratos totales", f"{fmt_carbs_rule(carb_pp_r)}", "g") + [(", ", False)]

# Fibra
    if "Fibra dietaria" in selected_macros:
        tokens_pp += tokens_item("Fibra dietaria", f"{fmt_one_decimal(fiber_pp_r)}", "g") + [(", ", False)]

# Polialcoholes
    if include_poly:
        tokens_pp += tokens_item("Polialcoholes", f"{fmt_one_decimal(poly_pp_r)}", "g") + [(", ", False)]

# Azúcares totales
    if "Azúcares totales" in selected_macros:
        tokens_pp += tokens_item("Azúcares totales", f"{fmt_one_decimal(sug_total_pp_r)}", "g") + [(", ", False)]

# Azúcares añadidos
    if "Azúcares añadidos" in selected_macros:
        tokens_pp  += tokens_item("Azúcares añadidos", f"{fmt_one_decimal(sug_added_pp_r)}", "g", emph=True) + [(", ", False)]

# Proteína
    if "Proteína" in selected_macros:
        tokens_pp += tokens_item("Proteína", f"{fmt_one_decimal(protein_pp_r)}", "g") + [(", ", False)]

# Sodio
    if "Sodio" in selected_macros:
        tokens_pp  += tokens_item("Sodio", f"{fmt_int(sodium_pp_mg_r)}", "mg", emph=True) + [(", ", False)]

    # Micronutrientes obligatorios POR PORCIÓN
    for name in ["Vitamina A", "Vitamina D", "Hierro", "Calcio", "Zinc"]:
        if name in selected_vm:
            unit = (
                "µg ER" if name == "Vitamina A"
                else "µg" if name == "Vitamina D"
                else "mg"
            )
            value = vm_pp.get((name, unit), 0)
            tokens_pp += [
                (f"{name} {fmt_micro_value(name, unit, value)}", False),
                (", ", False)
            ]
                
    # 👉 Quitar coma final si existe antes de cerrar con punto
    if tokens_pp and tokens_pp[-1] == (", ", False):
        tokens_pp.pop()
                
    if footnote_text.strip():
        tokens_pp += [
            (". ", False),
            ("No es fuente significativa de ", False),
            (footnote_text.replace("No es fuente significativa de ", ""), False)
        ]

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
        
    H_final = int(y + BORDER_W + 10)
    img = img.crop((0, 0, W, H_final))
    d = ImageDraw.Draw(img)
        
    d.rectangle([0, 0, W-1, H_final-1], outline=TEXT_COLOR, width=BORDER_W)
        
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
