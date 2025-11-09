# app.py
# ============================================================
# Generador de Tabla Nutricional (Colombia) -> PNG (solo PNG)
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Fig.1 (Vertical), Fig.3 (Simplificado), Fig.5 (Lineal)
# Entradas por 100 g / 100 mL. Cálculo por porción y kcal corregidos.
# Bloque "Calorías" con celda combinada (título centrado verticalmente),
# manteniendo columnas "Por 100" y "Por porción" independientes.
# ============================================================

from io import BytesIO
from datetime import datetime
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# --- Parche seguro: helpers de líneas por si no están en global ---
if 'draw_hline' not in globals():
    def draw_hline(draw, x0, x1, y, color, width):
        draw.line((x0, y, x1, y), fill=color, width=width)

if 'draw_vline' not in globals():
    def draw_vline(draw, x, y0, y1, color, width):
        draw.line((x, y0, x, y1), fill=color, width=width)
# --- Fin parche ---

# ============================================================
# FUNCIÓN PARA CARGAR FUENTES — AÑADIDO POR EL PATCHER
# ============================================================
def get_font(size, bold=False):
    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()

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
    include_poly = st.checkbox("Incluir polialcoholes", value=False, help="Agrega polialcoholes al rotulado")
    poly_100 = as_num(st.text_input("Polialcoholes (g/100)", value="0")) if include_poly else 0.0
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
poly_pp         = portion_from_per100(poly_100, portion_size) if "poly_100" in globals() or "poly_100" in locals() else 0.0
sodium_pp_mg    = portion_from_per100(sodium_100_mg, portion_size)

# Energía (antes de redondear)
kcal_100_raw = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp_raw  = kcal_from_macros(fat_total_pp,  carb_pp,  protein_pp)

# Aplicar "no significativas" por nutriente (criterios prácticos)
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
poly_100_r          = round_g(poly_100) if "poly_100" in globals() or "poly_100" in locals() else 0.0
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
poly_pp_r          = round_g(poly_pp) if "poly_pp" in globals() or "poly_pp" in locals() else 0.0
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

def compute_cols_vertical(draw, labels, v100_list, vpp_list, W):
    """
    Calcula posiciones de columnas para VERTICAL ESTÁNDAR - AJUSTADO AL CONTENIDO REAL
    """
    # Medir ancho máximo de nombres de nutrientes
    name_w_max = 0
    for t in labels:
        w,_ = measure_text(draw, t, FONT_LABEL)
        if w > name_w_max: name_w_max = w

    # Medir ancho máximo de valores "Por 100"
    v100_w_max = 0
    for t in v100_list:
        w,_ = measure_text(draw, t, FONT_LABEL)
        if w > v100_w_max: v100_w_max = w

    # Medir ancho máximo de valores "Por porción"
    vpp_w_max = 0
    for t in vpp_list:
        w,_ = measure_text(draw, t, FONT_LABEL)
        if w > vpp_w_max: vpp_w_max = w

    # Medir ancho de los encabezados de columna
    col100_label, colpp_label = column_labels()
    col100_w, _ = measure_text(draw, col100_label, FONT_SMALL_B)
    colpp_w, _ = measure_text(draw, colpp_label, FONT_SMALL_B)

    # Medir específicamente "Azúcares añadidos" para asegurar espacio suficiente
    azucares_added_width, _ = measure_text(draw, "  Azúcares añadidos", FONT_LABEL)
    
    # Usar el MÁXIMO entre todos los nombres y "Azúcares añadidos" específicamente + MARGEN EXTRA
    final_name_width = max(name_w_max, azucares_added_width) + 15  # MARGEN EXTRA de 15 píxeles

    # Espacios entre columnas
    name_to_values_gap = 35
    values_gap = 20
    right_margin = 15  # REDUCIDO de 20 a 15

    # Calcular posiciones basadas en el contenido real
    x0 = BORDER_W + CELL_PAD_X  # Inicio de nombres
    
    # Asegurar que la línea quede BIEN DESPUÉS del texto más largo CON MARGEN EXTRA
    x1 = x0 + final_name_width + name_to_values_gap  # Línea después de nombres
    
    # Ancho para columna "Por 100" - usar el máximo entre valores y encabezado + margen
    col100_width = max(v100_w_max, col100_w) + 15
    
    x2 = x1 + col100_width + values_gap  # Línea entre columnas de valores
    
    # Ancho para columna "Por porción" - usar el máximo entre valores y encabezado + margen REDUCIDO
    colpp_width = max(vpp_w_max, colpp_w) + 4  # REDUCIDO de 15 a 8
    
    x3 = x2 + colpp_width + right_margin  # Fin de la tabla

    # Calcular ancho total necesario
    total_width_needed = x3
    
    # Si el ancho necesario es mayor que el actual, aumentarlo
    if total_width_needed > W:
        W = total_width_needed + BORDER_W * 2

    return [x0, x1, x2, x3], W

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
        # Inserción condicional de polialcoholes
    if include_poly:
        rows.append(("  Polialcoholes", f"{fmt_one_decimal(poly_100_r)} g", f"{fmt_one_decimal(poly_pp_r)} g", 1, False, False))

    return rows

def micro_rows():
    # Orden solicitado: Hierro antes que Calcio
    order = ["Vitamina A","Vitamina D","Vitamina C","Vitamina E","Vitamina B1","Vitamina B12","Calcio","Hierro","Zinc","Potasio"]
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
# BLOQUE CALORÍAS CORREGIDO
# ============================================================
def draw_calories_combined_row(d, W, y, col_x, kcal_100_txt, kcal_pp_txt):
    """
    Bloque calorías con líneas verticales desde arriba hasta abajo
    """
    row_h = ROW_H * 2  # Doble altura para las 2 filas
    
    # Título "Calorías" en primera fila
    y_text_title = y + (ROW_H // 2) - 14
    d.text((BORDER_W + CELL_PAD_X, y_text_title), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)
    
    # Encabezados de columnas en primera fila
    c100, cpp = column_labels()
    w_c100, _ = measure_text(d, c100, FONT_SMALL_B)
    w_cpp, _ = measure_text(d, cpp, FONT_SMALL_B)
    
    d.text((col_x[2] - 15 - w_c100, y_text_title), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - 15 - w_cpp, y_text_title), cpp, fill=TEXT_COLOR, font=FONT_SMALL_B)
    
    # Línea horizontal divisoria entre fila de títulos y valores
    draw_hline(d, col_x[1], W-BORDER_W, y + ROW_H, TEXT_COLOR, GRID_W)
    
    # Valores en segunda fila
    y_text_values = y + ROW_H + (ROW_H // 2) - 14
    w100, _ = measure_text(d, kcal_100_txt, FONT_LABEL_B)
    wpp, _ = measure_text(d, kcal_pp_txt, FONT_LABEL_B)
    
    d.text((col_x[2] - 15 - w100, y_text_values), kcal_100_txt, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - 15 - wpp, y_text_values), kcal_pp_txt, fill=TEXT_COLOR, font=FONT_LABEL_B)
    
    return y + row_h

# ============================================================
# FIGURA 1 — VERTICAL ESTÁNDAR (ORIGINAL SIN CAMBIOS)
# ============================================================
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    # ANCHO INICIAL SUFICIENTE para evitar cortes
    W = 580
    header_h = 130
    gap_after_title = 5
    foot_h = 90 if footnote_tail.strip() else 20

    body_rows_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    
    # Altura temporal para crear imagen de prueba para mediciones
    H_temp = 100
    img_temp = Image.new("RGB", (W, H_temp), BG_WHITE)
    d_temp = ImageDraw.Draw(img_temp)
    
    # Calcular columnas BASADAS EN CONTENIDO REAL
    labels_all = [r[0] for r in rows_nutri] + ([r[0] for r in rows_micro] if show_micro else [])
    v100_all   = [r[1] for r in rows_nutri] + ([r[1] for r in rows_micro] if show_micro else [])
    vpp_all    = [r[2] for r in rows_nutri] + ([r[2] for r in rows_micro] if show_micro else [])
    
    col_x, W = compute_cols_vertical(d_temp, labels_all, v100_all, vpp_all, W)
    
    # Calcular altura final con el ancho ajustado
    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         (ROW_H * 2) + GRID_W_THICK + body_rows_h + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # marco
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # título
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

    # línea gruesa tras encabezado
    y_header_bottom = BORDER_W + header_h
    draw_hline(d, BORDER_W, W-BORDER_W, y_header_bottom, TEXT_COLOR, GRID_W_THICK)

    # BLOQUE CALORÍAS
    kcal_100_txt = f"{fmt_int(kcal_100)}"
    kcal_pp_txt  = f"{fmt_int(kcal_pp)}"
    y = draw_calories_combined_row(d, W, y_header_bottom+1, col_x, kcal_100_txt, kcal_pp_txt)

    # LÍNEA GRUESA después de calorías
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # LÍNEA GRUESA INFERIOR - después de micronutrientes
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK

    
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
        d.text((col_x[2]-15-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-15-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    # LÍNEA GRUESA entre macronutrientes y micronutrientes (si hay micronutrientes)
    if show_micro:
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

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
            d.text((col_x[2]-15-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-15-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO

    # LÍNEAS VERTICALES (hasta el final de los micronutrientes)
    draw_vline(d, col_x[1], y_header_bottom, y, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], y_header_bottom, y, TEXT_COLOR, GRID_W)


    # Línea gruesa final
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # pie (opcional)
    if footnote_tail.strip():
        d.text((BORDER_W + CELL_PAD_X, y + 15), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ============================================================
# FIGURA 3 — SIMPLIFICADO (MISMO LAYOUT, SIN MICRONUTRIENTES)
# ============================================================
def draw_fig3():
    rows_nutri = common_rows()
    rows_micro = []  # SIN micronutrientes
    W = 580
    header_h = 130
    foot_h = 90  # en simplificado siempre mostrar la frase

    # Cálculo de columnas como en vertical
    H_temp = 100
    img_temp = Image.new("RGB", (W, H_temp), BG_WHITE)
    d_temp = ImageDraw.Draw(img_temp)
    labels_all = [r[0] for r in rows_nutri]
    v100_all   = [r[1] for r in rows_nutri]
    vpp_all    = [r[2] for r in rows_nutri]
    col_x, W = compute_cols_vertical(d_temp, labels_all, v100_all, vpp_all, W)

    body_rows_h = len(rows_nutri)*ROW_H
    H = (BORDER_W*2 + header_h + GRID_W_THICK + (ROW_H * 2) + GRID_W_THICK + body_rows_h + GRID_W_THICK + foot_h)

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # Marco
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Título
    title = "Información Nutricional"
    tw, th = measure_text(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 15), title, fill=TEXT_COLOR, font=FONT_TITLE)

    # Porción
    y0 = BORDER_W + 15 + th + 12
    d.text((BORDER_W + CELL_PAD_X, y0),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, y0 + 35),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    # Línea gruesa tras encabezado
    y_header_bottom = BORDER_W + header_h
    draw_hline(d, BORDER_W, W-BORDER_W, y_header_bottom, TEXT_COLOR, GRID_W_THICK)

    # Bloque Calorías
    kcal_100_txt = f"{fmt_int(kcal_100)}"
    kcal_pp_txt  = f"{fmt_int(kcal_pp)}"
    y = draw_calories_combined_row(d, W, y_header_bottom+1, col_x, kcal_100_txt, kcal_pp_txt)

    # Línea gruesa después de calorías
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Líneas verticales
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], y_header_bottom, y + (2 * GRID_W_THICK), TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], y_header_bottom, y + (2 * GRID_W_THICK), TEXT_COLOR, GRID_W)
    
    # Filas macronutrientes (mismas que vertical)
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

    # Línea gruesa final
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # LÍNEAS VERTICALES (hasta la segunda línea gruesa, final del cuerpo)
    draw_vline(d, col_x[1], y_header_bottom, y + GRID_W_THICK, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], y_header_bottom, y + GRID_W_THICK, TEXT_COLOR, GRID_W)

    # Pie SIEMPRE visible
    tail = footnote_tail.strip()
    d.text((BORDER_W + CELL_PAD_X, y + 15), f"No es fuente significativa de {tail}", fill=TEXT_COLOR, font=FONT_SMALL)
    return img


# ----------------- Helpers for rich inline text (bold/regular) -----------------
def draw_inline_chunks(d, x, y, max_width, line_height, chunks):
    """
    chunks: list of (text, is_bold, font_regular, font_bold)
    Returns: final y after drawing
    """
    cx, cy = x, y
    for text, is_bold in chunks:
        font = FONT_LABEL_B if is_bold else FONT_LABEL
        # Split by spaces to wrap
        for token in text.split(' '):
            token_out = (token + ' ')
            tw, th = measure_text(d, token_out, font)
            if cx + tw > x + max_width:
                # new line
                cx = x
                cy += line_height
            d.text((cx, cy), token_out, fill=TEXT_COLOR, font=font)
            cx += tw
    return cy + line_height

# ============================================================
# FIGURA 5 — LINEAL
# ============================================================
def draw_fig5():
    # Tabular para empaque: sin "formato lineal" en el título
    # Construimos dos bloques: (100 g/mL) y (por porción)
    W = 1400
    H = 420
    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Encabezado general (negrilla): "Información nutricional (...)"
    basis = "(100 mL)" if is_liquid else "(100 g)"
    header1 = f"Información nutricional {basis}:"
    tw, th = measure_text(d, header1, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 10), header1, fill=TEXT_COLOR, font=FONT_TITLE)

    y0 = BORDER_W + 10 + th + 16
    draw_hline(d, BORDER_W, W-BORDER_W, y0, TEXT_COLOR, GRID_W_THICK)
    y = y0 + 16

    # ----- Bloque 1: por 100 -----
    max_text_width = W - 2*BORDER_W - 2*CELL_PAD_X
    x = BORDER_W + CELL_PAD_X
    line_h = 40

    # Lista completa por 100 (con etiquetas en negrilla donde aplica)
    chunks_100 = []
    # Calorías en negrilla
    chunks_100 += [(f"Calorías: {fmt_int(kcal_100)},", True)]
    chunks_100 += [(f"Grasa total: {fmt_one_decimal(fat_total_100_r)} g,", False)]
    chunks_100 += [(f"Sodio: {fmt_int(sodium_100_mg_r)} mg,", True)]
    chunks_100 += [(f"Carbohidratos totales: {fmt_carbs_rule(carb_100_r)} g,", False)]
    chunks_100 += [(f"Azúcares añadidos: {fmt_one_decimal(sug_added_100_r)} g,", True)]
    chunks_100 += [(f"Proteína: {fmt_one_decimal(protein_100_r)} g,", False)]
    # Micronutrientes (todos) en el orden definido
    # Usamos vm_options para asegurar presencia, con valores 0 si no fueron ingresados.
    def get_vm100(name):
        # Buscar unidad esperada
        unit = "µg ER" if name=="Vitamina A" else ("µg" if name in ("Vitamina D","Vitamina B12") else "mg")
        v = 0.0
        # si el usuario ingresó, está en vm_values_rounded
        for (n,u), val in vm_values_rounded.items():
            if n==name:
                v = val
                unit = u
        return fmt_micro_value(name, unit, v)
    for vm in ["Vitamina A","Vitamina D","Vitamina C","Vitamina E","Vitamina B1","Vitamina B12","Calcio","Hierro","Zinc","Potasio"]:
        chunks_100 += [(f"{vm}: {get_vm100(vm)},", False)]
    # Polialcoholes si aplica
    if ("include_poly" in globals() or "include_poly" in locals()) and include_poly:
        chunks_100 += [(f"Polialcoholes: {fmt_one_decimal(poly_100_r)} g,", False)]

    # Dibujado inline con negrillas selectivas
    chunks_100_draw = []
    for t,b in chunks_100:
        chunks_100_draw.append((t, b))
    y = draw_inline_chunks(d, x, y, max_text_width, line_h, chunks_100_draw)

    # ----- Bloque 2: por porción -----
    header2 = "Información nutricional (por porción):"
    tw2, th2 = measure_text(d, header2, FONT_TITLE)
    d.text(((W - tw2)//2, y + 14), header2, fill=TEXT_COLOR, font=FONT_TITLE)
    y = y + 14 + th2 + 10

    # Línea previa
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
    y += 16

    # "Tamaño de porción:" y "Número de porciones..." en negrilla, resto normal
    chunks_porcion = [
        ("Tamaño de porción:", True),
        (f" {household_name} ({int(round(portion_size))} {portion_unit})   ", False),
        ("Número de porciones por envase:", True),
        (f" {int(round(servings_per_pack))}   ", False),
        # Luego nutrientes por porción:
        (f"Calorías: {fmt_int(kcal_pp)},", True),
        (f" Grasa total: {fmt_one_decimal(fat_total_pp_r)} g,", False),
        (f" Sodio: {fmt_int(sodium_pp_mg_r)} mg,", True),
        (f" Carbohidratos totales: {fmt_carbs_rule(carb_pp_r)} g,", False),
        (f" Azúcares añadidos: {fmt_one_decimal(sug_added_pp_r)} g,", True),
        (f" Proteína: {fmt_one_decimal(protein_pp_r)} g,", False),
    ]
    # Micronutrientes por porción (todos)
    def get_vmpp(name):
        unit = "µg ER" if name=="Vitamina A" else ("µg" if name in ("Vitamina D","Vitamina B12") else "mg")
        v = 0.0
        for (n,u), val in vm_pp.items():
            if n==name:
                v = val
                unit = u
        return fmt_micro_value(name, unit, v)
    for vm in ["Vitamina A","Vitamina D","Vitamina C","Vitamina E","Vitamina B1","Vitamina B12","Calcio","Hierro","Zinc","Potasio"]:
        chunks_porcion.append((f" {vm}: {get_vmpp(vm)},", False))
    if ("include_poly" in globals() or "include_poly" in locals()) and include_poly:
        chunks_porcion.append((f" Polialcoholes: {fmt_one_decimal(poly_pp_r)} g,", False))

    y = draw_inline_chunks(d, x, y, max_text_width, line_h, chunks_porcion)

    # Pie opcional (si se escribió)
    if footnote_tail.strip():
        draw_hline(d, BORDER_W, W-BORDER_W, y+6, TEXT_COLOR, GRID_W_THICK)
        d.text((BORDER_W + CELL_PAD_X, y + 18), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)
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
    else:
        img_prev = draw_fig5()
    st.image(img_prev, caption="Vista previa (PNG)", use_column_width=True)

if export_btn:
    buf = BytesIO()
    img_prev.save(buf, format="PNG")
    buf.seek(0)
    fname = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    st.download_button("Descargar PNG", data=buf, file_name=fname, mime="image/png")
