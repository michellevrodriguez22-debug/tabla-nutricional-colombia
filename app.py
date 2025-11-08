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

# Reglas de redondeo por tipo de nutriente (ajuste fino solicitado)
def round_grams_by_field(name: str, v: float) -> float:
    """
    - Grasa total y saturada: 1 decimal siempre
    - Grasas trans: se trabaja en mg en la tabla (redondeo entero/1 decimal controlado en mg)
    - Carbohidratos totales: 10–99 → sin decimales; <10 → 1 decimal; ≥100 → entero
    - Fibra, Azúcares totales, Azúcares añadidos, Proteína: 1 decimal
    """
    if name in ("Grasa total", "Grasa saturada"):
        return float(round(v, 1))

    if name == "Carbohidratos totales":
        av = abs(v)
        if av < 10:
            return float(round(v, 1))
        elif av < 100:
            # sin decimales
            return float(int(round(v, 0)))
        else:
            return float(int(round(v, 0)))

    if name in ("Fibra dietaria", "Azúcares totales", "Azúcares añadidos", "Proteína"):
        return float(round(v, 1))

    # Por defecto (nunca debería caer aquí para los g usados)
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
    value="Proteína, Vitamina D, Hierro, Calcio, Zinc, Vitamina A y fibra."
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
    sug_total_100  = as_num(st.text_input("Azúcares totales (g/100)", value="1.1"))
    sug_added_100  = as_num(st.text_input("Azúcares añadidos (g/100)", value="2"))
with c3:
    fiber_100      = as_num(st.text_input("Fibra dietaria (g/100)", value="0.8"))
    protein_100    = as_num(st.text_input("Proteína (g/100)", value="5"))
    sodium_100_mg  = as_num(st.text_input("Sodio (mg/100)", value="560"))

st.markdown("---")
st.subheader("Valores de micronutrientes seleccionados (por 100)")
vm_values = {}
vm_col1, vm_col2 = st.columns([0.5, 0.5])

# Mapeo de unidades (Vit A en µg ER)
def micronutrient_unit(name: str) -> str:
    if name == "Vitamina A":
        return "µg ER"
    if name in ("Vitamina D", "Vitamina B12"):
        return "µg"
    return "mg"

with vm_col1:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 0:
            unit = micronutrient_unit(vm)
            vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))
with vm_col2:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 1:
            unit = micronutrient_unit(vm)
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
    # Reglas usadas:
    #   Grasa total < 0.5 g → 0
    #   Saturada/Trans < 0.1 g → 0
    #   Carbohidratos/Fibra/Proteína < 0.5 g → 0
    #   *** Azúcares totales: NO se aplica el corte <0.5 → 0 para conservar 0.3 g, etc. ***
    if name == "Grasa total" and v < 0.5: return 0.0
    if name in ("Grasa saturada","Grasas trans") and v < 0.1: return 0.0
    if name in ("Carbohidratos totales","Azúcares añadidos","Fibra dietaria","Proteína") and v < 0.5: return 0.0
    # Azúcares totales: no cero por no significativo (se muestra 0.1, 0.2, 0.3, etc. con 1 decimal)
    return v

def nonsig_zero_mg(name, vmg):
    if name == "Sodio" and vmg < 5: return 0
    return vmg

# Por 100 (redondeados)
fat_total_100_r     = round_grams_by_field("Grasa total",       nonsig_zero_g("Grasa total",       fat_total_100))
sat_fat_100_r       = round_grams_by_field("Grasa saturada",    nonsig_zero_g("Grasa saturada",    sat_fat_100))
carb_100_r          = round_grams_by_field("Carbohidratos totales", nonsig_zero_g("Carbohidratos totales", carb_100))
sug_total_100_r     = round_grams_by_field("Azúcares totales",  nonsig_zero_g("Azúcares totales",  sug_total_100))
sug_added_100_r     = round_grams_by_field("Azúcares añadidos", nonsig_zero_g("Azúcares añadidos", sug_added_100))
fiber_100_r         = round_grams_by_field("Fibra dietaria",    nonsig_zero_g("Fibra dietaria",    fiber_100))
protein_100_r       = round_grams_by_field("Proteína",          nonsig_zero_g("Proteína",          protein_100))
sodium_100_mg_r     = round_mg(nonsig_zero_mg("Sodio",          sodium_100_mg))
# trans por 100: entra en mg, convertimos a g para evaluar no significativo y regresamos a mg
_trans_g_100        = (trans_fat_100_mg or 0.0)/1000.0
_trans_g_100        = nonsig_zero_g("Grasas trans", _trans_g_100)
# Para trans en mg: si es <100 mg mostramos con 1 decimal, si no entero (lo haremos en fmt específico más abajo)
trans_fat_100_mg_r  = max(0, _trans_g_100*1000.0)

# Por porción (redondeados)
fat_total_pp_r     = round_grams_by_field("Grasa total",       nonsig_zero_g("Grasa total",       fat_total_pp))
sat_fat_pp_r       = round_grams_by_field("Grasa saturada",    nonsig_zero_g("Grasa saturada",    sat_fat_pp))
carb_pp_r          = round_grams_by_field("Carbohidratos totales", nonsig_zero_g("Carbohidratos totales", carb_pp))
sug_total_pp_r     = round_grams_by_field("Azúcares totales",  nonsig_zero_g("Azúcares totales",  sug_total_pp))
sug_added_pp_r     = round_grams_by_field("Azúcares añadidos", nonsig_zero_g("Azúcares añadidos", sug_added_pp))
fiber_pp_r         = round_grams_by_field("Fibra dietaria",    nonsig_zero_g("Fibra dietaria",    fiber_pp))
protein_pp_r       = round_grams_by_field("Proteína",          nonsig_zero_g("Proteína",          protein_pp))
sodium_pp_mg_r     = round_mg(nonsig_zero_mg("Sodio",          sodium_pp_mg))
# trans por porción (mg)
_trans_g_pp        = (trans_fat_pp_mg or 0.0)/1000.0
_trans_g_pp        = nonsig_zero_g("Grasas trans", _trans_g_pp)
trans_fat_pp_mg_r  = max(0, _trans_g_pp*1000.0)

# Calorías finales redondeadas
kcal_100 = round_kcal(kcal_100_raw)
kcal_pp  = round_kcal(kcal_pp_raw)

# ===== Micronutrientes por porción (reglas de redondeo específicas) =====
def round_micro_value(name: str, unit: str, v: float) -> float:
    """
    Reglas solicitadas (aplican a todos los micronutrientes):
    - < 1  → 2 decimales
    - 1–99.9 → 1 decimal
    - 3 cifras (>= 100) → entero
    Excepción de Vitamina A (ya expresada en µg ER): si < 10 → 1 decimal, si >=10 → entero.
    """
    if name == "Vitamina A":
        if v < 10:
            return float(round(v, 1))
        else:
            return float(int(round(v, 0)))

    if v < 1:
        return float(round(v, 2))
    elif v < 100:
        return float(round(v, 1))
    else:
        return float(int(round(v, 0)))

vm_pp = {}
vm_values_rounded = {}
for (name, unit), v100 in vm_values.items():
    vpp = portion_from_per100(v100, portion_size)
    vm_values_rounded[(name, unit)] = round_micro_value(name, unit, v100)
    vm_pp[(name, unit)]             = round_micro_value(name, unit, vpp)

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
# ESTILO GRÁFICO (ajustado para compacidad)
# ============================================================
BORDER_W       = 6
GRID_W         = 3
GRID_W_THICK   = 9
TEXT_COLOR     = (0,0,0)
BG_WHITE       = (255,255,255)

FONT_TITLE     = get_font(44, bold=True)
FONT_LABEL     = get_font(28, bold=False)
FONT_LABEL_B   = get_font(28, bold=True)
FONT_SMALL     = get_font(24, bold=False)
FONT_SMALL_B   = get_font(24, bold=True)
FONT_MICRO     = get_font(23, bold=False)
FONT_MICRO_B   = get_font(23, bold=True)

# Más compacto
ROW_H          = 54
ROW_H_MICRO    = 46
CELL_PAD_X     = 18
CELL_PAD_Y     = 12

def column_labels():
    return ("Por 100 g" if not is_liquid else "Por 100 mL", "Por porción")

# ============================================================
# COLS DINÁMICAS por ancho de texto (verticales ajustadas)
# ============================================================
def compute_col_positions(d, rows_nutri, rows_micro, kcal_100_txt, kcal_pp_txt, W, header_h, gap_after_title, colhdr_h, foot_h):
    """
    Calcula col_x[1], col_x[2], col_x[3] según el ancho real de:
      - Columna de etiquetas (incluyendo indent)
      - Columna "Por 100"
      - Columna "Por porción"
    Mantiene W fijo, las verticales se mueven para compactar.
    """
    # 1) Ancho máximo de etiqueta (incluye el indent de 1 nivel con +28 px)
    max_label_w = 0
    for label, _, _, indent, _, _ in rows_nutri:
        w,_ = text_size(d, label, FONT_LABEL if not _ else FONT_LABEL)
        max_label_w = max(max_label_w, w + indent*28)
    for label, _, _, indent, _, _ in rows_micro:
        w,_ = text_size(d, label, FONT_MICRO)
        max_label_w = max(max_label_w, w + indent*28)
    # Incluir "Calorías (kcal)"
    wcal,_ = text_size(d, "Calorías (kcal)", FONT_LABEL_B)
    max_label_w = max(max_label_w, wcal)

    # 2) Ancho máximo de valores
    max_v100_w = 0
    max_vpp_w  = 0
    # Recorremos valores de filas nutri
    for _, v100, vpp, _, _, _ in rows_nutri:
        w1,_ = text_size(d, v100, FONT_LABEL)
        w2,_ = text_size(d, vpp,  FONT_LABEL)
        max_v100_w = max(max_v100_w, w1)
        max_vpp_w  = max(max_vpp_w,  w2)
    # Recorremos valores de filas micro
    for _, v100, vpp, _, _, _ in rows_micro:
        w1,_ = text_size(d, v100, FONT_MICRO)
        w2,_ = text_size(d, vpp,  FONT_MICRO)
        max_v100_w = max(max_v100_w, w1)
        max_vpp_w  = max(max_vpp_w,  w2)
    # Incluir calorías
    w1,_ = text_size(d, kcal_100_txt, FONT_LABEL_B)
    w2,_ = text_size(d, kcal_pp_txt,  FONT_LABEL_B)
    max_v100_w = max(max_v100_w, w1)
    max_vpp_w  = max(max_vpp_w,  w2)

    # Armado de posiciones (de izquierda a derecha)
    left = BORDER_W
    col1_right = left + CELL_PAD_X + max_label_w + CELL_PAD_X
    col2_right = col1_right + CELL_PAD_X + max_v100_w + CELL_PAD_X
    col3_right = col2_right + CELL_PAD_X + max_vpp_w  + CELL_PAD_X

    # Si nos pasamos del ancho W, comprimimos paddings mínimos
    total_needed = col3_right + BORDER_W
    if total_needed > W:
        # Reducir paddings al mínimo de 12 px si hace falta
        pad = max(12, CELL_PAD_X - 4)
        col1_right = left + pad + max_label_w + pad
        col2_right = col1_right + pad + max_v100_w + pad
        col3_right = col2_right + pad + max_vpp_w  + pad
        total_needed = col3_right + BORDER_W
        # Si aún excede, forzamos col3 al borde y mantenemos proporciones.
        if total_needed > W:
            overflow = total_needed - W
            col1_right -= int(overflow*0.2)
            col2_right -= int(overflow*0.3)
            col3_right -= int(overflow*0.5)
            if col1_right < left + 80: col1_right = left + 80
            if col2_right < col1_right + 120: col2_right = col1_right + 120
            if col3_right > W - BORDER_W: col3_right = W - BORDER_W

    return [left, int(col1_right), int(col2_right), int(col3_right)]

# ============================================================
# FORMATEO DE TRANS (mg) CON REGLA: <100 mg → 1 decimal, si no entero
# ============================================================
def fmt_trans_mg(mg_value: float) -> str:
    try:
        v = float(mg_value)
    except:
        return "0 mg"
    if abs(v) < 100:
        return f"{v:.1f} mg".rstrip('0').rstrip('.')
    return f"{int(round(v))} mg"

# ============================================================
# FILAS (usando redondeos)
# ============================================================
def common_rows():
    rows = [
        ("Grasa total",            f"{fmt_g(fat_total_100_r)} g",       f"{fmt_g(fat_total_pp_r)} g",        0, False, False),
        ("  Grasa saturada",       f"{fmt_g(sat_fat_100_r)} g",         f"{fmt_g(sat_fat_pp_r)} g",          1, True,  False),
        ("  Grasas trans",         f"{fmt_trans_mg(trans_fat_100_mg_r)}",  f"{fmt_trans_mg(trans_fat_pp_mg_r)}",   1, True,  False),
        ("Carbohidratos totales",  f"{fmt_g(carb_100_r)} g",            f"{fmt_g(carb_pp_r)} g",             0, False, False),
        ("  Fibra dietaria",       f"{fmt_g(fiber_100_r)} g",           f"{fmt_g(fiber_pp_r)} g",            1, False, False),
        ("  Azúcares totales",     f"{fmt_g(sug_total_100_r)} g",       f"{fmt_g(sug_total_pp_r)} g",        1, False, False),
        ("  Azúcares añadidos",    f"{fmt_g(sug_added_100_r)} g",       f"{fmt_g(sug_added_pp_r)} g",        1, True,  False),
        ("Proteína",               f"{fmt_g(protein_100_r)} g",         f"{fmt_g(protein_pp_r)} g",          0, False, False),
        ("Sodio",                  f"{fmt_mg(sodium_100_mg_r)} mg",     f"{fmt_mg(sodium_pp_mg_r)} mg",      0, True,  False),
    ]
    return rows

# Orden de micronutrientes (Hierro antes que Calcio)
MICRO_ORDER = ["Vitamina A","Vitamina D","Vitamina C","Vitamina E","Vitamina B1","Vitamina B12","Hierro","Calcio","Zinc","Potasio"]

def micro_rows():
    # Reordenar según MICRO_ORDER, pero solo los seleccionados
    present = {name for (name, _), _v in vm_values_rounded.items()}
    order = [m for m in MICRO_ORDER if m in present]

    # Construcción, respetando unidades y redondeo textual
    rows_temp = []
    for (name, unit), v100 in vm_values_rounded.items():
        vpp = vm_pp[(name, unit)]
        # Mostrar decimal según unidad y valor ya redondeado
        if unit in ("mg",):
            v100_txt = f"{fmt_mg(v100)} {unit}"
            vpp_txt  = f"{fmt_mg(vpp)} {unit}"
        else:
            # µg o µg ER
            # si entero, entero; si no, con 1-2 decimales según reglas ya aplicadas
            if float(v100).is_integer():
                v100_txt = f"{int(v100)} {unit}"
            else:
                # si tiene 1 decimal (como Vit A <10) o 2 dec (otros <1) ya viene así
                # imprimimos tal cual con hasta 2 decimales
                v100_txt = f"{v100}".rstrip('0').rstrip('.') + f" {unit}"
            if float(vpp).is_integer():
                vpp_txt = f"{int(vpp)} {unit}"
            else:
                vpp_txt = f"{vpp}".rstrip('0').rstrip('.') + f" {unit}"
        rows_temp.append((name, v100_txt, vpp_txt, 0, False, True))

    # Ordenar rows_temp por el orden deseado
    name_to_row = {r[0]: r for r in rows_temp}
    rows = [name_to_row[n] for n in order if n in name_to_row]
    return rows

# ============================================================
# BLOQUE CALORÍAS (celda combinada)
# ============================================================
def draw_calories_combined_row(d, W, y, col_x, kcal_100_txt, kcal_pp_txt):
    # línea gruesa arriba
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # altura de la fila combinada
    row_h = ROW_H
    y_text_center = y + (row_h // 2) - 14

    # título a la izquierda
    d.text((BORDER_W + CELL_PAD_X, y_text_center), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)

    # valores centrados en sus columnas (derecha de las columnas de valores)
    w100, _ = text_size(d, kcal_100_txt, FONT_LABEL_B)
    wpp,  _ = text_size(d, kcal_pp_txt,  FONT_LABEL_B)

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

    W = 1300  # un poco más angosto por compacidad
    header_h = 130
    gap_after_title = 6
    colhdr_h = 64

    # Pie opcional (si el usuario no escribe, no reservamos espacio)
    foot_text = footnote_tail.strip().rstrip('.')
    show_foot = len(foot_text) > 0
    foot_h = 96 if show_foot else 0

    # Altura estimada del cuerpo
    body_rows_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + ROW_H + GRID_W_THICK + body_rows_h + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # Precalcular columnas dinámicas según contenido (antes de dibujar)
    kcal_100_txt = fmt_kcal(kcal_100)
    kcal_pp_txt  = fmt_kcal(kcal_pp)
    col_x = compute_col_positions(d, rows_nutri, rows_micro, kcal_100_txt, kcal_pp_txt, W, header_h, gap_after_title, colhdr_h, foot_h)

    # marco
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # título
    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 8), title, fill=TEXT_COLOR, font=FONT_TITLE)

    # porciones
    y0 = BORDER_W + 8 + th + 2
    d.text((BORDER_W + CELL_PAD_X, y0 + 12),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, y0 + 12 + 30),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    # línea gruesa tras encabezado
    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # etiquetas de columnas
    c100, cpp = column_labels()
    w_c100, _ = text_size(d, c100, FONT_SMALL_B)
    w_cpp,  _ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2] - CELL_PAD_X - w_c100, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - CELL_PAD_X - w_cpp,  y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    # línea fina bajo encabezados de columnas
    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    # verticales
    data_top    = y
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, data_bottom, TEXT_COLOR, GRID_W)

    # BLOQUE CALORÍAS
    y = draw_calories_combined_row(d, W, y+1, col_x, kcal_100_txt, kcal_pp_txt)

    # filas macronutrientes
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text  = y + (ROW_H//2) - 12
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
            y_text  = y + (ROW_H_MICRO//2) - 10
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100,_ = text_size(d, v100, FONT_MICRO)
            wvpp,_  = text_size(d, vpp,  FONT_MICRO)
            d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO

        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # pie (solo si el usuario escribió algo)
    if show_foot:
        d.text((BORDER_W + CELL_PAD_X, y + 16),
               f"No es fuente significativa de {foot_text}",
               fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ============================================================
# FIGURA 3 — SIMPLIFICADO
# ============================================================
def draw_fig3():
    rows = [
        ("Grasa total",            f"{fmt_g(fat_total_100_r)} g",    f"{fmt_g(fat_total_pp_r)} g",         0, False),
        ("  Grasa saturada",       f"{fmt_g(sat_fat_100_r)} g",      f"{fmt_g(sat_fat_pp_r)} g",           1, True),
        ("  Grasas trans",         f"{fmt_trans_mg(trans_fat_100_mg_r)}", f"{fmt_trans_mg(trans_fat_pp_mg_r)}",  1, True),
        ("Carbohidratos totales",  f"{fmt_g(carb_100_r)} g",         f"{fmt_g(carb_pp_r)} g",              0, False),
        ("  Azúcares añadidos",    f"{fmt_g(sug_added_100_r)} g",    f"{fmt_g(sug_added_pp_r)} g",         1, True),
        ("Proteína",               f"{fmt_g(protein_100_r)} g",      f"{fmt_g(protein_pp_r)} g",           0, False),
        ("Sodio",                  f"{fmt_mg(sodium_100_mg_r)} mg",  f"{fmt_mg(sodium_pp_mg_r)} mg",       0, True),
    ]
    W = 1200
    header_h = 130
    gap_after_title = 6
    colhdr_h = 60

    foot_text = footnote_tail.strip().rstrip('.')
    show_foot = len(foot_text) > 0
    foot_h = 90 if show_foot else 0

    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + ROW_H + GRID_W_THICK + len(rows)*ROW_H + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    kcal_100_txt = fmt_kcal(kcal_100)
    kcal_pp_txt  = fmt_kcal(kcal_pp)
    # Para simplified, no hay micro; pasamos lista vacía
    col_x = compute_col_positions(d, rows, [], kcal_100_txt, kcal_pp_txt, W, header_h, gap_after_title, colhdr_h, foot_h)

    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W-tw)//2, BORDER_W+8), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 8 + th + 12),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 8 + th + 12 + 28),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    c100, cpp = column_labels()
    w1,_ = text_size(d, c100, FONT_SMALL_B)
    w2,_ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2]-CELL_PAD_X-w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3]-CELL_PAD_X-w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    data_top = y
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, data_bottom, TEXT_COLOR, GRID_W)

    # Calorías (celda combinada)
    y = draw_calories_combined_row(d, W, y+1, col_x, fmt_kcal(kcal_100), fmt_kcal(kcal_pp))

    # Filas
    for label, v100, vpp, indent, bold in rows:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - 12
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = text_size(d, v100, font_val)
        wvpp,_  = text_size(d, vpp,  font_val)
        d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    if show_foot:
        d.text((BORDER_W + CELL_PAD_X, y + 16),
               f"No es fuente significativa de {foot_text}",
               fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ============================================================
# FIGURA 4 — TABULAR (con vertical extra)
# ============================================================
def draw_fig4():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1400
    header_h = 130
    gap_after_title = 6
    colhdr_h = 60

    foot_text = footnote_tail.strip().rstrip('.')
    show_foot = len(foot_text) > 0
    foot_h = 90 if show_foot else 0

    body_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + ROW_H + GRID_W_THICK + body_h + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)

    kcal_100_txt = fmt_kcal(kcal_100)
    kcal_pp_txt  = fmt_kcal(kcal_pp)
    col_x = compute_col_positions(d, rows_nutri, rows_micro, kcal_100_txt, kcal_pp_txt, W, header_h, gap_after_title, colhdr_h, foot_h)

    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W-tw)//2, BORDER_W+8), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 8 + th + 12),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 8 + th + 12 + 28),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    c100, cpp = column_labels()
    w1,_ = text_size(d, c100, FONT_SMALL_B)
    w2,_ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2]-CELL_PAD_X-w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3]-CELL_PAD_X-w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    data_bottom_limit = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], y, data_bottom_limit, TEXT_COLOR, GRID_W)  # vertical extra
    draw_vline(d, col_x[2], y, data_bottom_limit, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], y, data_bottom_limit, TEXT_COLOR, GRID_W)

    # Calorías (celda combinada)
    y = draw_calories_combined_row(d, W, y+1, col_x, fmt_kcal(kcal_100), fmt_kcal(kcal_pp))

    # Resto filas
    rows_n = rows_nutri
    for label, v100, vpp, indent, bold, _ in rows_n:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - 12
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
            y_text = y + (ROW_H_MICRO//2) - 10
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100,_ = text_size(d, v100, FONT_MICRO)
            wvpp,_ = text_size(d, vpp,  FONT_MICRO)
            d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO

        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    if show_foot:
        d.text((BORDER_W + CELL_PAD_X, y + 16),
               f"No es fuente significativa de {foot_text}",
               fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ============================================================
# FIGURA 5 — LINEAL
# ============================================================
def draw_fig5():
    items = []

    def pair(name, vpp, v100):
        items.append(f"{name}: {vpp} (por 100: {v100})")

    pair("Calorías", f"{fmt_kcal(kcal_pp)} kcal", f"{fmt_kcal(kcal_100)} kcal")
    pair("Grasa total", f"{fmt_g(fat_total_pp_r)} g", f"{fmt_g(fat_total_100_r)} g")
    pair("Grasa saturada", f"{fmt_g(sat_fat_pp_r)} g", f"{fmt_g(sat_fat_100_r)} g")
    pair("Grasas trans", f"{fmt_trans_mg(trans_fat_pp_mg_r)}", f"{fmt_trans_mg(trans_fat_100_mg_r)}")
    pair("Carbohidratos totales", f"{fmt_g(carb_pp_r)} g", f"{fmt_g(carb_100_r)} g")
    pair("Azúcares totales", f"{fmt_g(sug_total_pp_r)} g", f"{fmt_g(sug_total_100_r)} g")
    pair("Azúcares añadidos", f"{fmt_g(sug_added_pp_r)} g", f"{fmt_g(sug_added_100_r)} g")
    pair("Fibra dietaria", f"{fmt_g(fiber_pp_r)} g", f"{fmt_g(fiber_100_r)} g")
    pair("Proteína", f"{fmt_g(protein_pp_r)} g", f"{fmt_g(protein_100_r)} g")
    pair("Sodio", f"{fmt_mg(sodium_pp_mg_r)} mg", f"{fmt_mg(sodium_100_mg_r)} mg")

    for (name, unit), v100 in vm_values_rounded.items():
        vpp  = vm_pp[(name, unit)]
        # texto ya redondeado por reglas
        if unit == "mg":
            vpp_txt  = f"{fmt_mg(vpp)} {unit}"
            v100_txt = f"{fmt_mg(v100)} {unit}"
        else:
            if float(vpp).is_integer():
                vpp_txt = f"{int(vpp)} {unit}"
            else:
                vpp_txt = f"{vpp}".rstrip('0').rstrip('.') + f" {unit}"
            if float(v100).is_integer():
                v100_txt = f"{int(v100)} {unit}"
            else:
                v100_txt = f"{v100}".rstrip('0').rstrip('.') + f" {unit}"
        pair(name, vpp_txt, v100_txt)

    W = 1600
    H = 580
    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    left_x = BORDER_W + 24
    y = BORDER_W + 24
    d.text((left_x, y),
           f"Información nutricional (por porción): Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})   •   Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL_B)
    y += 44

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
        y += 42

    foot_text = footnote_tail.strip().rstrip('.')
    if foot_text:
        y += 8
        d.text((left_x, y),
               f"No es fuente significativa de {foot_text}",
               fill=TEXT_COLOR, font=FONT_SMALL)
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
