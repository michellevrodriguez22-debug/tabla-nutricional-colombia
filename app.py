# app.py
import math
from io import BytesIO
from datetime import datetime

import pandas as pd  # (puede usarse para logs/exportaciones futuras)
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)

# =============================================================================
# CONFIGURACIÓN GENERAL
# =============================================================================
st.set_page_config(
    page_title="Generador de Tabla Nutricional (Colombia)",
    layout="wide"
)
st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

# =============================================================================
# UTILIDADES NUMÉRICAS Y DE FORMATEO
# =============================================================================
def kcal_from_macros(
    fat_g: float,
    carb_g: float,
    protein_g: float,
    organic_acids_g: float = 0.0,
    alcohol_g: float = 0.0
) -> float:
    """
    Calcula energía (kcal) según factores aceptados en 810/2021:
    - Carbohidratos: 4 kcal/g
    - Proteína:      4 kcal/g
    - Grasa:         9 kcal/g
    - Alcohol:       7 kcal/g (poco frecuente en alimentos)
    - Ácidos org.:   3 kcal/g (si aplica)

    Se redondea a entero (0 decimales) tal como usualmente se reporta en tablas.
    """
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9 * fat_g + 4 * carb_g + 4 * protein_g + 7 * alcohol_g + 3 * organic_acids_g
    return float(round(kcal, 0))


def per100_from_portion(value_per_portion: float, portion_size: float) -> float:
    """
    Convierte un valor "por porción" a "por 100 g/mL".
    Si portion_size <= 0, retorna 0.
    """
    if portion_size and portion_size > 0:
        return float(round((value_per_portion / portion_size) * 100.0, 2))
    return 0.0


def portion_from_per100(value_per100: float, portion_size: float) -> float:
    """
    Convierte un valor "por 100 g/mL" a "por porción".
    Si portion_size <= 0, retorna 0.
    """
    if portion_size and portion_size > 0:
        return float(round((value_per100 * portion_size) / 100.0, 2))
    return 0.0


def pct_energy_from_nutrient_kcal(nutrient_kcal: float, total_kcal: float) -> float:
    """
    Calcula el % de energía que proviene de un nutriente específico respecto al total.
    Usado para validar sellos de advertencia (OPS).
    """
    if total_kcal and total_kcal > 0:
        return round((nutrient_kcal / total_kcal) * 100.0, 1)
    return 0.0


def as_num(x):
    """
    Convierte entradas a número flotante; si falla o está vacío, retorna 0.0
    (Protege al sistema de entradas vacías o no numéricas).
    """
    try:
        if x is None or x == "":
            return 0.0
        return float(x)
    except:
        return 0.0


def fmt_general_number(x, nd=1):
    """
    Formato visual simple para números en HTML.
    - Si nd>0: devuelve con nd decimales pero sin ceros ni punto sobrante.
    - Si nd=0: entero redondeado.
    """
    if isinstance(x, (int, float)):
        if math.isfinite(x):
            return f"{x:.{nd}f}".rstrip('0').rstrip('.') if nd > 0 else f"{int(round(x, 0))}"
    return "0"


# =============================================================================
# SIDEBAR — METADATOS Y CONFIGURACIÓN
# =============================================================================
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

table_format = st.sidebar.selectbox("Formato de tabla", ["Vertical estándar", "Simplificado"])
include_kj = st.sidebar.checkbox("Mostrar también kJ (opcional)", value=True)

# Vitaminas/minerales (multi-selección)
st.sidebar.header("Vitaminas y minerales a declarar (opcional)")
vm_options = [
    "Vitamina A (µg ER)",  # *** Mantener µg ER visible ***
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

# Frase opcional de "No es fuente significativa de..."
footnote_ns = st.sidebar.text_input("Frase al pie (opcional)", value="No es fuente significativa de _____.")

# =============================================================================
# INGRESO DE NUTRIENTES (SOLO NÚMEROS)
# =============================================================================
st.header("Ingreso de información nutricional (sin unidades)")
st.caption("Ingresa **solo números**. El sistema calcula automáticamente por 100 g/mL y por porción.")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Macronutrientes")
    fat_total_input = as_num(st.text_input("Grasa total (g)", value="5"))
    sat_fat_input   = as_num(st.text_input("Grasa saturada (g)", value="2"))

    # *** Grasa trans en mg (como solicitaste): se convierte a g para energía ***
    trans_fat_input_mg = as_num(st.text_input("Grasas trans (mg)", value="0"))
    trans_fat_input = trans_fat_input_mg / 1000.0  # -> g para cálculos

    carb_input      = as_num(st.text_input("Carbohidratos totales (g)", value="20"))
    sugars_total_input  = as_num(st.text_input("Azúcares totales (g)", value="10"))
    sugars_added_input  = as_num(st.text_input("Azúcares añadidos (g)", value="8"))
    fiber_input     = as_num(st.text_input("Fibra dietaria (g)", value="2"))
    protein_input   = as_num(st.text_input("Proteína (g)", value="3"))
    sodium_input_mg = as_num(st.text_input("Sodio (mg)", value="150"))

with c2:
    st.subheader("Micronutrientes (opcional)")
    vm_values = {}
    for vm in selected_vm:
        vm_values[vm] = as_num(st.text_input(vm, value="0"))

# =============================================================================
# NORMALIZACIÓN: POR PORCIÓN ↔ POR 100 g/mL
# =============================================================================
if input_basis == "Por porción":
    # Base: por porción -> calcular por 100
    fat_total_pp = fat_total_input
    sat_fat_pp   = sat_fat_input
    trans_fat_pp = trans_fat_input               # g
    carb_pp      = carb_input
    sugars_total_pp = sugars_total_input
    sugars_added_pp = sugars_added_input
    fiber_pp     = fiber_input
    protein_pp   = protein_input
    sodium_pp_mg = sodium_input_mg               # mg

    fat_total_100 = per100_from_portion(fat_total_pp, portion_size)
    sat_fat_100   = per100_from_portion(sat_fat_pp, portion_size)
    trans_fat_100 = per100_from_portion(trans_fat_pp, portion_size)   # g
    carb_100      = per100_from_portion(carb_pp, portion_size)
    sugars_total_100 = per100_from_portion(sugars_total_pp, portion_size)
    sugars_added_100 = per100_from_portion(sugars_added_pp, portion_size)
    fiber_100     = per100_from_portion(fiber_pp, portion_size)
    protein_100   = per100_from_portion(protein_pp, portion_size)
    sodium_100_mg = per100_from_portion(sodium_pp_mg, portion_size)   # mg
else:
    # Base: por 100 -> calcular por porción
    fat_total_100 = fat_total_input
    sat_fat_100   = sat_fat_input
    trans_fat_100 = trans_fat_input   # g
    carb_100      = carb_input
    sugars_total_100 = sugars_total_input
    sugars_added_100 = sugars_added_input
    fiber_100     = fiber_input
    protein_100   = protein_input
    sodium_100_mg = sodium_input_mg   # mg

    fat_total_pp = portion_from_per100(fat_total_100, portion_size)
    sat_fat_pp   = portion_from_per100(sat_fat_100, portion_size)
    trans_fat_pp = portion_from_per100(trans_fat_100, portion_size)   # g
    carb_pp      = portion_from_per100(carb_100, portion_size)
    sugars_total_pp = portion_from_per100(sugars_total_100, portion_size)
    sugars_added_pp = portion_from_per100(sugars_added_100, portion_size)
    fiber_pp     = portion_from_per100(fiber_100, portion_size)
    protein_pp   = portion_from_per100(protein_100, portion_size)
    sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_size)   # mg

# Vitaminas/minerales: normalizar también
vm_pp = {}
vm_100 = {}
for vm, val in vm_values.items():
    if input_basis == "Por porción":
        vm_pp[vm] = val
        vm_100[vm] = per100_from_portion(val, portion_size)
    else:
        vm_100[vm] = val
        vm_pp[vm] = portion_from_per100(val, portion_size)

# =============================================================================
# CÁLCULO DE ENERGÍA Y VALIDACIONES FOP (2492/2022, 254/2023)
# =============================================================================
kcal_pp = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)

kj_pp = round(kcal_pp * 4.184) if include_kj else None
kj_100 = round(kcal_100 * 4.184) if include_kj else None

# Porcentajes de energía (OPS)
pct_kcal_sug_add_pp = pct_energy_from_nutrient_kcal(4 * sugars_added_pp, kcal_pp)
pct_kcal_sat_fat_pp = pct_energy_from_nutrient_kcal(9 * sat_fat_pp, kcal_pp)
pct_kcal_trans_pp   = pct_energy_from_nutrient_kcal(9 * trans_fat_pp, kcal_pp)

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

# =============================================================================
# PREVISUALIZACIÓN “TABLA DE EMPAQUE” (HTML)
# =============================================================================
st.header("Previsualización de la Tabla de Información Nutricional")

def fmt(x, nd=1):
    """
    Formateo básico para la previsualización HTML.
    - mg: lo manejamos fuera para enteros.
    - g / otros: con 1 o 2 decimales de acuerdo al llamado.
    """
    return fmt_general_number(x, nd)

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
    perportion_label = f"por porción ({fmt(portion_size, 0)} {portion_unit})"

    # -------------------------------------------------------------------------
    # Construcción HTML
    # -------------------------------------------------------------------------
    html = f"""
    <table class="nutri-table" cellspacing="0" cellpadding="0">
      <tr>
        <th class="nutri-th" colspan="3">Información Nutricional</th>
      </tr>
      <tr>
        <td class="nutri-cell" colspan="3"><span class="nutri-small">Tamaño de porción:</span> {fmt(portion_size,0)} {portion_unit}<br>
        <span class="nutri-small">Porciones por envase:</span> {fmt(servings_per_pack,0)}</td>
      </tr>
      <tr>
        <td class="nutri-cell nutri-sep nutri-bold-13">Calorías</td>
        <td class="nutri-cell nutri-sep nutri-bold-13" style="text-align:right;">{fmt(kcal_100,0)} {('('+str(kj_100)+' kJ)') if include_kj else ''}</td>
        <td class="nutri-cell nutri-sep nutri-bold-13" style="text-align:right;">{fmt(kcal_pp,0)} {('('+str(kj_pp)+' kJ)') if include_kj else ''}</td>
      </tr>
      <tr class="nutri-row">
        <td class="nutri-cell"><b>{per100_label}</b></td>
        <td class="nutri-cell" style="text-align:right;"><b>{perportion_label}</b></td>
        <td class="nutri-cell" style="text-align:right;"><b></b></td>
      </tr>
    """

    # Helper HTML para filas con control de unidad y decimales
    def row_line(name, v100, vpp, unit, bold=False):
        """
        name: etiqueta izquierda
        v100: valor por 100
        vpp:  valor por porción
        unit: 'g', 'mg', 'µg', 'µg ER', etc.
        bold: resaltar nombre (p.ej. saturada, trans, añadidos, sodio)
        """
        name_html = f"<span class='nutri-bold-13'>{name}</span>" if bold else name

        # mg: se muestran como enteros
        if unit == "mg":
            v100_txt = f"{fmt_general_number(v100, 0)} mg"
            vpp_txt  = f"{fmt_general_number(vpp, 0)} mg"
        else:
            # Cubre 'g', 'µg', 'µg ER', etc.
            v100_txt = f"{fmt_general_number(v100, 1)} {unit}"
            vpp_txt  = f"{fmt_general_number(vpp, 1)} {unit}"

        return f"""
        <tr class="nutri-row">
          <td class="nutri-cell">{name_html}</td>
          <td class="nutri-cell" style="text-align:right;">{v100_txt}</td>
          <td class="nutri-cell" style="text-align:right;">{vpp_txt}</td>
        </tr>
        """

    # Orden 810
    html += row_line("Grasa total", fat_total_100, fat_total_pp, "g", bold=False)
    html += row_line("Grasa saturada", sat_fat_100, sat_fat_pp, "g", bold=True)

    # Trans en mg (conversión desde g para mostrar)
    html += row_line("Grasas trans", trans_fat_100 * 1000.0, trans_fat_pp * 1000.0, "mg", bold=True)

    html += row_line("Carbohidratos", carb_100, carb_pp, "g", bold=False)
    html += row_line("Azúcares totales", sugars_total_100, sugars_total_pp, "g", bold=False)
    html += row_line("Azúcares añadidos", sugars_added_100, sugars_added_pp, "g", bold=True)
    html += row_line("Fibra dietaria", fiber_100, fiber_pp, "g", bold=False)

    html += row_line("Proteína", protein_100, protein_pp, "g", bold=False)
    html += row_line("Sodio", sodium_100_mg, sodium_pp_mg, "mg", bold=True)

    # Línea de vitaminas y minerales
    if selected_vm:
        html += """
        <tr><td class="nutri-cell" colspan="3" style="border-top:2px solid #000;"></td></tr>
        """

        for vm in selected_vm:
            # Determinar unidad para la fila
            # Para Vitamina A usamos "µg ER" explícitamente
            if vm.startswith("Vitamina A"):
                unit = "µg ER"
                display_name = "Vitamina A (µg ER)"
            else:
                # Otras vitaminas y minerales:
                unit = "mg"
                if "µg" in vm:
                    unit = "µg"
                # El nombre visual se deja sin duplicar unidades al final
                display_name = vm.split(" (")[0]

            v100 = vm_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)

            html += row_line(display_name, v100, vpp, unit, bold=False)

    if footnote_ns.strip():
        html += f"""
        <tr>
          <td class="nutri-cell" colspan="3">{footnote_ns}</td>
        </tr>
        """

    html += "</table>"

    # Render robusto (evita fallo de JS dinámico)
    def render_html_safely(raw_html: str):
        try:
            st.components.v1.html(raw_html, height=600, scrolling=True)
        except Exception:
            st.markdown(raw_html, unsafe_allow_html=True)

    render_html_safely(html)

with col_preview_right:
    st.subheader("Datos de encabezado")
    st.write(f"**Producto:** {product_name or '-'}")
    if brand_name:
        st.write(f"**Marca:** {brand_name}")
    if provider:
        st.write(f"**Proveedor/Fabricante:** {provider}")
    st.write(f"**Formato de tabla:** {table_format}")
    st.write(f"**Estado físico:** {'Líquido' if is_liquid else 'Sólido'}")
    st.write(f"**Porción:** {fmt(portion_size,0)} {portion_unit} — **Porciones/Envase:** {fmt(servings_per_pack,0)}")

# =============================================================================
# GENERACIÓN DE PDF (B/N, Helvetica, líneas conectadas)
# =============================================================================
def build_pdf_buffer():
    """
    Genera el PDF con el recuadro normativo.
    - Corrige etiqueta y unidad de "Vitamina A (µg ER)" en el PDF.
    - Mantiene mg como enteros y g/µg con 1 decimal.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=10*mm, rightMargin=10*mm,
        topMargin=10*mm, bottomMargin=10*mm
    )
    styles = getSampleStyleSheet()
    style_header = ParagraphStyle("header", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=12)
    style_cell = ParagraphStyle("cell", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=11)
    style_cell_bold = ParagraphStyle("cell_b", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=12)  # ~1.3×

    story = []
    # Título superior (fuera del recuadro obligatorio, a modo informativo)
    meta = f"<b>Tabla de Información Nutricional</b> — {product_name or ''}"
    story.append(Paragraph(meta, style_header))
    story.append(Spacer(1, 4))

    # Encabezados de columnas
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    perportion_label = f"por porción ({int(round(portion_size))} {portion_unit})"

    # -------------------------------------------------------------------------
    # Filas del recuadro
    # -------------------------------------------------------------------------
    data = []
    # Título de caja
    data.append([
        Paragraph("<b>Información Nutricional</b>", style_header),
        "", ""
    ])
    # Tamaño de porción / Porciones
    data.append([
        Paragraph(
            f"Tamaño de porción: {int(round(portion_size))} {portion_unit}<br/>"
            f"Porciones por envase: {int(round(servings_per_pack))}",
            style_cell
        ),
        "", ""
    ])
    # Calorías (con kJ opcional)
    kcal_100_txt = f"{int(round(kcal_100))} kcal" + (f" ({int(round(kj_100))} kJ)" if include_kj else "")
    kcal_pp_txt = f"{int(round(kcal_pp))} kcal" + (f" ({int(round(kj_pp))} kJ)" if include_kj else "")
    data.append([
        Paragraph("Calorías", style_cell_bold),
        Paragraph(kcal_100_txt, style_cell_bold),
        Paragraph(kcal_pp_txt, style_cell_bold),
    ])
    # Encabezado de columnas (por 100 / por porción)
    data.append([
        Paragraph(per100_label, style_cell),
        Paragraph(perportion_label, style_cell),
        Paragraph("", style_cell),
    ])

    # Helper para filas con unidades
    def row(name, v100, vpp, unit, bold=False, indent=False):
        """
        Formatea una fila:
        - mg como enteros,
        - 'g', 'µg' y 'µg ER' con 1 decimal.
        - Indent agrega &nbsp;&nbsp; para subitems (saturada, trans, etc.).
        """
        label = name if not indent else f"&nbsp;&nbsp;{name}"
        pstyle = style_cell_bold if bold else style_cell

        if unit == "mg":
            v100_txt = f"{int(round(v100))} mg"
            vpp_txt  = f"{int(round(vpp))} mg"
        else:
            # 'g', 'µg', 'µg ER' (mantener 1 decimal y la unidad tal como se pasa)
            v100_txt = f"{v100:.1f} {unit}"
            vpp_txt  = f"{vpp:.1f} {unit}"

        return [Paragraph(label, pstyle), Paragraph(v100_txt, style_cell), Paragraph(vpp_txt, style_cell)]

    # Nutrientes principales (orden 810)
    data.append(row("Grasa total", fat_total_100, fat_total_pp, "g", bold=False))
    data.append(row("Grasa saturada", sat_fat_100, sat_fat_pp, "g", bold=True, indent=True))
    # Trans en mg (convertido desde g)
    data.append(row("Grasas trans", trans_fat_100 * 1000.0, trans_fat_pp * 1000.0, "mg", bold=True, indent=True))

    data.append(row("Carbohidratos", carb_100, carb_pp, "g", bold=False))
    data.append(row("Azúcares totales", sugars_total_100, sugars_total_pp, "g", bold=False, indent=True))
    data.append(row("Azúcares añadidos", sugars_added_100, sugars_added_pp, "g", bold=True, indent=True))
    data.append(row("Fibra dietaria", fiber_100, fiber_pp, "g", bold=False, indent=True))
    data.append(row("Proteína", protein_100, protein_pp, "g", bold=False))
    data.append(row("Sodio", sodium_100_mg, sodium_pp_mg, "mg", bold=True))

    # Línea separadora antes de VM (si aplica) y filas de VM
    vm_separator_row_index = None
    if selected_vm:
        # Fila vacía como marcador para línea encima de VM
        data.append(["", "", ""])
        vm_separator_row_index = len(data) - 1

        for vm in selected_vm:
            # Unidad para la fila:
            # Vitamina A: "µg ER"
            if vm.startswith("Vitamina A"):
                unit = "µg ER"
                display_name = "Vitamina A (µg ER)"  # *** Corrección clave en PDF ***
            else:
                unit = "mg"
                if "µg" in vm:
                    unit = "µg"
                display_name = vm.split(" (")[0]

            v100 = vm_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)

            data.append(row(display_name, v100, vpp, unit, bold=False))

    # Pie opcional dentro del recuadro
    if footnote_ns.strip():
        data.append([Paragraph(footnote_ns, style_cell), "", ""])

    # Construcción de tabla ReportLab
    col_widths = [110*mm, 85*mm, 85*mm]
    t = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=0)

    style_cmds = [
        # Marco externo
        ("BOX", (0,0), (-1,-1), 1.2, colors.black),

        # Rejilla vertical para crear tres columnas con bordes conectados
        ("LINEBEFORE", (1,0), (1,-1), 1.0, colors.black),
        ("LINEBEFORE", (2,0), (2,-1), 1.0, colors.black),

        # Cabecera "Información Nutricional"
        ("SPAN", (0,0), (2,0)),
        ("FONTNAME", (0,0), (0,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (2,0), 12),
        ("BOTTOMPADDING", (0,0), (2,0), 6),
        ("LINEBELOW", (0,0), (2,0), 1.2, colors.black),

        # Fila tamaño de porción / porciones por envase
        ("SPAN", (0,1), (2,1)),
        ("LINEBELOW", (0,1), (2,1), 1.2, colors.black),

        # Línea gruesa antes de calorías
        ("LINEABOVE", (0,2), (2,2), 1.5, colors.black),

        # Encabezados de columnas (por 100 / por porción)
        ("FONTNAME", (0,3), (2,3), "Helvetica-Bold"),
        ("LINEBELOW", (0,3), (2,3), 0.8, colors.black),

        # Alineación derecha para las cantidades numéricas
        ("ALIGN", (1,0), (2,-1), "RIGHT"),

        # Paddings
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]

    # Línea separadora antes de vitaminas/minerales
    if vm_separator_row_index is not None:
        style_cmds.append(("LINEABOVE", (0, vm_separator_row_index), (2, vm_separator_row_index), 1.2, colors.black))

    t.setStyle(TableStyle(style_cmds))
    story.append(t)

    # Pie de página simple (fecha)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d')}", style_cell))

    doc.build(story)
    buf.seek(0)
    return buf

# =============================================================================
# EXPORTAR
# =============================================================================
st.header("Exportar")
col_btn_pdf, _ = st.columns([0.4, 0.6])
with col_btn_pdf:
    if st.button("Generar PDF en blanco y negro"):
        pdf_buf = build_pdf_buffer()
        fname_base = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.download_button(
            "Descargar PDF",
            data=pdf_buf,
            file_name=f"{fname_base}.pdf",
            mime="application/pdf"
        )
