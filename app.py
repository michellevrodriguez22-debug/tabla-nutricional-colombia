# app.py
# ============================================================
# Generador de Tabla Nutricional (Colombia) -> PNG
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Fig.1 (Vertical estándar), Fig.3 (Simplificado),
# Fig.4 (Tabular) y Fig.5 (Lineal)
# Entradas por 100 g / 100 mL | Controles clave en barra lateral
# Solo exporta PNG
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
        if x is None or x == "":
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
# SIDEBAR (como tu código original)
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
    fat_total_100   = as_num(st.text_input("Grasa total (g/100)", value="13"))
    sat_fat_100     = as_num(st.text_input("Grasa saturada (g/100)", value="6"))
    trans_fat_100_mg= as_num(st.text_input("Grasas trans (mg/100)", value="820"))
with c2:
    carb_100        = as_num(st.text_input("Carbohidratos totales (g/100)", value="31"))
    sug_total_100   = as_num(st.text_input("Azúcares totales (g/100)", value="5"))
    sug_added_100   = as_num(st.text_input("Azúcares añadidos (g/100)", value="2"))
with c3:
    fiber_100       = as_num(st.text_input("Fibra dietaria (g/100)", value="0.8"))
    protein_100     = as_num(st.text_input("Proteína (g/100)", value="5"))
    sodium_100_mg   = as_num(st.text_input("Sodio (mg/100)", value="560"))

st.markdown("---")
st.subheader("Valores de micronutrientes seleccionados (por 100)")
vm_values = {}
vm_col1, vm_col2 = st.columns([0.5, 0.5])
with vm_col1:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 0:
            unit = "µg" if vm in ("Vitamina A","Vitamina D","Vitamina B12") else "mg"
            vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))
with vm_col2:
    for i, vm in enumerate(selected_vm):
        if i % 2 == 1:
            unit = "µg" if vm in ("Vitamina A","Vitamina D","Vitamina B12") else "mg"
            vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))

# ============================================================
# CÁLCULOS
# ============================================================
portion_size = household_mass
is_liquid = "Líquido" in physical_state

fat_total_pp    = portion_from_per100(fat_total_100, portion_size)
sat_fat_pp      = portion_from_per100(sat_fat_100, portion_size)
trans_fat_pp_mg = portion_from_per100(trans_fat_100_mg, portion_size)
carb_pp         = portion_from_per100(carb_100, portion_size)
sug_total_pp    = portion_from_per100(sug_total_100, portion_size)
sug_added_pp    = portion_from_per100(sug_added_100, portion_size)
fiber_pp        = portion_from_per100(fiber_100, portion_size)
protein_pp      = portion_from_per100(protein_100, portion_size)
sodium_pp_mg    = portion_from_per100(sodium_100_mg, portion_size)

# Micronutrientes por porción
vm_pp = {}
for (name, unit), v100 in vm_values.items():
    vm_pp[(name, unit)] = portion_from_per100(v100, portion_size)

# Energía
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp  = kcal_from_macros(fat_total_pp,  carb_pp,  protein_pp)

# ============================================================
# ESTILO GRÁFICO
# ============================================================
BORDER_W       = 6   # marco exterior
GRID_W         = 3   # líneas internas estándar
GRID_W_THICK   = 9   # líneas gruesas (triples)
TEXT_COLOR     = (0,0,0)
BG_WHITE       = (255,255,255)

FONT_TITLE     = get_font(46, bold=True)   # título centrado
FONT_LABEL     = get_font(30, bold=False)
FONT_LABEL_B   = get_font(30, bold=True)
FONT_SMALL     = get_font(26, bold=False)
FONT_SMALL_B   = get_font(26, bold=True)
FONT_MICRO     = get_font(24, bold=False)  # micronutrientes más pequeño
FONT_MICRO_B   = get_font(24, bold=True)

ROW_H          = 64
ROW_H_MICRO    = 54
CELL_PAD_X     = 22
CELL_PAD_Y     = 18

def column_labels():
    return ("Por 100 g" if not is_liquid else "Por 100 mL", "Por porción")

# ============================================================
# FILAS COMUNES
# ============================================================
def common_rows():
    rows = [
        # (label, v100_str, vpp_str, indent, bold, is_micro)
        ("Grasa total",           f"{fmt_g(fat_total_100,1)} g",        f"{fmt_g(fat_total_pp,1)} g",         0, False, False),
        ("  Grasa saturada",      f"{fmt_g(sat_fat_100,1)} g",          f"{fmt_g(sat_fat_pp,1)} g",           1, True,  False),
        ("  Grasas trans",        f"{fmt_mg(trans_fat_100_mg)} mg",     f"{fmt_mg(trans_fat_pp_mg)} mg",      1, True,  False),
        ("Carbohidratos totales", f"{fmt_g(carb_100,1)} g",             f"{fmt_g(carb_pp,1)} g",              0, False, False),
        ("  Fibra dietaria",      f"{fmt_g(fiber_100,1)} g",            f"{fmt_g(fiber_pp,1)} g",             1, False, False),
        ("  Azúcares totales",    f"{fmt_g(sug_total_100,1)} g",        f"{fmt_g(sug_total_pp,1)} g",         1, False, False),
        ("  Azúcares añadidos",   f"{fmt_g(sug_added_100,1)} g",        f"{fmt_g(sug_added_pp,1)} g",         1, True,  False),
        ("Proteína",              f"{fmt_g(protein_100,1)} g",          f"{fmt_g(protein_pp,1)} g",           0, False, False),
        ("Sodio",                 f"{fmt_mg(sodium_100_mg)} mg",        f"{fmt_mg(sodium_pp_mg)} mg",         0, True,  False),
    ]
    return rows

def micro_rows():
    rows = []
    for (name, unit), v100 in vm_values.items():
        vpp = vm_pp[(name, unit)]
        # unidades SOLO junto a los valores
        v100_txt = f"{fmt_mg(v100)} {unit}" if unit=="mg" else f"{fmt_g(v100,1)} {unit}"
        vpp_txt  = f"{fmt_mg(vpp)} {unit}"  if unit=="mg" else f"{fmt_g(vpp,1)} {unit}"
        rows.append((name, v100_txt, vpp_txt, 0, False, True))
    return rows

# ============================================================
# BLOQUES COMUNES DE DIBUJO
# ============================================================
def draw_title_and_portions(draw, W, start_y):
    # Título centrado
    title = "Información Nutricional"
    tw, th = text_size(draw, title, FONT_TITLE)
    draw.text(((W - tw)//2, start_y), title, fill=TEXT_COLOR, font=FONT_TITLE)
    y = start_y + th + 12
    # Línea gruesa separadora
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 12
    # Porciones (izquierda, NO centrado)
    draw.text((BORDER_W + CELL_PAD_X, y + 8),  f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})", fill=TEXT_COLOR, font=FONT_SMALL)
    draw.text((BORDER_W + CELL_PAD_X, y + 8 + 34), f"Número de porciones por envase: {fmt_mg(servings_per_pack)}", fill=TEXT_COLOR, font=FONT_SMALL)
    return y + 80

def draw_calories_block(draw, W, cur_y, portion_unit_for_label):
    # Línea gruesa arriba
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
    cur_y += 4

    # Columnas del bloque de calorías (nombre | por100 | porción)
    col_x = [BORDER_W, BORDER_W + int(W*0.52), BORDER_W + int(W*0.78), W - BORDER_W]
    row_h_header = 48
    row_h_values = 64
    total_h = row_h_header + row_h_values + 16

    # Etiqueta "Calorías (kcal)" en la celda izquierda, centrada verticalmente
    label = "Calorías (kcal)"
    lw, lh = text_size(draw, label, FONT_LABEL_B)
    label_y = cur_y + (total_h//2) - (lh//2)
    draw.text((BORDER_W + CELL_PAD_X, label_y), label, fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Encabezados subcolumnas
    per100_label = "Por 100 g" if portion_unit_for_label == "g" else "Por 100 mL"
    perportion_label = "Por porción"
    h1_w, _ = text_size(draw, per100_label, FONT_SMALL_B)
    h2_w, _ = text_size(draw, perportion_label, FONT_SMALL_B)

    col1_center = (col_x[1] + col_x[2]) // 2
    col2_center = (col_x[2] + col_x[3]) // 2

    draw.text((col1_center - h1_w//2, cur_y + 6), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col2_center - h2_w//2, cur_y + 6), perportion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)

    # División horizontal entre encabezados y valores
    mid_y = cur_y + row_h_header + 4
    draw_hline(draw, col_x[1], W-BORDER_W, mid_y, TEXT_COLOR, GRID_W)

    # Valores
    txt_100 = f"{fmt_kcal(kcal_100)}"
    txt_pp  = f"{fmt_kcal(kcal_pp)}"
    v1_w, _ = text_size(draw, txt_100, FONT_LABEL_B)
    v2_w, _ = text_size(draw, txt_pp,  FONT_LABEL_B)
    v_y = mid_y + 12
    draw.text((col1_center - v1_w//2, v_y), txt_100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    draw.text((col2_center - v2_w//2, v_y), txt_pp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Separadores verticales internos del bloque de calorías
    draw_vline(draw, col_x[1], cur_y, cur_y + total_h, TEXT_COLOR, GRID_W)  # entre nombre y valores
    draw_vline(draw, col_x[2], cur_y, cur_y + total_h, TEXT_COLOR, GRID_W)  # entre por100 y porción

    # Línea gruesa abajo
    draw_hline(draw, BORDER_W, W-BORDER_W, cur_y + total_h, TEXT_COLOR, GRID_W_THICK)

    return cur_y + total_h + 8, col_x

def draw_rows_grid(draw, W, start_y, rows, footer_text, extend_verticals_at_x=None):
    """
    Dibuja filas con:
      - línea fina arriba de cada fila
      - separador vertical entre nombre y valores (si extend_verticals_at_x)
      - columnas por 100 / porción a la derecha
      - línea gruesa entre macros y micros
      - pie al final
    """
    # Columnas: | label | (vertical) | por100 | porción |
    col_x = [BORDER_W, BORDER_W + int(W*0.52), BORDER_W + int(W*0.78), W - BORDER_W]
    y = start_y

    # Encabezados columnas (por 100 / porción), alineados derecha
    per100_label, perportion_label = column_labels()
    w_c100, _ = text_size(draw, per100_label, FONT_SMALL_B)
    w_cpp,  _ = text_size(draw, perportion_label, FONT_SMALL_B)
    draw.text((col_x[2] - CELL_PAD_X - w_c100, y + 6), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col_x[3] - CELL_PAD_X - w_cpp,  y + 6), perportion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw_hline(draw, BORDER_W, W-BORDER_W, y + 46, TEXT_COLOR, GRID_W)
    y += 50

    # Verticales completas desde aquí hasta antes del pie
    data_top = y
    # (el pie queda ~110 px más abajo al final; lo calcularemos tras recorrer filas)
    # Línea inicial superior
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    for label, v100, vpp, indent, bold, is_micro in rows:
        # Si encontramos el separador macros/micros
        if label == "---sep---":
            draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
            # seguir sin incrementar y, para que la siguiente fila pinte encima del grueso
            continue

        # Línea superior de la fila
        draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

        # Fuentes
        font_lbl = FONT_LABEL_B if bold else (FONT_MICRO if is_micro else FONT_LABEL)
        font_val = FONT_LABEL_B if bold else (FONT_MICRO_B if is_micro else FONT_LABEL)

        # Nombre (izquierda)
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text = y + (ROW_H//2) - (14 if not is_micro else 12)
        draw.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)

        # Valores (derecha)
        wv100, _ = text_size(draw, v100, font_val)
        wvpp,  _ = text_size(draw, vpp,  font_val)
        draw.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((col_x[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)

        y += (ROW_H_MICRO if is_micro else ROW_H)

    # Línea gruesa antes del pie
    draw_hline(draw, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Trazo de verticales completas (incluida la de separación nombre/valores)
    if extend_verticals_at_x is None:
        extend_verticals_at_x = col_x
    y_bottom_for_verticals = y  # justo antes del pie
    # Entre nombre y valores:
    draw_vline(draw, col_x[1], data_top - 50, y_bottom_for_verticals, TEXT_COLOR, GRID_W)
    # Entre por100 y porción:
    draw_vline(draw, col_x[2], data_top - 50, y_bottom_for_verticals, TEXT_COLOR, GRID_W)
    # Borde derecho de valores
    draw_vline(draw, col_x[3], data_top - 50, y_bottom_for_verticals, TEXT_COLOR, GRID_W)

    # Pie
    draw.text((BORDER_W + CELL_PAD_X, y + 20), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)
    return y + 60

# ============================================================
# FIGURA 1 — VERTICAL ESTÁNDAR
# ============================================================
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    if rows_micro:
        rows_nutri.append(("---sep---", "", "", 0, False, False))
        rows_nutri.extend(rows_micro)

    W = 1400
    # alto estimado; será suficiente por el padding usado
    H = 2200

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # Marco exterior
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Título + porciones
    y = d_y = draw_title_and_portions(d, W, BORDER_W + 8)

    # Bloque Calorías
    y, col_x = draw_calories_block(d, W, y, portion_unit)

    # Filas (con verticales completas hasta antes del pie)
    y_end = draw_rows_grid(d, W, y, rows_nutri, footnote_tail)

    # Recorte suave del lienzo si sobran píxeles
    H_used = int(y_end + 120)
    if H_used < H:
        img = img.crop((0,0,W,H_used))

    return img

# ============================================================
# FIGURA 3 — SIMPLIFICADO
# ============================================================
def draw_fig3():
    # Selección reducida
    base = common_rows()
    keep = {"Grasa total", "  Grasa saturada", "  Grasas trans", "Carbohidratos totales", "  Azúcares añadidos", "Proteína", "Sodio"}
    rows = [r for r in base if r[0] in keep]

    W = 1400
    H = 1600

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    y = draw_title_and_portions(d, W, BORDER_W + 8)
    y, _ = draw_calories_block(d, W, y, portion_unit)

    y_end = draw_rows_grid(d, W, y, rows, footnote_tail)
    H_used = int(y_end + 120)
    if H_used < H:
        img = img.crop((0,0,W,H_used))
    return img

# ============================================================
# FIGURA 4 — TABULAR (cuadrícula completa + vertical extra)
# ============================================================
def draw_fig4():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    if rows_micro:
        rows_nutri.append(("---sep---", "", "", 0, False, False))
        rows_nutri.extend(rows_micro)

    W = 1500
    H = 2300

    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    y = draw_title_and_portions(d, W, BORDER_W + 8)
    y, _ = draw_calories_block(d, W, y, portion_unit)

    y_end = draw_rows_grid(d, W, y, rows_nutri, footnote_tail)
    H_used = int(y_end + 120)
    if H_used < H:
        img = img.crop((0,0,W,H_used))
    return img

# ============================================================
# FIGURA 5 — LINEAL
# ============================================================
def draw_fig5():
    items = []

    def pair(name, vpp, v100):
        items.append(f"{name}: {vpp} (por 100: {v100})")

    pair("Calorías (kcal)", f"{fmt_kcal(kcal_pp)}", f"{fmt_kcal(kcal_100)}")
    pair("Grasa total", f"{fmt_g(fat_total_pp,1)} g", f"{fmt_g(fat_total_100,1)} g")
    pair("Grasa saturada", f"{fmt_g(sat_fat_pp,1)} g", f"{fmt_g(sat_fat_100,1)} g")
    pair("Grasas trans", f"{fmt_mg(trans_fat_pp_mg)} mg", f"{fmt_mg(trans_fat_100_mg)} mg")
    pair("Carbohidratos totales", f"{fmt_g(carb_pp,1)} g", f"{fmt_g(carb_100,1)} g")
    pair("Azúcares totales", f"{fmt_g(sug_total_pp,1)} g", f"{fmt_g(sug_total_100,1)} g")
    pair("Azúcares añadidos", f"{fmt_g(sug_added_pp,1)} g", f"{fmt_g(sug_added_100,1)} g")
    pair("Fibra dietaria", f"{fmt_g(fiber_pp,1)} g", f"{fmt_g(fiber_100,1)} g")
    pair("Proteína", f"{fmt_g(protein_pp,1)} g", f"{fmt_g(protein_100,1)} g")
    pair("Sodio", f"{fmt_mg(sodium_pp_mg)} mg", f"{fmt_mg(sodium_100_mg)} mg")

    for (name, unit), v100 in vm_values.items():
        vpp = vm_pp[(name, unit)]
        vpp_txt  = f"{fmt_mg(vpp)} {unit}" if unit=="mg" else f"{fmt_g(vpp,1)} {unit}"
        v100_txt = f"{fmt_mg(v100)} {unit}" if unit=="mg" else f"{fmt_g(v100,1)} {unit}"
        pair(name, vpp_txt, v100_txt)

    W = 1600
    H = 620
    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Título + porciones
    y = draw_title_and_portions(d, W, BORDER_W + 8)

    # Texto corrido
    left_x = BORDER_W + 28
    s = "  •  ".join(items)
    maxw = W - left_x - 30
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
