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

def get_font(size, bold=False):
    try:
        font_path = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()

def draw_hline(draw, x1, x2, y, color, width=2):
    """Dibuja una línea horizontal."""
    draw.line([(x1, y), (x2, y)], fill=color, width=width)

def draw_vline(draw, x, y1, y2, color, width=2):
    """Dibuja una línea vertical."""
    draw.line([(x, y1), (x, y2)], fill=color, width=width)



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
      - [0.5, 100) → 1 decimal (consistencia visual de esta app)
      - >=100 → entero
    """
    av = abs(v)
    if av >= 100:
        return float(int(round(v, 0)))
    else:
        return float(round(v, 1))

def round_mg(v_mg):
    # Sodio < 5 mg → 0 mg (no significativo). En general mg a entero.
    if v_mg < 5:
        return 0
    return int(round(v_mg))

# --------- Formatos solicitados por nutriente (solo impresión, no cambia cálculos) ---------
def fmt_one_decimal(v):
    try:
        return f"{float(v):.1f}"
    except:
        return "0.0"

def fmt_carbs_rule(v):
    """
    Carbohidratos totales: sin decimales si tiene 2 cifras (10-99), si solo tiene una cifra (<10) lleva un decimal.
    >=100 sin decimales.
    """
    try:
        v = float(v)
    except:
        return "0"
    av = abs(v)
    if av < 10:
        return f"{v:.1f}".rstrip('0').rstrip('.') if v % 1 != 0 else f"{v:.1f}"
    if av < 100:
        return f"{int(round(v))}"
    return f"{int(round(v))}"

def fmt_int(v):
    try:
        return f"{int(round(float(v)))}"
    except:
        return "0"

def fmt_default_g(x):
    """Imprime g sin ceros de cola: 3.0 -> 3 ; 3.5 -> 3.5"""
    try:
        x = float(x)
    except:
        return "0"
    if float(x).is_integer():
        return f"{int(x)}"
    return f"{x:.1f}".rstrip('0').rstrip('.')

# Micronutrientes (reglas de visualización)
def fmt_micro_value(name, unit, v):
    """
    Reglas pedidas:
    - Vitamina A: si tiene menos de 2 cifras (<10) incluir un decimal. Unidad: µg ER.
    - Vitamina D: si <1 incluir 2 decimales; si una cifra (<10) 1 decimal; si 3 cifras (>=100) sin decimales.
    - Resto: si 3 cifras (>=100) sin decimales; si una cifra (<10) 1 decimal; en otros casos 0 o 1 decimal según magnitud.
    """
    try:
        v = float(v)
    except:
        return f"0 {unit}"
    # Unidad especial para Vitamina A
    if name == "Vitamina A":
        unit = "µg ER"
        if abs(v) < 10:
            return f"{v:.1f} {unit}"
        if abs(v) >= 100:
            return f"{int(round(v))} {unit}"
        return f"{int(round(v))} {unit}"
    if name == "Vitamina D":
        if abs(v) < 1:
            return f"{v:.2f} {unit}"
        if abs(v) < 10:
            return f"{v:.1f} {unit}"
        if abs(v) >= 100:
            return f"{int(round(v))} {unit}"
        return f"{int(round(v))} {unit}"
    # Otros micronutrientes
    if abs(v) >= 100:
        return f"{int(round(v))} {unit}"
    if abs(v) < 10:
        return f"{v:.1f} {unit}"
    return f"{int(round(v))} {unit}"

# ============================================================
# SIDEBAR (estructura como tu código)
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
    default=["Vitamina A","Calcio","Hierro","Vitamina D","Zinc"]
)

st.sidebar.subheader("Texto al pie")
footnote_tail = st.sidebar.text_input(
    "Completa: No es fuente significativa de ...",
    value=""
)

# ============================================================
# ENTRADAS (CUERPO PRINCIPAL) — por 100 g/mL
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
with vm_col1:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 0:
            unit = ("µg ER" if vm == "Vitamina A" else ("µg" if vm in ("Vitamina D","Vitamina B12") else "mg"))
            vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))
with vm_col2:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 1:
            unit = ("µg ER" if vm == "Vitamina A" else ("µg" if vm in ("Vitamina D","Vitamina B12") else "mg"))
            vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))

# ============================================================
# CÁLCULOS (porción, calorías, redondeos/no significativas)
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

# Aplicar “no significativas” por nutriente (criterios prácticos)
def nonsig_zero_g(name, v):
    # Cero solo para grasas clave; no anular carbohidratos/azúcares/fibra/proteína
    if name == "Grasa total" and v < 0.5: return 0.0
    if name in ("Grasa saturada","Grasas trans") and v < 0.1: return 0.0
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
# trans por 100: entra en mg, convertimos a g para evaluar no significativo y regresamos a mg
_trans_g_100        = (trans_fat_100_mg or 0.0)/1000.0
_trans_g_100        = nonsig_zero_g("Grasas trans", _trans_g_100)
trans_fat_100_mg_r  = round_mg(_trans_g_100*1000.0)

# Por porción (redondeados)
fat_total_pp_r     = round_g(nonsig_zero_g("Grasa total",       fat_total_pp))
sat_fat_pp_r       = round_g(nonsig_zero_g("Grasa saturada",    sat_fat_pp))
carb_pp_r          = round_g(nonsig_zero_g("Carbohidratos totales", carb_pp))
sug_total_pp_r     = round_g(nonsig_zero_g("Azúcares totales",  sug_total_pp))
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

# Micronutrientes por porción (mg/µg -> guardamos valores, el formato aplica al imprimir)
vm_pp = {}
vm_values_rounded = {}
for (name, unit), v100 in vm_values.items():
    vpp = portion_from_per100(v100, portion_size)
    vm_values_rounded[(name, unit)] = v100  # mantener valor crudo, formateo abajo
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

# ============== Helper: medición y columnas compactas por contenido ==============
def measure_text(draw, text, font):
    bbox = draw.textbbox((0,0), text, font=font)
    return bbox[2]-bbox[0], bbox[3]-bbox[1]

def compute_cols_compact(draw, labels, v100_list, vpp_list, W, left_margin=20, right_margin=20):
    """
    Calcula posiciones de columnas en base al contenido más largo.
    Evita columna fantasma; deja "Por porción" pegada al borde interno.
    """
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

    # Columnas: [borde izq, después de nombres, después de por100, borde der]
    x0 = BORDER_W + left_margin
    x1 = x0 + CELL_PAD_X + name_w_max + CELL_PAD_X                  # fin columna de nombres
    x2 = x1 + v100_w_max + CELL_PAD_X + 10                          # fin "por 100"
    x3 = (W - BORDER_W - right_margin)                              # borde derecho interno

    # Si porción necesita más, ajusta x2 para dejar espacio al valor por porción
    # Alinearemos los números a la derecha de sus columnas
    return [x0 - (BORDER_W-0), x1, x2, x3]

# ============================================================
# FILAS (usando redondeos)
# ============================================================
def common_rows():
    # Valores con formatos pedidos por nutriente
    rows = [
        ("Grasa total",            f"{fmt_one_decimal(fat_total_100_r)} g",     f"{fmt_one_decimal(fat_total_pp_r)} g",       0, False, False),
        ("  Grasa saturada",       f"{fmt_one_decimal(sat_fat_100_r)} g",       f"{fmt_one_decimal(sat_fat_pp_r)} g",         1, True,  False),
        ("  Grasas trans",         f"{fmt_int(trans_fat_100_mg_r)} mg",         f"{fmt_int(trans_fat_pp_mg_r)} mg",           1, True,  False),
        ("Carbohidratos totales",  f"{fmt_carbs_rule(carb_100_r)} g",           f"{fmt_carbs_rule(carb_pp_r)} g",             0, False, False),
        ("  Fibra dietaria",       f"{fmt_one_decimal(fiber_100_r)} g",         f"{fmt_one_decimal(fiber_pp_r)} g",           1, False, False),
        ("  Azúcares totales",     f"{fmt_one_decimal(sug_total_100_r)} g",     f"{fmt_one_decimal(sug_total_pp_r)} g",       1, False, False),
        ("  Azúcares añadidos",    f"{fmt_one_decimal(sug_added_100_r)} g",     f"{fmt_one_decimal(sug_added_pp_r)} g",       1, True,  False),
        ("Proteína",               f"{fmt_one_decimal(protein_100_r)} g",       f"{fmt_one_decimal(protein_pp_r)} g",         0, False, False),
        ("Sodio",                  f"{fmt_int(sodium_100_mg_r)} mg",            f"{fmt_int(sodium_pp_mg_r)} mg",              0, True,  False),
    ]
    return rows

def micro_rows():
    # Orden solicitado: Hierro antes que Calcio
    order = ["Hierro","Calcio","Zinc","Potasio","Vitamina A","Vitamina D","Vitamina C","Vitamina E","Vitamina B1","Vitamina B12"]
    # Filtrar solo los seleccionados, respetando el orden definido
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

# ============================================================
# BLOQUE CALORÍAS (celda combinada) — helper reutilizable
# ============================================================
def draw_calories_combined_row(d, W, y, col_x, kcal_100_txt, kcal_pp_txt):
    # línea gruesa arriba
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # altura de la fila combinada
    row_h = ROW_H
    y_text_center = y + (row_h // 2) - 14

    # título a la izquierda
    d.text((BORDER_W + CELL_PAD_X, y_text_center), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)

    # valores centrados en sus columnas
    w100, _ = measure_text(d, kcal_100_txt, FONT_LABEL_B)
    wpp,  _ = measure_text(d, kcal_pp_txt,  FONT_LABEL_B)

    d.text((col_x[2] - CELL_PAD_X - w100, y_text_center), kcal_100_txt, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - CELL_PAD_X - wpp,  y_text_center), kcal_pp_txt,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    # línea gruesa abajo
    draw_hline(d, BORDER_W, W-BORDER_W, y + row_h, TEXT_COLOR, GRID_W_THICK)

    return y + row_h  # retorna y al final del bloque

# ============================================================
# FIGURA 1 — VERTICAL ESTÁNDAR
# ============================================================
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1200  # más compacto
    header_h = 140
    gap_after_title = 10
    colhdr_h = 70
    foot_h = 110 if footnote_tail.strip() else 30

    body_rows_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + ROW_H + GRID_W_THICK + body_rows_h + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # marco (se dibuja al final con H real, pero dejamos contorno base)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # título
    title = "Información Nutricional"
    tw, th = measure_text(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 10), title, fill=TEXT_COLOR, font=FONT_TITLE)

    # porciones
    y0 = BORDER_W + 10 + th + 6
    d.text((BORDER_W + CELL_PAD_X, y0 + 16),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, y0 + 16 + 36),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    # línea gruesa tras encabezado
    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # etiquetas de columnas
    c100, cpp = column_labels()
    w_c100, _ = measure_text(d, c100, FONT_SMALL_B)
    w_cpp,  _ = measure_text(d, cpp,  FONT_SMALL_B)

    # Calcular columnas compactas usando contenido de filas
    labels_all = [r[0] for r in rows_nutri] + ([r[0] for r in rows_micro] if show_micro else [])
    v100_all   = [r[1] for r in rows_nutri] + ([r[1] for r in rows_micro] if show_micro else [])
    vpp_all    = [r[2] for r in rows_nutri] + ([r[2] for r in rows_micro] if show_micro else [])
    col_x = compute_cols_compact(d, labels_all, v100_all+[c100], vpp_all+[cpp], W, left_margin=20, right_margin=20)

    d.text((col_x[2] - CELL_PAD_X - w_c100, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - CELL_PAD_X - w_cpp,  y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    # línea fina bajo encabezados de columnas
    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    # verticales
    data_top    = y
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], data_top, data_bottom, TEXT_COLOR, GRID_W)  # entre nombre y valores
    draw_vline(d, col_x[2], data_top, data_bottom, TEXT_COLOR, GRID_W)
    # (removida) línea vertical final

    # ------- BLOQUE CALORÍAS (celda combinada, sin línea media que corte texto) -------
    kcal_100_txt = f"{fmt_int(kcal_100)}"
    kcal_pp_txt  = f"{fmt_int(kcal_pp)}"
    y = draw_calories_combined_row(d, W, y+1, col_x, kcal_100_txt, kcal_pp_txt)

    # filas macronutrientes
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
        d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    # micronutrientes
    if show_micro:
        for label, v100, vpp, indent, _, _ in rows_micro:
            y += 1
            draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
            x_label = BORDER_W + CELL_PAD_X + indent*28
            y_text  = y + (ROW_H_MICRO//2) - 12
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100,_ = measure_text(d, v100, FONT_MICRO)
            wvpp,_  = measure_text(d, vpp,  FONT_MICRO)
            d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO

        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # pie (opcional)
    if footnote_tail.strip():
        d.text((BORDER_W + CELL_PAD_X, y + 20), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ============================================================
# FIGURA 3 — SIMPLIFICADO
# ============================================================
def draw_fig3():
    rows = [
        ("Grasa total",            f"{fmt_one_decimal(fat_total_100_r)} g",  f"{fmt_one_decimal(fat_total_pp_r)} g",   0, False),
        ("  Grasa saturada",       f"{fmt_one_decimal(sat_fat_100_r)} g",    f"{fmt_one_decimal(sat_fat_pp_r)} g",     1, True),
        ("  Grasas trans",         f"{fmt_int(trans_fat_100_mg_r)} mg",      f"{fmt_int(trans_fat_pp_mg_r)} mg",       1, True),
        ("Carbohidratos totales",  f"{fmt_carbs_rule(carb_100_r)} g",        f"{fmt_carbs_rule(carb_pp_r)} g",         0, False),
        ("  Azúcares añadidos",    f"{fmt_one_decimal(sug_added_100_r)} g",  f"{fmt_one_decimal(sug_added_pp_r)} g",   1, True),
        ("Proteína",               f"{fmt_one_decimal(protein_100_r)} g",    f"{fmt_one_decimal(protein_pp_r)} g",     0, False),
        ("Sodio",                  f"{fmt_int(sodium_100_mg_r)} mg",         f"{fmt_int(sodium_pp_mg_r)} mg",          0, True),
    ]
    W = 1100  # compacto
    header_h = 140
    gap_after_title = 10
    colhdr_h = 70
    foot_h = 110 if footnote_tail.strip() else 30

    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + ROW_H + GRID_W_THICK + len(rows)*ROW_H + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    title = "Información Nutricional"
    tw, th = measure_text(d, title, FONT_TITLE)
    d.text(((W-tw)//2, BORDER_W+10), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16 + 36),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    c100, cpp = column_labels()
    w1,_ = measure_text(d, c100, FONT_SMALL_B)
    w2,_ = measure_text(d, cpp,  FONT_SMALL_B)

    labels_all = [r[0] for r in rows]
    v100_all   = [r[1] for r in rows]
    vpp_all    = [r[2] for r in rows]
    col_x = compute_cols_compact(d, labels_all, v100_all+[c100], vpp_all+[cpp], W, left_margin=20, right_margin=20)

    d.text((col_x[2]-CELL_PAD_X-w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3]-CELL_PAD_X-w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    data_top = y
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], data_top, data_bottom, TEXT_COLOR, GRID_W)  # vertical extra
    draw_vline(d, col_x[2], data_top, data_bottom, TEXT_COLOR, GRID_W)
    # (removida) línea vertical final

    # Calorías (celda combinada)
    y = draw_calories_combined_row(d, W, y+1, col_x, fmt_int(kcal_100), fmt_int(kcal_pp))

    # Filas
    for label, v100, vpp, indent, bold in rows:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = measure_text(d, v100, font_val)
        wvpp,_  = measure_text(d, vpp,  font_val)
        d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    if footnote_tail.strip():
        d.text((BORDER_W + CELL_PAD_X, y + 20), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ============================================================
# FIGURA 4 — TABULAR (con vertical extra)
# ============================================================
def draw_fig4():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1300  # compacto
    header_h = 140
    gap_after_title = 10
    colhdr_h = 70
    foot_h = 110 if footnote_tail.strip() else 30

    body_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + ROW_H + GRID_W_THICK + body_h + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    title = "Información Nutricional"
    tw, th = measure_text(d, title, FONT_TITLE)
    d.text(((W-tw)//2, BORDER_W+10), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16 + 36),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    c100, cpp = column_labels()
    w1,_ = measure_text(d, c100, FONT_SMALL_B)
    w2,_ = measure_text(d, cpp,  FONT_SMALL_B)

    labels_all = [r[0] for r in rows_nutri] + ([r[0] for r in rows_micro] if show_micro else [])
    v100_all   = [r[1] for r in rows_nutri] + ([r[1] for r in rows_micro] if show_micro else [])
    vpp_all    = [r[2] for r in rows_nutri] + ([r[2] for r in rows_micro] if show_micro else [])
    col_x = compute_cols_compact(d, labels_all, v100_all+[c100], vpp_all+[cpp], W, left_margin=20, right_margin=20)

    d.text((col_x[2]-CELL_PAD_X-w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3]-CELL_PAD_X-w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    data_bottom_limit = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], y, data_bottom_limit, TEXT_COLOR, GRID_W)  # vertical extra
    draw_vline(d, col_x[2], y, data_bottom_limit, TEXT_COLOR, GRID_W)
    # (removida) línea vertical final

    # Calorías (celda combinada)
    y = draw_calories_combined_row(d, W, y+1, col_x, fmt_int(kcal_100), fmt_int(kcal_pp))

    # Resto filas
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = measure_text(d, v100, font_val)
        wvpp,_  = measure_text(d, vpp,  font_val)
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
            wv100,_ = measure_text(d, v100, FONT_MICRO)
            wvpp,_  = measure_text(d, vpp,  FONT_MICRO)
            d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO

        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    if footnote_tail.strip():
        d.text((BORDER_W + CELL_PAD_X, y + 20), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ============================================================
# FIGURA 5 — LINEAL
# ============================================================
def draw_fig5():
    items = []

    def pair(name, vpp, v100):
        items.append(f"{name}: {vpp} (por 100: {v100})")

    pair("Calorías", f"{fmt_kcal(kcal_pp)} kcal", f"{fmt_kcal(kcal_100)} kcal")
    pair("Grasa total", f"{round(fat_total_pp,1):.1f} g", f"{round(fat_total_100,1):.1f} g")
    pair("Grasa saturada", f"{round(sat_fat_pp,1):.1f} g", f"{round(sat_fat_100,1):.1f} g")
    pair("Grasas trans", f"{fmt_mg(trans_fat_pp_mg)} mg", f"{fmt_mg(trans_fat_100_mg)} mg")
    pair("Carbohidratos totales", ((f"{round(carb_pp,1):.1f}" if abs(carb_pp)<10 else f"{int(round(carb_pp))}") + " g"),
         ((f"{round(carb_100,1):.1f}" if abs(carb_100)<10 else f"{int(round(carb_100))}") + " g"))
    pair("Azúcares totales", f"{round(sug_total_pp,1):.1f} g", f"{round(sug_total_100,1):.1f} g")
    pair("Azúcares añadidos", f"{round(sug_added_pp,1):.1f} g", f"{round(sug_added_100,1):.1f} g")
    pair("Fibra dietaria", f"{round(fiber_pp,1):.1f} g", f"{round(fiber_100,1):.1f} g")
    pair("Proteína", f"{round(protein_pp,1):.1f} g", f"{round(protein_100,1):.1f} g")
    pair("Sodio", f"{int(round(sodium_pp_mg))} mg", f"{int(round(sodium_100_mg))} mg")

    for (name, unit), v100 in vm_values.items():
        vpp  = portion_from_per100(v100, portion_size)
        unit_out = "µg ER" if name == "Vitamina A" else unit
        # aplicar regla micro
        def fmicro_line(v):
            v = float(v)
            if name == "Vitamina D":
                if abs(v) < 1: 
                    return f"{v:.2f} {unit_out}"
                elif abs(v) < 100:
                    return f"{v:.1f} {unit_out}"
                else:
                    return f"{int(round(v))} {unit_out}"
            if abs(v) >= 100:
                return f"{int(round(v))} {unit_out}"
            return f"{v:.1f} {unit_out}"
        pair(name, fmicro_line(vpp), fmicro_line(v100))

    # Canvas dinámico
    W = 1600
    left_x = BORDER_W + 28
    top_y = BORDER_W + 28

    # Medimos líneas
    from PIL import Image, ImageDraw
    img_probe = Image.new("RGB", (W, 2000), BG_WHITE)
    d_probe = ImageDraw.Draw(img_probe)

    header_text = f"Información nutricional (por porción): Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})   •   Número de porciones por envase: {int(round(servings_per_pack))}"
    FONT_HDR = FONT_SMALL_B
    _, h_hdr = d_probe.textbbox((0,0), header_text, font=FONT_HDR)[2:4]
    line_h = 46

    s = "  •  ".join(items)
    words = s.split(" ")
    line = ""
    lines = []
    maxw = W - left_x - 30
    def textw(txt, font): 
        bbox = d_probe.textbbox((0,0), txt, font=font)
        return bbox[2]-bbox[0]
    for w in words:
        t = (line + " " + w).strip()
        if textw(t, FONT_LABEL) <= maxw:
            line = t
        else:
            lines.append(line); line = w
    if line: lines.append(line)

    # Altura total
    H = top_y + h_hdr + 52 + len(lines)*line_h + 30 + 40 + BORDER_W*2
    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    # Marco único grueso
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=GRID_W_THICK)

    y = top_y
    d.text((left_x, y), header_text, fill=TEXT_COLOR, font=FONT_HDR)
    y += 52
    for ln in lines:
        d.text((left_x, y), ln, fill=TEXT_COLOR, font=FONT_LABEL)
        y += line_h
    y += 10
    if footnote_tail.strip():
        d.text((left_x, y), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)
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
