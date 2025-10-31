# app.py
# -*- coding: utf-8 -*-
"""
Generador de Tabla de Información Nutricional (Colombia)
Cumple con Res. 810/2021, 2492/2022, 254/2023
- Vista previa en HTML
- Exportación a PNG (fondo blanco) en:
    * Formato tabular (Fig. 4)
    * Formato lineal (Fig. 5)
- Nota "No es fuente significativa de ..." SIEMPRE visible y personalizable (lo que sigue)
- Grasas trans: ingreso en mg, se muestra en mg; cálculos energéticos en g
- Vitamina A en µg ER (etiqueta y unidad)
"""

import math
import os
from io import BytesIO
from datetime import datetime
from typing import Dict, Tuple, List

import pandas as pd
import streamlit as st

# ===================== PIL / dibujo PNG =====================
from PIL import Image, ImageDraw, ImageFont

# ===================== ReportLab (opcional / sin PDF final) =====================
# (se mantiene importado si deseas reactivar PDF algún día)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# ============================================================
# Configuración general
# ============================================================
st.set_page_config(page_title="Generador de Tabla Nutricional (Colombia)", layout="wide")
st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

# ============================================================
# Utilidades numéricas
# ============================================================
def kcal_from_macros(fat_g: float, carb_g: float, protein_g: float, organic_acids_g: float = 0.0, alcohol_g: float = 0.0) -> float:
    """
    Energía según factores aceptados en 810/2021:
    - Carbohidratos: 4 kcal/g
    - Proteína:      4 kcal/g
    - Grasa:         9 kcal/g
    - Alcohol:       7 kcal/g (poco frecuente en alimentos)
    - Ácidos org.:   3 kcal/g (si aplica)
    """
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9*fat_g + 4*carb_g + 4*protein_g + 7*alcohol_g + 3*organic_acids_g
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

def as_num(x):
    try:
        if x is None or x == "":
            return 0.0
        return float(x)
    except:
        return 0.0

def fmt_num(value: float, unit: str, nd_g: int = 1) -> str:
    """
    Formato de valores:
    - mg sin decimales
    - g con nd_g decimales
    - µg sin decimales (por estabilidad visual)
    """
    if unit == "mg":
        return f"{int(round(value))} mg"
    elif unit == "µg":
        return f"{int(round(value))} µg"
    else:
        # g, mL, etc.
        if isinstance(value, (int, float)) and math.isfinite(value):
            return f"{value:.{nd_g}f}".rstrip('0').rstrip('.') + f" {unit}"
        return f"0 {unit}"

def try_load_font(preferred_paths: List[str], size: int) -> ImageFont.FreeTypeFont:
    """
    Intenta cargar una fuente que soporte 'µ', acentos, ER, etc.
    Ideal: DejaVuSans/DejaVuSans-Bold, NotoSans.
    """
    for p in preferred_paths:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            continue
    # Fallback a la default (puede no tener 'µ' perfecto, pero suele funcionar)
    return ImageFont.load_default()

# ============================================================
# Sidebar — Metadatos y configuración
# ============================================================
st.sidebar.header("Datos del producto")
product_type = st.sidebar.selectbox("Tipo de producto", ["Producto terminado", "Materia prima"])
physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])
input_basis = st.sidebar.radio("Modo de ingreso de datos", ["Por porción", "Por 100 g/mL"], index=0)

product_name = st.sidebar.text_input("Nombre del producto")
brand_name = st.sidebar.text_input("Marca (opcional)")
provider = st.sidebar.text_input("Proveedor/Fabricante (opcional)")

col_ps1, col_ps2 = st.sidebar.columns(2)
with col_ps1:
    portion_size = as_num(st.text_input("Tamaño de porción (solo número)", value="50"))
with col_ps2:
    portion_unit = "g" if "Sólido" in physical_state else "mL"
    st.text_input("Unidad de porción", value=portion_unit, disabled=True)

servings_per_pack = as_num(st.sidebar.text_input("Porciones por envase (número)", value="1"))

# Formatos de tabla (agregamos Fig. 4 y Fig. 5)
table_format = st.sidebar.selectbox(
    "Formato de presentación",
    ["Vertical estándar (Fig. 4)", "Lineal (Fig. 5)"],
    index=0
)

# Exportación PNG
st.sidebar.header("Exportación")
img_width_px = int(st.sidebar.number_input("Ancho PNG (px)", min_value=800, max_value=4000, value=1800, step=100))
padding_px = int(st.sidebar.number_input("Margen (px)", min_value=10, max_value=200, value=40, step=5))

include_kj = st.sidebar.checkbox("Mostrar también kJ (opcional)", value=True)

# Vitaminas/minerales (multi-selección)
st.sidebar.header("Vitaminas y minerales a declarar (opcional)")
vm_options = [
    "Vitamina A (µg ER)",  # etiqueta exacta: µg ER
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

# Pie: SIEMPRE visible. Tú personalizas lo que va después.
st.sidebar.header("Frase 'No es fuente significativa de…'")
footnote_tail = st.sidebar.text_input(
    "Completa aquí los nutrientes no significativos (ej.: vitamina C, calcio)",
    value="_____."
)
# Ensamblar pie completo (siempre inicia con la parte fija)
FOOTNOTE_PREFIX = "No es fuente significativa de "
footnote_full = FOOTNOTE_PREFIX + (footnote_tail or "")

# ============================================================
# Ingreso de nutrientes (sin unidades, solo números)
# ============================================================
st.header("Ingreso de información nutricional (sin unidades)")
st.caption("Ingresa **solo números**. El sistema calcula automáticamente por 100 g/mL y por porción.")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Macronutrientes")
    fat_total_input = as_num(st.text_input("Grasa total (g)", value="5"))
    sat_fat_input   = as_num(st.text_input("Grasa saturada (g)", value="2"))

    # Ingreso trans en mg (para mostrar en mg), convertir a g para energía
    trans_fat_input_mg = as_num(st.text_input("Grasas trans (mg)", value="0"))
    trans_fat_input_g  = trans_fat_input_mg / 1000.0

    carb_input      = as_num(st.text_input("Carbohidratos totales (g)", value="20"))
    sugars_total_input  = as_num(st.text_input("Azúcares totales (g)", value="10"))
    sugars_added_input  = as_num(st.text_input("Azúcares añadidos (g)", value="8"))
    fiber_input     = as_num(st.text_input("Fibra dietaria (g)", value="2"))
    protein_input   = as_num(st.text_input("Proteína (g)", value="3"))
    sodium_input_mg = as_num(st.text_input("Sodio (mg)", value="150"))

with c2:
    st.subheader("Micronutrientes (opcional)")
    vm_values: Dict[str, float] = {}
    for vm in selected_vm:
        vm_values[vm] = as_num(st.text_input(vm, value="0"))

# ============================================================
# Normalización por porción vs por 100 g/mL
# ============================================================
if input_basis == "Por porción":
    # Base: por porción -> calcular por 100
    fat_total_pp = fat_total_input
    sat_fat_pp   = sat_fat_input
    trans_fat_pp_g = trans_fat_input_g
    carb_pp      = carb_input
    sugars_total_pp = sugars_total_input
    sugars_added_pp = sugars_added_input
    fiber_pp     = fiber_input
    protein_pp   = protein_input
    sodium_pp_mg = sodium_input_mg

    fat_total_100 = per100_from_portion(fat_total_pp, portion_size)
    sat_fat_100   = per100_from_portion(sat_fat_pp, portion_size)
    trans_fat_100_g = per100_from_portion(trans_fat_pp_g, portion_size)
    carb_100      = per100_from_portion(carb_pp, portion_size)
    sugars_total_100 = per100_from_portion(sugars_total_pp, portion_size)
    sugars_added_100 = per100_from_portion(sugars_added_pp, portion_size)
    fiber_100     = per100_from_portion(fiber_pp, portion_size)
    protein_100   = per100_from_portion(protein_pp, portion_size)
    sodium_100_mg = per100_from_portion(sodium_pp_mg, portion_size)
else:
    # Base: por 100 -> calcular por porción
    fat_total_100 = fat_total_input
    sat_fat_100   = sat_fat_input
    trans_fat_100_g = trans_fat_input_g
    carb_100      = carb_input
    sugars_total_100 = sugars_total_input
    sugars_added_100 = sugars_added_input
    fiber_100     = fiber_input
    protein_100   = protein_input
    sodium_100_mg = sodium_input_mg

    fat_total_pp = portion_from_per100(fat_total_100, portion_size)
    sat_fat_pp   = portion_from_per100(sat_fat_100, portion_size)
    trans_fat_pp_g = portion_from_per100(trans_fat_100_g, portion_size)
    carb_pp      = portion_from_per100(carb_100, portion_size)
    sugars_total_pp = portion_from_per100(sugars_total_100, portion_size)
    sugars_added_pp = portion_from_per100(sugars_added_100, portion_size)
    fiber_pp     = portion_from_per100(fiber_100, portion_size)
    protein_pp   = portion_from_per100(protein_100, portion_size)
    sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_size)

# Vitaminas/minerales: normalizar también
vm_pp: Dict[str, float] = {}
vm_100: Dict[str, float] = {}
for vm, val in vm_values.items():
    if input_basis == "Por porción":
        vm_pp[vm] = val
        vm_100[vm] = per100_from_portion(val, portion_size)
    else:
        vm_100[vm] = val
        vm_pp[vm] = portion_from_per100(val, portion_size)

# ============================================================
# Cálculo de Energía y validaciones FOP
# ============================================================
kcal_pp = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)

kj_pp = round(kcal_pp * 4.184) if include_kj else None
kj_100 = round(kcal_100 * 4.184) if include_kj else None

# Porcentajes de energía de nutrientes críticos (para FOP)
pct_kcal_sug_add_pp = pct_energy_from_nutrient_kcal(4*sugars_added_pp, kcal_pp)
pct_kcal_sat_fat_pp = pct_energy_from_nutrient_kcal(9*sat_fat_pp, kcal_pp)
pct_kcal_trans_pp   = pct_energy_from_nutrient_kcal(9*trans_fat_pp_g, kcal_pp)

# Criterios 2492/2022 y 254/2023 (OPS)
is_liquid = ("Líquido" in physical_state)
fop_sugar = pct_kcal_sug_add_pp >= 10.0
fop_sat   = pct_kcal_sat_fat_pp >= 10.0
fop_trans = pct_kcal_trans_pp >= 1.0

# Sodio: 1 mg/kcal o >=300 mg/100 g para sólidos.
# Bebidas sin aporte energético: >=40 mg/100 mL
if is_liquid and kcal_100 == 0:
    fop_sodium = sodium_100_mg >= 40.0
else:
    fop_sodium = (sodium_100_mg >= 300.0) or ((sodium_pp_mg / max(kcal_pp, 1)) >= 1.0)

st.subheader("Resultado de validación informativa (Sellos de advertencia posibles)")
colf1, colf2, colf3, colf4 = st.columns(4)
with colf1:
    st.write(f"Azúcares añadidos ≥10% kcal: **{'Sí' if fop_sugar else 'No'}**")
with colf2:
    st.write(f"Grasa saturada ≥10% kcal: **{'Sí' if fop_sat else 'No'}**")
with colf3:
    st.write(f"Grasas trans ≥1% kcal: **{'Sí' if fop_trans else 'No'}**")
with colf4:
    st.write(f"Sodio criterio aplicable: **{'Sí' if fop_sodium else 'No'}**")

# ============================================================
# Previsualización HTML — estilo Fig. 4 (tabular)
# ============================================================
st.header("Previsualización de la Tabla de Información Nutricional")

def fmt_short(x, nd=1):
    if isinstance(x, (int, float)) and math.isfinite(x):
        return f"{x:.{nd}f}".rstrip('0').rstrip('.') if nd > 0 else f"{int(round(x,0))}"
    return "0"

col_preview_left, col_preview_right = st.columns([0.66, 0.34])

with col_preview_left:
    st.markdown("**Vista previa (no a escala)**")

    css = """
    <style>
    .nutri-table {border:2px solid #000; width:100%; font-family: Arial, Helvetica, sans-serif; color:#000;}
    .nutri-th {font-weight:bold; font-size:14px; padding:4px 6px; border-bottom:2px solid #000;}
    .nutri-row {border-top:1px solid #000;}
    .nutri-cell {padding:4px 6px; border-right:1px solid #000; vertical-align:top;}
    .nutri-cell:last-child {border-right:none;}
    .nutri-sep {border-top:2px solid #000;}
    .nutri-bold-13 {font-weight:bold; font-size: 1.15em;}
    .nutri-small {font-size: 12px;}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    perportion_label = f"por porción ({fmt_short(portion_size,0)} {portion_unit})"

    def row_line(name, v100, vpp, unit, bold=False):
        name_html = f"<span class='nutri-bold-13'>{name}</span>" if bold else name
        return f"""
        <tr class="nutri-row">
          <td class="nutri-cell">{name_html}</td>
          <td class="nutri-cell" style="text-align:right;">{fmt_short(v100, 1)} {unit}</td>
          <td class="nutri-cell" style="text-align:right;">{fmt_short(vpp, 1)} {unit}</td>
        </tr>
        """

    html = f"""
    <table class="nutri-table" cellspacing="0" cellpadding="0">
      <tr>
        <th class="nutri-th" colspan="3">Información Nutricional</th>
      </tr>
      <tr>
        <td class="nutri-cell" colspan="3"><span class="nutri-small">Tamaño de porción:</span> {fmt_short(portion_size,0)} {portion_unit}<br>
        <span class="nutri-small">Porciones por envase:</span> {fmt_short(servings_per_pack,0)}</td>
      </tr>
      <tr>
        <td class="nutri-cell nutri-sep nutri-bold-13">Calorías</td>
        <td class="nutri-cell nutri-sep nutri-bold-13" style="text-align:right;">{fmt_short(kcal_100,0)} {('('+str(kj_100)+' kJ)') if include_kj else ''}</td>
        <td class="nutri-cell nutri-sep nutri-bold-13" style="text-align:right;">{fmt_short(kcal_pp,0)} {('('+str(kj_pp)+' kJ)') if include_kj else ''}</td>
      </tr>
      <tr class="nutri-row">
        <td class="nutri-cell"><b>{per100_label}</b></td>
        <td class="nutri-cell" style="text-align:right;"><b>{perportion_label}</b></td>
        <td class="nutri-cell" style="text-align:right;"><b></b></td>
      </tr>
    """

    # Grasa total, saturada, trans (trans en mg)
    html += row_line("Grasa total", fat_total_100, fat_total_pp, "g", bold=False)
    html += row_line("  de las cuales Grasa saturada", sat_fat_100, sat_fat_pp, "g", bold=True)
    html += row_line("  Grasas trans", trans_fat_100_g*1000.0, trans_fat_pp_g*1000.0, "mg", bold=True)

    # CHO, azúcares, fibra
    html += row_line("Carbohidratos", carb_100, carb_pp, "g", bold=False)
    html += row_line("  Azúcares totales", sugars_total_100, sugars_total_pp, "g", bold=False)
    html += row_line("  Azúcares añadidos", sugars_added_100, sugars_added_pp, "g", bold=True)
    html += row_line("  Fibra dietaria", fiber_100, fiber_pp, "g", bold=False)

    # Proteína, sodio mg
    html += row_line("Proteína", protein_100, protein_pp, "g", bold=False)
    html += row_line("Sodio", sodium_100_mg, sodium_pp_mg, "mg", bold=True)

    # Vitaminas/minerales
    if selected_vm:
        html += """<tr><td class="nutri-cell" colspan="3" style="border-top:2px solid #000;"></td></tr>"""
        for vm in selected_vm:
            # unidad
            unit = "mg"
            if "µg" in vm:
                unit = "µg"
            # etiqueta limpia
            if vm.startswith("Vitamina A"):
                name = "Vitamina A (µg ER)"
            else:
                name = vm  # ya incluye unidad entre paréntesis
            v100 = vm_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)
            # Al mostrar, repetimos unidad (como en filas superiores)
            name_clean = name.split(" (")[0]
            html += row_line(name_clean, v100, vpp, unit, bold=False)

    # Pie siempre presente
    html += f"""
    <tr>
      <td class="nutri-cell" colspan="3">{footnote_full}</td>
    </tr>
    </table>
    """

    # Render robusto
    try:
        st.components.v1.html(html, height=600, scrolling=True)
    except Exception:
        st.markdown(html, unsafe_allow_html=True)

with col_preview_right:
    st.subheader("Datos de encabezado")
    st.write(f"**Producto:** {product_name or '-'}")
    if brand_name:
        st.write(f"**Marca:** {brand_name}")
    if provider:
        st.write(f"**Proveedor/Fabricante:** {provider}")
    st.write(f"**Formato:** {table_format}")
    st.write(f"**Estado físico:** {'Líquido' if is_liquid else 'Sólido'}")
    st.write(f"**Porción:** {fmt_short(portion_size,0)} {portion_unit} — **Porciones/Envase:** {fmt_short(servings_per_pack,0)}")

# ============================================================
# Render PNG — motores de dibujo
# ============================================================
# Rutas de fuentes sugeridas (ajusta si lo corres en otro entorno)
PREFERRED_FONTS_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/DejaVu Sans.ttf",
    "/Library/Fonts/DejaVu Sans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
PREFERRED_FONTS_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/DejaVu Sans Bold.ttf",
    "/Library/Fonts/DejaVu Sans Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

def measure_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    bbox = draw.textbbox((0,0), text, font=font)
    return bbox[2]-bbox[0], bbox[3]-bbox[1]

def draw_hline(draw: ImageDraw.Draw, x1: int, y: int, x2: int, width: int = 2, color: Tuple[int,int,int]=(0,0,0)):
    draw.line((x1, y, x2, y), fill=color, width=width)

def draw_vline(draw: ImageDraw.Draw, x: int, y1: int, y2: int, width: int = 2, color: Tuple[int,int,int]=(0,0,0)):
    draw.line((x, y1, x, y2), fill=color, width=width)

def make_canvas(width: int, height: int, bg=(255,255,255)) -> Image.Image:
    return Image.new("RGB", (width, height), bg)

def build_tabular_png(
    width_px: int,
    padding: int,
    show_kj: bool = True,
) -> BytesIO:
    """
    Renderiza la tabla Fig. 4 en PNG con fondo blanco
    """
    # Fuentes
    font_title = try_load_font(PREFERRED_FONTS_BOLD, 36)
    font_head  = try_load_font(PREFERRED_FONTS_BOLD, 22)
    font_cell  = try_load_font(PREFERRED_FONTS_REG, 20)
    font_cell_b= try_load_font(PREFERRED_FONTS_BOLD, 22)
    font_note  = try_load_font(PREFERRED_FONTS_REG, 18)

    # Proporciones
    outer_pad = padding
    col1_w = int(width_px * 0.42)  # nombre fila
    col2_w = int(width_px * 0.29)  # por 100
    col3_w = int(width_px * 0.29)  # por porción
    table_w = col1_w + col2_w + col3_w
    left_x = (width_px - table_w) // 2  # centrar tabla

    # Estimar alto
    # Conteo de filas base:
    row_h = 44
    sep_thick = 4
    thin = 2

    base_rows = 4  # título, tamaño porción/por envase, calorías, encabezados columnas
    nutrient_rows = 8 + 1  # (grasa tot, sat*, trans*, cho, az tot, az añad*, fibra, prot) + sodio*
    vm_rows = len(selected_vm)
    extra_seps = 1 if vm_rows > 0 else 0
    note_rows = 1

    total_rows = base_rows + nutrient_rows + extra_seps + vm_rows + note_rows
    height_px = outer_pad*2 + (total_rows * row_h) + 80

    # Canvas
    img = make_canvas(width_px, height_px, (255,255,255))
    draw = ImageDraw.Draw(img)

    # Marco exterior (box)
    top_y = outer_pad
    bottom_y = height_px - outer_pad
    left_border = left_x
    right_border = left_x + table_w

    # Encabezado dentro de caja
    cursor_y = top_y

    # Línea superior del recuadro
    draw_hline(draw, left_border, cursor_y, right_border, width=3)

    # ======= Fila 1: Título "Información Nutricional" =======
    cursor_y += 8
    title_text = "Información Nutricional"
    tw, th = measure_text(draw, title_text, font_head)
    draw.text((left_border + 10, cursor_y), title_text, fill=(0,0,0), font=font_head)
    cursor_y += th + 10
    draw_hline(draw, left_border, cursor_y, right_border, width=thin)

    # ======= Fila 2: Tamaño de porción / Porciones por envase =======
    cursor_y += 8
    line2 = f"Tamaño de porción: {int(round(portion_size))} {portion_unit}    Porciones por envase: {int(round(servings_per_pack))}"
    draw.text((left_border + 10, cursor_y), line2, fill=(0,0,0), font=font_cell)
    cursor_y += row_h - 16
    draw_hline(draw, left_border, cursor_y, right_border, width=thin)

    # ======= Fila 3: Calorías =======
    cursor_y += 8
    # Columnas
    x1 = left_border
    x2 = left_border + col1_w
    x3 = x2 + col2_w
    x4 = right_border

    # Líneas verticales
    draw_vline(draw, x2, top_y, bottom_y, width=thin)
    draw_vline(draw, x3, top_y, bottom_y, width=thin)

    cal_label = "Calorías"
    cal_100 = f"{int(round(kcal_100))} kcal" + (f" ({int(round(kj_100))} kJ)" if show_kj else "")
    cal_pp  = f"{int(round(kcal_pp))} kcal" + (f" ({int(round(kj_pp))} kJ)" if show_kj else "")

    draw.text((x1 + 10, cursor_y), cal_label, fill=(0,0,0), font=font_cell_b)
    w100, _ = measure_text(draw, cal_100, font_cell_b)
    draw.text((x3 - w100 - 10, cursor_y), cal_100, fill=(0,0,0), font=font_cell_b)
    wpp, _ = measure_text(draw, cal_pp, font_cell_b)
    draw.text((x4 - wpp - 10, cursor_y), cal_pp, fill=(0,0,0), font=font_cell_b)
    cursor_y += row_h - 12

    # Línea gruesa arriba de calorías (ya fue la superior del marco); aquí dibujamos separador inferior
    draw_hline(draw, left_border, cursor_y, right_border, width=sep_thick)

    # ======= Fila 4: encabezados por 100 / por porción =======
    cursor_y += 8
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    perportion_label = f"por porción ({int(round(portion_size))} {portion_unit})"
    draw.text((x1 + 10, cursor_y), per100_label, fill=(0,0,0), font=font_cell_b)
    wpph, _ = measure_text(draw, perportion_label, font_cell_b)
    draw.text((x3 - 10 - 0, cursor_y), perportion_label, fill=(0,0,0), font=font_cell_b)
    # Alinear encabezado central "por porción" realmente va en col2, y el de la derecha quedaría vacío (como en tu HTML)
    # Para mantener estética, dejamos solo título en col1 y col2.
    cursor_y += row_h - 16
    draw_hline(draw, left_border, cursor_y, right_border, width=thin)

    def write_row(label: str, v100: float, vpp: float, unit: str, bold: bool=False, indent: int=0):
        nonlocal cursor_y
        cursor_y += 8
        label_to_draw = ("  " * indent) + label
        lf = font_cell_b if bold else font_cell
        draw.text((x1 + 10, cursor_y), label_to_draw, fill=(0,0,0), font=lf)

        v100_txt = fmt_num(v100, unit, nd_g=1 if unit == "g" else 0)
        vpp_txt  = fmt_num(vpp, unit, nd_g=1 if unit == "g" else 0)

        w100, _ = measure_text(draw, v100_txt, font_cell)
        wpp, _  = measure_text(draw, vpp_txt, font_cell)
        draw.text((x3 - w100 - 10, cursor_y), v100_txt, fill=(0,0,0), font=font_cell)
        draw.text((x4 - wpp - 10, cursor_y), vpp_txt, fill=(0,0,0), font=font_cell)

        cursor_y += row_h - 16
        draw_hline(draw, left_border, cursor_y, right_border, width=thin)

    # ===== Nutrientes (orden 810) =====
    write_row("Grasa total", fat_total_100, fat_total_pp, "g", bold=False, indent=0)
    write_row("Grasa saturada", sat_fat_100, sat_fat_pp, "g", bold=True, indent=1)
    # Trans (mg): convertimos desde g -> mg
    write_row("Grasas trans", trans_fat_100_g*1000.0, trans_fat_pp_g*1000.0, "mg", bold=True, indent=1)

    write_row("Carbohidratos", carb_100, carb_pp, "g", bold=False, indent=0)
    write_row("Azúcares totales", sugars_total_100, sugars_total_pp, "g", bold=False, indent=1)
    write_row("Azúcares añadidos", sugars_added_100, sugars_added_pp, "g", bold=True, indent=1)
    write_row("Fibra dietaria", fiber_100, fiber_pp, "g", bold=False, indent=1)

    write_row("Proteína", protein_100, protein_pp, "g", bold=False, indent=0)
    write_row("Sodio", sodium_100_mg, sodium_pp_mg, "mg", bold=True, indent=0)

    # Vitaminas/minerales
    if selected_vm:
        # línea separadora gruesa
        draw_hline(draw, left_border, cursor_y, right_border, width=sep_thick)

        for vm in selected_vm:
            unit = "mg"
            if "µg" in vm:
                unit = "µg"
            # mostrar Vit. A en µg ER explícitamente
            if vm.startswith("Vitamina A"):
                name = "Vitamina A"
            else:
                name = vm.split(" (")[0]
            v100 = vm_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)
            write_row(name, v100, vpp, unit, bold=False, indent=0)

    # Pie SIEMPRE
    cursor_y += 8
    draw.text((left_border + 10, cursor_y), footnote_full, fill=(0,0,0), font=font_note)
    cursor_y += row_h - 16

    # Marco exterior final: líneas laterales y base
    # Re-dibujar verticales para asegurar continuidad
    draw_vline(draw, left_border, top_y, cursor_y + 8, width=2)
    draw_vline(draw, right_border, top_y, cursor_y + 8, width=2)
    draw_hline(draw, left_border, cursor_y + 8, right_border, width=2)

    # Guardar en buffer
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def build_linear_png(
    width_px: int,
    padding: int,
    show_kj: bool = True,
) -> BytesIO:
    """
    Renderiza el formato lineal (Fig. 5) en PNG con fondo blanco.
    Se arma una sola línea (o párrafo) con separadores ";"
    """
    # Fuentes
    font_title = try_load_font(PREFERRED_FONTS_BOLD, 30)
    font_text  = try_load_font(PREFERRED_FONTS_REG, 22)
    font_note  = try_load_font(PREFERRED_FONTS_REG, 20)

    # Construir texto
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    cal_100_txt = f"{int(round(kcal_100))} kcal" + (f" ({int(round(kj_100))} kJ)" if show_kj else "")
    cal_pp_txt  = f"{int(round(kcal_pp))} kcal" + (f" ({int(round(kj_pp))} kJ)" if show_kj else "")

    base_parts = [
        f"Energía {cal_pp_txt}",
        f"Grasas totales {fmt_num(fat_total_pp,'g',1)}",
        f"Grasas saturadas {fmt_num(sat_fat_pp,'g',1)}",
        f"Grasas trans {fmt_num(trans_fat_pp_g*1000.0,'mg',0)}",
        f"Carbohidratos {fmt_num(carb_pp,'g',1)}",
        f"Azúcares totales {fmt_num(sugars_total_pp,'g',1)}",
        f"Azúcares añadidos {fmt_num(sugars_added_pp,'g',1)}",
        f"Fibra dietaria {fmt_num(fiber_pp,'g',1)}",
        f"Proteína {fmt_num(protein_pp,'g',1)}",
        f"Sodio {fmt_num(sodium_pp_mg,'mg',0)}",
    ]

    # Micronutrientes lineales
    for vm in selected_vm:
        unit = "mg"
        if "µg" in vm:
            unit = "µg"
        name = "Vitamina A (µg ER)" if vm.startswith("Vitamina A") else vm
        name_clean = name.split(" (")[0]
        vpp = vm_pp.get(vm, 0.0)
        base_parts.append(f"{name_clean} {fmt_num(vpp, unit, 1)}")

    lineal_text = "; ".join(base_parts) + "."

    # Pie (siempre)
    foot_text = footnote_full

    # Medidas aproximadas de alto: dos bloques (línea + pie) + título
    height_px = padding*2 + 160 + 80

    img = make_canvas(width_px, height_px, (255,255,255))
    draw = ImageDraw.Draw(img)

    # Título
    y = padding
    draw.text((padding, y), "Información nutricional (formato lineal)", fill=(0,0,0), font=font_title)
    y += 50

    # Párrafo lineal
    # En caso de exceder ancho, hacer wrap manual
    max_text_w = width_px - 2*padding
    words = lineal_text.split(" ")
    lines = []
    current = ""
    for w in words:
        test = (current + " " + w).strip()
        tw, _ = measure_text(draw, test, font_text)
        if tw <= max_text_w:
            current = test
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)

    for ln in lines:
        draw.text((padding, y), ln, fill=(0,0,0), font=font_text)
        y += 32

    y += 12
    draw.text((padding, y), foot_text, fill=(0,0,0), font=font_note)
    y += 40

    # Redimensionar canvas si fue insuficiente
    actual_bottom = y + padding
    if actual_bottom > height_px:
        new_img = make_canvas(width_px, actual_bottom, (255,255,255))
        new_img.paste(img, (0,0))
        img = new_img

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ============================================================
# Exportar — descarga PNG
# ============================================================
st.header("Exportar (PNG fondo blanco)")
col1, col2 = st.columns(2)

with col1:
    if st.button("Generar PNG — Formato tabular (Fig. 4)"):
        png_buf = build_tabular_png(img_width_px, padding_px, show_kj=include_kj)
        fname_base = f"tabla_nutricional_tabular_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        st.download_button("Descargar PNG (Fig. 4)", data=png_buf, file_name=fname_base, mime="image/png")

with col2:
    if st.button("Generar PNG — Formato lineal (Fig. 5)"):
        png_buf = build_linear_png(img_width_px, padding_px, show_kj=include_kj)
        fname_base = f"tabla_nutricional_lineal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        st.download_button("Descargar PNG (Fig. 5)", data=png_buf, file_name=fname_base, mime="image/png")
