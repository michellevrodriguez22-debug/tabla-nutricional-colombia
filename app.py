# app.py
# ============================================================
# Generador de Tabla Nutricional (Colombia) -> PNG (solo PNG)
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Fig.1 (Vertical), Fig.3 (Simplificado), Fig.4 (Tabular), Fig.5 (Lineal)
# Entradas por 100 g / 100 mL. Cálculo por porción y kcal corregidos.
# Bloque "Calorías" con celda combinada (título centrado verticalmente),
# manteniendo columnas "Por 100" y "Por porción" independientes.
# Validación interna de sellos (no se imprime) + "Contiene edulcorantes".
# ============================================================

from io import BytesIO
from datetime import datetime
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(page_title="Generador de Tabla Nutricional (Colombia)", layout="wide")
st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

# ============================================================
# UTILIDADES
# ============================================================
def as_num(x):
    try:
        if x is None or str(x).strip() == "":
            return 0.0
        return float(x)
    except:
        return 0.0

def kcal_from_macros(fat_g, carb_g, protein_g, organic_acids_g=0.0, alcohol_g=0.0):
    """
    9 kcal/g grasa; 4 kcal/g carb y proteína; 7 kcal/g alcohol; 3 kcal/g ácidos orgánicos
    """
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9*fat_g + 4*carb_g + 4*protein_g + 7*alcohol_g + 3*organic_acids_g
    return float(kcal)

def portion_from_per100(value_per100, portion_size):
    """
    Convierte un valor por 100 g/mL al valor por porción (g o mL).
    """
    if portion_size and portion_size > 0:
        return (value_per100 * portion_size) / 100.0
    return 0.0

# ---- Reglas de redondeo/aproximación (criterios prácticos acordes a 810) ----
def round_kcal(v):
    # Valores < 5 kcal pueden declararse 0 (criterio de no significativo)
    if v < 5:
        return 0
    # Energía en entero
    return int(round(v))

def round_g(v):
    """
    Regla práctica por magnitud:
      - <0.5 → 0.0 si aplica "no significativo" (se evalúa afuera por nutriente)
      - [0.5, 10) → 1 decimal
      - [10, 100) → 1 decimal
      - >=100 → entero
    """
    av = abs(v)
    if av >= 100:
        return float(int(round(v, 0)))
    else:
        # 1 decimal para la mayoría de rangos en esta app
        return float(round(v, 1))

def round_mg(v_mg):
    # Sodio < 5 mg → 0 mg (no significativo). En general mg a entero.
    if v_mg < 5:
        return 0
    return int(round(v_mg))

def fmt_g(x):
    """
    Imprime g sin ceros de cola: 3.0 -> 3 ; 3.5 -> 3.5
    """
    try:
        x = float(x)
    except:
        return "0"
    if float(x).is_integer():
        return f"{int(x)}"
    return f"{x:.1f}".rstrip('0').rstrip('.')

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
# SIDEBAR
# ============================================================
st.sidebar.header("Configuración")

format_choice = st.sidebar.selectbox(
    "Formato a exportar",
    ["Fig. 1 — Vertical estándar", "Fig. 3 — Simplificado", "Fig. 4 — Tabular", "Fig. 5 — Lineal"],
    index=0
)

physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])
portion_unit = "g" if "Sólido" in physical_state else "mL"

st.sidebar.subheader("Porción")
household_name = st.sidebar.text_input("Medida casera (p. ej. 1 unidad, 1 taza)", value="1 unidad")
household_mass = as_num(st.sidebar.text_input(f"Equivalencia en {portion_unit} (número)", value="40"))
servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="2"))

# Validación no impresa
st.sidebar.subheader("Validación interna (no se imprime)")
contains_sweeteners = st.sidebar.checkbox("Contiene edulcorantes", value=False)

st.sidebar.subheader("Micronutrientes a declarar")
vm_options = [
    "Vitamina A", "Vitamina D", "Vitamina B1", "Vitamina B12",
    "Vitamina C", "Vitamina E", "Calcio", "Hierro", "Zinc", "Potasio"
]
selected_vm = st.sidebar.multiselect(
    "Selecciona los que declararás",
    vm_options,
    default=["Vitamina A","Hierro","Calcio","Vitamina D","Zinc"]  # Hierro antes que Calcio
)

st.sidebar.subheader("Texto al pie")
footnote_tail = st.sidebar.text_input(
    "Completa: No es fuente significativa de ...",
    value=""
)

# ============================================================
# ENTRADAS — por 100 g/mL
# ============================================================
st.header("Ingreso de datos por 100 g / 100 mL")

c1, c2, c3 = st.columns([0.33, 0.33, 0.34])
with c1:
    st.subheader("Macronutrientes (por 100)")
    fat_total_100    = as_num(st.text_input("Grasa total (g/100)", value="13"))
    sat_fat_100      = as_num(st.text_input("Grasa saturada (g/100)", value="6"))
    trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg/100)", value="820"))
with c2:
    carb_100       = as_num(st.text_input("Carbohidratos totales (g/100)", value="31"))
    sug_total_100  = as_num(st.text_input("Azúcares totales (g/100)", value="1.1"))
    sug_added_100  = as_num(st.text_input("Azúcares añadidos (g/100)", value="0.2"))
with c3:
    fiber_100      = as_num(st.text_input("Fibra dietaria (g/100)", value="0.8"))
    protein_100    = as_num(st.text_input("Proteína (g/100)", value="5"))
    sodium_100_mg  = as_num(st.text_input("Sodio (mg/100)", value="560"))

st.markdown("---")
st.subheader("Valores de micronutrientes seleccionados (por 100)")
vm_values = {}
vm_col1, vm_col2 = st.columns([0.5, 0.5])
with vm_col1:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 0:
            # Vitamina A en µg ER
            unit = "µg ER" if vm == "Vitamina A" else ("µg" if vm in ("Vitamina D","Vitamina B12") else "mg")
            vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))
with vm_col2:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 1:
            unit = "µg ER" if vm == "Vitamina A" else ("µg" if vm in ("Vitamina D","Vitamina B12") else "mg")
            vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))

# ============================================================
# CÁLCULOS
# ============================================================
portion_size = household_mass
is_liquid = "Líquido" in physical_state

# Por porción (sin redondear)
fat_total_pp    = portion_from_per100(fat_total_100, portion_size)
sat_fat_pp      = portion_from_per100(sat_fat_100, portion_size)
trans_fat_pp_mg = portion_from_per100(trans_fat_100_mg, portion_size)  # sigue en mg
carb_pp         = portion_from_per100(carb_100, portion_size)
sug_total_pp    = portion_from_per100(sug_total_100, portion_size)
sug_added_pp    = portion_from_per100(sug_added_100, portion_size)
fiber_pp        = portion_from_per100(fiber_100, portion_size)
protein_pp      = portion_from_per100(protein_100, portion_size)
sodium_pp_mg    = portion_from_per100(sodium_100_mg, portion_size)

# Energía (antes de redondear)
kcal_100_raw = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp_raw  = kcal_from_macros(fat_total_pp,  carb_pp,  protein_pp)

# "No significativas" por nutriente
def nonsig_zero_g(name, v):
    # Grasa total < 0.5 g → 0
    # Saturada/Trans < 0.1 g → 0
    # Carbohidratos/Fibra/Proteína < 0.5 g → 0
    # Azúcares totales: NO aplicar corte a 0 para evitar 0.3 -> 0.0 (se mantiene)
    if name == "Grasa total" and v < 0.5: return 0.0
    if name in ("Grasa saturada","Grasas trans") and v < 0.1: return 0.0
    if name in ("Carbohidratos totales","Fibra dietaria","Proteína","Azúcares añadidos") and v < 0.5: return 0.0
    return v

def nonsig_zero_mg(name, vmg):
    if name == "Sodio" and vmg < 5: return 0
    return vmg

# Por 100 (redondeados)
fat_total_100_r     = round_g(nonsig_zero_g("Grasa total",       fat_total_100))
sat_fat_100_r       = round_g(nonsig_zero_g("Grasa saturada",    sat_fat_100))
carb_100_r          = round_g(nonsig_zero_g("Carbohidratos totales", carb_100))
sug_total_100_r     = round_g(nonsig_zero_g("Azúcares totales",  sug_total_100))
sug_added_100_r     = round_g(nonsig_zero_g("Azúcares añadidos", sug_added_100))
fiber_100_r         = round_g(nonsig_zero_g("Fibra dietaria",    fiber_100))
protein_100_r       = round_g(nonsig_zero_g("Proteína",          protein_100))
sodium_100_mg_r     = round_mg(nonsig_zero_mg("Sodio",           sodium_100_mg))
# trans por 100
_trans_g_100        = (trans_fat_100_mg or 0.0)/1000.0
_trans_g_100        = nonsig_zero_g("Grasas trans", _trans_g_100)
trans_fat_100_mg_r  = round_mg(_trans_g_100*1000.0)

# Por porción (redondeados)
fat_total_pp_r     = round_g(nonsig_zero_g("Grasa total",       fat_total_pp))
sat_fat_pp_r       = round_g(nonsig_zero_g("Grasa saturada",    sat_fat_pp))
carb_pp_r          = round_g(nonsig_zero_g("Carbohidratos totales", carb_pp))
sug_total_pp_r     = round_g(nonsig_zero_g("Azúcares totales",  sug_total_pp))  # <- mantiene 0.3 como 0.3
sug_added_pp_r     = round_g(nonsig_zero_g("Azúcares añadidos", sug_added_pp))
fiber_pp_r         = round_g(nonsig_zero_g("Fibra dietaria",    fiber_pp))
protein_pp_r       = round_g(nonsig_zero_g("Proteína",          protein_pp))
sodium_pp_mg_r     = round_mg(nonsig_zero_mg("Sodio",           sodium_pp_mg))
# trans por porción (mg)
_trans_g_pp        = (trans_fat_pp_mg or 0.0)/1000.0
_trans_g_pp        = nonsig_zero_g("Grasas trans", _trans_g_pp)
trans_fat_pp_mg_r  = round_mg(_trans_g_pp*1000.0)

# Calorías finales redondeadas
kcal_100 = round_kcal(kcal_100_raw)
kcal_pp  = round_kcal(kcal_pp_raw)

# Micronutrientes por porción (redondeo condicionado)
def format_micronutrient(name, unit, v):
    # Reglas de decimales:
    # - Vitamina A: si tiene < 2 cifras -> 1 decimal
    # - Vitamina D: <1 -> 2 dec; si 1 cifra -> 1 dec; si 3 cifras -> 0 dec
    # - En general: si <2 cifras -> 1 decimal, si 3 cifras -> 0
    if unit in ("mg", "µg", "µg ER"):
        av = abs(v)
        if name == "Vitamina D":
            if av < 1: return f"{v:.2f}".rstrip('0').rstrip('.')
            if av < 10: return f"{v:.1f}".rstrip('0').rstrip('.')
            if av >= 100: return f"{int(round(v))}"
            return f"{v:.1f}".rstrip('0').rstrip('.')
        if name == "Vitamina A":
            if av < 10: return f"{v:.1f}".rstrip('0').rstrip('.')
        if av >= 100: 
            return f"{int(round(v))}"
        if av < 10:
            return f"{v:.1f}".rstrip('0').rstrip('.')
        return f"{int(round(v))}"
    return f"{v}"

vm_pp = {}
vm_values_rounded = {}
for (name, unit), v100 in vm_values.items():
    vpp = portion_from_per100(v100, portion_size)
    vm_values_rounded[(name, unit)] = v100
    vm_pp[(name, unit)] = vpp

# ============================================================
# VALIDACIÓN DE SELLOS (no impresa)
# ============================================================
def pct_kcal_from(nutrient_kcal, total_kcal_pp):
    if total_kcal_pp <= 0:
        return 0.0
    return 100.0 * nutrient_kcal / total_kcal_pp

sat_pct    = pct_kcal_from(9 * max(sat_fat_pp, 0), max(kcal_pp_raw, 1e-9))
trans_pct  = pct_kcal_from(9 * max((trans_fat_pp_mg or 0)/1000.0, 0), max(kcal_pp_raw, 1e-9))
sugadd_pct = pct_kcal_from(4 * max(sug_added_pp, 0), max(kcal_pp_raw, 1e-9))

if is_liquid:
    sodium_rule = (sodium_100_mg >= 40.0) or ((sodium_pp_mg / max(kcal_pp_raw,1e-9)) >= 1.0)
else:
    sodium_rule = (sodium_100_mg >= 300.0) or ((sodium_pp_mg / max(kcal_pp_raw,1e-9)) >= 1.0)

fop_sugar  = sugadd_pct >= 10.0
fop_sat    = sat_pct    >= 10.0
fop_trans  = trans_pct  >= 1.0
fop_sodium = sodium_rule
fop_sweet  = contains_sweeteners

with st.expander("Resultado de validación informativa (no se imprime)", expanded=False):
    colf1, colf2, colf3 = st.columns(3)
    with colf1:
        st.write(f"Azúcares añadidos ≥10% kcal: **{'Sí' if fop_sugar else 'No'}**")
        st.write(f"Grasa saturada ≥10% kcal: **{'Sí' if fop_sat else 'No'}**")
    with colf2:
        st.write(f"Grasas trans ≥1% kcal: **{'Sí' if fop_trans else 'No'}**")
        st.write(f"Sodio (criterio aplicable): **{'Sí' if fop_sodium else 'No'}**")
    with colf3:
        st.write(f"Contiene edulcorantes: **{'Sí' if fop_sweet else 'No'}**")

# ============================================================
# ESTILO GRÁFICO
# ============================================================
BORDER_W       = 6
GRID_W         = 3
GRID_W_THICK   = 9
TEXT_COLOR     = (0,0,0)
BG_WHITE       = (255,255,255)

FONT_TITLE     = get_font(46, bold=True)
FONT_LABEL     = get_font(30, bold=False)
FONT_LABEL_B   = get_font(30, bold=True)
FONT_SMALL     = get_font(24, bold=False)   # más compacto
FONT_SMALL_B   = get_font(24, bold=True)
FONT_MICRO     = get_font(22, bold=False)
FONT_MICRO_B   = get_font(22, bold=True)

ROW_H          = 58
ROW_H_MICRO    = 48
CELL_PAD_X     = 18
CELL_PAD_Y     = 12

def column_labels():
    return ("Por 100 g" if not is_liquid else "Por 100 mL", "Por porción")

# ============================================================
# FILAS
# ============================================================
def common_rows():
    rows = [
        ("Grasa total",            f"{fmt_g(fat_total_100_r)} g",       f"{fmt_g(fat_total_pp_r)} g",        0, False, False),
        ("  Grasa saturada",       f"{fmt_g(sat_fat_100_r)} g",         f"{fmt_g(sat_fat_pp_r)} g",          1, True,  False),
        ("  Grasas trans",         f"{fmt_mg(trans_fat_100_mg_r)} mg",  f"{fmt_mg(trans_fat_pp_mg_r)} mg",   1, True,  False),
        ("Carbohidratos totales",  f"{fmt_g(carb_100_r)} g",            f"{fmt_g(carb_pp_r)} g",             0, False, False),
        ("  Fibra dietaria",       f"{fmt_g(fiber_100_r)} g",           f"{fmt_g(fiber_pp_r)} g",            1, False, False),
        ("  Azúcares totales",     f"{fmt_g(sug_total_100_r)} g",       f"{fmt_g(sug_total_pp_r)} g",        1, False, False),
        ("  Azúcares añadidos",    f"{fmt_g(sug_added_100_r)} g",       f"{fmt_g(sug_added_pp_r)} g",        1, True,  False),
        ("Proteína",               f"{fmt_g(protein_100_r)} g",         f"{fmt_g(protein_pp_r)} g",          0, False, False),
        ("Sodio",                  f"{fmt_mg(sodium_100_mg_r)} mg",     f"{fmt_mg(sodium_pp_mg_r)} mg",      0, True,  False),
    ]
    return rows

def micro_rows():
    # Orden específico: Hierro antes que Calcio cuando ambos existan
    items = list(vm_values_rounded.items())
    def sort_key(item):
        (name, unit) = item[0]
        # Fuerza Hierro primero, luego Calcio; el resto por nombre
        if name == "Hierro": return (0, name)
        if name == "Calcio": return (1, name)
        return (2, name)
    items.sort(key=sort_key)

    rows = []
    for (name, unit), v100 in items:
        vpp = vm_pp[(name, unit)]
        # formateo decimales por reglas
        v100_txt = f"{format_micronutrient(name, unit, v100)} {unit}"
        vpp_txt  = f"{format_micronutrient(name, unit, vpp)} {unit}"
        rows.append((name, v100_txt, vpp_txt, 0, False, True))
    return rows

# ============================================================
# COLUMNA DINÁMICA
# ============================================================
def compute_col_positions(d, rows_nutri, rows_micro, kcal_100_txt, kcal_pp_txt, W, header_h, gap_after_title, colhdr_h, foot_h):
    # Determinar anchos máximos con padding
    max_label_w = 0
    pad_extra = 10  # margen adicional para que no corte palabras
    indent_px = 28

    def consider_label(lbl, indent):
        nonlocal max_label_w
        w,_ = text_size(d, lbl, FONT_LABEL if indent==0 else FONT_LABEL)
        max_label_w = max(max_label_w, CELL_PAD_X + indent*indent_px + w + pad_extra)

    for label, _, _, indent, _, _ in rows_nutri:
        consider_label(label, indent)
    for label, _, _, indent, _, _ in rows_micro:
        consider_label(label, indent)

    # ancho de "Por 100" y "Por porción"
    c100, cpp = column_labels()
    w_c100,_ = text_size(d, c100, FONT_SMALL_B)
    w_cpp,_  = text_size(d, cpp,  FONT_SMALL_B)

    # ancho estimado números (tomar máximos)
    def max_val_width(rows):
        mw100 = 0
        mwpp  = 0
        for _, v100, vpp, _, _, _ in rows:
            w1,_ = text_size(d, v100, FONT_LABEL)
            w2,_ = text_size(d, vpp,  FONT_LABEL)
            mw100 = max(mw100, w1)
            mwpp  = max(mwpp,  w2)
        return mw100, mwpp

    mw100_1, mwpp_1 = max_val_width(rows_nutri)
    mw100_2, mwpp_2 = max_val_width(rows_micro)
    mw100 = max(mw100_1, mw100_2, text_size(d, kcal_100_txt, FONT_LABEL_B)[0])
    mwpp  = max(mwpp_1, mwpp_2, text_size(d, kcal_pp_txt,  FONT_LABEL_B)[0])

    # construir posiciones
    col_x = [0,0,0,0]
    col_x[0] = BORDER_W
    col_x[1] = max(BORDER_W + int(W*0.50), BORDER_W + max_label_w)  # separa etiqueta del resto según texto
    sep_min = 80  # separación mínima anti solape
    col_x[2] = max(col_x[1] + sep_min, W - BORDER_W - mwpp - mw100 - sep_min)
    col_x[3] = max(col_x[2] + sep_min + mw100, W - BORDER_W - mwpp)

    # evitar sobreposición de encabezados
    if (col_x[2] - col_x[1]) < (w_c100 + 2*CELL_PAD_X):
        col_x[2] = col_x[1] + w_c100 + 2*CELL_PAD_X + 10
    if (col_x[3] - col_x[2]) < (w_cpp + 2*CELL_PAD_X):
        col_x[3] = col_x[2] + w_cpp + 2*CELL_PAD_X + 10
    if col_x[3] > W - BORDER_W:
        col_x[3] = W - BORDER_W

    return col_x

# ============================================================
# BLOQUE CALORÍAS
# ============================================================
def draw_calories_combined_row(d, W, y, col_x, kcal_100_txt, kcal_pp_txt):
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    row_h = ROW_H
    y_text_center = y + (row_h // 2) - 14

    d.text((BORDER_W + CELL_PAD_X, y_text_center), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)
    w100,_ = text_size(d, kcal_100_txt, FONT_LABEL_B)
    wpp,_  = text_size(d, kcal_pp_txt,  FONT_LABEL_B)

    d.text((col_x[2] - CELL_PAD_X - w100, y_text_center), kcal_100_txt, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - CELL_PAD_X - wpp,  y_text_center), kcal_pp_txt,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    draw_hline(d, BORDER_W, W-BORDER_W, y + row_h, TEXT_COLOR, GRID_W_THICK)
    return y + row_h

# ============================================================
# FIGURA 1 — VERTICAL ESTÁNDAR
# ============================================================
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1400
    header_h = 130
    gap_after_title = 6
    colhdr_h = 60
    foot_h = 90

    # imagen con altura provisional; se ajusta al final
    H = 2200
    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # título
    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 10), title, fill=TEXT_COLOR, font=FONT_TITLE)

    # porciones
    y0 = BORDER_W + 10 + th + 2
    d.text((BORDER_W + CELL_PAD_X, y0 + 10),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, y0 + 10 + 28),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    # encabezado de columnas
    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    c100, cpp = column_labels()

    kcal_100_txt = fmt_kcal(kcal_100)
    kcal_pp_txt  = fmt_kcal(kcal_pp)
    col_x = compute_col_positions(d, rows_nutri, rows_micro if show_micro else [], kcal_100_txt, kcal_pp_txt, W, header_h, gap_after_title, colhdr_h, foot_h)

    w_c100,_ = text_size(d, c100, FONT_SMALL_B)
    w_cpp,_  = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2] - CELL_PAD_X - w_c100, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - CELL_PAD_X - w_cpp,  y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    data_top    = y
    # verticales
    draw_vline(d, col_x[1], data_top, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], data_top, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)

    # calorías
    y = draw_calories_combined_row(d, W, y+1, col_x, kcal_100_txt, kcal_pp_txt)

    # filas
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text  = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = text_size(d, v100, font_val)
        wvpp,_  = text_size(d, vpp,  font_val)
        d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # micronutrientes
    if show_micro:
        for label, v100, vpp, indent, _, _ in rows_micro:
            y += 1
            draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
            x_label = BORDER_W + CELL_PAD_X + indent*28
            y_text  = y + (ROW_H_MICRO//2) - 12
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100,_ = text_size(d, v100, FONT_MICRO)
            wvpp,_  = text_size(d, vpp,  FONT_MICRO)
            d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # pie condicional
    if footnote_tail.strip():
        d.text((BORDER_W + CELL_PAD_X, y + 16),
               f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
               fill=TEXT_COLOR, font=FONT_SMALL)
        y += 40

    # Redibuja verticales con límite correcto y dibuja marco al final
    data_bottom = y + GRID_W_THICK + 10
    draw_vline(d, col_x[1], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, data_bottom, TEXT_COLOR, GRID_W)

    # Dibuja marco externo usando la altura final
    d.rectangle([0,0,W-1,int(data_bottom)+BORDER_W], outline=TEXT_COLOR, width=BORDER_W)

    # Recortar imagen a la altura final
    H_final = int(data_bottom) + BORDER_W
    img = img.crop((0,0,W,H_final))
    return img

# ============================================================
# FIGURA 3 — SIMPLIFICADO
# ============================================================
def draw_fig3():
    # filas con dummy para compatibilidad (6 elementos)
    rows = [
        ("Grasa total",            f"{fmt_g(fat_total_100_r)} g",    f"{fmt_g(fat_total_pp_r)} g",         0, False, False),
        ("  Grasa saturada",       f"{fmt_g(sat_fat_100_r)} g",      f"{fmt_g(sat_fat_pp_r)} g",           1, True,  False),
        ("  Grasas trans",         f"{fmt_mg(trans_fat_100_mg_r)} mg", f"{fmt_mg(trans_fat_pp_mg_r)} mg",  1, True,  False),
        ("Carbohidratos totales",  f"{fmt_g(carb_100_r)} g",         f"{fmt_g(carb_pp_r)} g",              0, False, False),
        ("  Azúcares añadidos",    f"{fmt_g(sug_added_100_r)} g",    f"{fmt_g(sug_added_pp_r)} g",         1, True,  False),
        ("Proteína",               f"{fmt_g(protein_100_r)} g",      f"{fmt_g(protein_pp_r)} g",           0, False, False),
        ("Sodio",                  f"{fmt_mg(sodium_100_mg_r)} mg",  f"{fmt_mg(sodium_pp_mg_r)} mg",       0, True,  False),
    ]

    W = 1200
    header_h = 120
    gap_after_title = 6
    colhdr_h = 60
    foot_h = 90

    H = 1800
    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W-tw)//2, BORDER_W+10), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 8),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 8 + 26),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    c100, cpp = column_labels()
    kcal_100_txt = fmt_kcal(kcal_100)
    kcal_pp_txt  = fmt_kcal(kcal_pp)
    col_x = compute_col_positions(d, rows, [], kcal_100_txt, kcal_pp_txt, W, header_h, gap_after_title, colhdr_h, foot_h)

    w1,_ = text_size(d, c100, FONT_SMALL_B)
    w2,_ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2]-CELL_PAD_X-w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3]-CELL_PAD_X-w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    data_top = y
    draw_vline(d, col_x[1], data_top, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], data_top, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)

    # Calorías (celda combinada)
    y = draw_calories_combined_row(d, W, y+1, col_x, kcal_100_txt, kcal_pp_txt)

    # Filas
    for label, v100, vpp, indent, bold, _ in rows:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = text_size(d, v100, font_val)
        wvpp,_  = text_size(d, vpp,  font_val)
        d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    if footnote_tail.strip():
        d.text((BORDER_W + CELL_PAD_X, y + 16),
               f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
               fill=TEXT_COLOR, font=FONT_SMALL)
        y += 36

    data_bottom = y + GRID_W_THICK + 10
    draw_vline(d, col_x[1], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, data_bottom, TEXT_COLOR, GRID_W)

    # Marco externo al final
    d.rectangle([0,0,W-1,int(data_bottom)+BORDER_W], outline=TEXT_COLOR, width=BORDER_W)
    H_final = int(data_bottom) + BORDER_W
    img = img.crop((0,0,W,H_final))
    return img

# ============================================================
# FIGURA 4 — TABULAR
# ============================================================
def draw_fig4():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1500
    header_h = 130
    gap_after_title = 6
    colhdr_h = 60
    foot_h = 90

    H = 2200
    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)

    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W-tw)//2, BORDER_W+10), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 8),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 8 + 26),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    c100, cpp = column_labels()
    kcal_100_txt = fmt_kcal(kcal_100)
    kcal_pp_txt  = fmt_kcal(kcal_pp)
    col_x = compute_col_positions(d, rows_nutri, rows_micro if show_micro else [], kcal_100_txt, kcal_pp_txt, W, header_h, gap_after_title, colhdr_h, foot_h)

    w1,_ = text_size(d, c100, FONT_SMALL_B)
    w2,_ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2]-CELL_PAD_X-w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3]-CELL_PAD_X-w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    draw_vline(d, col_x[1], y, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], y, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], y, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)

    # Calorías
    y = draw_calories_combined_row(d, W, y+1, col_x, kcal_100_txt, kcal_pp_txt)

    # Resto filas
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = text_size(d, v100, font_val)
        wvpp,_  = text_size(d, vpp,  font_val)
        d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    if show_micro:
        for label, v100, vpp, indent, _, _ in rows_micro:
            y += 1
            draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
            x_label = BORDER_W + CELL_PAD_X + indent*28
            y_text = y + (ROW_H_MICRO//2) - 12
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100,_ = text_size(d, v100, FONT_MICRO)
            wvpp,_  = text_size(d, vpp,  FONT_MICRO)
            d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO

        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    if footnote_tail.strip():
        d.text((BORDER_W + CELL_PAD_X, y + 16),
               f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
               fill=TEXT_COLOR, font=FONT_SMALL)
        y += 36

    data_bottom = y + GRID_W_THICK + 10
    draw_vline(d, col_x[1], BORDER_W + header_h + gap_after_title + colhdr_h, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], BORDER_W + header_h + gap_after_title + colhdr_h, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], BORDER_W + header_h + gap_after_title + colhdr_h, data_bottom, TEXT_COLOR, GRID_W)

    # Marco externo ajustado al final
    d.rectangle([0,0,W-1,int(data_bottom)+BORDER_W], outline=TEXT_COLOR, width=BORDER_W)
    H_final = int(data_bottom) + BORDER_W
    img = img.crop((0,0,W,H_final))
    return img

# ============================================================
# FIGURA 5 — LINEAL (estilo Resolución 810)
# ============================================================
def draw_fig5():
    # Texto corrido, sin marco, separado por "•"
    items = []

    def pair(name, vpp, v100):
        items.append(f"{name}: {vpp} (por 100: {v100})")

    pair("Calorías", f"{fmt_kcal(kcal_pp)} kcal", f"{fmt_kcal(kcal_100)} kcal")
    pair("Grasa total", f"{fmt_g(fat_total_pp_r)} g", f"{fmt_g(fat_total_100_r)} g")
    pair("Grasa saturada", f"{fmt_g(sat_fat_pp_r)} g", f"{fmt_g(sat_fat_100_r)} g")
    pair("Grasas trans", f"{fmt_mg(trans_fat_pp_mg_r)} mg", f"{fmt_mg(trans_fat_100_mg_r)} mg")
    pair("Carbohidratos totales", f"{fmt_g(carb_pp_r)} g", f"{fmt_g(carb_100_r)} g")
    pair("Azúcares totales", f"{fmt_g(sug_total_pp_r)} g", f"{fmt_g(sug_total_100_r)} g")
    pair("Azúcares añadidos", f"{fmt_g(sug_added_pp_r)} g", f"{fmt_g(sug_added_100_r)} g")
    pair("Fibra dietaria", f"{fmt_g(fiber_pp_r)} g", f"{fmt_g(fiber_100_r)} g")
    pair("Proteína", f"{fmt_g(protein_pp_r)} g", f"{fmt_g(protein_100_r)} g")
    pair("Sodio", f"{fmt_mg(sodium_pp_mg_r)} mg", f"{fmt_mg(sodium_100_mg_r)} mg")

    # micronutrientes (Hierro antes que Calcio)
    items_micro = list(vm_values_rounded.items())
    def sort_key(item):
        (name, unit) = item[0]
        if name == "Hierro": return (0, name)
        if name == "Calcio": return (1, name)
        return (2, name)
    items_micro.sort(key=sort_key)

    for (name, unit), v100 in items_micro:
        vpp  = vm_pp[(name, unit)]
        vpp_txt  = f"{format_micronutrient(name, unit, vpp)} {unit}"
        v100_txt = f"{format_micronutrient(name, unit, v100)} {unit}"
        pair(name, vpp_txt, v100_txt)

    W = 1600
    H = 600
    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)

    left_x = BORDER_W + 16
    y = BORDER_W + 16

    # encabezado simple, sin marco
    d.text((left_x, y),
           f"Información nutricional por porción: {household_name} ({int(round(portion_size))} {portion_unit}) – Porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL_B)
    y += 40

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
        y += 40

    if footnote_tail.strip():
        y += 6
        d.text((left_x, y),
               f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
               fill=TEXT_COLOR, font=FONT_SMALL)

    # recorte a la altura real
    H_final = min(y + 80, H)
    img = img.crop((0,0,W,H_final))
    return img

# ============================================================
# PREVISUALIZACIÓN + EXPORTACIÓN
# ============================================================
st.header("Previsualización")
left, right = st.columns([0.72, 0.28])
with right:
    export_btn = st.button("Generar PNG", use_container_width=True)

with left:
    if format_choice.startswith("Fig. 1"):
        img_prev = draw_fig1()
    elif format_choice.startswith("Fig. 3"):
        img_prev = draw_fig3()
    elif format_choice.startswith("Fig. 4"):
        img_prev = draw_fig4()
    else:
        img_prev = draw_fig5()
    st.image(img_prev, caption="Vista previa (PNG)", use_column_width=True)

if export_btn:
    buf = BytesIO()
    img_prev.save(buf, format="PNG")
    buf.seek(0)
    fname = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    st.download_button("Descargar PNG", data=buf, file_name=fname, mime="image/png")
