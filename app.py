# app.py
# ============================================================
# Generador de Tabla Nutricional (Colombia) -> PNG
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Fig.1 (Vertical estándar), Fig.3 (Simplificado),
# Fig.4 (Tabular) y Fig.5 (Lineal)
# Entradas por 100 g / 100 mL | Controles clave en barra lateral
# ============================================================

from io import BytesIO
from datetime import datetime
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
st.set_page_config(page_title="Generador de Tabla Nutricional (Colombia)", layout="wide")
st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================
def as_num(x):
    try:
        if x is None or str(x).strip() == "":
            return 0.0
        return float(x)
    except:
        return 0.0

def kcal_from_macros(fat_g, carb_g, protein_g, organic_acids_g=0.0, alcohol_g=0.0):
    """Calcula calorías según los factores 9-4-4-7-3"""
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9*fat_g + 4*carb_g + 4*protein_g + 7*alcohol_g + 3*organic_acids_g
    return float(kcal)

def portion_from_per100(value_per100, portion_size):
    if portion_size and portion_size > 0:
        return (value_per100 * portion_size) / 100.0
    return 0.0

# ============================================================
# REDONDEOS Y FORMATOS SEGÚN RES. 810/2021
# ============================================================
def round_kcal(v):
    if v < 5:
        return 0
    return int(round(v))

def round_g(v):
    av = abs(v)
    if av < 0.5:
        return float(round(v, 1))
    if av >= 100:
        return float(int(round(v, 0)))
    elif av >= 10:
        return float(round(v, 1))
    else:
        return float(round(v, 1))

def round_mg(v_mg):
    if v_mg < 5:
        return 0
    return int(round(v_mg))

def fmt_g(x):
    x = float(x)
    if x.is_integer():
        return f"{int(x)}"
    return f"{x:.1f}".rstrip('0').rstrip('.')

def fmt_mg(x): return f"{int(round(x))}"
def fmt_kcal(x): return f"{int(round(x))}"

def get_font(size, bold=False):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size)
    except:
        return ImageFont.load_default()

def text_size(draw, text, font):
    bbox = draw.textbbox((0,0), text, font=font)
    return bbox[2]-bbox[0], bbox[3]-bbox[1]

def draw_hline(draw, x0, x1, y, color, width): draw.line((x0, y, x1, y), fill=color, width=width)
def draw_vline(draw, x, y0, y1, color, width): draw.line((x, y0, x, y1), fill=color, width=width)

# ============================================================
# ESTILO GRÁFICO GENERAL
# ============================================================
BORDER_W, GRID_W, GRID_W_THICK = 6, 3, 9
TEXT_COLOR, BG_WHITE = (0,0,0), (255,255,255)
FONT_TITLE   = get_font(46, bold=True)
FONT_LABEL   = get_font(30, bold=False)
FONT_LABEL_B = get_font(30, bold=True)
FONT_SMALL   = get_font(26, bold=False)
FONT_SMALL_B = get_font(26, bold=True)
FONT_MICRO   = get_font(24, bold=False)
FONT_MICRO_B = get_font(24, bold=True)
ROW_H, ROW_H_MICRO = 64, 54
CELL_PAD_X, CELL_PAD_Y = 22, 18

# ============================================================
# PANEL LATERAL — CONFIGURACIÓN
# ============================================================
st.sidebar.header("Configuración")
format_choice = st.sidebar.selectbox(
    "Formato a exportar",
    ["Fig. 1 — Vertical estándar", "Fig. 3 — Simplificado", "Fig. 4 — Tabular", "Fig. 5 — Lineal"]
)
physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])
portion_unit = "g" if "Sólido" in physical_state else "mL"

st.sidebar.subheader("Porción")
household_name = st.sidebar.text_input("Medida casera (p. ej. 1 unidad, 1 taza)", value="1 unidad")
household_mass = as_num(st.sidebar.text_input(f"Equivalencia en {portion_unit} (número)", value="40"))
servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="2"))

st.sidebar.subheader("Validación interna (no se imprime)")
contains_sweeteners = st.sidebar.checkbox("Contiene edulcorantes", value=False)

st.sidebar.subheader("Micronutrientes a declarar")
vm_options = ["Vitamina A","Vitamina D","Vitamina B1","Vitamina B12","Vitamina C","Vitamina E","Calcio","Hierro","Zinc","Potasio"]
selected_vm = st.sidebar.multiselect("Selecciona los que declararás", vm_options, default=["Vitamina A","Calcio","Hierro","Vitamina D","Zinc"])

st.sidebar.subheader("Texto al pie")
footnote_tail = st.sidebar.text_input(
    "Completa: No es fuente significativa de ...",
    value="Proteína, Vitamina D, Hierro, Calcio, Zinc, Vitamina A y fibra."
)

# ============================================================
# ENTRADAS PRINCIPALES — POR 100 g/mL
# ============================================================
st.header("Ingreso de datos por 100 g / 100 mL")
c1, c2, c3 = st.columns([0.33,0.33,0.34])
with c1:
    st.subheader("Macronutrientes")
    fat_total_100 = as_num(st.text_input("Grasa total (g/100)", "13"))
    sat_fat_100   = as_num(st.text_input("Grasa saturada (g/100)", "6"))
    trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg/100)", "820"))
with c2:
    carb_100 = as_num(st.text_input("Carbohidratos totales (g/100)", "31"))
    sug_total_100 = as_num(st.text_input("Azúcares totales (g/100)", "5"))
    sug_added_100 = as_num(st.text_input("Azúcares añadidos (g/100)", "2"))
with c3:
    fiber_100 = as_num(st.text_input("Fibra dietaria (g/100)", "0.8"))
    protein_100 = as_num(st.text_input("Proteína (g/100)", "5"))
    sodium_100_mg = as_num(st.text_input("Sodio (mg/100)", "560"))

st.markdown("---")
st.subheader("Valores de micronutrientes seleccionados (por 100)")
vm_values = {}
vm_col1, vm_col2 = st.columns(2)
for i, vm in enumerate(selected_vm):
    unit = "µg" if vm in ("Vitamina A","Vitamina D","Vitamina B12") else "mg"
    with (vm_col1 if i%2==0 else vm_col2):
        vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))

# ============================================================
# CÁLCULOS — PORCIÓN Y REDONDEO
# ============================================================
portion_size = household_mass
is_liquid = "Líquido" in physical_state
# ================================
# CÁLCULOS POR PORCIÓN (sin redondear aún)
# ================================
fat_total_pp    = portion_from_per100(fat_total_100, portion_size)
sat_fat_pp      = portion_from_per100(sat_fat_100, portion_size)
trans_fat_pp_mg = portion_from_per100(trans_fat_100_mg, portion_size)
carb_pp         = portion_from_per100(carb_100, portion_size)
sug_total_pp    = portion_from_per100(sug_total_100, portion_size)
sug_added_pp    = portion_from_per100(sug_added_100, portion_size)
fiber_pp        = portion_from_per100(fiber_100, portion_size)
protein_pp      = portion_from_per100(protein_100, portion_size)
sodium_pp_mg    = portion_from_per100(sodium_100_mg, portion_size)

# ================================
# CALORÍAS crudas (antes de redondear)
# ================================
kcal_100_raw = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp_raw  = kcal_from_macros(fat_total_pp,  carb_pp,  protein_pp)

# ================================
# “CANTIDADES NO SIGNIFICATIVAS” (heurística basada en 810/2021)
# ================================
def nonsig_zero_g(name, v):
    if name == "Grasa total" and v < 0.5: return 0.0
    if name in ("Grasa saturada","Grasas trans") and v < 0.1: return 0.0
    if name in ("Carbohidratos totales","Azúcares totales","Azúcares añadidos","Fibra dietaria","Proteína") and v < 0.5: return 0.0
    return v

def nonsig_zero_mg(name, vmg):
    if name == "Sodio" and vmg < 5: return 0
    return vmg

# ================================
# REDONDEO “POR 100”
# ================================
# trans de entrada está en mg; se evalúa “no significativa” en g y se regresa a mg
_trans_g_100 = (trans_fat_100_mg or 0.0)/1000.0
_trans_g_100 = nonsig_zero_g("Grasas trans", _trans_g_100)

fat_total_100_r     = round_g(nonsig_zero_g("Grasa total",       fat_total_100))
sat_fat_100_r       = round_g(nonsig_zero_g("Grasa saturada",    sat_fat_100))
trans_fat_100_mg_r  = round_mg(_trans_g_100*1000.0)
carb_100_r          = round_g(nonsig_zero_g("Carbohidratos totales", carb_100))
sug_total_100_r     = round_g(nonsig_zero_g("Azúcares totales",  sug_total_100))
sug_added_100_r     = round_g(nonsig_zero_g("Azúcares añadidos", sug_added_100))
fiber_100_r         = round_g(nonsig_zero_g("Fibra dietaria",    fiber_100))
protein_100_r       = round_g(nonsig_zero_g("Proteína",          protein_100))
sodium_100_mg_r     = round_mg(nonsig_zero_mg("Sodio",           sodium_100_mg))

# ================================
# REDONDEO “POR PORCIÓN”
# ================================
fat_total_pp_r     = round_g(nonsig_zero_g("Grasa total",       fat_total_pp))
sat_fat_pp_r       = round_g(nonsig_zero_g("Grasa saturada",    sat_fat_pp))
trans_fat_pp_mg_r  = round_mg(nonsig_zero_g("Grasas trans", (trans_fat_pp_mg or 0.0)/1000.0)*1000.0)
carb_pp_r          = round_g(nonsig_zero_g("Carbohidratos totales", carb_pp))
sug_total_pp_r     = round_g(nonsig_zero_g("Azúcares totales",  sug_total_pp))
sug_added_pp_r     = round_g(nonsig_zero_g("Azúcares añadidos", sug_added_pp))
fiber_pp_r         = round_g(nonsig_zero_g("Fibra dietaria",    fiber_pp))
protein_pp_r       = round_g(nonsig_zero_g("Proteína",          protein_pp))
sodium_pp_mg_r     = round_mg(nonsig_zero_mg("Sodio",           sodium_pp_mg))

# ================================
# CALORÍAS finales (regla de <5 kcal -> 0, entero)
# ================================
kcal_100 = round_kcal(kcal_100_raw)
kcal_pp  = round_kcal(kcal_pp_raw)

# ================================
# MICRONUTRIENTES: por 100 y por porción (enteros)
# ================================
vm_pp = {}
vm_values_rounded = {}
for (name, unit), v100 in vm_values.items():
    vpp = portion_from_per100(v100, portion_size)
    if unit == "mg":
        vm_values_rounded[(name, unit)] = int(round(v100))
        vm_pp[(name, unit)]             = int(round(vpp))
    else:  # µg
        vm_values_rounded[(name, unit)] = int(round(v100))
        vm_pp[(name, unit)]             = int(round(vpp))

# ================================
# VALIDACIÓN DE SELLOS (no impresa)
# ================================
def pct_kcal_from(nutrient_kcal, total_kcal_pp):
    if total_kcal_pp <= 0:
        return 0.0
    return 100.0 * nutrient_kcal / total_kcal_pp

sat_pct    = pct_kcal_from(9 * max(sat_fat_pp, 0.0),           max(kcal_pp_raw, 1e-9))
trans_pct  = pct_kcal_from(9 * max((trans_fat_pp_mg or 0)/1000.0, 0.0), max(kcal_pp_raw, 1e-9))
sug_add_pct= pct_kcal_from(4 * max(sug_added_pp, 0.0),         max(kcal_pp_raw, 1e-9))

if is_liquid:
    sodium_rule = (sodium_100_mg >= 40.0) or ((sodium_pp_mg / max(kcal_pp_raw,1e-9)) >= 1.0)
else:
    sodium_rule = (sodium_100_mg >= 300.0) or ((sodium_pp_mg / max(kcal_pp_raw,1e-9)) >= 1.0)

fop_sugar  = sug_add_pct >= 10.0
fop_sat    = sat_pct    >= 10.0
fop_trans  = trans_pct  >= 1.0
fop_sodium = sodium_rule
fop_sweet  = contains_sweeteners  # Contiene edulcorantes

with st.expander("Resultado de validación informativa (no se imprime en PNG)", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.write(f"Azúcares añadidos ≥10% kcal: *{'Sí' if fop_sugar else 'No'}*")
        st.write(f"Grasa saturada ≥10% kcal: *{'Sí' if fop_sat else 'No'}*")
    with c2:
        st.write(f"Grasas trans ≥1% kcal: *{'Sí' if fop_trans else 'No'}*")
        st.write(f"Sodio (criterio aplicable): *{'Sí' if fop_sodium else 'No'}*")
    with c3:
        st.write(f"Contiene edulcorantes: *{'Sí' if fop_sweet else 'No'}*")

# ================================
# HELPERS PARA TABLAS
# ================================
def column_labels():
    return ("Por 100 g" if not is_liquid else "Por 100 mL", "Por porción")

def common_rows():
    """Filas de macronutrientes con valores redondeados y umbrales aplicados."""
    return [
        ("Grasa total",           f"{fmt_g(fat_total_100_r)} g",        f"{fmt_g(fat_total_pp_r)} g",         0, False, False),
        ("  Grasa saturada",      f"{fmt_g(sat_fat_100_r)} g",          f"{fmt_g(sat_fat_pp_r)} g",           1, True,  False),
        ("  Grasas trans",        f"{fmt_mg(trans_fat_100_mg_r)} mg",   f"{fmt_mg(trans_fat_pp_mg_r)} mg",    1, True,  False),
        ("Carbohidratos totales", f"{fmt_g(carb_100_r)} g",             f"{fmt_g(carb_pp_r)} g",              0, False, False),
        ("  Fibra dietaria",      f"{fmt_g(fiber_100_r)} g",            f"{fmt_g(fiber_pp_r)} g",             1, False, False),
        ("  Azúcares totales",    f"{fmt_g(sug_total_100_r)} g",        f"{fmt_g(sug_total_pp_r)} g",         1, False, False),
        ("  Azúcares añadidos",   f"{fmt_g(sug_added_100_r)} g",        f"{fmt_g(sug_added_pp_r)} g",         1, True,  False),
        ("Proteína",              f"{fmt_g(protein_100_r)} g",          f"{fmt_g(protein_pp_r)} g",           0, False, False),
        ("Sodio",                 f"{fmt_mg(sodium_100_mg_r)} mg",      f"{fmt_mg(sodium_pp_mg_r)} mg",       0, True,  False),
    ]

def micro_rows():
    """Filas de micronutrientes: unidades SOLO con los valores."""
    rows = []
    for (name, unit), v100 in vm_values_rounded.items():
        vpp = vm_pp[(name, unit)]
        v100_txt = f"{fmt_mg(v100)} {unit}" if unit=="mg" else f"{int(v100)} {unit}"
        vpp_txt  = f"{fmt_mg(vpp)} {unit}"  if unit=="mg" else f"{int(vpp)} {unit}"
        rows.append((name, v100_txt, vpp_txt, 0, False, True))
    return rows

# ============================================================
# DIBUJO DE FIGURAS (con “Calorías (kcal)” en celda combinada)
# ============================================================

def _draw_header_and_colhdr(d, W, H, header_h, colhdr_h, col_x):
    """Título + bloque de porciones + línea gruesa + encabezados de columnas."""
    # Marco exterior se dibuja en cada figura fuera
    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 10), title, fill=TEXT_COLOR, font=FONT_TITLE)

    # Bloque porciones (izquierda)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16 + 36),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    # Línea gruesa debajo del encabezado
    y_line_top = BORDER_W + header_h
    draw_hline(d, BORDER_W, W-BORDER_W, y_line_top, TEXT_COLOR, GRID_W_THICK)

    # Encabezados columnas
    c100, cpp = column_labels()
    w_c100, _ = text_size(d, c100, FONT_SMALL_B)
    w_cpp,  _ = text_size(d, cpp,  FONT_SMALL_B)
    y = y_line_top + 1
    d.text((col_x[2] - CELL_PAD_X - w_c100, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - CELL_PAD_X - w_cpp,  y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    # Línea fina bajo encabezados
    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
    return y  # y es la línea base para comenzar calorías

def _draw_calories_merged_cell(d, W, y, col_x):
    """
    Dibuja el bloque de Calorías en 'celda combinada':
      - línea gruesa superior del bloque
      - UNA celda de altura ROW_H que contiene:
          * una línea fina intermedia (para mantener estética de 2 medias-filas)
          * texto 'Calorías (kcal)' centrado verticalmente
          * valores por 100 y por porción alineados en sus columnas
      - línea gruesa inferior del bloque
    Retorna y final del bloque.
    """
    # Separador grueso antes del bloque
    y += 1
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y_top = y

    # Línea fina intermedia (simula dos medias filas visualmente)
    mid_y = y_top + ROW_H//2
    draw_hline(d, BORDER_W, W-BORDER_W, mid_y, TEXT_COLOR, GRID_W)

    # Etiqueta centrada verticalmente dentro de la "celda combinada"
    d.text((BORDER_W + CELL_PAD_X, y_top + (ROW_H//2) - 14), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Valores por 100 y por porción, alineados a derecha de sus columnas
    kc100 = fmt_kcal(kcal_100)
    kcpp  = fmt_kcal(kcal_pp)
    w1,_ = text_size(d, kc100, FONT_LABEL_B)
    w2,_ = text_size(d, kcpp,  FONT_LABEL_B)
    d.text((col_x[2] - CELL_PAD_X - w1, y_top + (ROW_H//2) - 14), kc100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - CELL_PAD_X - w2, y_top + (ROW_H//2) - 14), kcpp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Línea gruesa al finalizar el bloque
    y = y_top + ROW_H
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    return y

# ---------------- Fig. 1: Vertical estándar ----------------
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1400
    header_h = 140
    colhdr_h = 70
    foot_h   = 110

    body_rows_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    H = BORDER_W*2 + header_h + GRID_W_THICK + colhdr_h + GRID_W + ROW_H + GRID_W_THICK + body_rows_h + GRID_W_THICK + foot_h

    # Columnas: | label | separación | por100 | porción |
    col_x = [BORDER_W, BORDER_W + int(W*0.52), BORDER_W + int(W*0.78), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    # Marco exterior
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Encabezado + etiquetas de columnas
    y = _draw_header_and_colhdr(d, W, H, header_h, colhdr_h, col_x)

    # Verticales completas, incluyendo la 'nueva' entre nombre y valores
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], y, data_bottom, TEXT_COLOR, GRID_W)  # nueva vertical
    draw_vline(d, col_x[2], y, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], y, data_bottom, TEXT_COLOR, GRID_W)

    # Bloque Calorías con celda combinada
    y = _draw_calories_merged_cell(d, W, y, col_x)

    # Filas de nutrientes
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label  = BORDER_W + CELL_PAD_X + indent*28
        y_text   = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = text_size(d, v100, font_val)
        wvpp,_  = text_size(d, vpp,  font_val)
        d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    # Separador grueso previo a micronutrientes / pie
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Micronutrientes
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

    # Pie
    d.text((BORDER_W + CELL_PAD_X, y + 20),
           f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
           fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ---------------- Fig. 3: Simplificado ----------------
def draw_fig3():
    rows = [
        ("Grasa total",           f"{fmt_g(fat_total_100_r)} g",    f"{fmt_g(fat_total_pp_r)} g",         0, False),
        ("  Grasa saturada",      f"{fmt_g(sat_fat_100_r)} g",      f"{fmt_g(sat_fat_pp_r)} g",           1, True),
        ("  Grasas trans",        f"{fmt_mg(trans_fat_100_mg_r)} mg", f"{fmt_mg(trans_fat_pp_mg_r)} mg",  1, True),
        ("Carbohidratos totales", f"{fmt_g(carb_100_r)} g",         f"{fmt_g(carb_pp_r)} g",              0, False),
        ("  Azúcares añadidos",   f"{fmt_g(sug_added_100_r)} g",    f"{fmt_g(sug_added_pp_r)} g",         1, True),
        ("Proteína",              f"{fmt_g(protein_100_r)} g",      f"{fmt_g(protein_pp_r)} g",           0, False),
        ("Sodio",                 f"{fmt_mg(sodium_100_mg_r)} mg",  f"{fmt_mg(sodium_pp_mg_r)} mg",       0, True),
    ]
    W = 1200
    header_h = 140
    colhdr_h = 70
    foot_h   = 110

    H = BORDER_W*2 + header_h + GRID_W_THICK + colhdr_h + GRID_W + ROW_H + GRID_W_THICK + len(rows)*ROW_H + GRID_W_THICK + foot_h
    col_x = [BORDER_W, BORDER_W + int(W*0.52), BORDER_W + int(W*0.78), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Encabezado + etiquetas de columnas
    y = _draw_header_and_colhdr(d, W, H, header_h, colhdr_h, col_x)

    # Verticales
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], y, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], y, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], y, data_bottom, TEXT_COLOR, GRID_W)

    # Bloque Calorías merged
    y = _draw_calories_merged_cell(d, W, y, col_x)

    # Filas simplificadas
    for label, v100, vpp, indent, bold in rows:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label  = BORDER_W + CELL_PAD_X + indent*28
        y_text   = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = text_size(d, v100, font_val)
        wvpp,_  = text_size(d, vpp,  font_val)
        d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    d.text((BORDER_W + CELL_PAD_X, y + 20),
           f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
           fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ---------------- Fig. 4: Tabular ----------------
def draw_fig4():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro)>0

    W = 1500
    header_h = 140
    colhdr_h = 70
    foot_h   = 110

    body_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    H = BORDER_W*2 + header_h + GRID_W_THICK + colhdr_h + GRID_W + ROW_H + GRID_W_THICK + body_h + GRID_W_THICK + foot_h

    col_x = [BORDER_W, BORDER_W + int(W*0.50), BORDER_W + int(W*0.76), W - BORDER_W]

    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Encabezado + etiquetas de columnas
    y = _draw_header_and_colhdr(d, W, H, header_h, colhdr_h, col_x)

    # Verticales completas
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], y, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], y, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], y, data_bottom, TEXT_COLOR, GRID_W)

    # Bloque Calorías merged
    y = _draw_calories_merged_cell(d, W, y, col_x)

    # Filas tabulares
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label  = BORDER_W + CELL_PAD_X + indent*28
        y_text   = y + (ROW_H//2) - 14
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
            y_text  = y + (ROW_H_MICRO//2) - 12
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100,_ = text_size(d, v100, FONT_MICRO)
            wvpp,_  = text_size(d, vpp,  FONT_MICRO)
            d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    d.text((BORDER_W + CELL_PAD_X, y + 20),
           f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
           fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ---------------- Fig. 5: Lineal ----------------
def draw_fig5():
    items = []
    def pair(name, vpp, v100):
        items.append(f"{name}: {vpp} (por 100: {v100})")

    pair("Calorías", f"{fmt_kcal(kcal_pp)} kcal", f"{fmt_kcal(kcal_100)} kcal")
    pair("Grasa total",          f"{fmt_g(fat_total_pp_r)} g",   f"{fmt_g(fat_total_100_r)} g")
    pair("Grasa saturada",       f"{fmt_g(sat_fat_pp_r)} g",     f"{fmt_g(sat_fat_100_r)} g")
    pair("Grasas trans",         f"{fmt_mg(trans_fat_pp_mg_r)} mg", f"{fmt_mg(trans_fat_100_mg_r)} mg")
    pair("Carbohidratos totales",f"{fmt_g(carb_pp_r)} g",        f"{fmt_g(carb_100_r)} g")
    pair("Azúcares totales",     f"{fmt_g(sug_total_pp_r)} g",   f"{fmt_g(sug_total_100_r)} g")
    pair("Azúcares añadidos",    f"{fmt_g(sug_added_pp_r)} g",   f"{fmt_g(sug_added_100_r)} g")
    pair("Fibra dietaria",       f"{fmt_g(fiber_pp_r)} g",       f"{fmt_g(fiber_100_r)} g")
    pair("Proteína",             f"{fmt_g(protein_pp_r)} g",     f"{fmt_g(protein_100_r)} g")
    pair("Sodio",                f"{fmt_mg(sodium_pp_mg_r)} mg", f"{fmt_mg(sodium_100_mg_r)} mg")

    for (name, unit), v100 in vm_values_rounded.items():
        vpp  = vm_pp[(name, unit)]
        vpp_txt  = f"{fmt_mg(vpp)} {unit}" if unit=="mg" else f"{int(vpp)} {unit}"
        v100_txt = f"{fmt_mg(v100)} {unit}" if unit=="mg" else f"{int(v100)} {unit}"
        pair(name, vpp_txt, v100_txt)

    W = 1600
    H = 620
    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    left_x = BORDER_W + 28
    y = BORDER_W + 28
    d.text((left_x, y),
           f"Información nutricional (por porción): Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})   •   Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL_B)
    y += 52

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
    if line: lines.append(line)

    for ln in lines:
        d.text((left_x, y), ln, fill=TEXT_COLOR, font=FONT_LABEL)
        y += 46

    y += 10
    d.text((left_x, y),
           f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
           fill=TEXT_COLOR, font=FONT_SMALL)
    return img
    # ============================================================
# PREVISUALIZACIÓN Y EXPORTACIÓN
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
