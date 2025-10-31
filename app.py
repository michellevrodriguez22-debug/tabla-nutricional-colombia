# app.py
# -*- coding: utf-8 -*-
"""
Generador de TABLA NUTRICIONAL (COLOMBIA)
Cumple formatos FIGURA 1 (Vertical estándar), FIGURA 3 (Simplificado),
FIGURA 4 (Tabular) y FIGURA 5 (Lineal), según Resolución 810/2021
(con ajustes 2492/2022 y 254/2023 para sellos informativos).
Salida en PNG (fondo blanco) lista para colocar en empaque.

Autoría: preparado para Michelle (UTadeo)
"""

import math
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import pandas as pd
import streamlit as st

# Pillow para dibujar PNG con control total sobre líneas, fuentes, grosores
from PIL import Image, ImageDraw, ImageFont

# =======================================
# Configuración general de la app
# =======================================
st.set_page_config(page_title="Generador tabla nutricional CO (PNG)", layout="wide")
st.title("Generador de Tabla de Información Nutricional (PNG) — Res. 810/2021")

# =======================================
# Utilidades numéricas y helpers
# =======================================
def as_num(x) -> float:
    try:
        if x is None or str(x).strip() == "":
            return 0.0
        return float(str(x).replace(",", "."))
    except Exception:
        return 0.0


def kcal_from_macros(
    fat_g: float, carb_g: float, protein_g: float, organic_acids_g: float = 0.0, alcohol_g: float = 0.0
) -> float:
    """
    Factores aceptados por 810/2021:
    - CHO 4 kcal/g, PRO 4 kcal/g, GRASA 9 kcal/g, Alcohol 7, Ácidos orgánicos 3.
    Se redondea a entero.
    """
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9 * fat_g + 4 * carb_g + 4 * protein_g + 7 * alcohol_g + 3 * organic_acids_g
    return float(round(kcal, 0))


def per100_from_portion(value_per_portion: float, portion_size: float) -> float:
    if portion_size and portion_size > 0:
        return float(round((value_per_portion / portion_size) * 100.0, 2))
    return 0.0


def portion_from_per100(value_per100: float, portion_size: float) -> float:
    if portion_size and portion_size > 0:
        return float(round((value_per100 * portion_size) / 100.0, 2))
    return 0.0


def pct_energy_from_nutrient_kcal(nutrient_kcal: float, total_kcal: float) -> float:
    if total_kcal and total_kcal > 0:
        return round((nutrient_kcal / total_kcal) * 100.0, 1)
    return 0.0


def fmt_g(x: float, nd: int = 1) -> str:
    # g con 1 decimal típico
    try:
        if x is None or math.isnan(x):
            return "0 g"
        return f"{x:.{nd}f} g".rstrip("0").rstrip(".") + (" g" if nd == 0 else "")
    except Exception:
        return "0 g"


def fmt_g_only(x: float, nd: int = 1) -> str:
    try:
        if x is None or math.isnan(x):
            return "0"
        s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
        return s
    except Exception:
        return "0"


def fmt_mg_int(x: float) -> str:
    try:
        return f"{int(round(x))} mg"
    except Exception:
        return "0 mg"


def fmt_ug(x: float, nd: int = 1) -> str:
    try:
        s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
        return f"{s} µg"
    except Exception:
        return "0 µg"


def fmt_uger(x: float, nd: int = 1) -> str:
    try:
        s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
        return f"{s} µg ER"
    except Exception:
        return "0 µg ER"


def fmt_kcal(x: float) -> str:
    try:
        return f"{int(round(x))}"
    except Exception:
        return "0"

# =======================================
# Fuentes (Pillow)
# =======================================
# Para asegurar render consistente sin depender del sistema, usamos DejaVu (incluida en muchas distros)
# y en caso de no estar, Pillow caerá a la fuente por defecto.
def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    # Intentos razonables
    candidates = []
    if bold:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/ttf/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/ttf/dejavu/DejaVuSans.ttf",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    # fallback
    return ImageFont.load_default()


# =======================================
# Parámetros globales de dibujo
# =======================================
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
THICK = 4         # grosor de líneas gruesas
MEDIUM = 3
THIN = 2

PADDING = 18      # margen interno
ROW_H = 42        # alto base de fila
HEAD_H = 56       # alto de cabeceras
TITLE_FS = 30     # tamaño fuente título "Información Nutricional"
BASE_FS = 22      # tamaño base
SMALL_FS = 19     # detalle pequeño

FONT_REG = lambda s: _load_font(s, bold=False)
FONT_BOLD = lambda s: _load_font(s, bold=True)

# =======================================
# Sidebar — datos del producto y configuración
# =======================================
st.sidebar.header("Datos del producto")
product_type = st.sidebar.selectbox("Tipo de producto", ["Producto terminado", "Materia prima"], index=0)
physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"], index=0)
input_basis = st.sidebar.radio("Modo de ingreso de datos", ["Por porción", "Por 100 g/mL"], index=0)

product_name = st.sidebar.text_input("Nombre del producto (no se imprime en PNG)", value="")
brand_name = st.sidebar.text_input("Marca (opcional, no se imprime)", value="")
provider = st.sidebar.text_input("Proveedor/Fabricante (opcional, no se imprime)", value="")

cps1, cps2 = st.sidebar.columns(2)
with cps1:
    portion_size = as_num(st.text_input("Tamaño de porción (número)", value="50"))
with cps2:
    portion_unit = "g" if "Sólido" in physical_state else "mL"
    st.text_input("Unidad de porción", value=portion_unit, disabled=True)

servings_per_pack = as_num(st.sidebar.text_input("Porciones por envase (número)", value="1"))

st.sidebar.header("Formato (según 810/2021)")
format_choice = st.sidebar.selectbox(
    "Elige el formato a exportar",
    [
        "Figura 1 — Vertical estándar",
        "Figura 3 — Simplificado",
        "Figura 4 — Tabular",
        "Figura 5 — Lineal",
    ],
    index=0,
)

include_kj = st.sidebar.checkbox("Mostrar también kJ en Calorías (opcional)", value=False)

st.sidebar.header("Micronutrientes a declarar")
vm_options = [
    "Vitamina A (µg ER)",  # µg equivalentes de retinol
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
    "Selecciona micronutrientes (opcionales)",
    vm_options,
    default=["Vitamina A (µg ER)", "Vitamina D (µg)", "Calcio (mg)", "Hierro (mg)", "Zinc (mg)"],
)

st.sidebar.header("Frase al pie")
footnote_base = st.sidebar.text_input(
    "Texto después de 'No es fuente significativa de ...' (puedes dejarlo vacío)",
    value="Proteína, Vitamina D, Hierro, Calcio, Zinc, Vitamina A y fibra",
)

# =======================================
# Ingreso de nutrientes
# =======================================
st.header("Ingreso de información nutricional (sin unidades, SOLO números)")
st.caption("El sistema calcula por 100 g/mL y por porción. Las grasas trans se ingresan en mg.")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Macronutrientes")
    fat_total_input = as_num(st.text_input("Grasa total (g)", value="5"))
    sat_fat_input = as_num(st.text_input("Grasa saturada (g)", value="2"))
    # Trans en mg (para visual), pero convertiremos a g para los cálculos
    trans_fat_input_mg = as_num(st.text_input("Grasas trans (mg)", value="0"))
    trans_fat_input_g = trans_fat_input_mg / 1000.0

    carb_input = as_num(st.text_input("Carbohidratos totales (g)", value="20"))
    sugars_total_input = as_num(st.text_input("Azúcares totales (g)", value="10"))
    sugars_added_input = as_num(st.text_input("Azúcares añadidos (g)", value="8"))
    fiber_input = as_num(st.text_input("Fibra dietaria (g)", value="2"))
    protein_input = as_num(st.text_input("Proteína (g)", value="3"))
    sodium_input_mg = as_num(st.text_input("Sodio (mg)", value="150"))

with c2:
    st.subheader("Micronutrientes seleccionados")
    vm_values: Dict[str, float] = {}
    for vm in selected_vm:
        vm_values[vm] = as_num(st.text_input(vm, value="0"))

# =======================================
# Normalización por porción vs por 100 g/mL
# =======================================
if input_basis == "Por porción":
    # Tomamos la porción como base
    fat_total_pp = fat_total_input
    sat_fat_pp = sat_fat_input
    trans_fat_pp = trans_fat_input_g  # g
    carb_pp = carb_input
    sugars_total_pp = sugars_total_input
    sugars_added_pp = sugars_added_input
    fiber_pp = fiber_input
    protein_pp = protein_input
    sodium_pp_mg = sodium_input_mg  # mg

    fat_total_100 = per100_from_portion(fat_total_pp, portion_size)
    sat_fat_100 = per100_from_portion(sat_fat_pp, portion_size)
    trans_fat_100 = per100_from_portion(trans_fat_pp, portion_size)  # g
    carb_100 = per100_from_portion(carb_pp, portion_size)
    sugars_total_100 = per100_from_portion(sugars_total_pp, portion_size)
    sugars_added_100 = per100_from_portion(sugars_added_pp, portion_size)
    fiber_100 = per100_from_portion(fiber_pp, portion_size)
    protein_100 = per100_from_portion(protein_pp, portion_size)
    sodium_100_mg = per100_from_portion(sodium_pp_mg, portion_size)  # mg
else:
    # Base por 100 g/mL
    fat_total_100 = fat_total_input
    sat_fat_100 = sat_fat_input
    trans_fat_100 = trans_fat_input_g  # g
    carb_100 = carb_input
    sugars_total_100 = sugars_total_input
    sugars_added_100 = sugars_added_input
    fiber_100 = fiber_input
    protein_100 = protein_input
    sodium_100_mg = sodium_input_mg  # mg

    fat_total_pp = portion_from_per100(fat_total_100, portion_size)
    sat_fat_pp = portion_from_per100(sat_fat_100, portion_size)
    trans_fat_pp = portion_from_per100(trans_fat_100, portion_size)  # g
    carb_pp = portion_from_per100(carb_100, portion_size)
    sugars_total_pp = portion_from_per100(sugars_total_100, portion_size)
    sugars_added_pp = portion_from_per100(sugars_added_100, portion_size)
    fiber_pp = portion_from_per100(fiber_100, portion_size)
    protein_pp = portion_from_per100(protein_100, portion_size)
    sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_size)  # mg

# ✅ IMPORTANTE: convertir trans a mg **DESPUÉS** de normalizar
trans_100_mg = trans_fat_100 * 1000.0
trans_pp_mg = trans_fat_pp * 1000.0

# Vitaminas/minerales: normalizar
vm_pp: Dict[str, float] = {}
vm_100: Dict[str, float] = {}
for vm, val in vm_values.items():
    if input_basis == "Por porción":
        vm_pp[vm] = val
        vm_100[vm] = per100_from_portion(val, portion_size)
    else:
        vm_100[vm] = val
        vm_pp[vm] = portion_from_per100(val, portion_size)

# =======================================
# Cálculo de energía y criterios FOP (informativo)
# =======================================
kcal_pp = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)

kj_pp = round(kcal_pp * 4.184) if include_kj else None
kj_100 = round(kcal_100 * 4.184) if include_kj else None

# Porcentajes para advertencias (2492/2022 y 254/2023)
pct_kcal_sug_add_pp = pct_energy_from_nutrient_kcal(4 * sugars_added_pp, kcal_pp)
pct_kcal_sat_fat_pp = pct_energy_from_nutrient_kcal(9 * sat_fat_pp, kcal_pp)
pct_kcal_trans_pp = pct_energy_from_nutrient_kcal(9 * trans_fat_pp, kcal_pp)

is_liquid = ("Líquido" in physical_state)
fop_sugar = pct_kcal_sug_add_pp >= 10.0
fop_sat = pct_kcal_sat_fat_pp >= 10.0
fop_trans = pct_kcal_trans_pp >= 1.0
if is_liquid and kcal_100 == 0:
    fop_sodium = sodium_100_mg >= 40.0
else:
    fop_sodium = (sodium_100_mg >= 300.0) or ((sodium_pp_mg / max(kcal_pp, 1)) >= 1.0)

with st.expander("Resultado de validación informativa (sellos posibles)"):
    cfs1, cfs2, cfs3, cfs4 = st.columns(4)
    cfs1.write(f"Azúcares añadidos ≥10% kcal: **{'Sí' if fop_sugar else 'No'}**")
    cfs2.write(f"Grasa saturada ≥10% kcal: **{'Sí' if fop_sat else 'No'}**")
    cfs3.write(f"Grasas trans ≥1% kcal: **{'Sí' if fop_trans else 'No'}**")
    cfs4.write(f"Sodio criterio aplicable: **{'Sí' if fop_sodium else 'No'}**")

# =======================================
# Funciones de dibujo (Pillow)
# =======================================
def draw_line(draw: ImageDraw.Draw, xy1, xy2, w=THIN):
    draw.line([xy1, xy2], fill=BLACK, width=w)


def draw_rect(draw: ImageDraw.Draw, xy, w=THIN):
    x1, y1, x2, y2 = xy
    draw.rectangle([x1, y1, x2, y2], outline=BLACK, width=w)


def text(draw: ImageDraw.Draw, xy, s: str, font: ImageFont.ImageFont, align="left"):
    x, y = xy
    if align == "left":
        draw.text((x, y), s, fill=BLACK, font=font, anchor="la")
    elif align == "right":
        draw.text((x, y), s, fill=BLACK, font=font, anchor="ra")
    elif align == "center":
        draw.text((x, y), s, fill=BLACK, font=font, anchor="ma")


def measure(s: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    bbox = font.getbbox(s)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w, h


def mk_canvas(width: int, height: int, white_bg=True) -> Image.Image:
    bg = WHITE if white_bg else (250, 250, 250)
    return Image.new("RGB", (width, height), color=bg)


def save_png(img: Image.Image, filename: str) -> BytesIO:
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf

# =======================================
# Construcción de contenidos comunes
# =======================================
per100_label = "Por 100 g" if not is_liquid else "Por 100 mL"
perportion_label = f"Por porción"

portion_label_text = f"Tamaño de porción: 1 unidad ({int(round(portion_size))}{portion_unit})"
servings_label_text = f"Número de porciones por envase: Aprox. {fmt_g_only(servings_per_pack, 0)}"

cal_100_txt = fmt_kcal(kcal_100)
cal_pp_txt = fmt_kcal(kcal_pp)
if include_kj:
    cal_100_txt += f" ({kj_100} kJ)"
    cal_pp_txt += f" ({kj_pp} kJ)"

# Micronutrientes: nombre limpio + unidad para Figuras 1/3/4 y texto lineal para Figura 5
def vm_unit_of(vm_name: str) -> str:
    if "(µg ER)" in vm_name:
        return "µg ER"
    if "(µg)" in vm_name:
        return "µg"
    if "(mg)" in vm_name:
        return "mg"
    return ""


def fmt_vm_value(name: str, v: float) -> str:
    unit = vm_unit_of(name)
    if unit == "µg ER":
        return fmt_uger(v, 1)
    if unit == "µg":
        return fmt_ug(v, 1)
    if unit == "mg":
        return fmt_mg_int(v)
    # fallback g (no debería pasar)
    return fmt_g(v, 1)


def clean_vm_label(name: str) -> str:
    # Para celdas, quitamos paréntesis de unidad en el nombre,
    # excepto que la Figura 1 muestra "Vitamina A" (y la unidad aparece al final).
    return name.split(" (")[0]

# =======================================
# Dibujo: Figura 1 (Vertical estándar)
# =======================================
def draw_figure1_vertical() -> BytesIO:
    """
    Estructura muy parecida a la referencia oficial,
    con cabecera, fila calorías en bold, bloque macronutrientes, bloque sodio,
    y bloque de vitaminas/minerales (si se seleccionan).
    """
    cols = 3  # Col0: etiqueta, Col1: por 100, Col2: por porción
    W = 1320
    left_col_w = 620
    right_w = W - left_col_w
    col_w = right_w // 2
    # Altura: estimada según número de filas
    base_rows = 2 + 1 + 1 + 8 + 1  # (título, porción/por-envase) + calorías + encabezados + 8 filas macro + bloque sodio (1 línea)
    vm_rows = len(selected_vm)
    total_rows = base_rows + (vm_rows if vm_rows > 0 else 0) + 2  # +2 por separadores adicionales
    H = 180 + total_rows * ROW_H

    img = mk_canvas(W, H, white_bg=True)
    draw = ImageDraw.Draw(img)

    # Marco exterior
    draw_rect(draw, (THIN, THIN, W-THIN, H-THIN), w=THICK)

    # Título “Información Nutricional”
    title_font = FONT_BOLD(TITLE_FS)
    w_title, h_title = measure("Información Nutricional", title_font)
    text(draw, (W/2, PADDING + h_title//2), "Información Nutricional", title_font, align="center")

    y = PADDING + h_title + 12

    # Línea horizontal gruesa
    draw_line(draw, (THIN, y), (W-THIN, y), w=THICK)
    y += 8

    # Tamaño de porción + porciones por envase en dos líneas
    font_small = FONT_REG(SMALL_FS)
    text(draw, (PADDING, y + 6), portion_label_text, font_small, align="left")
    y += ROW_H - 8
    text(draw, (PADDING, y), servings_label_text, font_small, align="left")
    y += ROW_H - 10

    # Línea bajo metadatos
    draw_line(draw, (THIN, y), (W-THIN, y), w=THICK)

    # Fila Calorías
    y += 6
    font_bold = FONT_BOLD(BASE_FS)
    font_reg = FONT_REG(BASE_FS)

    # Celda "Calorías (kcal)" a izquierda
    text(draw, (PADDING, y + ROW_H//2), "Calorías (kcal)", font_bold, align="left")
    # Encabezado Por 100 / Por porción (sobre la derecha)
    # Creamos tres columnas: etiqueta | por 100 | por porción
    # Cabeceras por 100 / por porción:
    header_y = y - (ROW_H//2)
    # Rect columnas
    x0 = THIN
    x1 = left_col_w
    x2 = left_col_w + col_w
    x3 = W - THIN

    # Marco vertical interior
    draw_line(draw, (x1, header_y), (x1, H-THIN), w=MEDIUM)
    draw_line(draw, (x2, header_y), (x2, H-THIN), w=MEDIUM)

    # Encabezados por 100/por porción (sobre la fila de calorías)
    text(draw, (x1 + col_w/2, y - 6), per100_label, font_reg, align="center")
    text(draw, (x2 + col_w/2, y - 6), perportion_label, font_reg, align="center")

    # Valores calorías
    text(draw, (x2 - 10, y + ROW_H//2), cal_pp_txt, font_bold, align="right")
    text(draw, (x1 + col_w - 10, y + ROW_H//2), cal_100_txt, font_bold, align="right")

    # Separador grueso bajo calorías
    y += ROW_H + 6
    draw_line(draw, (THIN, y), (W-THIN, y), w=THICK)

    # Filas de macronutrientes en orden 810: grasa total, saturada, trans; carbohidratos, fibra, azúcares totales/añadidos; proteína
    rows = [
        ("Grasa total", fmt_g_only(fat_total_100, 1) + " g", fmt_g_only(fat_total_pp, 1) + " g", False),
        ("Grasa poliinsaturada", fmt_g_only(0.0, 1) + " g", fmt_g_only(0.0, 1) + " g", False),  # opcional ilustrativo (como figura guía)
        ("Grasa saturada", fmt_g_only(sat_fat_100, 1) + " g", fmt_g_only(sat_fat_pp, 1) + " g", True),
        ("Grasa trans", fmt_mg_int(trans_100_mg), fmt_mg_int(trans_pp_mg), True),
        ("Carbohidratos totales", fmt_g_only(carb_100, 1) + " g", fmt_g_only(carb_pp, 1) + " g", False),
        ("Fibra dietaria", fmt_g_only(fiber_100, 1) + " g", fmt_g_only(fiber_pp, 1) + " g", False),
        ("Azúcares totales", fmt_g_only(sugars_total_100, 1) + " g", fmt_g_only(sugars_total_pp, 1) + " g", False),
        ("Azúcares añadidos", fmt_g_only(sugars_added_100, 1) + " g", fmt_g_only(sugars_added_pp, 1) + " g", True),
        ("Proteína", fmt_g_only(protein_100, 1) + " g", fmt_g_only(protein_pp, 1) + " g", False),
    ]

    for label, v100, vpp, is_bold in rows:
        y0 = y
        y1 = y + ROW_H
        # línea fina de fila
        draw_line(draw, (THIN, y0), (W-THIN, y0), w=THIN)
        f = FONT_BOLD(BASE_FS) if is_bold else FONT_REG(BASE_FS)
        text(draw, (PADDING, y0 + ROW_H/2), label, f, align="left")
        text(draw, (x1 + col_w - 10, y0 + ROW_H/2), v100, f, align="right")
        text(draw, (x2 + col_w - 10, y0 + ROW_H/2), vpp, f, align="right")
        y = y1

    # Separador y bloque Sodio (resaltado)
    draw_line(draw, (THIN, y), (W-THIN, y), w=THICK)
    y += 6
    fbold = FONT_BOLD(BASE_FS)
    text(draw, (PADDING, y + ROW_H/2), "Sodio", fbold, align="left")
    text(draw, (x1 + col_w - 10, y + ROW_H/2), fmt_mg_int(sodium_100_mg), fbold, align="right")
    text(draw, (x2 + col_w - 10, y + ROW_H/2), fmt_mg_int(sodium_pp_mg), fbold, align="right")
    y += ROW_H + 6
    draw_line(draw, (THIN, y), (W-THIN, y), w=THICK)

    # Vitaminas/minerales (si hay)
    if selected_vm:
        y += 4
        for vm in selected_vm:
            v100 = vm_100.get(vm, 0.0)
            vpp = vm_pp.get(vm, 0.0)
            unit = vm_unit_of(vm)
            label = clean_vm_label(vm)
            # Seleccionar formato de cantidad según unidad
            if unit == "µg ER":
                v100s = fmt_uger(v100, 1)
                vpps = fmt_uger(vpp, 1)
            elif unit == "µg":
                v100s = fmt_ug(v100, 1)
                vpps = fmt_ug(vpp, 1)
            else:
                v100s = fmt_mg_int(v100)
                vpps = fmt_mg_int(vpp)
            text(draw, (PADDING, y + ROW_H/2), label, FONT_REG(BASE_FS), align="left")
            text(draw, (x1 + col_w - 10, y + ROW_H/2), v100s, FONT_REG(BASE_FS), align="right")
            text(draw, (x2 + col_w - 10, y + ROW_H/2), vpps, FONT_REG(BASE_FS), align="right")
            y += ROW_H

        draw_line(draw, (THIN, y), (W-THIN, y), w=THIN)

    # Pie “No es fuente significativa de …”
    y += 8
    foot_text = "No es fuente significativa de "
    tail = footnote_base.strip()
    foot = foot_text + tail if tail != "" else foot_text
    text(draw, (PADDING, y + 4), foot, FONT_REG(SMALL_FS), align="left")

    return save_png(img, "fig1_vertical.png")

# =======================================
# Dibujo: Figura 3 (Simplificado)
# =======================================
def draw_figure3_simple() -> BytesIO:
    """
    Formato simplificado: Menos filas visibles, mismas reglas de bold en:
    Calorías, Grasa saturada, Grasa trans, Azúcares añadidos, Sodio.
    """
    W = 1180
    left_col_w = 560
    col_w = (W - left_col_w) // 2
    # Filas: cabecera + porción/envase + calorías + encabezados + 7 filas + pie
    rows_count = 2 + 1 + 1 + 7 + 2
    H = 160 + rows_count * ROW_H

    img = mk_canvas(W, H, white_bg=True)
    draw = ImageDraw.Draw(img)

    draw_rect(draw, (THIN, THIN, W-THIN, H-THIN), w=THICK)

    title_font = FONT_BOLD(TITLE_FS)
    w_title, h_title = measure("Información Nutricional", title_font)
    text(draw, (W/2, PADDING + h_title//2), "Información Nutricional", title_font, align="center")

    y = PADDING + h_title + 12
    draw_line(draw, (THIN, y), (W-THIN, y), w=THICK)
    y += 6

    font_small = FONT_REG(SMALL_FS)
    text(draw, (PADDING, y + 6), portion_label_text, font_small, align="left")
    y += ROW_H - 8
    text(draw, (PADDING, y), servings_label_text, font_small, align="left")
    y += ROW_H - 10

    draw_line(draw, (THIN, y), (W-THIN, y), w=THICK)

    # Columnas
    x1 = left_col_w
    x2 = left_col_w + col_w
    draw_line(draw, (x1, y - ROW_H), (x1, H-THIN), w=MEDIUM)
    draw_line(draw, (x2, y - ROW_H), (x2, H-THIN), w=MEDIUM)

    # Calorías fila
    y += 6
    font_bold = FONT_BOLD(BASE_FS)
    font_reg = FONT_REG(BASE_FS)
    text(draw, (PADDING, y + ROW_H//2), "Calorías (kcal)", font_bold, align="left")
    text(draw, (x1 + col_w/2, y - 6), per100_label, font_reg, align="center")
    text(draw, (x2 + col_w/2, y - 6), perportion_label, font_reg, align="center")
    text(draw, (x1 + col_w - 10, y + ROW_H//2), cal_100_txt, font_bold, align="right")
    text(draw, (x2 + col_w - 10, y + ROW_H//2), cal_pp_txt, font_bold, align="right")

    y += ROW_H + 6
    draw_line(draw, (THIN, y), (W-THIN, y), w=THICK)

    rows = [
        ("Grasa total", fmt_g_only(fat_total_100, 1) + " g", fmt_g_only(fat_total_pp, 1) + " g", False),
        ("Grasa saturada", fmt_g_only(sat_fat_100, 1) + " g", fmt_g_only(sat_fat_pp, 1) + " g", True),
        ("Grasa trans", fmt_mg_int(trans_100_mg), fmt_mg_int(trans_pp_mg), True),
        ("Carbohidratos totales", fmt_g_only(carb_100, 1) + " g", fmt_g_only(carb_pp, 1) + " g", False),
        ("Azúcares totales", fmt_g_only(sugars_total_100, 1) + " g", fmt_g_only(sugars_total_pp, 1) + " g", False),
        ("Azúcares añadidos", fmt_g_only(sugars_added_100, 1) + " g", fmt_g_only(sugars_added_pp, 1) + " g", True),
        ("Sodio", fmt_mg_int(sodium_100_mg), fmt_mg_int(sodium_pp_mg), True),
    ]

    for label, v100, vpp, isb in rows:
        y0 = y
        y1 = y + ROW_H
        draw_line(draw, (THIN, y0), (W-THIN, y0), w=THIN)
        f = FONT_BOLD(BASE_FS) if isb else FONT_REG(BASE_FS)
        text(draw, (PADDING, y0 + ROW_H/2), label, f, align="left")
        text(draw, (x1 + col_w - 10, y0 + ROW_H/2), v100, f, align="right")
        text(draw, (x2 + col_w - 10, y0 + ROW_H/2), vpp, f, align="right")
        y = y1

    # Pie
    draw_line(draw, (THIN, y), (W-THIN, y), w=THIN)
    y += 8
    foot_text = "No es fuente significativa de "
    tail = footnote_base.strip()
    foot = foot_text + tail if tail != "" else foot_text
    text(draw, (PADDING, y + 4), foot, FONT_REG(SMALL_FS), align="left")

    return save_png(img, "fig3_simplificado.png")

# =======================================
# Dibujo: Figura 4 (Tabular)
# =======================================
def draw_figure4_tabular() -> BytesIO:
    """
    Formato tabular: primera columna “Información Nutricional”,
    segunda columna con nutrimento (Calorías, Grasa total, etc.),
    y columnas Por 100 / Por porción a la derecha.
    Bolding en los requeridos por guía (Calorías, Grasa saturada, Grasa trans, Azúcares añadidos, Sodio).
    """
    W = 1500
    col0_w = 370   # Columna fija izquierda "Información Nutricional" + metadatos
    col1_w = 470   # Nombre nutrimento
    col2_w = 330   # Por 100
    col3_w = 330   # Por porción
    H = 1100

    img = mk_canvas(W, H, white_bg=True)
    draw = ImageDraw.Draw(img)

    # Marco exterior
    draw_rect(draw, (THIN, THIN, W-THIN, H-THIN), w=THICK)

    # Título interno (no se imprime título grande; figura 4 muestra en encabezado de tabla)
    title_font = FONT_BOLD(TITLE_FS)
    title = "Información Nutricional"
    w_title, h_title = measure(title, title_font)
    y = PADDING
    text(draw, (W/2, y + h_title/2), title, title_font, align="center")
    y += h_title + 8
    draw_line(draw, (THIN, y), (W-THIN, y), w=THICK)

    # Columnas verticales
    x0 = THIN
    x1 = col0_w
    x2 = col0_w + col1_w
    x3 = col0_w + col1_w + col2_w
    x4 = W - THIN
    draw_line(draw, (x1, y), (x1, H-THIN), w=MEDIUM)
    draw_line(draw, (x2, y), (x2, H-THIN), w=MEDIUM)
    draw_line(draw, (x3, y), (x3, H-THIN), w=MEDIUM)

    # Cabeceras en fila
    y += 6
    font_reg = FONT_REG(BASE_FS)
    font_bold = FONT_BOLD(BASE_FS)
    text(draw, (x1 + col1_w/2, y - 6), "Calorías", font_bold, align="center")
    text(draw, (x2 + col2_w/2, y - 6), per100_label, font_reg, align="center")
    text(draw, (x3 + col3_w/2, y - 6), perportion_label, font_reg, align="center")

    # Fila Calorías
    y0 = y
    y1 = y + ROW_H
    draw_line(draw, (THIN, y0), (W-THIN, y0), w=THIN)
    # Col0 (izq) texto metadatos
    text(draw, (PADDING, y0 + ROW_H/2), portion_label_text, FONT_REG(SMALL_FS), align="left")
    # Col1 nombre "Calorías (kcal)"
    text(draw, (x1 + 10, y0 + ROW_H/2), "Calorías (kcal)", font_bold, align="left")
    # Col2 valor por 100
    text(draw, (x2 + col2_w - 12, y0 + ROW_H/2), cal_100_txt, font_bold, align="right")
    # Col3 valor por porción
    text(draw, (x3 + col3_w - 12, y0 + ROW_H/2), cal_pp_txt, font_bold, align="right")
    y = y1

    # Fila metadatos segunda
    y0 = y
    y1 = y + int(ROW_H * 0.9)
    draw_line(draw, (THIN, y0), (W-THIN, y0), w=THIN)
    text(draw, (PADDING, y0 + (y1 - y0)/2), servings_label_text, FONT_REG(SMALL_FS), align="left")
    y = y1

    # Bloque de filas
    rows = [
        ("Grasa total", fmt_g_only(fat_total_100, 1) + " g", fmt_g_only(fat_total_pp, 1) + " g", False),
        ("Grasa saturada", fmt_g_only(sat_fat_100, 1) + " g", fmt_g_only(sat_fat_pp, 1) + " g", True),
        ("Grasa Trans", fmt_mg_int(trans_100_mg), fmt_mg_int(trans_pp_mg), True),
        ("Sodio", fmt_mg_int(sodium_100_mg), fmt_mg_int(sodium_pp_mg), True),
        ("Carbohidratos totales", fmt_g_only(carb_100, 1) + " g", fmt_g_only(carb_pp, 1) + " g", False),
        ("Fibra dietaria", fmt_g_only(fiber_100, 1) + " g", fmt_g_only(fiber_pp, 1) + " g", False),
        ("Azúcares totales", fmt_g_only(sugars_total_100, 1) + " g", fmt_g_only(sugars_total_pp, 1) + " g", False),
        ("Azúcares añadidos", fmt_g_only(sugars_added_100, 1) + " g", fmt_g_only(sugars_added_pp, 1) + " g", True),
        ("Proteína", fmt_g_only(protein_100, 1) + " g", fmt_g_only(protein_pp, 1) + " g", False),
    ]
    for label, v100, vpp, isb in rows:
        y0 = y
        y1 = y + ROW_H
        draw_line(draw, (THIN, y0), (W-THIN, y0), w=THIN)
        f = FONT_BOLD(BASE_FS) if isb else FONT_REG(BASE_FS)
        text(draw, (x1 + 10, y0 + ROW_H/2), label, f, align="left")
        text(draw, (x2 + col2_w - 12, y0 + ROW_H/2), v100, f, align="right")
        text(draw, (x3 + col3_w - 12, y0 + ROW_H/2), vpp, f, align="right")
        y = y1

    # Vitaminas y minerales (opcionales)
    if selected_vm:
        # Separador suave
        draw_line(draw, (THIN, y), (W-THIN, y), w=THIN)
        for vm in selected_vm:
            v100 = vm_100.get(vm, 0.0)
            vpp = vm_pp.get(vm, 0.0)
            unit = vm_unit_of(vm)
            label = clean_vm_label(vm)
            if unit == "µg ER":
                v100s = fmt_uger(v100, 1)
                vpps = fmt_uger(vpp, 1)
            elif unit == "µg":
                v100s = fmt_ug(v100, 1)
                vpps = fmt_ug(vpp, 1)
            else:
                v100s = fmt_mg_int(v100)
                vpps = fmt_mg_int(vpp)
            y0 = y
            y1 = y + int(ROW_H * 0.9)
            draw_line(draw, (THIN, y0), (W-THIN, y0), w=THIN)
            text(draw, (x1 + 10, y0 + (y1 - y0)/2), label, FONT_REG(BASE_FS), align="left")
            text(draw, (x2 + col2_w - 12, y0 + (y1 - y0)/2), v100s, FONT_REG(BASE_FS), align="right")
            text(draw, (x3 + col3_w - 12, y0 + (y1 - y0)/2), vpps, FONT_REG(BASE_FS), align="right")
            y = y1

    # Pie
    draw_line(draw, (THIN, y), (W-THIN, y), w=THIN)
    y += 8
    foot_text = "No es fuente significativa de "
    tail = footnote_base.strip()
    foot = foot_text + tail if tail != "" else foot_text
    text(draw, (PADDING, y + 4), foot, FONT_REG(SMALL_FS), align="left")

    return save_png(img, "fig4_tabular.png")

# =======================================
# Dibujo: Figura 5 (Lineal)
# =======================================
def draw_figure5_linear() -> BytesIO:
    """
    Formato lineal estilo párrafo con dos bloques:
    - Información nutricional (100 g o 100 mL)
    - Información nutricional (porción)
    y la frase final No es fuente significativa de ...
    Resaltos en negrilla para calorías, sodio, azúcares añadidos y los obligatorios.
    """
    W = 1600
    H = 340 + 40 * max(1, len(selected_vm))
    img = mk_canvas(W, H, white_bg=True)
    draw = ImageDraw.Draw(img)

    draw_rect(draw, (THIN, THIN, W-THIN, H-THIN), w=THICK)

    y = PADDING + 8
    title_font = FONT_BOLD(TITLE_FS - 2)
    text(draw, (PADDING, y), "Información nutricional (100 g o 100 mL):", title_font, align="left")
    y += 44

    # Línea 1: calorías, grasa total, sodio (bold), carbohidratos totales, azúcares añadidos (bold), proteína, vitaminas
    font_r = FONT_REG(BASE_FS)
    font_b = FONT_BOLD(BASE_FS)

    # Construcción de frase “por 100”
    parts_100: List[Tuple[str, bool]] = []
    parts_100.append((f"Calorías {fmt_kcal(kcal_100)}", True))
    parts_100.append((f", Grasa total {fmt_g_only(fat_total_100,1)} g", False))
    parts_100.append((f", Sodio {int(round(sodium_100_mg))} mg", True))
    parts_100.append((f", Carbohidratos totales {fmt_g_only(carb_100,1)} g", False))
    parts_100.append((f", Azúcares añadidos {fmt_g_only(sugars_added_100,1)} g", True))
    parts_100.append((f", Proteína {fmt_g_only(protein_100,1)} g", False))

    # Vitaminas seleccionadas por 100
    for vm in selected_vm:
        v = vm_100.get(vm, 0.0)
        unit = vm_unit_of(vm)
        label = clean_vm_label(vm)
        if unit == "µg ER":
            parts_100.append((f", {label} {fmt_uger(v,1)}", False))
        elif unit == "µg":
            parts_100.append((f", {label} {fmt_ug(v,1)}", False))
        else:
            parts_100.append((f", {label} {fmt_mg_int(v)}", False))

    # Pintar línea por 100
    x = PADDING
    for seg, bold in parts_100:
        f = font_b if bold else font_r
        text(draw, (x, y), seg, f, align="left")
        w, _ = measure(seg, f)
        x += w
    y += 44

    # Segunda cabecera (porción)
    text(draw, (PADDING, y), "Información nutricional (porción):", title_font, align="left")
    y += 44

    # Construcción de frase “por porción”
    parts_pp: List[Tuple[str, bool]] = []
    parts_pp.append((f"Tamaño de porción: 1 unidad ({int(round(portion_size))}{portion_unit})", False))
    parts_pp.append((f", Número de porciones por envase: Aprox. {fmt_g_only(servings_per_pack,0)}", False))
    parts_pp.append((f", Calorías {fmt_kcal(kcal_pp)}", True))
    parts_pp.append((f", Grasa total {fmt_g_only(fat_total_pp,1)} g", False))
    parts_pp.append((f", Sodio {int(round(sodium_pp_mg))} mg", True))
    parts_pp.append((f", Carbohidratos totales {fmt_g_only(carb_pp,1)} g", False))
    parts_pp.append((f", Azúcares añadidos {fmt_g_only(sugars_added_pp,1)} g", True))
    parts_pp.append((f", Proteína {fmt_g_only(protein_pp,1)} g", False))

    for vm in selected_vm:
        v = vm_pp.get(vm, 0.0)
        unit = vm_unit_of(vm)
        label = clean_vm_label(vm)
        if unit == "µg ER":
            parts_pp.append((f", {label} {fmt_uger(v,1)}", False))
        elif unit == "µg":
            parts_pp.append((f", {label} {fmt_ug(v,1)}", False))
        else:
            parts_pp.append((f", {label} {fmt_mg_int(v)}", False))

    # Pintar línea por porción
    x = PADDING
    for seg, bold in parts_pp:
        f = font_b if bold else font_r
        text(draw, (x, y), seg, f, align="left")
        w, _ = measure(seg, f)
        x += w
    y += 46

    # Pie
    foot_text = "No es fuente significativa de "
    tail = footnote_base.strip()
    foot = foot_text + tail if tail != "" else foot_text
    text(draw, (PADDING, y), foot, FONT_REG(SMALL_FS), align="left")

    return save_png(img, "fig5_lineal.png")

# =======================================
# Vista previa en Streamlit y Exportación PNG
# =======================================
st.header("Previsualización y exportación")

def build_png_buffer(choice: str) -> BytesIO:
    if "Figura 1" in choice:
        return draw_figure1_vertical()
    if "Figura 3" in choice:
        return draw_figure3_simple()
    if "Figura 4" in choice:
        return draw_figure4_tabular()
    if "Figura 5" in choice:
        return draw_figure5_linear()
    # fallback
    return draw_figure1_vertical()

# Render previo (thumbnail)
png_buf = build_png_buffer(format_choice)
img = Image.open(png_buf)
st.image(img, caption="Vista previa (PNG, fondo blanco)", use_column_width=True)

st.write("**Exportar**")
colb1, colb2 = st.columns([0.4, 0.6])
with colb1:
    fname_base = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    st.download_button(
        "Descargar PNG",
        data=png_buf,
        file_name=f"{fname_base}.png",
        mime="image/png",
    )

with colb2:
    st.info(
        "El PNG se genera sin título del formato y con fondo blanco para que puedas insertarlo directamente en el empaque. "
        "Los nutrimentos en **negrilla** siguen la guía de la 810/2021: Calorías, Grasa saturada, Grasas trans, Azúcares añadidos y Sodio."
    )

# =======================================
# (Opcional) Tabla de datos calculados
# =======================================
with st.expander("Ver datos calculados (por 100 y por porción)"):
    df = pd.DataFrame({
        "Nutrimento": [
            "Calorías (kcal)",
            "Grasa total (g)",
            "Grasa saturada (g)",
            "Grasas trans (mg)",
            "Carbohidratos totales (g)",
            "Azúcares totales (g)",
            "Azúcares añadidos (g)",
            "Fibra dietaria (g)",
            "Proteína (g)",
            "Sodio (mg)",
        ],
        "Por 100": [
            int(round(kcal_100)),
            round(fat_total_100, 1),
            round(sat_fat_100, 1),
            int(round(trans_100_mg)),
            round(carb_100, 1),
            round(sugars_total_100, 1),
            round(sugars_added_100, 1),
            round(fiber_100, 1),
            round(protein_100, 1),
            int(round(sodium_100_mg)),
        ],
        "Por porción": [
            int(round(kcal_pp)),
            round(fat_total_pp, 1),
            round(sat_fat_pp, 1),
            int(round(trans_pp_mg)),
            round(carb_pp, 1),
            round(sugars_total_pp, 1),
            round(sugars_added_pp, 1),
            round(fiber_pp, 1),
            round(protein_pp, 1),
            int(round(sodium_pp_mg)),
        ],
    })
    st.dataframe(df, hide_index=True)

# =======================================
# Notas finales / guía rápida
# =======================================
with st.expander("Notas de uso"):
    st.markdown(
        """
- **Grasas trans**: ingrésalas en **mg**. El sistema convierte a **g** para energía y a **mg** para el rotulado visible.
- **Vitamina A** se imprime como **µg ER** en todos los formatos, como exige la norma.  
- **Frase al pie**: siempre se antepone _“No es fuente significativa de ”_ y luego tu texto; si lo dejas vacío, igual imprime la frase base.
- **PNG** con **fondo blanco** y **sin título del formato** para que lo puedas pegar directamente sobre el arte del empaque.
- Los valores usan redondeo estándar (enteros para kcal y mg; 1 decimal para g).
        """
    )
