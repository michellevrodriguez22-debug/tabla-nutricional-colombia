# app.py
# ============================================================
# Generador de Tabla Nutricional (Colombia) -> PNG
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Fig.1 (Vertical estándar), Fig.3 (Simplificado),
# Fig.4 (Tabular) y Fig.5 (Lineal)
# Entradas únicamente por 100 g / 100 mL
# ============================================================

import math
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
# SIDEBAR (solo por 100 g / 100 mL)
# ============================================================
st.sidebar.header("Configuración")
format_choice = st.sidebar.selectbox(
    "Formato a exportar",
    ["Fig. 1 — Vertical estándar", "Fig. 3 — Simplificado", "Fig. 4 — Tabular", "Fig. 5 — Lineal"],
    index=0
)

physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])
portion_unit = "g" if "Sólido" in physical_state else "mL"

# Tamaño de porción (el usuario define la medida casera y el gramaje)
st.sidebar.subheader("Porción")
household_name = st.sidebar.text_input("Medida casera (p. ej. 1 unidad, 1 taza)", value="1 unidad")
household_mass = as_num(st.sidebar.text_input(f"Equivalencia en {portion_unit} (número)", value="40"))
servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="2"))

# Macronutrientes por 100 g / 100 mL
st.sidebar.subheader("Macronutrientes (por 100 g / 100 mL)")
fat_total_100   = as_num(st.sidebar.text_input("Grasa total (g/100)", value="13"))
sat_fat_100     = as_num(st.sidebar.text_input("Grasa saturada (g/100)", value="6"))
trans_fat_100_mg= as_num(st.sidebar.text_input("Grasas trans (mg/100)", value="820"))
carb_100        = as_num(st.sidebar.text_input("Carbohidratos totales (g/100)", value="31"))
sug_total_100   = as_num(st.sidebar.text_input("Azúcares totales (g/100)", value="5"))
sug_added_100   = as_num(st.sidebar.text_input("Azúcares añadidos (g/100)", value="2"))
fiber_100       = as_num(st.sidebar.text_input("Fibra dietaria (g/100)", value="0.8"))
protein_100     = as_num(st.sidebar.text_input("Proteína (g/100)", value="5"))
sodium_100_mg   = as_num(st.sidebar.text_input("Sodio (mg/100)", value="560"))

# Micronutrientes por 100 g / 100 mL
st.sidebar.subheader("Micronutrientes (por 100 g / 100 mL) — opcional")
vm_options = [
    "Vitamina A", "Vitamina D", "Vitamina B1", "Vitamina B12",
    "Vitamina C", "Vitamina E", "Calcio", "Hierro", "Zinc", "Potasio"
]
selected_vm = st.sidebar.multiselect("Selecciona los que declararás", vm_options, default=["Vitamina A","Calcio","Hierro","Vitamina D","Zinc"])
vm_values = {}
for vm in selected_vm:
    unit = "µg" if vm in ("Vitamina A","Vitamina D","Vitamina B12") else "mg"
    vm_values[(vm, unit)] = as_num(st.sidebar.text_input(f"{vm} ({unit}/100)", value="0"))

# Pie — siempre inicia con el texto normativo
st.sidebar.subheader("Texto al pie")
footnote_tail = st.sidebar.text_input("Completa: No es fuente significativa de ...", value="Proteína, Vitamina D, Hierro, Calcio, Zinc, Vitamina A y fibra.")

# ============================================================
# CÁLCULOS POR PORCIÓN
# ============================================================
portion_size = household_mass
is_liquid = "Líquido" in physical_state

fat_total_pp  = portion_from_per100(fat_total_100, portion_size)
sat_fat_pp    = portion_from_per100(sat_fat_100, portion_size)
trans_fat_pp_mg = portion_from_per100(trans_fat_100_mg, portion_size)
carb_pp       = portion_from_per100(carb_100, portion_size)
sug_total_pp  = portion_from_per100(sug_total_100, portion_size)
sug_added_pp  = portion_from_per100(sug_added_100, portion_size)
fiber_pp      = portion_from_per100(fiber_100, portion_size)
protein_pp    = portion_from_per100(protein_100, portion_size)
sodium_pp_mg  = portion_from_per100(sodium_100_mg, portion_size)

# Micronutrientes por porción
vm_pp = {}
for (name, unit), v100 in vm_values.items():
    vm_pp[(name, unit)] = portion_from_per100(v100, portion_size)

# Energía
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp  = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)

# ============================================================
# ESTILO GRÁFICO
# ============================================================
BORDER_W       = 6   # marco exterior
GRID_W         = 3   # líneas standard
GRID_W_THICK   = 9   # líneas gruesas (triple)
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

# ============================================================
# CONSTRUCCIÓN DE FILAS COMUNES (nombres + valores formateados)
# ============================================================
def common_rows():
    rows = [
        # (label, v100_str, vpp_str, indent, bold, is_micro)
        ("Grasa total",        f"{fmt_g(fat_total_100,1)} g",        f"{fmt_g(fat_total_pp,1)} g",         0, False, False),
        ("  Grasa saturada",   f"{fmt_g(sat_fat_100,1)} g",          f"{fmt_g(sat_fat_pp,1)} g",           1, True,  False),
        ("  Grasas trans",     f"{fmt_mg(trans_fat_100_mg)} mg",     f"{fmt_mg(trans_fat_pp_mg)} mg",      1, True,  False),
        ("Carbohidratos totales", f"{fmt_g(carb_100,1)} g",          f"{fmt_g(carb_pp,1)} g",              0, False, False),
        ("  Fibra dietaria",   f"{fmt_g(fiber_100,1)} g",            f"{fmt_g(fiber_pp,1)} g",             1, False, False),
        ("  Azúcares totales", f"{fmt_g(sug_total_100,1)} g",        f"{fmt_g(sug_total_pp,1)} g",         1, False, False),
        ("  Azúcares añadidos",f"{fmt_g(sug_added_100,1)} g",        f"{fmt_g(sug_added_pp,1)} g",         1, True,  False),
        ("Proteína",           f"{fmt_g(protein_100,1)} g",          f"{fmt_g(protein_pp,1)} g",           0, False, False),
        ("Sodio",              f"{fmt_mg(sodium_100_mg)} mg",        f"{fmt_mg(sodium_pp_mg)} mg",         0, True,  False),
    ]
    return rows

def micro_rows():
    rows = []
    for (name, unit), v100 in vm_values.items():
        vpp = vm_pp[(name, unit)]
        rows.append(
            (name, f"{fmt_mg(v100) if unit=='mg' else fmt_g(v100,1)} {unit}",
                   f"{fmt_mg(vpp)  if unit=='mg' else fmt_g(vpp,1)} {unit}",
             0, False, True)
        )
    return rows

def column_labels():
    return ("Por 100 g" if not is_liquid else "Por 100 mL", "Por porción")

# ============================================================
# FIGURA 1 — VERTICAL ESTÁNDAR
# ============================================================
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1400
    header_h = 140  # título + bloque izq con porción/porciones
    colhdr_h = 70
    calories_h = ROW_H
    gap_after_title = 10

    body_rows_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    foot_h = 110

    H = BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK + colhdr_h + GRID_W + calories_h + GRID_W_THICK + body_rows_h + GRID_W_THICK + foot_h

    # Columnas: label / por100 / porción
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # Marco
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # ---------- Título centrado ----------
    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W - tw)//2, BORDER_W + 10), title, fill=TEXT_COLOR, font=FONT_TITLE)

    # ---------- Bloque porción (izquierda) ----------
    y0 = BORDER_W + 10 + th + 6
    d.text((BORDER_W + CELL_PAD_X, y0 + 16), f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})", fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, y0 + 16 + 36), f"Número de porciones por envase: Aprox. {fmt_g(servings_per_pack,0)}", fill=TEXT_COLOR, font=FONT_SMALL)

    # Línea gruesa separando título/bloque de todo lo demás
    y_line_top = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y_line_top, TEXT_COLOR, GRID_W_THICK)

    # ---------- Encabezados de columnas ----------
    c100, cpp = column_labels()
    y = y_line_top + 1
    w_c100, _ = text_size(d, c100, FONT_SMALL_B)
    w_cpp, _  = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2] - CELL_PAD_X - w_c100, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - CELL_PAD_X - w_cpp,  y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    # Línea fina bajo encabezados
    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    # ---------- Inician verticales internas (no atraviesan título) ----------
    data_top = y  # desde aquí bajan las verticales hasta el pie
    draw_vline(d, col_x[2], data_top, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, H - BORDER_W - foot_h - GRID_W_THICK, TEXT_COLOR, GRID_W)

    # ---------- Fila Calorías (misma fila, sin repetir “Por 100 g / Por porción”) ----------
    y += 1
    # línea gruesa arriba de calorías
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 2

    d.text((BORDER_W + CELL_PAD_X, y + (ROW_H//2) - 14), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)

    kc100 = fmt_kcal(kcal_100)
    kcpp  = fmt_kcal(kcal_pp)
    w1, _ = text_size(d, kc100, FONT_LABEL_B)
    w2, _ = text_size(d, kcpp,  FONT_LABEL_B)
    d.text((col_x[2] - CELL_PAD_X - w1, y + (ROW_H//2) - 14), kc100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - CELL_PAD_X - w2, y + (ROW_H//2) - 14), kcpp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    y += calories_h
    # línea gruesa bajo calorías
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # ---------- Resto de nutrientes ----------
    for label, v100, vpp, indent, bold, is_micro in rows_nutri:
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

    # Separador nutrientes/micro
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # ---------- Micronutrientes (pequeños) ----------
    if show_micro:
        for label, v100, vpp, indent, bold, _ in rows_micro:
            y += 1
            draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
            font_lbl = FONT_MICRO
            font_val = FONT_MICRO
            x_label = BORDER_W + CELL_PAD_X + indent*28
            y_text = y + (ROW_H_MICRO//2) - 12
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
            wv100, _ = text_size(d, v100, font_val)
            wvpp,  _ = text_size(d, vpp,  font_val)
            d.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
            d.text((col_x[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
            y += ROW_H_MICRO

    # Línea gruesa antes del pie
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # ---------- Pie ----------
    foot = f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}"
    d.text((BORDER_W + CELL_PAD_X, y + 20), foot, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

# ============================================================
# FIGURA 3 — SIMPLIFICADO
# ============================================================
def draw_fig3():
    # Selección reducida
    rows = [
        ("Grasa total",        f"{fmt_g(fat_total_100,1)} g",    f"{fmt_g(fat_total_pp,1)} g",         0, False),
        ("  Grasa saturada",   f"{fmt_g(sat_fat_100,1)} g",      f"{fmt_g(sat_fat_pp,1)} g",           1, True),
        ("  Grasas trans",     f"{fmt_mg(trans_fat_100_mg)} mg", f"{fmt_mg(trans_fat_pp_mg)} mg",      1, True),
        ("Carbohidratos totales", f"{fmt_g(carb_100,1)} g",      f"{fmt_g(carb_pp,1)} g",              0, False),
        ("  Azúcares añadidos",f"{fmt_g(sug_added_100,1)} g",    f"{fmt_g(sug_added_pp,1)} g",         1, True),
        ("Proteína",           f"{fmt_g(protein_100,1)} g",      f"{fmt_g(protein_pp,1)} g",           0, False),
        ("Sodio",              f"{fmt_mg(sodium_100_mg)} mg",    f"{fmt_mg(sodium_pp_mg)} mg",         0, True),
    ]
    W = 1200
    header_h = 140
    colhdr_h = 70
    calories_h = ROW_H
    foot_h = 110
    H = BORDER_W*2 + header_h + 10 + GRID_W_THICK + colhdr_h + GRID_W + calories_h + GRID_W_THICK + len(rows)*ROW_H + GRID_W_THICK + foot_h

    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Título + bloque izquierdo
    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W-tw)//2, BORDER_W+10), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16), f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})", fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16 + 36), f"Número de porciones por envase: Aprox. {fmt_g(servings_per_pack,0)}", fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + 10
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Encabezados columnas
    c100, cpp = column_labels()
    w1,_ = text_size(d, c100, FONT_SMALL_B)
    w2,_ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2]-CELL_PAD_X-w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3]-CELL_PAD_X-w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
    data_top = y
    draw_vline(d, col_x[2], data_top, H-BORDER_W-foot_h-GRID_W_THICK, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, H-BORDER_W-foot_h-GRID_W_THICK, TEXT_COLOR, GRID_W)

    # Calorías
    y += 1
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 2
    d.text((BORDER_W + CELL_PAD_X, y + (ROW_H//2) - 14), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)
    kc100 = fmt_kcal(kcal_100); kcpp = fmt_kcal(kcal_pp)
    wv1,_ = text_size(d, kc100, FONT_LABEL_B)
    wv2,_ = text_size(d, kcpp,  FONT_LABEL_B)
    d.text((col_x[2] - CELL_PAD_X - wv1, y + (ROW_H//2) - 14), kc100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - CELL_PAD_X - wv2, y + (ROW_H//2) - 14), kcpp,  fill=TEXT_COLOR, font=FONT_LABEL_B)
    y += ROW_H
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # filas
    for label, v100, vpp, indent, bold in rows:
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
    d.text((BORDER_W + CELL_PAD_X, y + 20), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)

    return img

# ============================================================
# FIGURA 4 — TABULAR
# ============================================================
def draw_fig4():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro)>0

    # Estética tabular: cuadrícula completa, celdas bien ajustadas
    W = 1500
    header_h = 140
    colhdr_h = 70
    calories_h = ROW_H
    foot_h = 110

    body_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    H = BORDER_W*2 + header_h + 10 + GRID_W_THICK + colhdr_h + GRID_W + calories_h + GRID_W_THICK + body_h + GRID_W_THICK + foot_h

    # Columnas más “tabla”: 1ra más ancha, 2da y 3ra balanceadas
    col_x = [BORDER_W, BORDER_W + int(W*0.52), BORDER_W + int(W*0.78), W - BORDER_W]

    img = Image.new("RGB", (W,H), BG_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Título + bloque izq
    title = "Información Nutricional"
    tw, th = text_size(d, title, FONT_TITLE)
    d.text(((W-tw)//2, BORDER_W+10), title, fill=TEXT_COLOR, font=FONT_TITLE)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16), f"Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})", fill=TEXT_COLOR, font=FONT_SMALL)
    d.text((BORDER_W + CELL_PAD_X, BORDER_W + 10 + th + 16 + 36), f"Número de porciones por envase: Aprox. {fmt_g(servings_per_pack,0)}", fill=TEXT_COLOR, font=FONT_SMALL)

    y = BORDER_W + header_h + 10
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Encabezados columnas
    c100, cpp = column_labels()
    w1,_ = text_size(d, c100, FONT_SMALL_B)
    w2,_ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2]-CELL_PAD_X-w1, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3]-CELL_PAD_X-w2, y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    # Verticales completas (cuadrícula)
    data_bottom_limit = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], y, data_bottom_limit, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], y, data_bottom_limit, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], y, data_bottom_limit, TEXT_COLOR, GRID_W)

    # Calorías — negrilla
    y += 1
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)
    y += 2
    d.text((BORDER_W + CELL_PAD_X, y + (ROW_H//2) - 14), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)
    kc100 = fmt_kcal(kcal_100); kcpp = fmt_kcal(kcal_pp)
    wv1,_ = text_size(d, kc100, FONT_LABEL_B)
    wv2,_ = text_size(d, kcpp,  FONT_LABEL_B)
    d.text((col_x[2]-CELL_PAD_X-wv1, y + (ROW_H//2) - 14), kc100, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3]-CELL_PAD_X-wv2, y + (ROW_H//2) - 14), kcpp,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    y += ROW_H
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Resto de filas (con cuadrícula completa y negrillas normativas)
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

    # Micronutrientes (si hay)
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

    # Pie
    d.text((BORDER_W + CELL_PAD_X, y + 20), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)

    return img

# ============================================================
# FIGURA 5 — LINEAL
# ============================================================
def draw_fig5():
    # Itinerario textual — por porción con paréntesis por 100
    items = []

    def pair(name, vpp, v100):
        items.append(f"{name}: {vpp} (por 100: {v100})")

    pair("Calorías", f"{fmt_kcal(kcal_pp)} kcal", f"{fmt_kcal(kcal_100)} kcal")
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

    # Primera línea informativa
    left_x = BORDER_W + 28
    y = BORDER_W + 28
    d.text((left_x, y), f"Información nutricional (por porción): Tamaño por porción: {household_name} ({int(round(portion_size))} {portion_unit})   •   Número de porciones por envase: Aprox. {fmt_g(servings_per_pack,0)}", fill=TEXT_COLOR, font=FONT_SMALL_B)
    y += 52

    # Texto corrido con saltos por ancho
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
    d.text((left_x, y), f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}", fill=TEXT_COLOR, font=FONT_SMALL)

    return img

# ============================================================
# PREVISUALIZACIÓN + EXPORTACIÓN
# ============================================================
st.header("Previsualización")
left, right = st.columns([0.72, 0.28])
with right:
    export_btn = st.button("Generar PNG")

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
