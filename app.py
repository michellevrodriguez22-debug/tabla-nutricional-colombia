# app.py
# =====================================================================
# Generador de Tabla Nutricional Colombia (PNG export, sin PDF)
# Cumple visualmente con Res. 810/2021 (y 2492/2022, 254/2023)
# Formatos soportados desde la barra lateral:
#   - Fig. 1  → Vertical estándar
#   - Fig. 3  → Simplificado
#   - Fig. 4  → Tabular (grid)
#   - Fig. 5  → Lineal
#
# Cambios solicitados y aplicados:
#   ✓ SOLO ingreso por 100 g / 100 mL (se eliminó "por porción" como base).
#   ✓ Se eliminó "tipo de producto" (materias primas generalmente no llevan tabla).
#   ✓ Título "Información Nutricional" centrado y más grande.
#   ✓ En la cabecera: “Tamaño de porción: <medida casera> (<peso en g/mL>)”
#     y “Número de porciones por envase: <n>” (texto exacto).
#   ✓ En la fila de Calorías: texto “Calorías (kcal)” y, en la MISMA FILA,
#     columnas “por 100 g/mL” y “por porción” con sus valores.
#   ✓ Las etiquetas de columnas muestran SOLO el título (“por 100 … / por porción”);
#     no se repite el tamaño de porción allí.
#   ✓ Líneas gruesas: arriba y abajo de calorías, y entre macros y micros.
#   ✓ Micronutrientes en fuente un poco más pequeña.
#   ✓ Fig. 4 (Tabular) con estética de grilla real (verticales y horizontales
#     consistentes, sin atravesar encabezados).
#   ✓ Negrillas en: Calorías, Grasa saturada, Grasas trans, Azúcares añadidos, Sodio.
#   ✓ Exporta SIEMPRE PNG (fondo blanco), sin título adicional ni marca.
#   ✓ Mantiene spacing, centrado horizontal de med. casera (texto), y la
#     “misma escala” visual acordada.
#
# NOTA DE IMPLEMENTACIÓN:
#   - La app pide: estado físico (Sólido/Líquido), y TODOS los valores “por 100 g/mL”.
#   - Calcula “por porción” a partir de: Peso por porción (g/mL).
#   - “Medida casera” se ingresa como texto (p. ej., “1 taza”, “1 unidad”).
#   - Se respetan unidades: g / mg; Vitamina A en µg ER (como pediste).
# =====================================================================

import math
from io import BytesIO
from datetime import datetime

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------
# CONFIG STREAMLIT
# ---------------------------------------------------------------------
st.set_page_config(page_title="Generador de Tabla Nutricional (Colombia)", layout="wide")
st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

# ---------------------------------------------------------------------
# UTILIDADES NUMÉRICAS Y DE FORMATO
# ---------------------------------------------------------------------
def as_num(x, default=0.0):
    try:
        if x is None or (isinstance(x, str) and x.strip() == ""):
            return float(default)
        return float(x)
    except Exception:
        return float(default)

def fmt_g(x, nd=1):
    try:
        x = float(x)
        if nd <= 0:
            return f"{int(round(x))}"
        s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
        return s if s != "" else "0"
    except Exception:
        return "0"

def fmt_mg(x):
    try:
        return f"{int(round(float(x)))}"
    except Exception:
        return "0"

def fmt_kcal(x):
    try:
        return f"{int(round(float(x)))}"
    except Exception:
        return "0"

def kcal_from_macros_100g(fat_g, carb_g, protein_g, organic_acids_g=0.0, alcohol_g=0.0):
    """
    Res. 810: 9 kcal/g (grasa), 4 (carb/proteína), 7 (alcohol, si aplica), 3 (ácidos orgánicos)
    """
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9*fat_g + 4*carb_g + 4*protein_g + 7*alcohol_g + 3*organic_acids_g
    return float(round(kcal, 0))

def scale_to_portion(value_per100, portion_size):
    """
    Convierte un valor dado por 100 g/mL a valor por porción.
    """
    ps = portion_size or 0.0
    if ps <= 0:
        return 0.0
    return float(round((value_per100 * ps) / 100.0, 2))

# ---------------------------------------------------------------------
# ESTILO (FUENTES, LÍNEAS, COLORES)
# ---------------------------------------------------------------------
def get_font(size, bold=False):
    """
    Carga DejaVu Sans / Bold si está disponible en el entorno.
    Si falla, usa la fuente por defecto de PIL para evitar romper.
    """
    try:
        if bold:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()

def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])

def draw_hline(draw, x0, x1, y, color, width):
    draw.line((x0, y, x1, y), fill=color, width=width)

def draw_vline(draw, x, y0, y1, color, width):
    draw.line((x, y0, x, y1), fill=color, width=width)

# Colores y grosores unificados (mantenemos “misma escala”)
TEXT_COLOR = (0, 0, 0)
BG_WHITE = (255, 255, 255)
BORDER_W = 6           # marco externo
GRID_W_THICK = 9       # (triplicado respecto a una línea fina ~3)
GRID_W = 3             # línea normal

# Tipografías (escalas)
FONT_TITLE = get_font(44, bold=True)      # Título centrado un poco más grande
FONT_LABEL = get_font(30, bold=False)
FONT_LABEL_B = get_font(30, bold=True)
FONT_MICRO = get_font(26, bold=False)     # Micronutrientes ligeramente más pequeños
FONT_MICRO_B = get_font(26, bold=True)
FONT_SMALL = get_font(24, bold=False)
FONT_SMALL_B = get_font(24, bold=True)

# Alturas y paddings
ROW_H = 64
CELL_PAD_X = 22
CELL_PAD_Y = 18

# ---------------------------------------------------------------------
# BARRA LATERAL — CONFIGURACIÓN
# ---------------------------------------------------------------------
st.sidebar.header("Configuración general")

format_choice = st.sidebar.selectbox(
    "Formato a exportar",
    ["Fig. 1 — Vertical estándar", "Fig. 3 — Simplificado", "Fig. 4 — Tabular", "Fig. 5 — Lineal"],
    index=0
)

physical_state = st.sidebar.selectbox("Estado físico (para rotular 100):", ["Sólido (g)", "Líquido (mL)"])
is_liquid = ("Líquido" in physical_state)
unit_100 = "mL" if is_liquid else "g"

# SOLO ingreso por 100 g / 100 mL
st.sidebar.header(f"Ingreso por 100 {unit_100}")
fat_total_100 = as_num(st.sidebar.text_input("Grasa total (g / 100)", value="5"))
sat_fat_100   = as_num(st.sidebar.text_input("Grasa saturada (g / 100)", value="2"))
# Trans se ingresa en mg / 100 (respetando tu preferencia), y convertimos a g si hiciera falta
trans_100_mg  = as_num(st.sidebar.text_input("Grasas trans (mg / 100)", value="0"))
carb_100      = as_num(st.sidebar.text_input("Carbohidratos totales (g / 100)", value="20"))
sug_tot_100   = as_num(st.sidebar.text_input("Azúcares totales (g / 100)", value="10"))
sug_add_100   = as_num(st.sidebar.text_input("Azúcares añadidos (g / 100)", value="8"))
fiber_100     = as_num(st.sidebar.text_input("Fibra dietaria (g / 100)", value="2"))
protein_100   = as_num(st.sidebar.text_input("Proteína (g / 100)", value="3"))
sodium_100_mg = as_num(st.sidebar.text_input("Sodio (mg / 100)", value="150"))

# Medida casera y peso por porción
st.sidebar.header("Porción")
household_measure = st.sidebar.text_input("Medida casera (solo nombre, p.ej. '1 taza', '1 unidad')", value="1 porción")
portion_size = as_num(st.sidebar.text_input(f"Peso por porción ({unit_100})", value="50"))
servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="1"))

# Mostrar kJ
include_kj = st.sidebar.checkbox("Mostrar kJ junto a kcal", value=True)

# Micronutrientes
st.sidebar.header("Micronutrientes (opcional)")
vm_options = [
    "Vitamina A (µg ER)",  # µg ER explícito
    "Vitamina D (µg)",
    "Calcio (mg)",
    "Hierro (mg)",
    "Zinc (mg)",
    "Potasio (mg)",
    "Vitamina C (mg)",
    "Vitamina E (mg)",
    "Vitamina B12 (µg)",
    "Ácido fólico (µg)",
]
selected_vm = st.sidebar.multiselect(
    "Selecciona micronutrientes a incluir",
    vm_options,
    default=["Vitamina A (µg ER)", "Vitamina D (µg)", "Calcio (mg)", "Hierro (mg)", "Zinc (mg)"]
)

vm_values_100 = {}
for vm in selected_vm:
    vm_values_100[vm] = as_num(st.sidebar.text_input(f"{vm} por 100 ({'µg' if 'µg' in vm else 'mg'})", value="0"))

# Frase pie (siempre presente)
st.sidebar.header("Texto al pie")
tail = st.sidebar.text_input("Completa 'No es fuente significativa de …'", value="_____.")
footnote_ns = f"No es fuente significativa de {tail.strip()}"

# ---------------------------------------------------------------------
# CÁLCULOS (por porción derivados desde 100)
# ---------------------------------------------------------------------
# Calorías por 100
kcal_100 = kcal_from_macros_100g(fat_total_100, carb_100, protein_100)
kj_100 = round(kcal_100 * 4.184) if include_kj else None

# Escalados por porción
def to_portion_g(val_100):
    return scale_to_portion(val_100, portion_size)

def to_portion_mg(val_100_mg):
    return scale_to_portion(val_100_mg, portion_size)

fat_pp        = to_portion_g(fat_total_100)
sat_fat_pp    = to_portion_g(sat_fat_100)
trans_pp_mg   = to_portion_mg(trans_100_mg)
carb_pp       = to_portion_g(carb_100)
sug_tot_pp    = to_portion_g(sug_tot_100)
sug_add_pp    = to_portion_g(sug_add_100)
fiber_pp      = to_portion_g(fiber_100)
protein_pp    = to_portion_g(protein_100)
sodium_pp_mg  = to_portion_mg(sodium_100_mg)

kcal_pp = kcal_from_macros_100g(fat_pp, carb_pp, protein_pp)
kj_pp = round(kcal_pp * 4.184) if include_kj else None

# Micronutrientes por porción
vm_values_pp = {}
for vm, v100 in vm_values_100.items():
    vm_values_pp[vm] = scale_to_portion(v100, portion_size)

# ---------------------------------------------------------------------
# FILAS DE NUTRIENTES (common builder)
# ---------------------------------------------------------------------
def build_rows_common(is_tabular=False):
    """
    Genera:
      - etiquetas de columnas (“por 100 …” vs “por porción”)
      - pares de (label, v100_text, vpp_text, indent, bold, is_micronutrient)
    Donde 'indent'=1 dibuja como sub-ítem (sangría).
    """
    per100_label = f"por 100 {unit_100}"
    perportion_label = "por porción"  # (sin tamaño; pediste solo el título)

    rows = []

    # Cabecera de columnas (se dibuja textual; en tabular también)
    rows.append(("", per100_label, perportion_label, 0, False, False, True))  # flag final: header columnas

    # Macronutrientes (orden 810)
    rows.append(("Grasa total", f"{fmt_g(fat_total_100,1)} g", f"{fmt_g(fat_pp,1)} g", 0, False, False, False))
    rows.append(("Grasa saturada", f"{fmt_g(sat_fat_100,1)} g", f"{fmt_g(sat_fat_pp,1)} g", 1, True,  False, False))
    rows.append(("Grasas trans", f"{fmt_mg(trans_100_mg)} mg", f"{fmt_mg(trans_pp_mg)} mg", 1, True,  False, False))

    rows.append(("Carbohidratos", f"{fmt_g(carb_100,1)} g", f"{fmt_g(carb_pp,1)} g", 0, False, False, False))
    rows.append(("Azúcares totales", f"{fmt_g(sug_tot_100,1)} g", f"{fmt_g(sug_tot_pp,1)} g", 1, False, False, False))
    rows.append(("Azúcares añadidos", f"{fmt_g(sug_add_100,1)} g", f"{fmt_g(sug_add_pp,1)} g", 1, True,  False, False))
    rows.append(("Fibra dietaria", f"{fmt_g(fiber_100,1)} g", f"{fmt_g(fiber_pp,1)} g", 1, False, False, False))

    rows.append(("Proteína", f"{fmt_g(protein_100,1)} g", f"{fmt_g(protein_pp,1)} g", 0, False, False, False))
    rows.append(("Sodio", f"{fmt_mg(sodium_100_mg)} mg", f"{fmt_mg(sodium_pp_mg)} mg", 0, True,  False, False))

    # Separador grueso antes de micronutrientes
    if selected_vm:
        rows.append(("---sep---", "", "", 0, False, False, False))

        for vm in selected_vm:
            unit = "µg" if "µg" in vm else "mg"
            name = "Vitamina A (µg ER)" if vm.startswith("Vitamina A") else vm
            v100 = vm_values_100.get(vm, 0.0)
            vpp  = vm_values_pp.get(vm, 0.0)

            v100_str = f"{fmt_g(v100,1)} {unit}" if unit == "µg" else f"{fmt_mg(v100)} {unit}"
            vpp_str  = f"{fmt_g(vpp,1)} {unit}"  if unit == "µg" else f"{fmt_mg(vpp)} {unit}"

            # Micronutrientes van un poco más pequeños
            rows.append((name, v100_str, vpp_str, 0, False, True, False))

    return per100_label, perportion_label, rows

# ---------------------------------------------------------------------
# DIBUJO DE FORMATOS
# ---------------------------------------------------------------------
def draw_header_block(draw, W, cur_y, title_align_center=True):
    """
    Cabecera común:
      - Marco externo: fuera
      - Dentro: título centrado “Información Nutricional”
      - Debajo: “Tamaño de porción: <medida casera> (<peso y unidad>)”
               “Número de porciones por envase: <n>”
    Retorna: nueva_y (fin de cabecera)
    """
    # Título centrado
    title = "Información Nutricional"
    tw, th = text_size(draw, title, FONT_TITLE)
    title_x = (W - tw) // 2
    draw.text((title_x, cur_y + 10), title, fill=TEXT_COLOR, font=FONT_TITLE)

    # Medida casera y peso por porción
    sub1 = f"Tamaño de porción: {household_measure} ({int(round(portion_size))} {unit_100})"
    sub2 = f"Número de porciones por envase: {int(round(servings_per_pack))}"

    sw1, sh1 = text_size(draw, sub1, FONT_SMALL_B)
    sw2, sh2 = text_size(draw, sub2, FONT_SMALL)

    # Centrado horizontal (como pediste)
    x_sub1 = (W - sw1) // 2
    x_sub2 = (W - sw2) // 2

    draw.text((x_sub1, cur_y + th + 18), sub1, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((x_sub2, cur_y + th + 18 + sh1 + 8), sub2, fill=TEXT_COLOR, font=FONT_SMALL)

    return cur_y + th + 18 + sh1 + 8 + sh2 + 10

def draw_calories_row(draw, W, col_x, cur_y):
    """
    Dibuja la fila de Calorías (kcal) en negrita y, EN LA MISMA FILA,
    sus dos valores: “por 100 …” y “por porción”.
    También dibuja líneas gruesas arriba y abajo.
    """
    # Línea gruesa superior
    draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)

    # Texto “Calorías (kcal)”
    label = "Calorías (kcal)"
    draw.text((BORDER_W + CELL_PAD_X, cur_y + (ROW_H // 2) - 12), label, fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Valores kcal
    kcal_100_txt = fmt_kcal(kcal_100) + (f" ({kj_100} kJ)" if include_kj else "")
    kcal_pp_txt  = fmt_kcal(kcal_pp)  + (f" ({kj_pp} kJ)" if include_kj else "")

    w1, _ = text_size(draw, kcal_100_txt, FONT_LABEL_B)
    w2, _ = text_size(draw, kcal_pp_txt,  FONT_LABEL_B)

    draw.text((col_x[2] - CELL_PAD_X - w1, cur_y + (ROW_H // 2) - 12), kcal_100_txt, fill=TEXT_COLOR, font=FONT_LABEL_B)
    draw.text((col_x[3] - CELL_PAD_X - w2, cur_y + (ROW_H // 2) - 12), kcal_pp_txt,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Línea gruesa inferior
    cur_y += ROW_H
    draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
    return cur_y

def draw_column_headers(draw, col_x, cur_y, per100_label, perportion_label):
    """
    Dibuja la fila de cabeceras de columnas (por 100 … / por porción)
    y una línea fina debajo. No dibuja verticales para no atravesar.
    """
    w_c100, _ = text_size(draw, per100_label, FONT_SMALL_B)
    w_cpp,  _ = text_size(draw, perportion_label, FONT_SMALL_B)
    draw.text((col_x[2] - CELL_PAD_X - w_c100, cur_y + CELL_PAD_Y), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col_x[3] - CELL_PAD_X - w_cpp,  cur_y + CELL_PAD_Y), perportion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    cur_y += 70
    return cur_y

def draw_rows_block(draw, W, H, col_x, cur_y, rows, footer_h, micros_smaller=True, tabular_grid=False):
    """
    Dibuja filas (macros y micros). Para 'tabular_grid' se usan verticales de columna
    desde aquí hacia abajo; para los otros, solo verticales a partir de esta sección.
    Inserta línea gruesa entre macros y micros si hay micronutrientes.
    """
    # Línea fina bajo cabeceras
    draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W)

    # Verticales (evitando atravesar encabezado)
    if tabular_grid:
        draw_vline(draw, col_x[1], cur_y, H - BORDER_W - footer_h - 40, TEXT_COLOR, GRID_W)
        draw_vline(draw, col_x[2], cur_y, H - BORDER_W - footer_h - 40, TEXT_COLOR, GRID_W)
        draw_vline(draw, col_x[3], cur_y, H - BORDER_W - footer_h - 40, TEXT_COLOR, GRID_W)
    else:
        draw_vline(draw, col_x[2], cur_y, H - BORDER_W - footer_h - 40, TEXT_COLOR, GRID_W)
        draw_vline(draw, col_x[3], cur_y, H - BORDER_W - footer_h - 40, TEXT_COLOR, GRID_W)

    # Bucle filas
    passed_sep = False
    for tup in rows[1:]:
        label, v100, vpp, indent, bold, is_micro, _ = tup

        if label == "---sep---":
            draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
            passed_sep = True
            continue

        # Línea superior de fila
        draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W)

        font_lbl = FONT_MICRO_B if (is_micro and micros_smaller and bold) else (
                   FONT_MICRO if (is_micro and micros_smaller) else (
                   FONT_LABEL_B if bold else FONT_LABEL))

        font_val = font_lbl  # mismos pesos para el valor cuando bold

        x_label = BORDER_W + CELL_PAD_X + (indent * 28)
        y_text  = cur_y + (ROW_H // 2) - 14

        # Dibuja label
        draw.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)

        # Valores (alineados a derecha en col 2 y col 3)
        wv100, _ = text_size(draw, v100, font_val)
        wvpp,  _ = text_size(draw, vpp,  font_val)
        draw.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((col_x[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)

        cur_y += ROW_H

    # Si hubo micronutrientes, asegurar remate visual con línea gruesa antes de pie
    if passed_sep:
        draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
    else:
        draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W)

    return cur_y

# ----------------- Fig. 1: Vertical estándar --------------------------
def draw_table_fig1():
    per100_label, perportion_label, rows = build_rows_common(is_tabular=False)

    # Dimensiones
    W = 1400
    header_h = 160
    colhdr_h = 70
    footer_h = 120

    # Altura dinámica
    sep_count = sum(1 for r in rows if r[0] == "---sep---")
    data_rows = [r for r in rows if r[0] != "---sep---"]
    H = BORDER_W*2 + header_h + ROW_H + colhdr_h + len(data_rows)*ROW_H + sep_count*GRID_W_THICK + footer_h + 40

    # Columnas
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco
    draw.rectangle([0, 0, W-1, H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Cabecera centrada
    cur_y = BORDER_W + 6
    cur_y = draw_header_block(draw, W, cur_y)

    # Calorías (misma fila con valores)
    cur_y = draw_calories_row(draw, W, col_x, cur_y)

    # Cabeceras de columnas
    cur_y = draw_column_headers(draw, col_x, cur_y, per100_label, perportion_label)

    # Filas
    cur_y = draw_rows_block(draw, W, H, col_x, cur_y, rows, footer_h, micros_smaller=True, tabular_grid=False)

    # Pie
    cur_y += 16
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 12), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

# ----------------- Fig. 3: Simplificado -------------------------------
def draw_table_fig3():
    # Construimos una lista recortada (conservando reglas de negrilla)
    per100_label = f"por 100 {unit_100}"
    perportion_label = "por porción"

    rows = [
        ("", per100_label, perportion_label, 0, False, False, True),
        ("Grasa total", f"{fmt_g(fat_total_100,1)} g", f"{fmt_g(fat_pp,1)} g", 0, False, False, False),
        ("Grasa saturada", f"{fmt_g(sat_fat_100,1)} g", f"{fmt_g(sat_fat_pp,1)} g", 1, True, False, False),
        ("Grasas trans", f"{fmt_mg(trans_100_mg)} mg", f"{fmt_mg(trans_pp_mg)} mg", 1, True, False, False),
        ("Carbohidratos", f"{fmt_g(carb_100,1)} g", f"{fmt_g(carb_pp,1)} g", 0, False, False, False),
        ("Azúcares añadidos", f"{fmt_g(sug_add_100,1)} g", f"{fmt_g(sug_add_pp,1)} g", 1, True, False, False),
        ("Proteína", f"{fmt_g(protein_100,1)} g", f"{fmt_g(protein_pp,1)} g", 0, False, False, False),
        ("Sodio", f"{fmt_mg(sodium_100_mg)} mg", f"{fmt_mg(sodium_pp_mg)} mg", 0, True, False, False),
    ]

    W = 1200
    header_h = 160
    colhdr_h = 70
    footer_h = 120
    H = BORDER_W*2 + header_h + ROW_H + colhdr_h + len(rows)*ROW_H + footer_h + 40

    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W-1, H-1], outline=TEXT_COLOR, width=BORDER_W)

    cur_y = BORDER_W + 6
    cur_y = draw_header_block(draw, W, cur_y)
    cur_y = draw_calories_row(draw, W, col_x, cur_y)
    cur_y = draw_column_headers(draw, col_x, cur_y, per100_label, perportion_label)
    cur_y = draw_rows_block(draw, W, H, col_x, cur_y, rows, footer_h, micros_smaller=True, tabular_grid=False)

    cur_y += 16
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 12), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

# ----------------- Fig. 4: Tabular (grid real) ------------------------
def draw_table_fig4():
    per100_label, perportion_label, rows = build_rows_common(is_tabular=True)

    # Dimensiones amplias y grid
    W = 1400
    header_h = 160
    colhdr_h = 70
    footer_h = 120
    sep_count = sum(1 for r in rows if r[0] == "---sep---")
    data_rows = [r for r in rows if r[0] != "---sep---"]
    H = BORDER_W*2 + header_h + ROW_H + colhdr_h + len(data_rows)*ROW_H + sep_count*GRID_W_THICK + footer_h + 40

    # En tabular la primera columna algo más ancha
    col_x = [BORDER_W, BORDER_W + int(W*0.56), BORDER_W + int(W*0.80), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W-1, H-1], outline=TEXT_COLOR, width=BORDER_W)

    cur_y = BORDER_W + 6
    cur_y = draw_header_block(draw, W, cur_y)
    cur_y = draw_calories_row(draw, W, col_x, cur_y)
    # Cabeceras
    w_c100, _ = text_size(draw, per100_label, FONT_SMALL_B)
    w_cpp,  _ = text_size(draw, perportion_label, FONT_SMALL_B)
    draw.text((col_x[2] - CELL_PAD_X - w_c100, cur_y + CELL_PAD_Y), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((col_x[3] - CELL_PAD_X - w_cpp,  cur_y + CELL_PAD_Y), perportion_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    cur_y += colhdr_h

    # Línea fina bajo cabecera de columnas
    draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W)

    # Verticales completas (grid)
    top_grid_y = cur_y
    grid_bottom = H - BORDER_W - footer_h - 40
    draw_vline(draw, col_x[1], top_grid_y, grid_bottom, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[2], top_grid_y, grid_bottom, TEXT_COLOR, GRID_W)
    draw_vline(draw, col_x[3], top_grid_y, grid_bottom, TEXT_COLOR, GRID_W)

    passed_sep = False
    for tup in rows[1:]:
        if tup[0] == "---sep---":
            draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
            passed_sep = True
            continue

        label, v100, vpp, indent, bold, is_micro, _ = tup

        # línea superior de fila
        draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W)

        # celdas
        font_lbl = FONT_MICRO_B if (is_micro and bold) else (FONT_MICRO if is_micro else (FONT_LABEL_B if bold else FONT_LABEL))
        font_val = font_lbl

        x_label = BORDER_W + CELL_PAD_X + (indent * 28)
        y_text = cur_y + (ROW_H // 2) - 14
        draw.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)

        wv100, _ = text_size(draw, v100, font_val)
        wvpp,  _ = text_size(draw, vpp,  font_val)
        draw.text((col_x[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((col_x[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)

        cur_y += ROW_H

    # Base
    if passed_sep:
        draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W_THICK)
    else:
        draw_hline(draw, BORDER_W, W - BORDER_W, cur_y, TEXT_COLOR, GRID_W)

    cur_y += 16
    draw.text((BORDER_W + CELL_PAD_X, cur_y + 12), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

# ----------------- Fig. 5: Lineal -------------------------------------
def draw_table_fig5():
    # Cadena lineal: por porción (valor), y entre paréntesis por 100
    items = []

    kcal_100_txt = fmt_kcal(kcal_100) + (f" ({kj_100} kJ)" if include_kj else "")
    kcal_pp_txt  = fmt_kcal(kcal_pp)  + (f" ({kj_pp} kJ)" if include_kj else "")

    def add_pair(name, vpp, v100):
        items.append(f"{name}: {vpp} (por 100: {v100})")

    add_pair("Calorías (kcal)", f"{fmt_kcal(kcal_pp)}" + (f" ({kj_pp} kJ)" if include_kj else ""),
             f"{fmt_kcal(kcal_100)}" + (f" ({kj_100} kJ)" if include_kj else ""))
    add_pair("Grasa total", f"{fmt_g(fat_pp,1)} g", f"{fmt_g(fat_total_100,1)} g")
    add_pair("Grasa saturada", f"{fmt_g(sat_fat_pp,1)} g", f"{fmt_g(sat_fat_100,1)} g")
    add_pair("Grasas trans", f"{fmt_mg(trans_pp_mg)} mg", f"{fmt_mg(trans_100_mg)} mg")
    add_pair("Carbohidratos", f"{fmt_g(carb_pp,1)} g", f"{fmt_g(carb_100,1)} g")
    add_pair("Azúcares totales", f"{fmt_g(sug_tot_pp,1)} g", f"{fmt_g(sug_tot_100,1)} g")
    add_pair("Azúcares añadidos", f"{fmt_g(sug_add_pp,1)} g", f"{fmt_g(sug_add_100,1)} g")
    add_pair("Fibra dietaria", f"{fmt_g(fiber_pp,1)} g", f"{fmt_g(fiber_100,1)} g")
    add_pair("Proteína", f"{fmt_g(protein_pp,1)} g", f"{fmt_g(protein_100,1)} g")
    add_pair("Sodio", f"{fmt_mg(sodium_pp_mg)} mg", f"{fmt_mg(sodium_100_mg)} mg")

    for vm in selected_vm:
        unit = "µg" if "µg" in vm else "mg"
        name = "Vitamina A (µg ER)" if vm.startswith("Vitamina A") else vm
        v100 = vm_values_100.get(vm, 0.0)
        vpp  = vm_values_pp.get(vm, 0.0)
        vpp_txt  = f"{fmt_g(vpp,1)} {unit}" if unit == "µg" else f"{fmt_mg(vpp)} {unit}"
        v100_txt = f"{fmt_g(v100,1)} {unit}" if unit == "µg" else f"{fmt_mg(v100)} {unit}"
        add_pair(name, vpp_txt, v100_txt)

    W = 1600
    H = 560 if len(items) <= 8 else 720 if len(items) <= 14 else 900
    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco
    draw.rectangle([0, 0, W-1, H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Cabecera centrada (sin caja interior adicional)
    y = BORDER_W + 6
    y = draw_header_block(draw, W, y)

    # Texto lineal
    left_x = BORDER_W + 28
    y += 20

    # Construir una sola cadena separada por • y hacer wrap
    line_items = "  •  ".join(items)
    max_width = W - left_x - 30
    words = line_items.split(" ")
    line = ""
    lines = []
    for w in words:
        tmp = (line + " " + w).strip()
        if text_size(draw, tmp, FONT_LABEL)[0] <= max_width:
            line = tmp
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)

    for ln in lines:
        draw.text((left_x, y), ln, fill=TEXT_COLOR, font=FONT_LABEL)
        y += 48

    y += 6
    draw.text((left_x, y), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ---------------------------------------------------------------------
# PREVISUALIZACIÓN Y EXPORTACIÓN
# ---------------------------------------------------------------------
st.header("Previsualización")
preview_col, controls_col = st.columns([0.72, 0.28])

with controls_col:
    st.caption("Elige el formato y exporta la imagen (PNG, fondo blanco).")
    export_btn = st.button("Generar PNG", type="primary")

with preview_col:
    if format_choice.startswith("Fig. 1"):
        img_prev = draw_table_fig1()
    elif format_choice.startswith("Fig. 3"):
        img_prev = draw_table_fig3()
    elif format_choice.startswith("Fig. 4"):
        img_prev = draw_table_fig4()
    else:
        img_prev = draw_table_fig5()

    st.image(img_prev, caption="Vista previa (escala reducida)", use_column_width=True)

if export_btn:
    buf = BytesIO()
    img_prev.save(buf, format="PNG")
    buf.seek(0)
    fname = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    st.download_button("Descargar imagen PNG", data=buf, file_name=fname, mime="image/png")
