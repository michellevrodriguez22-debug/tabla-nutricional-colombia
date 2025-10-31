# app.py
# ---------------------------------------------------------
# Generador de Tabla Nutricional (Colombia)
# Formatos: Fig. 1 (vertical estándar), Fig. 3 (simplificado),
#           Fig. 4 (tabular), Fig. 5 (lineal)
# Exporta PNG con fondo blanco y marco exterior.
# Cumple Res. 810/2021, 2492/2022, 254/2023.
# ---------------------------------------------------------

import math
from io import BytesIO
from datetime import datetime

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ============ Config Streamlit ============
st.set_page_config(page_title="Tabla Nutricional — CO", layout="wide")

# ============ Utilidades numéricas ============
def as_num(x):
    try:
        if x is None or str(x).strip() == "":
            return 0.0
        return float(str(x).replace(",", "."))
    except:
        return 0.0

def kcal_from_macros(fat_g, carb_g, protein_g, organic_acids_g=0.0, alcohol_g=0.0):
    """
    Factores (Res. 810/2021):
    CHO 4, Proteína 4, Grasa 9, Alcohol 7, Ácidos orgánicos 3
    """
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9 * fat_g + 4 * carb_g + 4 * protein_g + 7 * alcohol_g + 3 * organic_acids_g
    return float(round(kcal, 0))

def per100_from_portion(value_per_portion, portion_size):
    if portion_size and portion_size > 0:
        return float(round((value_per_portion / portion_size) * 100.0, 2))
    return 0.0

def portion_from_per100(value_per100, portion_size):
    if portion_size and portion_size > 0:
        return float(round((value_per100 * portion_size) / 100.0, 2))
    return 0.0

def pct_energy_from_nutrient_kcal(nutrient_kcal, total_kcal):
    if total_kcal and total_kcal > 0:
        return round((nutrient_kcal / total_kcal) * 100.0, 1)
    return 0.0

def fmt_num(x, unit="g", nd=1, is_mg=False):
    """
    Formato compacto:
    - mg sin decimales
    - g con nd decimales
    - kcal/kJ enteros
    """
    if is_mg:
        return f"{int(round(x))} mg"
    if unit in ("kcal", "kJ"):
        return f"{int(round(x))} {unit}"
    try:
        val = float(x)
    except:
        val = 0.0
    s = f"{val:.{nd}f}".rstrip("0").rstrip(".")
    return f"{s} {unit}".strip()

# ============ Carga de fuentes ============
def load_font(size, bold=False):
    """
    Intento de cargar DejaVu Sans (común en muchos entornos).
    Fallback a la fuente por defecto de PIL si no está disponible.
    """
    paths_try = []
    if bold:
        paths_try += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/HelveticaNeue.ttc",
        ]
    else:
        paths_try += [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        ]
    for p in paths_try:
        try:
            return ImageFont.truetype(p, size=size)
        except:
            continue
    return ImageFont.load_default()

# ============ UI — Barra lateral ============
st.sidebar.header("Configuración")
format_choice = st.sidebar.selectbox(
    "Formato (Res. 810):",
    ["Fig. 1 — Vertical estándar", "Fig. 3 — Simplificado", "Fig. 4 — Tabular", "Fig. 5 — Lineal"],
    index=0
)

is_solid = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"], index=0)
portion_unit = "g" if "Sólido" in is_solid else "mL"

portion_size = as_num(st.sidebar.text_input("Tamaño de porción (solo número)", value="50"))
servings_per_pack = as_num(st.sidebar.text_input("Porciones por envase (número)", value="1"))

include_kj = st.sidebar.checkbox("Mostrar también kJ", value=True)

st.sidebar.markdown("---")
st.sidebar.header("Macronutrientes")
fat_total_input = as_num(st.sidebar.text_input("Grasa total (g)", value="5"))
sat_fat_input = as_num(st.sidebar.text_input("Grasa saturada (g)", value="2"))
# Trans en mg (se convertirá a g para cálculos energéticos)
trans_fat_input_mg = as_num(st.sidebar.text_input("Grasas trans (mg)", value="0"))
trans_fat_input_g = trans_fat_input_mg / 1000.0

carb_input = as_num(st.sidebar.text_input("Carbohidratos totales (g)", value="20"))
sugars_total_input = as_num(st.sidebar.text_input("Azúcares totales (g)", value="10"))
sugars_added_input = as_num(st.sidebar.text_input("Azúcares añadidos (g)", value="8"))
fiber_input = as_num(st.sidebar.text_input("Fibra dietaria (g)", value="2"))
protein_input = as_num(st.sidebar.text_input("Proteína (g)", value="3"))
sodium_input_mg = as_num(st.sidebar.text_input("Sodio (mg)", value="150"))

st.sidebar.markdown("---")
st.sidebar.header("Micronutrientes (opcional)")
vm_options = [
    "Vitamina A (µg ER)",  # µg ER
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
    "Seleccione micronutrientes a declarar",
    vm_options,
    default=["Vitamina A (µg ER)", "Vitamina D (µg)", "Calcio (mg)", "Hierro (mg)", "Zinc (mg)"]
)
vm_values = {}
for vm in selected_vm:
    vm_values[vm] = as_num(st.sidebar.text_input(vm, value="0"))

st.sidebar.markdown("---")
footnote_text = st.sidebar.text_input(
    "Frase al pie",
    value="No es fuente significativa de ______."
)

# Base de ingreso
input_basis = st.sidebar.radio("Modo de ingreso de datos", ["Por porción", "Por 100 g/mL"], index=0)
is_liquid = "Líquido" in is_solid

# ============ Normalización por 100 y por porción ============
if input_basis == "Por porción":
    # Base por porción
    fat_total_pp = fat_total_input
    sat_fat_pp = sat_fat_input
    trans_fat_pp_g = trans_fat_input_g  # g
    carb_pp = carb_input
    sugars_total_pp = sugars_total_input
    sugars_added_pp = sugars_added_input
    fiber_pp = fiber_input
    protein_pp = protein_input
    sodium_pp_mg = sodium_input_mg

    fat_total_100 = per100_from_portion(fat_total_pp, portion_size)
    sat_fat_100 = per100_from_portion(sat_fat_pp, portion_size)
    trans_fat_100_g = per100_from_portion(trans_fat_pp_g, portion_size)
    carb_100 = per100_from_portion(carb_pp, portion_size)
    sugars_total_100 = per100_from_portion(sugars_total_pp, portion_size)
    sugars_added_100 = per100_from_portion(sugars_added_pp, portion_size)
    fiber_100 = per100_from_portion(fiber_pp, portion_size)
    protein_100 = per100_from_portion(protein_pp, portion_size)
    sodium_100_mg = per100_from_portion(sodium_pp_mg, portion_size)
else:
    # Base por 100
    fat_total_100 = fat_total_input
    sat_fat_100 = sat_fat_input
    trans_fat_100_g = trans_fat_input_g
    carb_100 = carb_input
    sugars_total_100 = sugars_total_input
    sugars_added_100 = sugars_added_input
    fiber_100 = fiber_input
    protein_100 = protein_input
    sodium_100_mg = sodium_input_mg

    fat_total_pp = portion_from_per100(fat_total_100, portion_size)
    sat_fat_pp = portion_from_per100(sat_fat_100, portion_size)
    trans_fat_pp_g = portion_from_per100(trans_fat_100_g, portion_size)
    carb_pp = portion_from_per100(carb_100, portion_size)
    sugars_total_pp = portion_from_per100(sugars_total_100, portion_size)
    sugars_added_pp = portion_from_per100(sugars_added_100, portion_size)
    fiber_pp = portion_from_per100(fiber_100, portion_size)
    protein_pp = portion_from_per100(protein_100, portion_size)
    sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_size)

# Vitaminas/minerales normalizados
vm_100 = {}
vm_pp = {}
for vm, val in vm_values.items():
    if input_basis == "Por porción":
        vm_pp[vm] = val
        vm_100[vm] = per100_from_portion(val, portion_size)
    else:
        vm_100[vm] = val
        vm_pp[vm] = portion_from_per100(val, portion_size)

# Energía
kcal_pp = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)
kj_pp = int(round(kcal_pp * 4.184)) if include_kj else None
kj_100 = int(round(kcal_100 * 4.184)) if include_kj else None

# FOP validación
pct_kcal_sug_add_pp = pct_energy_from_nutrient_kcal(4 * sugars_added_pp, kcal_pp)
pct_kcal_sat_fat_pp = pct_energy_from_nutrient_kcal(9 * sat_fat_pp, kcal_pp)
pct_kcal_trans_pp = pct_energy_from_nutrient_kcal(9 * trans_fat_pp_g, kcal_pp)

if is_liquid and kcal_100 == 0:
    fop_sodium = sodium_100_mg >= 40.0
else:
    fop_sodium = (sodium_100_mg >= 300.0) or ((sodium_pp_mg / max(kcal_pp, 1)) >= 1.0)

# ============ Construcción de filas por formato ============
def common_rows_vertical():
    """Filas (nombre, per100, perportion, unit, bold, indent) para Fig.1/3."""
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    perportion_label = f"por porción ({int(round(portion_size))} {portion_unit})"

    rows = []
    # Encabezados de columnas (van ARRIBA de calorías)
    rows.append(("__hdr__", per100_label, perportion_label, "", False, 0))
    # Calorías en negrilla
    kcal_100_txt = f"{int(round(kcal_100))} kcal" + (f" ({kj_100} kJ)" if include_kj else "")
    kcal_pp_txt = f"{int(round(kcal_pp))} kcal" + (f" ({kj_pp} kJ)" if include_kj else "")
    rows.append(("Calorías", kcal_100_txt, kcal_pp_txt, "", True, 0))

    # Macronutrientes (norma 810)
    rows.append(("Grasa total", fmt_num(fat_total_100, "g", nd=1), fmt_num(fat_total_pp, "g", nd=1), "g", False, 0))
    rows.append(("Grasa saturada", fmt_num(sat_fat_100, "g", nd=1), fmt_num(sat_fat_pp, "g", nd=1), "g", True, 1))
    # Trans en mg en visual
    rows.append(("Grasas trans", fmt_num(trans_fat_100_g * 1000.0, is_mg=True), fmt_num(trans_fat_pp_g * 1000.0, is_mg=True), "mg", True, 1))

    rows.append(("Carbohidratos", fmt_num(carb_100, "g", nd=1), fmt_num(carb_pp, "g", nd=1), "g", False, 0))
    rows.append(("Azúcares totales", fmt_num(sugars_total_100, "g", nd=1), fmt_num(sugars_total_pp, "g", nd=1), "g", False, 1))
    rows.append(("Azúcares añadidos", fmt_num(sugars_added_100, "g", nd=1), fmt_num(sugars_added_pp, "g", nd=1), "g", True, 1))
    rows.append(("Fibra dietaria", fmt_num(fiber_100, "g", nd=1), fmt_num(fiber_pp, "g", nd=1), "g", False, 1))

    rows.append(("Proteína", fmt_num(protein_100, "g", nd=1), fmt_num(protein_pp, "g", nd=1), "g", False, 0))
    rows.append(("Sodio", fmt_num(sodium_100_mg, is_mg=True), fmt_num(sodium_pp_mg, is_mg=True), "mg", True, 0))

    # Separador VM
    if selected_vm:
        rows.append(("__sep__", "", "", "", False, 0))
        for vm in selected_vm:
            unit = "mg"
            if "µg" in vm:
                unit = "µg"
            name = "Vitamina A" if vm.startswith("Vitamina A") else vm.split(" (")[0]
            rows.append((name, fmt_num(vm_100.get(vm, 0.0), unit=unit, nd=1), fmt_num(vm_pp.get(vm, 0.0), unit=unit, nd=1), unit, False, 0))

    # Pie
    rows.append(("__foot__", footnote_text, "", "", False, 0))
    return rows

def rows_tabular():
    """
    Fig.4 Tabular: filas con varias columnas por grupo.
    Mantener negrilla normativa en etiquetas de la primera columna.
    """
    # Estructura: Lista de grupos; cada grupo: (titulo_grupo, [ (nombre, per100, perportion, unit, bold_label, indent) ... ])
    # Nota: en diseño tabular, los encabezados per100/perporción van ARRIBA de la tabla (como fila de encabezado).
    hdr_per100 = "por 100 g" if not is_liquid else "por 100 mL"
    hdr_perportion = f"por porción ({int(round(portion_size))} {portion_unit})"

    groups = []

    # Grupo Calorías
    kcal_100_txt = f"{int(round(kcal_100))} kcal" + (f" ({kj_100} kJ)" if include_kj else "")
    kcal_pp_txt = f"{int(round(kcal_pp))} kcal" + (f" ({kj_pp} kJ)" if include_kj else "")
    groups.append((
        None,
        [("Calorías", kcal_100_txt, kcal_pp_txt, "", True, 0)]
    ))

    # Grupo Grasas
    groups.append((
        "Grasas",
        [
            ("Grasa total", fmt_num(fat_total_100, "g", nd=1), fmt_num(fat_total_pp, "g", nd=1), "g", False, 0),
            ("Grasa saturada", fmt_num(sat_fat_100, "g", nd=1), fmt_num(sat_fat_pp, "g", nd=1), "g", True, 1),
            ("Grasas trans", fmt_num(trans_fat_100_g * 1000.0, is_mg=True), fmt_num(trans_fat_pp_g * 1000.0, is_mg=True), "mg", True, 1),
        ]
    ))

    # Grupo Carbohidratos
    groups.append((
        "Carbohidratos",
        [
            ("Carbohidratos", fmt_num(carb_100, "g", nd=1), fmt_num(carb_pp, "g", nd=1), "g", False, 0),
            ("Azúcares totales", fmt_num(sugars_total_100, "g", nd=1), fmt_num(sugars_total_pp, "g", nd=1), "g", False, 1),
            ("Azúcares añadidos", fmt_num(sugars_added_100, "g", nd=1), fmt_num(sugars_added_pp, "g", nd=1), "g", True, 1),
            ("Fibra dietaria", fmt_num(fiber_100, "g", nd=1), fmt_num(fiber_pp, "g", nd=1), "g", False, 1),
        ]
    ))

    # Grupo Proteínas y Sodio
    groups.append((
        "Otros",
        [
            ("Proteína", fmt_num(protein_100, "g", nd=1), fmt_num(protein_pp, "g", nd=1), "g", False, 0),
            ("Sodio", fmt_num(sodium_100_mg, is_mg=True), fmt_num(sodium_pp_mg, is_mg=True), "mg", True, 0),
        ]
    ))

    # Grupo Vitaminas/Minerales (si hay)
    if selected_vm:
        vm_rows = []
        for vm in selected_vm:
            unit = "mg"
            if "µg" in vm:
                unit = "µg"
            name = "Vitamina A (µg ER)" if vm.startswith("Vitamina A") else vm
            name = name.split(" (")[0] + (" (µg ER)" if vm.startswith("Vitamina A") else "")
            vm_rows.append(
                (name.split(" (")[0], fmt_num(vm_100.get(vm, 0.0), unit=unit, nd=1), fmt_num(vm_pp.get(vm, 0.0), unit=unit, nd=1), unit, False, 0)
            )
        groups.append(("Vitaminas y minerales", vm_rows))

    return hdr_per100, hdr_perportion, groups

def rows_lineal():
    """
    Fig.5 Lineal: todos los nutrientes en filas de una sola columna por cantidad por porción
    y una fila para por 100 g/mL arriba, siguiendo la estética lineal.
    """
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    rows = []
    rows.append(("__hdr__", per100_label, "", "", False, 0))

    # Calorías
    kcal_line = f"Calorías: {int(round(kcal_pp))} kcal" + (f" ({kj_pp} kJ)" if include_kj else "")
    rows.append((kcal_line, "", "", "", True, 0))

    # Grasas
    rows.append((f"Grasa total: {fmt_num(fat_total_pp, 'g', 1)}", "", "", "", False, 0))
    rows.append((f"  Grasa saturada: {fmt_num(sat_fat_pp, 'g', 1)}", "", "", "", True, 1))
    rows.append((f"  Grasas trans: {fmt_num(trans_fat_pp_g * 1000.0, is_mg=True)}", "", "", "", True, 1))

    # Carbohidratos
    rows.append((f"Carbohidratos: {fmt_num(carb_pp, 'g', 1)}", "", "", "", False, 0))
    rows.append((f"  Azúcares totales: {fmt_num(sugars_total_pp, 'g', 1)}", "", "", "", False, 1))
    rows.append((f"  Azúcares añadidos: {fmt_num(sugars_added_pp, 'g', 1)}", "", "", "", True, 1))
    rows.append((f"  Fibra dietaria: {fmt_num(fiber_pp, 'g', 1)}", "", "", "", False, 1))

    rows.append((f"Proteína: {fmt_num(protein_pp, 'g', 1)}", "", "", "", False, 0))
    rows.append((f"Sodio: {fmt_num(sodium_pp_mg, is_mg=True)}", "", "", "", True, 0))

    if selected_vm:
        rows.append(("__sep__", "", "", "", False, 0))
        for vm in selected_vm:
            unit = "mg"
            if "µg" in vm:
                unit = "µg"
            name = "Vitamina A (µg ER)" if vm.startswith("Vitamina A") else vm
            name = name.split(" (")[0] + (" (µg ER)" if vm.startswith("Vitamina A") else "")
            rows.append((f"{name.split(' (')[0]}: {fmt_num(vm_pp.get(vm, 0.0), unit=unit, nd=1)}", "", "", "", False, 0))

    rows.append(("__foot__", footnote_text, "", "", False, 0))
    return rows

# ============ Render de imagen ============

# Parámetros visuales (ajustados para líneas gruesas “triplicadas”)
PX = 1  # píxel base
THIN = 2 * PX
THICK = 6 * PX  # triplicado respecto a una línea típica de 2px
BORDER = THICK

PAD_X = 16
PAD_Y = 10
ROW_H = 36
FONT_SIZE = 24
FONT_SIZE_SMALL = 20
FONT_SIZE_HDR = 24

FONT = load_font(FONT_SIZE, bold=False)
FONT_B = load_font(FONT_SIZE, bold=True)
FONT_S = load_font(FONT_SIZE_SMALL, bold=False)
FONT_S_B = load_font(FONT_SIZE_SMALL, bold=True)
FONT_HDR = load_font(FONT_SIZE_HDR, bold=True)

def text_w(draw, text, font):
    if not text:
        return 0
    return draw.textlength(text, font=font)

def draw_vertical_table(rows, title=False, show_columns=True):
    """
    Dibuja formato vertical (Fig. 1 y Fig. 3).
    - rows: lista de tuplas (name, per100, perportion, unit, bold, indent)
    - show_columns: muestra las 2 columnas de cantidades (por 100 / porción)
    """
    # Medición de columnas: 3 columnas (Nombre, Col2, Col3)
    # Ajuste automático al contenido y marco exterior pegado al texto.
    # Reservamos un margen visual lateral pequeño.
    left_margin = 40
    right_margin = 40
    max_name_w = 0
    max_c2_w = 0
    max_c3_w = 0

    # Primer pase: medir anchos
    img_tmp = Image.new("RGB", (10, 10), "white")
    draw_tmp = ImageDraw.Draw(img_tmp)

    for name, c2, c3, unit, bold, indent in rows:
        if name in ("__sep__", "__foot__", "__hdr__"):
            continue
        font_lbl = FONT_B if bold else FONT
        name_txt = ("  " * indent) + name
        max_name_w = max(max_name_w, text_w(draw_tmp, name_txt, font_lbl))

        # c2 y c3 son strings ya formateados (incluyen unidad)
        max_c2_w = max(max_c2_w, text_w(draw_tmp, c2, FONT))
        max_c3_w = max(max_c3_w, text_w(draw_tmp, c3, FONT))

    # Encabezado fila especial (por 100 / porción) si existe
    hdr_h = 0
    hdr_text_l = ""
    hdr_text_r = ""
    for name, c2, c3, unit, bold, indent in rows:
        if name == "__hdr__":
            hdr_text_l = c2
            hdr_text_r = c3
            hdr_h = ROW_H
            # medir por si ocupa más
            max_c2_w = max(max_c2_w, text_w(draw_tmp, hdr_text_l, FONT_B))
            max_c3_w = max(max_c3_w, text_w(draw_tmp, hdr_text_r, FONT_B))
            break

    # Anchos de columnas + padding
    col1_w = int(max_name_w + 2 * PAD_X)
    col2_w = int(max_c2_w + 2 * PAD_X) if show_columns else 0
    col3_w = int(max_c3_w + 2 * PAD_X) if show_columns else 0

    table_w = col1_w + col2_w + col3_w
    img_w = left_margin + table_w + right_margin

    # Altura: filas + separadores + pie
    rows_count = sum(1 for r in rows if r[0] not in ("__sep__", "__hdr__")) + sum(1 for r in rows if r[0] == "__sep__")
    # Header inside table (Información nutricional) — opcional: aquí NO ponemos título, solo tabla
    # Alto = borde + (hdr fila si existe) + filas * ROW_H + bordes
    total_h = BORDER + hdr_h + sum(ROW_H for r in rows if r[0] != "__sep__") + sum(THICK for r in rows if r[0] == "__sep__") + BORDER

    img_h = int(total_h + 20)
    img = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    # Marco exterior
    x0 = left_margin
    y0 = 10
    x1 = x0 + table_w
    y1 = y0 + total_h - 10
    draw.rectangle([x0, y0, x1, y1], outline="black", width=BORDER)

    # Columnas verticales (dos líneas internas)
    if show_columns:
        c1_x = x0 + col1_w
        c2_x = c1_x + col2_w
        draw.line([c1_x, y0, c1_x, y1], fill="black", width=THIN)
        draw.line([c2_x, y0, c2_x, y1], fill="black", width=THIN)

    # Dibujar filas
    cur_y = y0
    # Línea gruesa superior debajo del marco para separar bloque superior del header (normativa suele pedir gruesa antes de calorías; aquí la usamos tras hdr)
    # 1) Si hubo __hdr__, lo dibujamos primero
    if hdr_h > 0:
        # Fila __hdr__ (negrita)
        for name, c2, c3, unit, bold, indent in rows:
            if name == "__hdr__":
                # Encabezado por 100 y por porción
                if show_columns:
                    # texto vacío en col1 (nombre)
                    # col2
                    draw.text((x0 + col1_w + PAD_X, cur_y + (ROW_H - FONT_HDR.size)//2), c2, font=FONT_B, fill="black")
                    # col3
                    draw.text((x0 + col1_w + col2_w + PAD_X, cur_y + (ROW_H - FONT_HDR.size)//2), c3, font=FONT_B, fill="black")
                cur_y += ROW_H
                break
        # línea gruesa antes de Calorías
        draw.line([x0, cur_y, x1, cur_y], fill="black", width=THICK)

    # 2) Resto de filas
    for name, c2, c3, unit, bold, indent in rows:
        if name == "__hdr__":
            continue

        if name == "__sep__":
            # línea separadora gruesa (vitaminas)
            draw.line([x0, cur_y, x1, cur_y], fill="black", width=THICK)
            continue

        # Contenido de la fila
        font_lbl = FONT_B if bold else FONT
        name_txt = ("  " * indent) + name
        # Columna 1
        draw.text((x0 + PAD_X, cur_y + (ROW_H - FONT.size)//2), name_txt, font=font_lbl, fill="black")

        if show_columns:
            # Col2
            draw.text((x0 + col1_w + PAD_X, cur_y + (ROW_H - FONT.size)//2), c2, font=FONT, fill="black")
            # Col3
            draw.text((x0 + col1_w + col2_w + PAD_X, cur_y + (ROW_H - FONT.size)//2), c3, font=FONT, fill="black")

        cur_y += ROW_H
        # Línea delgada entre filas
        draw.line([x0, cur_y, x1, cur_y], fill="black", width=THIN)

    return img

def draw_tabular_table(hdr_per100, hdr_perportion, groups):
    """
    Dibuja formato tabular (Fig. 4).
    Estructura por grupos, con nombre a la izquierda y dos columnas de valores.
    Mantiene negrilla normativa en etiquetas: Calorías, Grasa saturada, Grasas trans, Azúcares añadidos, Sodio.
    """
    left_margin = 40
    right_margin = 40

    # Medición
    img_tmp = Image.new("RGB", (10, 10), "white")
    draw_tmp = ImageDraw.Draw(img_tmp)

    # Columnas: Nombre | por 100 | por porción
    max_name_w = 0
    max_c2_w = 0
    max_c3_w = 0

    # Encabezados
    max_c2_w = max(max_c2_w, text_w(draw_tmp, hdr_per100, FONT_B))
    max_c3_w = max(max_c3_w, text_w(draw_tmp, hdr_perportion, FONT_B))

    # Medir contenido
    all_rows = []
    for title, rows in groups:
        # título de grupo puede ocupar una fila con estilo
        if title:
            all_rows.append(("__grp__", title, "", "", False, 0))
        for name, c2, c3, unit, bold, indent in rows:
            all_rows.append((name, c2, c3, unit, bold, indent))
            max_name_w = max(max_name_w, text_w(draw_tmp, ("  " * indent) + name, FONT_B if bold else FONT))
            max_c2_w = max(max_c2_w, text_w(draw_tmp, c2, FONT))
            max_c3_w = max(max_c3_w, text_w(draw_tmp, c3, FONT))

    col1_w = int(max_name_w + 2 * PAD_X)
    col2_w = int(max_c2_w + 2 * PAD_X)
    col3_w = int(max_c3_w + 2 * PAD_X)

    table_w = col1_w + col2_w + col3_w
    img_w = left_margin + table_w + right_margin

    # Altura total
    header_h = ROW_H
    # grupos + filas
    total_rows_h = 0
    for name, c2, c3, unit, bold, indent in all_rows:
        total_rows_h += ROW_H
        # si es línea de separación visual tras títulos de grupo, aplicamos al dibujar

    total_h = BORDER + header_h + THICK + total_rows_h + BORDER
    img_h = int(total_h + 20)

    img = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    # Marco exterior
    x0 = left_margin
    y0 = 10
    x1 = x0 + table_w
    y1 = y0 + total_h - 10
    draw.rectangle([x0, y0, x1, y1], outline="black", width=BORDER)

    # Encabezado (por 100 / por porción) arriba
    # Línea inferior gruesa del header
    # Línea vertical de columnas
    c1_x = x0 + col1_w
    c2_x = c1_x + col2_w

    # Encabezado
    # Nombre de columna 1 vacío
    draw.text((x0 + col1_w + PAD_X, y0 + (ROW_H - FONT_B.size)//2), hdr_per100, font=FONT_B, fill="black")
    draw.text((x0 + col1_w + col2_w + PAD_X, y0 + (ROW_H - FONT_B.size)//2), hdr_perportion, font=FONT_B, fill="black")

    y_line = y0 + header_h
    draw.line([x0, y_line, x1, y_line], fill="black", width=THICK)

    # Columnas verticales
    draw.line([c1_x, y0, c1_x, y1], fill="black", width=THIN)
    draw.line([c2_x, y0, c2_x, y1], fill="black", width=THIN)

    # Dibujar filas de grupos
    cur_y = y_line
    for name, c2, c3, unit, bold, indent in all_rows:
        if name == "__grp__":
            # Fila de título de grupo
            draw.text((x0 + PAD_X, cur_y + (ROW_H - FONT_B.size)//2), c2, font=FONT_B, fill="black")  # c2 guarda el título
            cur_y += ROW_H
            draw.line([x0, cur_y, x1, cur_y], fill="black", width=THIN)
            continue

        # Fila normal
        font_lbl = FONT_B if bold else FONT
        name_txt = ("  " * indent) + name
        draw.text((x0 + PAD_X, cur_y + (ROW_H - FONT.size)//2), name_txt, font=font_lbl, fill="black")
        draw.text((c1_x + PAD_X, cur_y + (ROW_H - FONT.size)//2), c2, font=FONT, fill="black")
        draw.text((c2_x + PAD_X, cur_y + (ROW_H - FONT.size)//2), c3, font=FONT, fill="black")

        cur_y += ROW_H
        draw.line([x0, cur_y, x1, cur_y], fill="black", width=THIN)

    return img

def draw_lineal_table(rows):
    """
    Dibuja formato lineal (Fig. 5).
    """
    left_margin = 40
    right_margin = 40
    img_tmp = Image.new("RGB", (10, 10), "white")
    draw_tmp = ImageDraw.Draw(img_tmp)

    # medir ancho máximo de las líneas
    max_w = 0
    for name, _, _, _, bold, indent in rows:
        if name in ("__sep__", "__foot__", "__hdr__"):
            continue
        max_w = max(max_w, text_w(draw_tmp, name, FONT_B if bold else FONT))

    # Encabezado por 100 g/mL
    hdr_text = ""
    for name, c2, _, _, _, _ in rows:
        if name == "__hdr__":
            hdr_text = c2
            max_w = max(max_w, text_w(draw_tmp, hdr_text, FONT_B))
            break

    # Pie
    foot_w = 0
    for name, _, _, _, _, _ in rows:
        if name == "__foot__":
            foot_w = max(foot_w, text_w(draw_tmp, footnote_text, FONT))
            break

    overall_w = int(max(max_w, foot_w) + 2 * PAD_X)
    img_w = left_margin + overall_w + right_margin

    # Altura
    total_h = BORDER + (ROW_H if hdr_text else 0) + THICK  # línea gruesa tras hdr
    for name, *_ in rows:
        if name == "__hdr__":
            continue
        total_h += ROW_H
    total_h += BORDER

    img_h = int(total_h + 20)
    img = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    # Marco
    x0 = left_margin
    y0 = 10
    x1 = x0 + overall_w
    y1 = y0 + total_h - 10
    draw.rectangle([x0, y0, x1, y1], outline="black", width=BORDER)

    cur_y = y0
    # Encabezado
    if hdr_text:
        draw.text((x0 + PAD_X, cur_y + (ROW_H - FONT_B.size)//2), hdr_text, font=FONT_B, fill="black")
        cur_y += ROW_H
        draw.line([x0, cur_y, x1, cur_y], fill="black", width=THICK)

    for name, *_ in rows:
        if name in ("__hdr__", "__sep__"):
            continue
        if name == "__foot__":
            draw.text((x0 + PAD_X, cur_y + (ROW_H - FONT.size)//2), footnote_text, font=FONT, fill="black")
        else:
            # Detectar si la línea está en negrita por prefijo "  "?
            is_bold = name.strip().startswith("Calorías:") or ("Grasa saturada:" in name) or ("Grasas trans:" in name) or ("Azúcares añadidos:" in name) or ("Sodio:" in name)
            draw.text((x0 + PAD_X, cur_y + (ROW_H - FONT.size)//2), name, font=(FONT_B if is_bold else FONT), fill="black")

        cur_y += ROW_H
        draw.line([x0, cur_y, x1, cur_y], fill="black", width=THIN)

    return img

# ============ Render según selección ============
st.header("Previsualización")
col_prev, col_btns = st.columns([0.7, 0.3])

with col_prev:
    if "Fig. 1" in format_choice or "Fig. 3" in format_choice:
        rows = common_rows_vertical()
        # Fig.1 y Fig.3 comparten estructura; la diferencia “simplificado” suele ser reducción de campos,
        # pero acá mantenemos la estética consistente (según tu solicitud de misma visual).
        img = draw_vertical_table(rows, show_columns=True)
        st.image(img, caption=None, use_container_width=True)

    elif "Fig. 4" in format_choice:
        hdr_per100, hdr_perportion, groups = rows_tabular()
        img = draw_tabular_table(hdr_per100, hdr_perportion, groups)
        st.image(img, caption=None, use_container_width=True)

    else:  # Fig. 5
        rows = rows_lineal()
        img = draw_lineal_table(rows)
        st.image(img, caption=None, use_container_width=True)

with col_btns:
    st.subheader("Exportar")
    if st.button("Descargar PNG"):
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        fname = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        st.download_button("Guardar imagen", data=buf, file_name=fname, mime="image/png")
