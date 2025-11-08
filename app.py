# ============================================================
# Generador de Tabla Nutricional (Colombia) → PNG
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Fig. 1 (Vertical estándar), Fig. 3 (Simplificado),
# Fig. 4 (Tabular) y Fig. 5 (Lineal)
# Entradas por 100 g / 100 mL | Controles clave en barra lateral
# ============================================================

from io import BytesIO
from datetime import datetime
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ============================================================
# CONFIGURACIÓN
# ============================================================
st.set_page_config(
    page_title="Generador de Tabla Nutricional (Colombia)",
    layout="wide"
)
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
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9 * fat_g + 4 * carb_g + 4 * protein_g + 7 * alcohol_g + 3 * organic_acids_g
    return float(kcal)


def portion_from_per100(value_per100, portion_size):
    if portion_size and portion_size > 0:
        return (value_per100 * portion_size) / 100.0
    return 0.0


# ---- Reglas de redondeo (Res. 810/2021 Tabla 1 y Tabla 2) ----
def round_kcal(v):
    if v < 5:
        return 0
    return int(round(v))


def round_g(v):
    if v < 0.005:
        v = 0.0
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
    if float(x).is_integer():
        return f"{int(x)}"
    return f"{x:.1f}".rstrip("0").rstrip(".")


def fmt_mg(x):
    return f"{int(round(x))}"


def fmt_kcal(x):
    return f"{int(round(x))}"


def get_font(size, bold=False):
    try:
        return ImageFont.truetype(
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size
        )
    except:
        return ImageFont.load_default()


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_hline(draw, x0, x1, y, color, width):
    draw.line((x0, y, x1, y), fill=color, width=width)


def draw_vline(draw, x, y0, y1, color, width):
    draw.line((x, y0, x, y1), fill=color, width=width)


# ============================================================
# BARRA LATERAL — CONFIGURACIÓN
# ============================================================
st.sidebar.header("Configuración")

format_choice = st.sidebar.selectbox(
    "Formato a exportar",
    [
        "Fig. 1 — Vertical estándar",
        "Fig. 3 — Simplificado",
        "Fig. 4 — Tabular",
        "Fig. 5 — Lineal",
    ],
    index=0,
)

physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])
portion_unit = "g" if "Sólido" in physical_state else "mL"

st.sidebar.subheader("Porción")
household_name = st.sidebar.text_input(
    "Medida casera (p. ej. 1 unidad, 1 taza)", value="1 unidad"
)
household_mass = as_num(
    st.sidebar.text_input(f"Equivalencia en {portion_unit} (número)", value="40")
)
servings_per_pack = as_num(
    st.sidebar.text_input("Número de porciones por envase", value="2")
)

# Validación (no impresa)
st.sidebar.subheader("Validación interna (no se imprime)")
contains_sweeteners = st.sidebar.checkbox("Contiene edulcorantes", value=False)

st.sidebar.subheader("Micronutrientes a declarar")
vm_options = [
    "Vitamina A",
    "Vitamina D",
    "Vitamina B1",
    "Vitamina B12",
    "Vitamina C",
    "Vitamina E",
    "Calcio",
    "Hierro",
    "Zinc",
    "Potasio",
]
selected_vm = st.sidebar.multiselect(
    "Selecciona los que declararás",
    vm_options,
    default=["Vitamina A", "Calcio", "Hierro", "Vitamina D", "Zinc"],
)

st.sidebar.subheader("Texto al pie")
footnote_tail = st.sidebar.text_input(
    "Completa: No es fuente significativa de …",
    value="Proteína, Vitamina D, Hierro, Calcio, Zinc, Vitamina A y fibra.",
)
# ============================================================
# ENTRADAS (CUERPO PRINCIPAL) — por 100 g/mL
# ============================================================
st.header("Ingreso de datos por 100 g / 100 mL")

c1, c2, c3 = st.columns([0.33, 0.33, 0.34])
with c1:
    st.subheader("Macronutrientes (por 100)")
    fat_total_100 = as_num(st.text_input("Grasa total (g/100)", value="13"))
    sat_fat_100 = as_num(st.text_input("Grasa saturada (g/100)", value="6"))
    trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg/100)", value="820"))
with c2:
    carb_100 = as_num(st.text_input("Carbohidratos totales (g/100)", value="31"))
    sug_total_100 = as_num(st.text_input("Azúcares totales (g/100)", value="5"))
    sug_added_100 = as_num(st.text_input("Azúcares añadidos (g/100)", value="2"))
with c3:
    fiber_100 = as_num(st.text_input("Fibra dietaria (g/100)", value="0.8"))
    protein_100 = as_num(st.text_input("Proteína (g/100)", value="5"))
    sodium_100_mg = as_num(st.text_input("Sodio (mg/100)", value="560"))

st.markdown("---")
st.subheader("Valores de micronutrientes seleccionados (por 100)")
vm_values = {}
vm_col1, vm_col2 = st.columns([0.5, 0.5])
with vm_col1:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 0:
            unit = "µg" if vm in ("Vitamina A", "Vitamina D", "Vitamina B12") else "mg"
            vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))
with vm_col2:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 1:
            unit = "µg" if vm in ("Vitamina A", "Vitamina D", "Vitamina B12") else "mg"
            vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))

# ============================================================
# CÁLCULOS Y REDONDEO
# ============================================================
portion_size = household_mass
is_liquid = "Líquido" in physical_state

# Por porción (sin redondear)
def per_portion(v): return portion_from_per100(v, portion_size)

fat_total_pp = per_portion(fat_total_100)
sat_fat_pp = per_portion(sat_fat_100)
trans_fat_pp_mg = per_portion(trans_fat_100_mg)
carb_pp = per_portion(carb_100)
sug_total_pp = per_portion(sug_total_100)
sug_added_pp = per_portion(sug_added_100)
fiber_pp = per_portion(fiber_100)
protein_pp = per_portion(protein_100)
sodium_pp_mg = per_portion(sodium_100_mg)

# Calorías
kcal_100_raw = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp_raw = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)

def nonsig_zero_g(name, v):
    if name == "Grasa total" and v < 0.5: return 0.0
    if name in ("Grasa saturada","Grasas trans") and v < 0.1: return 0.0
    if name in ("Carbohidratos totales","Azúcares totales","Azúcares añadidos","Fibra dietaria","Proteína") and v < 0.5: return 0.0
    return v

def nonsig_zero_mg(name, vmg):
    if name == "Sodio" and vmg < 5: return 0
    return vmg

# Aplicar redondeos
fat_total_100_r = round_g(nonsig_zero_g("Grasa total", fat_total_100))
sat_fat_100_r = round_g(nonsig_zero_g("Grasa saturada", sat_fat_100))
trans_fat_100_mg_r = round_mg(nonsig_zero_mg("Grasas trans", trans_fat_100_mg))
carb_100_r = round_g(nonsig_zero_g("Carbohidratos totales", carb_100))
sug_total_100_r = round_g(nonsig_zero_g("Azúcares totales", sug_total_100))
sug_added_100_r = round_g(nonsig_zero_g("Azúcares añadidos", sug_added_100))
fiber_100_r = round_g(nonsig_zero_g("Fibra dietaria", fiber_100))
protein_100_r = round_g(nonsig_zero_g("Proteína", protein_100))
sodium_100_mg_r = round_mg(nonsig_zero_mg("Sodio", sodium_100_mg))

fat_total_pp_r = round_g(nonsig_zero_g("Grasa total", fat_total_pp))
sat_fat_pp_r = round_g(nonsig_zero_g("Grasa saturada", sat_fat_pp))
trans_fat_pp_mg_r = round_mg(nonsig_zero_g("Grasas trans", trans_fat_pp_mg))
carb_pp_r = round_g(nonsig_zero_g("Carbohidratos totales", carb_pp))
sug_total_pp_r = round_g(nonsig_zero_g("Azúcares totales", sug_total_pp))
sug_added_pp_r = round_g(nonsig_zero_g("Azúcares añadidos", sug_added_pp))
fiber_pp_r = round_g(nonsig_zero_g("Fibra dietaria", fiber_pp))
protein_pp_r = round_g(nonsig_zero_g("Proteína", protein_pp))
sodium_pp_mg_r = round_mg(nonsig_zero_mg("Sodio", sodium_pp_mg))

kcal_100 = round_kcal(kcal_100_raw)
kcal_pp = round_kcal(kcal_pp_raw)

vm_pp = {}
vm_values_rounded = {}
for (name, unit), v100 in vm_values.items():
    vpp = portion_from_per100(v100, portion_size)
    if unit == "mg":
        vm_values_rounded[(name, unit)] = int(round(v100))
        vm_pp[(name, unit)] = int(round(vpp))
    else:
        vm_values_rounded[(name, unit)] = int(round(v100))
        vm_pp[(name, unit)] = int(round(vpp))
# ============================================================
# FILAS (usando los valores redondeados de la Parte 2)
# ============================================================
def common_rows():
    return [
        ("Grasa total",           f"{fmt_g(fat_total_100_r)} g",      f"{fmt_g(fat_total_pp_r)} g",       0, False, False),
        ("  Grasa saturada",      f"{fmt_g(sat_fat_100_r)} g",        f"{fmt_g(sat_fat_pp_r)} g",         1, True,  False),
        ("  Grasas trans",        f"{fmt_mg(trans_fat_100_mg_r)} mg", f"{fmt_mg(trans_fat_pp_mg_r)} mg",  1, True,  False),
        ("Carbohidratos totales", f"{fmt_g(carb_100_r)} g",           f"{fmt_g(carb_pp_r)} g",            0, False, False),
        ("  Fibra dietaria",      f"{fmt_g(fiber_100_r)} g",          f"{fmt_g(fiber_pp_r)} g",           1, False, False),
        ("  Azúcares totales",    f"{fmt_g(sug_total_100_r)} g",      f"{fmt_g(sug_total_pp_r)} g",       1, False, False),
        ("  Azúcares añadidos",   f"{fmt_g(sug_added_100_r)} g",      f"{fmt_g(sug_added_pp_r)} g",       1, True,  False),
        ("Proteína",              f"{fmt_g(protein_100_r)} g",        f"{fmt_g(protein_pp_r)} g",         0, False, False),
        ("Sodio",                 f"{fmt_mg(sodium_100_mg_r)} mg",    f"{fmt_mg(sodium_pp_mg_r)} mg",     0, True,  False),
    ]

def micro_rows():
    rows = []
    for (name, unit), v100 in vm_values_rounded.items():
        vpp = vm_pp[(name, unit)]
        # unidades SOLO junto a valores
        v100_txt = f"{fmt_mg(v100)} {unit}" if unit == "mg" else f"{int(v100)} {unit}"
        vpp_txt  = f"{fmt_mg(vpp)} {unit}"  if unit == "mg" else f"{int(vpp)} {unit}"
        rows.append((name, v100_txt, vpp_txt, 0, False, True))
    return rows

def column_labels():
    return ("Por 100 g" if not is_liquid else "Por 100 mL", "Por porción")


# ============================================================
# FIGURA 1 — VERTICAL ESTÁNDAR (calorías con celda combinada)
# ============================================================
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1400
    header_h = 140
    gap_after_title = 10
    colhdr_h = 70
    calories_h = ROW_H               # altura nominal del bloque calorías
    body_rows_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    foot_h = 110

    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + calories_h + GRID_W_THICK +
         body_rows_h + GRID_W_THICK + foot_h)

    # columnas: | etiqueta | (vertical extra) | por100 | porción |
    col_x = [BORDER_W, BORDER_W + int(W*0.52), BORDER_W + int(W*0.78), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # marco exterior
    d.rectangle([0, 0, W-1, H-1], outline=TEXT_COLOR, width=BORDER_W)

    # título
    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 10), title, fill=TEXT_COLOR, font=FONT_TITLE)

    # porciones
    y0 = BORDER_W + 10 + th + 6
    d.text((BORDER_W + CELL_PAD_X, y0 + 16),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, y0 + 16 + 36),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    # línea gruesa debajo del encabezado
    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # encabezados columnas
    c100, cpp = column_labels()
    w_c100, _ = text_size(d, c100, FONT_SMALL_B)
    w_cpp,  _ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2] - CELL_PAD_X - w_c100, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - CELL_PAD_X - w_cpp,  y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    # línea fina bajo encabezados
    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    # verticales internas (incluye la nueva entre nombre y valores)
    data_top = y
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], data_top, data_bottom, TEXT_COLOR, GRID_W)  # vertical nueva
    draw_vline(d, col_x[2], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, data_bottom, TEXT_COLOR, GRID_W)

    # ===== Bloque Calorías con "celda combinada" para el título =====
    y += 1
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y_top_cal = y                       # borde superior del bloque de calorías

    # línea media (para conservar el “ritmo” de filas a la derecha)
    y_mid_cal = y_top_cal + (ROW_H // 2)
    draw_hline(d, BORDER_W, W-BORDER_W, y_mid_cal, TEXT_COLOR, GRID_W)

    # título calorías centrado verticalmente entre y_top_cal y y_mid_cal
    d.text((BORDER_W + CELL_PAD_X, y_top_cal + (ROW_H//2) - 14),
           "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)

    # valores por 100 y por porción, centrados verticalmente en el bloque calorías
    kc100 = fmt_kcal(kcal_100)
    kcpp  = fmt_kcal(kcal_pp)
    w1, _ = text_size(d, kc100, FONT_LABEL_B)
    w2, _ = text_size(d, kcpp,  FONT_LABEL_B)
    v_y = y_top_cal + (ROW_H//2) - 14
    d.text((col_x[2] - CELL_PAD_X - w1, v_y), kc100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - CELL_PAD_X - w2, v_y), kcpp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    # cierre del bloque calorías
    y = y_top_cal + ROW_H
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # ===== Filas de nutrientes =====
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100, _ = text_size(d, v100, font_val)
        wvpp,  _ = text_size(d, vpp,  font_val)
        d.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    # separador grueso
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # ===== Micronutrientes =====
    if show_micro:
        for label, v100, vpp, indent, _, _ in rows_micro:
            y += 1
            draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
            x_label = BORDER_W + CELL_PAD_X + indent*28
            y_text = y + (ROW_H_MICRO//2) - 12
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100, _ = text_size(d, v100, FONT_MICRO)
            wvpp,  _ = text_size(d, vpp,  FONT_MICRO)
            d.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO

        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # pie
    d.text((BORDER_W + CELL_PAD_X, y + 20),
           f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
           fill=TEXT_COLOR, font=FONT_SMALL)
    return img


# ============================================================
# FIGURA 3 — SIMPLIFICADA (misma estética de Fig.1)
# ============================================================
def draw_fig3():
    rows = [
        ("Grasa total",           f"{fmt_g(fat_total_100_r)} g",      f"{fmt_g(fat_total_pp_r)} g",       0, False),
        ("  Grasa saturada",      f"{fmt_g(sat_fat_100_r)} g",        f"{fmt_g(sat_fat_pp_r)} g",         1, True),
        ("  Grasas trans",        f"{fmt_mg(trans_fat_100_mg_r)} mg", f"{fmt_mg(trans_fat_pp_mg_r)} mg",  1, True),
        ("Carbohidratos totales", f"{fmt_g(carb_100_r)} g",           f"{fmt_g(carb_pp_r)} g",            0, False),
        ("  Azúcares añadidos",   f"{fmt_g(sug_added_100_r)} g",      f"{fmt_g(sug_added_pp_r)} g",       1, True),
        ("Proteína",              f"{fmt_g(protein_100_r)} g",        f"{fmt_g(protein_pp_r)} g",         0, False),
        ("Sodio",                 f"{fmt_mg(sodium_100_mg_r)} mg",    f"{fmt_mg(sodium_pp_mg_r)} mg",     0, True),
    ]

    W = 1200
    header_h = 140
    gap_after_title = 10
    colhdr_h = 70
    calories_h = ROW_H
    foot_h = 110
    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + calories_h + GRID_W_THICK +
         len(rows)*ROW_H + GRID_W_THICK + foot_h)

    col_x = [BORDER_W, BORDER_W + int(W*0.52), BORDER_W + int(W*0.78), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W-1, H-1], outline=TEXT_COLOR, width=BORDER_W)

    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 10), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16 + 36),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    c100, cpp = column_labels()
    w1, _ = text_size(d, c100, FONT_SMALL_B)
    w2, _ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2] - CELL_PAD_X - w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - CELL_PAD_X - w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    data_top = y
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, data_bottom, TEXT_COLOR, GRID_W)

    # Calorías (misma celda combinada)
    y += 1
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y_top_cal = y
    y_mid_cal = y_top_cal + (ROW_H // 2)
    draw_hline(d, BORDER_W, W-BORDER_W, y_mid_cal, TEXT_COLOR, GRID_W)

    d.text((BORDER_W + CELL_PAD_X, y_top_cal + (ROW_H//2) - 14),
           "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)
    kc100 = fmt_kcal(kcal_100); kcpp = fmt_kcal(kcal_pp)
    wv1, _ = text_size(d, kc100, FONT_LABEL_B)
    wv2, _ = text_size(d, kcpp,  FONT_LABEL_B)
    v_y = y_top_cal + (ROW_H//2) - 14
    d.text((col_x[2] - CELL_PAD_X - wv1, v_y), kc100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - CELL_PAD_X - wv2, v_y), kcpp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    y = y_top_cal + ROW_H
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    for label, v100, vpp, indent, bold in rows:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100, _ = text_size(d, v100, font_val)
        wvpp,  _ = text_size(d, vpp,  font_val)
        d.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    d.text((BORDER_W + CELL_PAD_X, y + 20),
           f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
           fill=TEXT_COLOR, font=FONT_SMALL)
    return img


# ============================================================
# FIGURA 4 — TABULAR (cuadrícula completa + vertical extra)
# ============================================================
def draw_fig4():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1500
    header_h = 140
    gap_after_title = 10
    colhdr_h = 70
    calories_h = ROW_H
    foot_h = 110
    body_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)

    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + calories_h + GRID_W_THICK +
         body_h + GRID_W_THICK + foot_h)

    col_x = [BORDER_W, BORDER_W + int(W*0.50), BORDER_W + int(W*0.76), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W-1, H-1], outline=TEXT_COLOR, width=BORDER_W)

    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 10), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16),
           f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})",
           fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16 + 36),
           f"Número de porciones por envase: {int(round(servings_per_pack))}",
           fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    c100, cpp = column_labels()
    w1, _ = text_size(d, c100, FONT_SMALL_B)
    w2, _ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2] - CELL_PAD_X - w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - CELL_PAD_X - w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    # encabezado en malla
    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    data_bottom_limit = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], y, data_bottom_limit, TEXT_COLOR, GRID_W)  # vertical extra
    draw_vline(d, col_x[2], y, data_bottom_limit, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], y, data_bottom_limit, TEXT_COLOR, GRID_W)

    # Calorías con celda combinada
    y += 1
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y_top_cal = y
    y_mid_cal = y_top_cal + (ROW_H // 2)
    draw_hline(d, BORDER_W, W-BORDER_W, y_mid_cal, TEXT_COLOR, GRID_W)

    d.text((BORDER_W + CELL_PAD_X, y_top_cal + (ROW_H//2) - 14),
           "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)
    kc100 = fmt_kcal(kcal_100); kcpp = fmt_kcal(kcal_pp)
    wv1, _ = text_size(d, kc100, FONT_LABEL_B)
    wv2, _ = text_size(d, kcpp,  FONT_LABEL_B)
    v_y = y_top_cal + (ROW_H//2) - 14
    d.text((col_x[2] - CELL_PAD_X - wv1, v_y), kc100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - CELL_PAD_X - wv2, v_y), kcpp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    y = y_top_cal + ROW_H
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # resto de filas (malla)
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100, _ = text_size(d, v100, font_val)
        wvpp,  _ = text_size(d, vpp,  font_val)
        d.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H

    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    if show_micro:
        for label, v100, vpp, indent, _, _ in rows_micro:
            y += 1
            draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
            x_label = BORDER_W + CELL_PAD_X + indent*28
            y_text = y + (ROW_H_MICRO//2) - 12
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100, _ = text_size(d, v100, FONT_MICRO)
            wvpp,  _ = text_size(d, vpp,  FONT_MICRO)
            d.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO

        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    d.text((BORDER_W + CELL_PAD_X, y + 20),
           f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
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
    pair("Grasas trans", f"{fmt_mg(trans_fat_pp_mg_r)} mg", f"{fmt_mg(trans_fat_100_mg_r)} mg")
    pair("Carbohidratos totales", f"{fmt_g(carb_pp_r)} g", f"{fmt_g(carb_100_r)} g")
    pair("Azúcares totales", f"{fmt_g(sug_total_pp_r)} g", f"{fmt_g(sug_total_100_r)} g")
    pair("Azúcares añadidos", f"{fmt_g(sug_added_pp_r)} g", f"{fmt_g(sug_added_100_r)} g")
    pair("Fibra dietaria", f"{fmt_g(fiber_pp_r)} g", f"{fmt_g(fiber_100_r)} g")
    pair("Proteína", f"{fmt_g(protein_pp_r)} g", f"{fmt_g(protein_100_r)} g")
    pair("Sodio", f"{fmt_mg(sodium_pp_mg_r)} mg", f"{fmt_mg(sodium_100_mg_r)} mg")

    for (name, unit), v100 in vm_values_rounded.items():
        vpp = vm_pp[(name, unit)]
        vpp_txt  = f"{fmt_mg(vpp)} {unit}" if unit == "mg" else f"{int(vpp)} {unit}"
        v100_txt = f"{fmt_mg(v100)} {unit}" if unit == "mg" else f"{int(v100)} {unit}"
        pair(name, vpp_txt, v100_txt)

    W = 1600
    H = 620
    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W-1, H-1], outline=TEXT_COLOR, width=BORDER_W)

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
    if line:
        lines.append(line)

    for ln in lines:
        d.text((left_x, y), ln, fill=TEXT_COLOR, font=FONT_LABEL)
        y += 46

    y += 10
    d.text((left_x, y),
           f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
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
