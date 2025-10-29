# app.py
import math
from io import BytesIO
from datetime import datetime

import pandas as pd
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

# =======================================
# Configuración general
# =======================================
st.set_page_config(page_title="Generador de Tabla Nutricional (Colombia)", layout="wide")
st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

# =======================================
# Utilidades
# =======================================
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

# =======================================
# Sidebar — Metadatos y configuración
# =======================================
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
    "Vitamina A (µg RE)",
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
selected_vm = st.sidebar.multiselect("Selecciona micronutrientes a incluir", vm_options, default=["Vitamina A (µg RE)", "Vitamina D (µg)", "Calcio (mg)", "Hierro (mg)", "Zinc (mg)"])

# Frase opcional de "No es fuente significativa de..."
footnote_ns = st.sidebar.text_input("Frase al pie (opcional)", value="No es fuente significativa de _____.")

# =======================================
# Ingreso de nutrientes (sin unidades, solo números)
# =======================================
st.header("Ingreso de información nutricional (sin unidades)")
st.caption("Ingresa **solo números**. El sistema calcula automáticamente por 100 g/mL y por porción.")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Macronutrientes")
    fat_total_input = as_num(st.text_input("Grasa total (g)", value="5"))
    sat_fat_input   = as_num(st.text_input("Grasa saturada (g)", value="2"))
    trans_fat_input = as_num(st.text_input("Grasas trans (g)", value="0"))
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

# =======================================
# Normalización por porción vs por 100 g/mL
# =======================================
if input_basis == "Por porción":
    # Base: por porción -> calcular por 100
    fat_total_pp = fat_total_input
    sat_fat_pp   = sat_fat_input
    trans_fat_pp = trans_fat_input
    carb_pp      = carb_input
    sugars_total_pp = sugars_total_input
    sugars_added_pp = sugars_added_input
    fiber_pp     = fiber_input
    protein_pp   = protein_input
    sodium_pp_mg = sodium_input_mg

    fat_total_100 = per100_from_portion(fat_total_pp, portion_size)
    sat_fat_100   = per100_from_portion(sat_fat_pp, portion_size)
    trans_fat_100 = per100_from_portion(trans_fat_pp, portion_size)
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
    trans_fat_100 = trans_fat_input
    carb_100      = carb_input
    sugars_total_100 = sugars_total_input
    sugars_added_100 = sugars_added_input
    fiber_100     = fiber_input
    protein_100   = protein_input
    sodium_100_mg = sodium_input_mg

    fat_total_pp = portion_from_per100(fat_total_100, portion_size)
    sat_fat_pp   = portion_from_per100(sat_fat_100, portion_size)
    trans_fat_pp = portion_from_per100(trans_fat_100, portion_size)
    carb_pp      = portion_from_per100(carb_100, portion_size)
    sugars_total_pp = portion_from_per100(sugars_total_100, portion_size)
    sugars_added_pp = portion_from_per100(sugars_added_100, portion_size)
    fiber_pp     = portion_from_per100(fiber_100, portion_size)
    protein_pp   = portion_from_per100(protein_100, portion_size)
    sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_size)

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

# =======================================
# Cálculo de Energía y validaciones FOP
# =======================================
kcal_pp = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)

kj_pp = round(kcal_pp * 4.184) if include_kj else None
kj_100 = round(kcal_100 * 4.184) if include_kj else None

# Porcentajes de energía de nutrientes críticos (para FOP)
pct_kcal_sug_add_pp = pct_energy_from_nutrient_kcal(4*sugars_added_pp, kcal_pp)
pct_kcal_sat_fat_pp = pct_energy_from_nutrient_kcal(9*sat_fat_pp, kcal_pp)
pct_kcal_trans_pp   = pct_energy_from_nutrient_kcal(9*trans_fat_pp, kcal_pp)

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

# =======================================
# Previsualización tipo “tabla de empaque”
# (negro/blanco; orden, negrillas y línea separadora)
# =======================================
st.header("Previsualización de la Tabla de Información Nutricional")

def fmt(x, nd=1):
    # Para sodio (mg) usamos 0 decimales; para g, 1 o 2. Mantener simple:
    if isinstance(x, (int, float)):
        if math.isfinite(x):
            return f"{x:.{nd}f}".rstrip('0').rstrip('.') if nd > 0 else f"{int(round(x,0))}"
    return "0"

col_preview_left, col_preview_right = st.columns([0.66, 0.34])

with col_preview_left:
    st.markdown("**Vista previa (no a escala)**")
    # HTML/CSS para una vista previa simple en B/N (PDF se hará con reportlab)
    # Negrillas 1.3x para calorías, grasa saturada, trans, azúcares añadidos y sodio (simulamos con font-weight y tamaño).
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
    perportion_label = f"por porción ({fmt(portion_size,0)} {portion_unit})"

    # Construcción HTML
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

    # Para alinear con orden 810: grasa total, saturada, trans; carbohidratos, fibra, azúcares totales, añadidos; proteína; sodio
    def row_line(name, v100, vpp, unit, bold=False):
        name_html = f"<span class='nutri-bold-13'>{name}</span>" if bold else name
        return f"""
        <tr class="nutri-row">
          <td class="nutri-cell">{name_html}</td>
          <td class="nutri-cell" style="text-align:right;">{fmt(v100, 1)} {unit}</td>
          <td class="nutri-cell" style="text-align:right;">{fmt(vpp, 1)} {unit}</td>
        </tr>
        """

    html += row_line("Grasa total", fat_total_100, fat_total_pp, "g", bold=False)
    html += row_line("  de las cuales Grasa saturada", sat_fat_100, sat_fat_pp, "g", bold=True)
    html += row_line("  Grasas trans", trans_fat_100, trans_fat_pp, "g", bold=True)

    html += row_line("Carbohidratos", carb_100, carb_pp, "g", bold=False)
    html += row_line("  Azúcares totales", sugars_total_100, sugars_total_pp, "g", bold=False)
    html += row_line("  Azúcares añadidos", sugars_added_100, sugars_added_pp, "g", bold=True)
    html += row_line("  Fibra dietaria", fiber_100, fiber_pp, "g", bold=False)

    html += row_line("Proteína", protein_100, protein_pp, "g", bold=False)
    html += row_line("Sodio", sodium_100_mg, sodium_pp_mg, "mg", bold=True)

    # Línea de separación para vitaminas/minerales (si hay)
    if selected_vm:
        html += """
        <tr><td class="nutri-cell" colspan="3" style="border-top:2px solid #000;"></td></tr>
        """

        for vm in selected_vm:
            unit = "mg"
            if "µg" in vm:
                unit = "µg"
            if "Potasio" in vm:
                unit = "mg"
            v100 = vm_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)
            html += row_line(vm.replace(" (µg RE)", "").replace(" (µg)", "").replace(" (mg)", ""), v100, vpp, unit, bold=False)

    if footnote_ns.strip():
        html += f"""
        <tr>
          <td class="nutri-cell" colspan="3">{footnote_ns}</td>
        </tr>
        """

    html += "</table>"
    st.markdown(html, unsafe_allow_html=True)

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

# =======================================
# Generación de PDF (blanco y negro, Helvetica, líneas conectadas)
# =======================================
def build_pdf_buffer():
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
    # Título superior (no parte de la caja obligatoria; solo para el reporte)
    meta = f"<b>Tabla de Información Nutricional</b> — {product_name or ''}"
    story.append(Paragraph(meta, style_header))
    story.append(Spacer(1, 4))

    # Construcción de la tabla normativa (recuadro)
    # Encabezado de caja
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    perportion_label = f"por porción ({int(round(portion_size))} {portion_unit})"

    # Filas
    data = []
    # Título dentro del recuadro
    data.append([
        Paragraph("<b>Información Nutricional</b>", style_header),
        "", ""
    ])
    # Tamaño de porción / Porciones
    data.append([
        Paragraph(f"Tamaño de porción: {int(round(portion_size))} {portion_unit}<br/>Porciones por envase: {int(round(servings_per_pack))}", style_cell),
        "", ""
    ])
    # Línea separadora gruesa antes de calorías
    # (la definiremos vía TableStyle con LINEABOVE en la fila de calorías)
    # Calorías (negrilla 1.3×)
    kcal_100_txt = f"{int(round(kcal_100))} kcal" + (f" ({int(round(kj_100))} kJ)" if include_kj else "")
    kcal_pp_txt = f"{int(round(kcal_pp))} kcal" + (f" ({int(round(kj_pp))} kJ)" if include_kj else "")
    data.append([
        Paragraph("Calorías", style_cell_bold),
        Paragraph(kcal_100_txt, style_cell_bold),
        Paragraph(kcal_pp_txt, style_cell_bold),
    ])
    # Encabezados de columnas por 100 y por porción
    data.append([
        Paragraph(per100_label, style_cell),
        Paragraph(perportion_label, style_cell),
        Paragraph("", style_cell),
    ])

    # Helper para filas
    def row(name, v100, vpp, unit, bold=False, indent=False):
        label = name if not indent else f"&nbsp;&nbsp;{name}"
        pstyle = style_cell_bold if bold else style_cell
        return [
            Paragraph(label, pstyle),
            Paragraph(f"{v100:.1f} {unit}" if unit != "mg" else f"{int(round(v100))} mg", style_cell),
            Paragraph(f"{vpp:.1f} {unit}"  if unit != "mg" else f"{int(round(vpp))} mg", style_cell),
        ]

    # Nutrientes (orden 810)
    data.append(row("Grasa total", fat_total_100, fat_total_pp, "g", bold=False))
    data.append(row("Grasa saturada", sat_fat_100, sat_fat_pp, "g", bold=True, indent=True))
    data.append(row("Grasas trans", trans_fat_100, trans_fat_pp, "g", bold=True, indent=True))

    data.append(row("Carbohidratos", carb_100, carb_pp, "g", bold=False))
    data.append(row("Azúcares totales", sugars_total_100, sugars_total_pp, "g", bold=False, indent=True))
    data.append(row("Azúcares añadidos", sugars_added_100, sugars_added_pp, "g", bold=True, indent=True))
    data.append(row("Fibra dietaria", fiber_100, fiber_pp, "g", bold=False, indent=True))

    data.append(row("Proteína", protein_100, protein_pp, "g", bold=False))
    # Sodio en mg sin decimales
    data.append(row("Sodio", sodium_100_mg, sodium_pp_mg, "mg", bold=True))

    # Línea de separación para vitaminas/minerales
    if selected_vm:
        data.append(["", "", ""])  # fila vacía para dibujar línea arriba

        for vm in selected_vm:
            unit = "mg"
            if "µg" in vm:
                unit = "µg"
            name_clean = vm.split(" (")[0]
            v100 = vm_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)
            data.append(row(name_clean, v100, vpp, unit, bold=False))

    # Pie opcional
    if footnote_ns.strip():
        data.append([
            Paragraph(footnote_ns, style_cell),
            "", ""
        ])

    # Tabla reportlab
    col_widths = [110*mm, 85*mm, 85*mm]  # suficiente para conectar líneas al borde sin espacios
    t = Table(data, colWidths=col_widths, hAlign="LEFT", repeatRows=0)

    # Estilos: B/N, bordes conectados, línea superior gruesa antes de calorías, negrillas en cabecera
    style_cmds = [
        # Marco externo
        ("BOX", (0,0), (-1,-1), 1.2, colors.black),
        # Rejilla vertical interna
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

        # Encabezados de columnas (per100 / per porción)
        ("FONTNAME", (0,3), (2,3), "Helvetica-Bold"),
        ("LINEBELOW", (0,3), (2,3), 0.8, colors.black),

        # Alineación derecha para cantidades
        ("ALIGN", (1,0), (2,-1), "RIGHT"),

        # Paddings
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]

    # Línea separadora antes de vitaminas/minerales (si existen)
    if selected_vm:
        # La fila justo antes del bloque VM es la primera del bloque VM; dibujamos una línea superior gruesa
        # Buscamos el índice donde empieza VM: es después de los nutrientes base + 1 fila vacía
        # Nutrientes base: 1 título + 1 porción + 1 calorías + 1 encabezado columnas + 8 líneas nutrientes + 1 sodio = 12 filas hasta sodio
        # Precálculo robusto: localizamos la fila vacía que insertamos antes de VM
        vm_start_row = None
        for i, row in enumerate(data):
            if row == ["", "", ""]:
                vm_start_row = i
                break
        if vm_start_row is not None:
            style_cmds.append(("LINEABOVE", (0, vm_start_row), (2, vm_start_row), 1.2, colors.black))

    # Pie de “No es fuente significativa…” sin línea especial extra (queda dentro de caja)
    t.setStyle(TableStyle(style_cmds))
    story.append(t)

    # Pie de página simple (fecha)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d')}", style_cell))

    doc.build(story)
    buf.seek(0)
    return buf

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
