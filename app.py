# app.py
# =======================================================================================
# Generador de Tabla Nutricional Colombia (PNG export)
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Soporta Fig.1 (vertical estándar), Fig.3 (simplificado), Fig.4 (tabular), Fig.5 (lineal)
# Exporta imagen PNG con fondo blanco, sin título adicional (para usar directamente en empaque)
#
# Cambios solicitados y aplicados:
# - Solo ingreso por 100 g / 100 mL (se elimina modo "por porción" en sidebar)
# - Se elimina "tipo de producto"
# - Título "Información Nutricional" centrado; separado por línea gruesa del bloque de porción
# - "Tamaño de porción" y "Número de porciones por envase" alineados a la izquierda
# - Sin kJ (eliminado)
# - Fila de Calorías (kcal) con 5 celdas en una sola fila:
#     [Calorías (kcal)] | [por 100 g/mL] | [valor por 100] | [por porción] | [valor por porción]
#   con líneas verticales y horizontales gruesas
# - Líneas gruesas arriba y abajo de "Calorías" y entre nutrientes y micronutrientes
# - Micronutrientes: nombre sin unidad; la unidad va junto al valor (en tipografía menor)
# - Fig.4 (tabular) con malla completa y negritas donde aplica (saturada, trans, azúcares añadidos, sodio)
# - “No es fuente significativa de …” siempre presente; texto personalizable
# - Solicitud de medida casera, cantidad casera y gramaje (g/mL) para el tamaño de porción
# - “Número de porciones por envase” con ese texto exacto
# =======================================================================================

import math
from io import BytesIO
from datetime import datetime

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------------------
# CONFIG STREAMLIT
# ---------------------------------------------------------------------------------------
st.set_page_config(page_title="Generador de Tabla Nutricional (Colombia)", layout="wide")
st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

# ---------------------------------------------------------------------------------------
# UTILIDADES NUMÉRICAS Y FORMATO
# ---------------------------------------------------------------------------------------
def as_num(x):
    try:
        if x is None or (isinstance(x, str) and x.strip() == ""):
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

# ---------------------------------------------------------------------------------------
# TIPOGRAFÍAS Y DIBUJO
# ---------------------------------------------------------------------------------------
def get_font(size, bold=False):
    """
    Intenta usar DejaVu Sans (muy común en entornos de Streamlit/PIL).
    Si no existe, usa la fuente por defecto.
    """
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size)
    except:
        return ImageFont.load_default()

def text_size(draw, text, font):
    bbox = draw.textbbox((0,0), text, font=font)
    return bbox[2]-bbox[0], bbox[3]-bbox[1]

def draw_hline(draw, x0, x1, y, color, width):
    draw.line((x0, y, x1, y), fill=color, width=width)

def draw_vline(draw, x, y0, y1, color, width):
    draw.line((x, y0, x, y1), fill=color, width=width)

# ---------------------------------------------------------------------------------------
# SIDEBAR — CONFIGURACIÓN
# ---------------------------------------------------------------------------------------
st.sidebar.header("Configuración general")

format_choice = st.sidebar.selectbox(
    "Formato a exportar",
    [
        "Fig. 1 — Vertical estándar",
        "Fig. 3 — Simplificado",
        "Fig. 4 — Tabular",
        "Fig. 5 — Lineal"
    ],
    index=0
)

physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])

product_name = st.sidebar.text_input("Nombre del producto", value="")
brand_name = st.sidebar.text_input("Marca (opcional)", value="")
provider = st.sidebar.text_input("Proveedor/Fabricante (opcional)", value="")

# Tamaño de porción (medida casera + cantidad + gramaje/volumen)
st.sidebar.subheader("Tamaño de porción")
portion_household_name = st.sidebar.text_input("Medida casera (p.ej., \"taza\", \"unidad\", \"cucharada\")", value="porción")
portion_household_qty  = st.sidebar.text_input("Cantidad de medida casera (p.ej., 1, 1/2, 2)", value="1")
portion_size = as_num(st.sidebar.text_input("Gramaje/volumen de la porción (solo número)", value="50"))
portion_unit = "g" if "Sólido" in physical_state else "mL"

servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="1"))

# Micronutrientes seleccionables
st.sidebar.header("Micronutrientes (opcional)")
vm_options = [
    "Vitamina A (µg ER)",   # mantener µg ER como etiqueta interna
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

# Texto al pie (siempre inicia con "No es fuente significativa de")
st.sidebar.header("Texto al pie")
footnote_tail = st.sidebar.text_input("Completa la frase (aparecerá siempre)", value=" _____.")
footnote_ns = f"No es fuente significativa de{'' if footnote_tail.strip().startswith(' ') else ' '}{footnote_tail.strip()}"

# ---------------------------------------------------------------------------------------
# INGRESO DE NUTRIENTES — SIEMPRE POR 100 g / 100 mL
# ---------------------------------------------------------------------------------------
st.header("Ingreso de información nutricional (por 100 g / 100 mL, sin unidades)")
st.caption("Ingresa solo números. El sistema calcula automáticamente los valores por porción para la imagen.")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Macronutrientes")
    fat_total_100    = as_num(st.text_input("Grasa total (g) por 100", value="5"))
    sat_fat_100      = as_num(st.text_input("Grasa saturada (g) por 100", value="2"))
    trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg) por 100", value="0"))  # ingreso en mg por 100
    carb_100         = as_num(st.text_input("Carbohidratos totales (g) por 100", value="20"))
    sugars_total_100 = as_num(st.text_input("Azúcares totales (g) por 100", value="10"))
    sugars_added_100 = as_num(st.text_input("Azúcares añadidos (g) por 100", value="8"))
    fiber_100        = as_num(st.text_input("Fibra dietaria (g) por 100", value="2"))
    protein_100      = as_num(st.text_input("Proteína (g) por 100", value="3"))
    sodium_100_mg    = as_num(st.text_input("Sodio (mg) por 100", value="150"))

with c2:
    st.subheader("Micronutrientes (por 100)")
    vm_values_100 = {}
    for vm in selected_vm:
        vm_values_100[vm] = as_num(st.text_input(vm, value="0"))

# ---------------------------------------------------------------------------------------
# CÁLCULO POR PORCIÓN DESDE POR 100
# ---------------------------------------------------------------------------------------
# Para cálculos energéticos, grasa trans en g
trans_fat_100_g = (trans_fat_100_mg or 0.0) / 1000.0

fat_total_pp    = portion_from_per100(fat_total_100, portion_size)
sat_fat_pp      = portion_from_per100(sat_fat_100, portion_size)
trans_fat_pp_g  = portion_from_per100(trans_fat_100_g, portion_size)
carb_pp         = portion_from_per100(carb_100, portion_size)
sugars_total_pp = portion_from_per100(sugars_total_100, portion_size)
sugars_added_pp = portion_from_per100(sugars_added_100, portion_size)
fiber_pp        = portion_from_per100(fiber_100, portion_size)
protein_pp      = portion_from_per100(protein_100, portion_size)
sodium_pp_mg    = portion_from_per100(sodium_100_mg, portion_size)

# Micronutrientes por porción
vm_pp = {}
for vm, val100 in vm_values_100.items():
    vm_pp[vm] = portion_from_per100(val100, portion_size)

# ---------------------------------------------------------------------------------------
# ENERGÍA (SOLO KCAL) Y CRITERIOS FOP (INFORMATIVO)
# ---------------------------------------------------------------------------------------
kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)
kcal_pp  = kcal_from_macros(fat_total_pp,  carb_pp,  protein_pp)

is_liquid = ("Líquido" in physical_state)

# Cálculo informativo FOP (no impreso en la tabla)
def pct_energy_from_nutrient_kcal(nutrient_kcal, total_kcal):
    if total_kcal and total_kcal > 0:
        return round((nutrient_kcal / total_kcal) * 100.0, 1)
    return 0.0

pct_kcal_sug_add_pp = pct_energy_from_nutrient_kcal(4*sugars_added_pp, kcal_pp)
pct_kcal_sat_fat_pp = pct_energy_from_nutrient_kcal(9*sat_fat_pp,   kcal_pp)
pct_kcal_trans_pp   = pct_energy_from_nutrient_kcal(9*trans_fat_pp_g, kcal_pp)

fop_sugar = pct_kcal_sug_add_pp >= 10.0
fop_sat   = pct_kcal_sat_fat_pp >= 10.0
fop_trans = pct_kcal_trans_pp   >= 1.0

if is_liquid and kcal_100 == 0:
    fop_sodium = sodium_100_mg >= 40.0
else:
    fop_sodium = (sodium_100_mg >= 300.0) or ((sodium_pp_mg / max(kcal_pp, 1)) >= 1.0)

with st.expander("Resultado de validación informativa (Sellos de advertencia posibles)", expanded=False):
    colf1, colf2, colf3, colf4 = st.columns(4)
    with colf1:
        st.write(f"Azúcares añadidos ≥10% kcal: **{'Sí' if fop_sugar else 'No'}**")
    with colf2:
        st.write(f"Grasa saturada ≥10% kcal: **{'Sí' if fop_sat else 'No'}**")
    with colf3:
        st.write(f"Grasas trans ≥1% kcal: **{'Sí' if fop_trans else 'No'}**")
    with colf4:
        st.write(f"Sodio criterio aplicable: **{'Sí' if fop_sodium else 'No'}**")

# ---------------------------------------------------------------------------------------
# ESTILO VISUAL GLOBAL PARA PNG
# ---------------------------------------------------------------------------------------
# Mantenemos los grosores confirmados
BORDER_W      = 6      # marco externo
GRID_W_THICK  = 9      # separadores principales (triplicado respecto a líneas normales)
GRID_W        = 3      # línea normal
TEXT_COLOR    = (0, 0, 0)
BG_WHITE      = (255, 255, 255)

# Tipografías (tamaños ajustados)
FONT_TITLE     = get_font(40, bold=True)   # Título centrado (más grande)
FONT_LABEL     = get_font(30, bold=False)  # Labels
FONT_LABEL_B   = get_font(32, bold=True)   # Negritas necesarias (ligeramente más grandes)
FONT_SMALL     = get_font(26, bold=False)  # Texto menor
FONT_SMALL_B   = get_font(26, bold=True)   # Texto menor en negrita
FONT_MICRO     = get_font(24, bold=False)  # Micronutrientes (más pequeño)
FONT_MICRO_B   = get_font(24, bold=True)   # Micronutrientes en negrita (si aplica)

# Medidas comunes
ROW_H        = 64
CELL_PAD_X   = 22
CELL_PAD_Y   = 18

# ---------------------------------------------------------------------------------------
# FILAS DE NUTRIENTES COMUNES (para Fig.1 y Fig.4)
# ---------------------------------------------------------------------------------------
def nutrient_rows_common():
    """
    Construye tuplas para las filas comunes:
    (label, v100_str, vpp_str, unit_key, indent, bold, is_header_row)
    * unit_key solo como referencia; valores ya incluyen unidad final donde corresponde.
    * En micronutrientes el nombre va SIN unidad; las unidades van en los valores.
    """
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"
    # Importante: la columna de "por porción" NO debe llevar cantidad en el encabezado
    perportion_label = "por porción"

    # Macros y sodio — negritas donde lo exige la norma (saturada, trans, azúcares añadidos, sodio)
    rows = [
        ("__COLHDR__", per100_label, perportion_label, "", 0, False, True),
        ("Grasa total",          f"{fmt_g(fat_total_100,1)} g",      f"{fmt_g(fat_total_pp,1)} g",      "g", 0, False, False),
        ("  Grasa saturada",     f"{fmt_g(sat_fat_100,1)} g",        f"{fmt_g(sat_fat_pp,1)} g",        "g", 1, True,  False),
        ("  Grasas trans",       f"{fmt_mg(trans_fat_100_mg)} mg",   f"{fmt_mg(trans_fat_pp_g*1000)} mg","mg",1, True,  False),
        ("Carbohidratos",        f"{fmt_g(carb_100,1)} g",           f"{fmt_g(carb_pp,1)} g",           "g", 0, False, False),
        ("  Azúcares totales",   f"{fmt_g(sugars_total_100,1)} g",   f"{fmt_g(sugars_total_pp,1)} g",   "g", 1, False, False),
        ("  Azúcares añadidos",  f"{fmt_g(sugars_added_100,1)} g",   f"{fmt_g(sugars_added_pp,1)} g",   "g", 1, True,  False),
        ("  Fibra dietaria",     f"{fmt_g(fiber_100,1)} g",          f"{fmt_g(fiber_pp,1)} g",          "g", 1, False, False),
        ("Proteína",             f"{fmt_g(protein_100,1)} g",        f"{fmt_g(protein_pp,1)} g",        "g", 0, False, False),
        ("Sodio",                f"{fmt_mg(sodium_100_mg)} mg",      f"{fmt_mg(sodium_pp_mg)} mg",      "mg",0, True,  False),
    ]

    # Micronutrientes
    if selected_vm:
        rows.append(("---SEP---", "", "", "", 0, False, False))  # separador grueso
        for vm in selected_vm:
            # nombre sin unidad
            if vm.startswith("Vitamina A"):
                name = "Vitamina A"  # se entiende µg ER en valor
                unit = "µg"
            else:
                # quitar el sufijo de unidad del nombre
                name = vm.split(" (")[0]
                unit = "µg" if "µg" in vm else "mg"

            v100 = vm_values_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)

            val100 = f"{fmt_g(v100,1)} {unit}" if unit == "µg" else f"{fmt_mg(v100)} {unit}"
            valpp  = f"{fmt_g(vpp,1)} {unit}"  if unit == "µg" else f"{fmt_mg(vpp)} {unit}"

            rows.append((name, val100, valpp, unit, 0, False, False))

    return rows

# ---------------------------------------------------------------------------------------
# DIBUJADO DE FIGURAS
# ---------------------------------------------------------------------------------------
def header_block(draw, img_w, start_y):
    """
    Dibuja:
      - Título centrado: "Información Nutricional"
      - Línea gruesa inferior
      - Debajo, alineado a la izquierda:
          * Tamaño de porción: {nombre medida casera} {cantidad} ({gramaje unidad})
          * Número de porciones por envase: {servings}
      - Línea fina debajo del bloque de porción
    Retorna y actualiza la coordenada y actual.
    """
    # Título centrado
    title = "Información Nutricional"
    tw, th = text_size(draw, title, FONT_TITLE)
    x_center = img_w // 2
    y = BORDER_W + 10
    draw.text((x_center - tw//2, y), title, fill=TEXT_COLOR, font=FONT_TITLE)
    y += th + 10
    draw_hline(draw, BORDER_W, img_w - BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # Bloque porción (alineado a la izquierda)
    y += 10
    # Tamaño de porción: Medida casera + cantidad + (gramaje unidad)
    portion_left = BORDER_W + CELL_PAD_X
    portion_line = f"Tamaño de porción: {portion_household_name} {portion_household_qty} ({int(round(portion_size))} {portion_unit})"
    draw.text((portion_left, y + 6), portion_line, fill=TEXT_COLOR, font=FONT_SMALL)
    y += 40
    servings_line = f"Número de porciones por envase: {int(round(servings_per_pack))}"
    draw.text((portion_left, y + 2), servings_line, fill=TEXT_COLOR, font=FONT_SMALL)

    y += 40
    draw_hline(draw, BORDER_W, img_w - BORDER_W, y, TEXT_COLOR, GRID_W)
    return y

def draw_calories_row(draw, x_cols, cur_y, per100_label):
    """
    Dibuja la fila de Calorías como UNA sola fila con 5 celdas:
      [Calorías (kcal)] | [por 100 g/mL] | [valor por 100] | [por porción] | [valor por porción]
    Con líneas verticales y horizontales gruesas arriba/abajo.
    """
    # Texto
    c0 = "Calorías (kcal)"
    c1 = per100_label                 # "por 100 g" o "por 100 mL"
    c2 = fmt_kcal(kcal_100)           # valor por 100
    c3 = "por porción"                # etiqueta sin cantidad
    c4 = fmt_kcal(kcal_pp)            # valor por porción

    # Línea gruesa superior
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W_THICK)

    # Altura de fila de calorías (más alta que ROW_H estándar)
    row_h = max(ROW_H, 80)
    y_text = cur_y + (row_h // 2) - 16

    # Celdas: 5 columnas (ya están en x_cols)
    # c0
    draw.text((x_cols[0] + CELL_PAD_X, y_text), c0, fill=TEXT_COLOR, font=FONT_LABEL_B)
    # c1
    w1, _ = text_size(draw, c1, FONT_SMALL_B)
    draw.text((x_cols[1+1] - CELL_PAD_X - w1, y_text), c1, fill=TEXT_COLOR, font=FONT_SMALL_B)
    # c2
    w2, _ = text_size(draw, c2, FONT_LABEL_B)
    draw.text((x_cols[2+1] - CELL_PAD_X - w2, y_text), c2, fill=TEXT_COLOR, font=FONT_LABEL_B)
    # c3
    w3, _ = text_size(draw, c3, FONT_SMALL_B)
    draw.text((x_cols[3+1] - CELL_PAD_X - w3, y_text), c3, fill=TEXT_COLOR, font=FONT_SMALL_B)
    # c4
    w4, _ = text_size(draw, c4, FONT_LABEL_B)
    draw.text((x_cols[4] - CELL_PAD_X - w4, y_text), c4, fill=TEXT_COLOR, font=FONT_LABEL_B)

    # Verticales internas
    # x_cols: [x0, x1, x2, x3, x4, x5]
    for i in range(1, len(x_cols)-1):
        draw_vline(draw, x_cols[i], cur_y, cur_y + row_h, TEXT_COLOR, GRID_W)

    # Línea gruesa inferior
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y + row_h, TEXT_COLOR, GRID_W_THICK)

    return cur_y + row_h  # nueva y

def draw_table_fig1_vertical():
    """
    Dibuja Fig.1 (vertical estándar) como imagen PNG:
      - Título centrado
      - Bloque de porción alineado a la izquierda
      - Fila de calorías (kcal) en una sola fila con 5 celdas
      - Fila de cabeceras de columnas (por 100 … | por porción)
      - Nutrientes con negritas donde corresponde
      - Separador grueso antes de micronutrientes
      - Pie de "No es fuente significativa de …"
    """
    rows = nutrient_rows_common()
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"

    # Dimensiones base
    W = 1600
    header_extra = 180     # espacio para título, línea gruesa, porción y línea fina
    calories_h   = 84      # altura específica de la fila de calorías
    colhdr_h     = 70      # altura de fila de cabeceras
    footer_h     = 120

    # Contemos filas visuales reales
    data_rows = [r for r in rows if r[0] != "---SEP---"]
    sep_count = len([r for r in rows if r[0] == "---SEP---"])
    H = BORDER_W*2 + header_extra + calories_h + colhdr_h + (len(data_rows)-1)*ROW_H + sep_count*GRID_W_THICK + footer_h + 40

    # Columnas:
    # Para calorías usaremos 5 celdas (x0..x5). Luego, para el resto, 3 columnas: label, v100, vpp.
    # Definimos anchos proporcionados:
    # - Para calorías (5 celdas): 30% | 17% | 13% | 17% | 23%
    x0 = BORDER_W
    x1 = x0 + int(W*0.30)
    x2 = x1 + int(W*0.17)
    x3 = x2 + int(W*0.13)
    x4 = x3 + int(W*0.17)
    x5 = W - BORDER_W
    x_cols_cal = [x0, x1, x2, x3, x4, x5]

    # Para filas normales (3 columnas) reusaremos:
    #   col1: label, col2: por 100, col3: por porción
    col1 = x0
    col2 = x0 + int(W*0.62)
    col3 = x0 + int(W*0.84)
    col4 = W - BORDER_W  # fin marco
    x_cols = [col1, col2, col3, col4]

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco externo
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Header
    cur_y = header_block(draw, W, BORDER_W+10)

    # Fila de calorías (única fila con 5 celdas)
    cur_y = draw_calories_row(draw, x_cols_cal, cur_y, per100_label)

    # Cabeceras de columnas (por 100 … | por porción)
    # OJO: Estas cabeceras van como una fila independiente y NO incluyen cantidades
    #      (y NO van bajo la fila de calorías, sino inmediatamente después)
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W)
    y_text = cur_y + CELL_PAD_Y
    _, per100_hdr, perportion_hdr, _, _, _, _ = ("__COLHDR__", per100_label, "por porción", "", 0, False, True)
    wc100, _ = text_size(draw, per100_hdr, FONT_SMALL_B)
    wcpp,  _ = text_size(draw, perportion_hdr, FONT_SMALL_B)
    draw.text((x_cols[2] - CELL_PAD_X - wc100, y_text), per100_hdr, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((x_cols[3] - CELL_PAD_X - wcpp,  y_text), perportion_hdr, fill=TEXT_COLOR, font=FONT_SMALL_B)

    cur_y += colhdr_h
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W)

    # Verticales internas (solo desde debajo de la fila de cabeceras)
    draw_vline(draw, x_cols[1], cur_y, H-BORDER_W- (footer_h+20), TEXT_COLOR, GRID_W)
    draw_vline(draw, x_cols[2], cur_y, H-BORDER_W- (footer_h+20), TEXT_COLOR, GRID_W)
    draw_vline(draw, x_cols[3], cur_y, H-BORDER_W- (footer_h+20), TEXT_COLOR, GRID_W)

    # Filas de nutrientes
    for tup in rows[1:]:
        if tup[0] == "---SEP---":
            draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W_THICK)
            continue

        label, v100, vpp, unit, indent, bold, _ = tup
        # línea superior de la fila
        draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W)

        # Label izquierda
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        x_label = x_cols[0] + CELL_PAD_X + (indent * 28)
        y_label = cur_y + (ROW_H//2) - 14
        draw.text((x_label, y_label), label, fill=TEXT_COLOR, font=font_lbl)

        # Valores a la derecha
        # Micronutrientes con tipografía menor
        is_micro = (label not in ["Grasa total", "  Grasa saturada", "  Grasas trans", "Carbohidratos",
                                  "  Azúcares totales", "  Azúcares añadidos", "  Fibra dietaria",
                                  "Proteína", "Sodio"])
        font_val = (FONT_MICRO_B if bold else FONT_MICRO) if is_micro else (FONT_LABEL_B if bold else FONT_LABEL)

        wv100, _ = text_size(draw, v100, font_val)
        wvpp,  _ = text_size(draw, vpp,  font_val)
        draw.text((x_cols[2] - CELL_PAD_X - wv100, y_label), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((x_cols[3] - CELL_PAD_X - wvpp,  y_label), vpp,  fill=TEXT_COLOR, font=font_val)

        cur_y += ROW_H

    # Base antes de pie (separador grueso)
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W_THICK)
    cur_y += 16
    draw.text((x_cols[0] + CELL_PAD_X, cur_y + 10), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

def draw_table_fig3_simple():
    """
    Dibuja Fig.3 (simplificado):
      - Misma cabecera (centrada) y bloque porción alineado a izquierda
      - Fila de calorías (kcal) en una sola fila con 5 celdas
      - Subconjunto de nutrientes (simplificado) en 3 columnas
      - Micronutrientes opcionales, en tipografía menor, con línea gruesa separadora
    """
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"

    # Definimos el subconjunto simplificado (orden 810 + negritas donde aplica)
    rows = [
        ("__COLHDR__", per100_label, "por porción", "", 0, False, True),
        ("Grasa total",          f"{fmt_g(fat_total_100,1)} g",      f"{fmt_g(fat_total_pp,1)} g",      "g", 0, False, False),
        ("  Grasa saturada",     f"{fmt_g(sat_fat_100,1)} g",        f"{fmt_g(sat_fat_pp,1)} g",        "g", 1, True,  False),
        ("  Grasas trans",       f"{fmt_mg(trans_fat_100_mg)} mg",   f"{fmt_mg(trans_fat_pp_g*1000)} mg","mg",1, True,  False),
        ("Carbohidratos",        f"{fmt_g(carb_100,1)} g",           f"{fmt_g(carb_pp,1)} g",           "g", 0, False, False),
        ("  Azúcares añadidos",  f"{fmt_g(sugars_added_100,1)} g",   f"{fmt_g(sugars_added_pp,1)} g",   "g", 1, True,  False),
        ("Proteína",             f"{fmt_g(protein_100,1)} g",        f"{fmt_g(protein_pp,1)} g",        "g", 0, False, False),
        ("Sodio",                f"{fmt_mg(sodium_100_mg)} mg",      f"{fmt_mg(sodium_pp_mg)} mg",      "mg",0, True,  False),
    ]

    # Añadir micronutrientes si hay
    if selected_vm:
        rows.append(("---SEP---", "", "", "", 0, False, False))
        for vm in selected_vm:
            if vm.startswith("Vitamina A"):
                name = "Vitamina A"; unit = "µg"
            else:
                name = vm.split(" (")[0]; unit = "µg" if "µg" in vm else "mg"
            v100 = vm_values_100.get(vm, 0.0)
            vpp  = vm_pp.get(vm, 0.0)
            val100 = f"{fmt_g(v100,1)} {unit}" if unit == "µg" else f"{fmt_mg(v100)} {unit}"
            valpp  = f"{fmt_g(vpp,1)} {unit}"  if unit == "µg" else f"{fmt_mg(vpp)} {unit}"
            rows.append((name, val100, valpp, unit, 0, False, False))

    # Dimensiones
    W = 1500
    header_extra = 180
    calories_h   = 84
    colhdr_h     = 70
    footer_h     = 120

    data_rows = [r for r in rows if r[0] != "---SEP---"]
    sep_count = len([r for r in rows if r[0] == "---SEP---"])
    H = BORDER_W*2 + header_extra + calories_h + colhdr_h + (len(data_rows)-1)*ROW_H + sep_count*GRID_W_THICK + footer_h + 40

    # Columnas calorías (5 celdas)
    x0 = BORDER_W
    x1 = x0 + int(W*0.30)
    x2 = x1 + int(W*0.17)
    x3 = x2 + int(W*0.13)
    x4 = x3 + int(W*0.17)
    x5 = W - BORDER_W
    x_cols_cal = [x0, x1, x2, x3, x4, x5]

    # Columnas normales (3)
    col1 = x0
    col2 = x0 + int(W*0.60)
    col3 = x0 + int(W*0.83)
    col4 = W - BORDER_W
    x_cols = [col1, col2, col3, col4]

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Header
    cur_y = header_block(draw, W, BORDER_W+10)

    # Fila calorías
    cur_y = draw_calories_row(draw, x_cols_cal, cur_y, per100_label)

    # Cabeceras
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W)
    y_text = cur_y + CELL_PAD_Y
    wc100, _ = text_size(draw, per100_label, FONT_SMALL_B)
    wcpp,  _ = text_size(draw, "por porción",  FONT_SMALL_B)
    draw.text((x_cols[2] - CELL_PAD_X - wc100, y_text), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((x_cols[3] - CELL_PAD_X - wcpp,  y_text), "por porción",  fill=TEXT_COLOR, font=FONT_SMALL_B)

    cur_y += colhdr_h
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W)

    # Verticales internas
    draw_vline(draw, x_cols[1], cur_y, H-BORDER_W-(footer_h+20), TEXT_COLOR, GRID_W)
    draw_vline(draw, x_cols[2], cur_y, H-BORDER_W-(footer_h+20), TEXT_COLOR, GRID_W)
    draw_vline(draw, x_cols[3], cur_y, H-BORDER_W-(footer_h+20), TEXT_COLOR, GRID_W)

    # Filas
    for tup in rows[1:]:
        if tup[0] == "---SEP---":
            draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W_THICK)
            continue
        label, v100, vpp, unit, indent, bold, _ = tup

        draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        x_label = x_cols[0] + CELL_PAD_X + (indent * 28)
        y_label = cur_y + (ROW_H//2) - 14
        draw.text((x_label, y_label), label, fill=TEXT_COLOR, font=font_lbl)

        # Micronutrientes tipografía menor
        is_micro = (label not in ["Grasa total", "  Grasa saturada", "  Grasas trans",
                                  "Carbohidratos", "  Azúcares añadidos",
                                  "Proteína", "Sodio"])
        font_val = (FONT_MICRO_B if bold else FONT_MICRO) if is_micro else (FONT_LABEL_B if bold else FONT_LABEL)

        wv100, _ = text_size(draw, v100, font_val)
        wvpp,  _ = text_size(draw, vpp,  font_val)
        draw.text((x_cols[2] - CELL_PAD_X - wv100, y_label), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((x_cols[3] - CELL_PAD_X - wvpp,  y_label), vpp,  fill=TEXT_COLOR, font=font_val)

        cur_y += ROW_H

    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W_THICK)
    cur_y += 16
    draw.text((x_cols[0] + CELL_PAD_X, cur_y + 10), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

def draw_table_fig4_tabular():
    """
    Dibuja Fig.4 (tabular):
      - Título centrado y bloque porción a izquierda (como en otras figs)
      - Fila de calorías (kcal) en 5 celdas (coherencia visual)
      - Grid uniforme tipo tabla: cada fila se ve como “celdas” completas
      - Negritas en saturada, trans, azúcares añadidos y sodio
      - Separador grueso antes de micronutrientes (que van más pequeños, sin unidad en nombre)
    """
    rows = nutrient_rows_common()
    per100_label = "por 100 g" if not is_liquid else "por 100 mL"

    # Dimensiones más “tablares”
    W = 1650
    header_extra = 180
    calories_h   = 84
    colhdr_h     = 70
    footer_h     = 120

    data_rows = [r for r in rows if r[0] != "---SEP---"]
    sep_count = len([r for r in rows if r[0] == "---SEP---"])
    H = BORDER_W*2 + header_extra + calories_h + colhdr_h + (len(data_rows)-1)*ROW_H + sep_count*GRID_W_THICK + footer_h + 40

    # Columnas para calorías (5 celdas)
    x0 = BORDER_W
    x1 = x0 + int(W*0.28)
    x2 = x1 + int(W*0.18)
    x3 = x2 + int(W*0.12)
    x4 = x3 + int(W*0.18)
    x5 = W - BORDER_W
    x_cols_cal = [x0, x1, x2, x3, x4, x5]

    # Columnas tabulares (todas con verticales — grid completo):
    # col_label, col_100, col_pp
    col1 = x0
    col2 = x0 + int(W*0.58)
    col3 = x0 + int(W*0.79)
    col4 = W - BORDER_W
    x_cols = [col1, col2, col3, col4]

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Header
    cur_y = header_block(draw, W, BORDER_W+10)

    # Fila Calorías (5 celdas)
    cur_y = draw_calories_row(draw, x_cols_cal, cur_y, per100_label)

    # Fila de cabeceras tabulares
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W)
    y_text = cur_y + CELL_PAD_Y
    wc100, _ = text_size(draw, per100_label, FONT_SMALL_B)
    wcpp,  _ = text_size(draw, "por porción", FONT_SMALL_B)
    draw.text((x_cols[2] - CELL_PAD_X - wc100, y_text), per100_label, fill=TEXT_COLOR, font=FONT_SMALL_B)
    draw.text((x_cols[3] - CELL_PAD_X - wcpp,  y_text), "por porción",  fill=TEXT_COLOR, font=FONT_SMALL_B)
    cur_y += colhdr_h
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W)

    # Verticales (grid completo) desde aquí
    for xline in [x_cols[1], x_cols[2], x_cols[3]]:
        draw_vline(draw, xline, cur_y, H-BORDER_W-(footer_h+20), TEXT_COLOR, GRID_W)

    # Filas tipo celdas completas
    for tup in rows[1:]:
        if tup[0] == "---SEP---":
            # Separador grueso entre nutrientes y micronutrientes
            draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W_THICK)
            continue

        label, v100, vpp, unit, indent, bold, _ = tup
        # Línea superior de la fila
        draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W)

        # Columna 1 (label, con indent)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        x_label = x_cols[0] + CELL_PAD_X + (indent * 28)
        y_text  = cur_y + (ROW_H//2) - 14
        draw.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)

        # Columnas 2 y 3 (valores)
        is_micro = (label not in ["Grasa total", "  Grasa saturada", "  Grasas trans",
                                  "Carbohidratos", "  Azúcares totales", "  Azúcares añadidos",
                                  "  Fibra dietaria", "Proteína", "Sodio"])
        font_val = (FONT_MICRO_B if bold else FONT_MICRO) if is_micro else (FONT_LABEL_B if bold else FONT_LABEL)

        wv100, _ = text_size(draw, v100, font_val)
        wvpp,  _ = text_size(draw, vpp,  font_val)
        draw.text((x_cols[2] - CELL_PAD_X - wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        draw.text((x_cols[3] - CELL_PAD_X - wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)

        cur_y += ROW_H

    # Base y pie
    draw_hline(draw, x_cols[0], x_cols[-1], cur_y, TEXT_COLOR, GRID_W_THICK)
    cur_y += 16
    draw.text((x_cols[0] + CELL_PAD_X, cur_y + 10), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)

    return img

def draw_table_fig5_linear():
    """
    Dibuja Fig.5 (lineal):
      - Título centrado, bloque porción a izquierda
      - Lista lineal separada por " • "
      - Micronutrientes con nombre sin unidad; unidad junto al valor
    """
    items = []

    def add_pair(name, vpp_txt, v100_txt):
        items.append(f"{name}: {vpp_txt} (por 100: {v100_txt})")

    # Energía (solo kcal)
    add_pair("Calorías (kcal)", fmt_kcal(kcal_pp), fmt_kcal(kcal_100))
    # Macros y sodio
    add_pair("Grasa total",        f"{fmt_g(fat_total_pp,1)} g",      f"{fmt_g(fat_total_100,1)} g")
    add_pair("Grasa saturada",     f"{fmt_g(sat_fat_pp,1)} g",        f"{fmt_g(sat_fat_100,1)} g")
    add_pair("Grasas trans",       f"{fmt_mg(trans_fat_pp_g*1000)} mg", f"{fmt_mg(trans_fat_100_mg)} mg")
    add_pair("Carbohidratos",      f"{fmt_g(carb_pp,1)} g",           f"{fmt_g(carb_100,1)} g")
    add_pair("Azúcares totales",   f"{fmt_g(sugars_total_pp,1)} g",   f"{fmt_g(sugars_total_100,1)} g")
    add_pair("Azúcares añadidos",  f"{fmt_g(sugars_added_pp,1)} g",   f"{fmt_g(sugars_added_100,1)} g")
    add_pair("Fibra dietaria",     f"{fmt_g(fiber_pp,1)} g",          f"{fmt_g(fiber_100,1)} g")
    add_pair("Proteína",           f"{fmt_g(protein_pp,1)} g",        f"{fmt_g(protein_100,1)} g")
    add_pair("Sodio",              f"{fmt_mg(sodium_pp_mg)} mg",      f"{fmt_mg(sodium_100_mg)} mg")

    # Micronutrientes
    for vm in selected_vm:
        if vm.startswith("Vitamina A"):
            name = "Vitamina A"; unit = "µg"
        else:
            name = vm.split(" (")[0]; unit = "µg" if "µg" in vm else "mg"
        vpp  = vm_pp.get(vm, 0.0)
        v100 = vm_values_100.get(vm, 0.0)
        vpp_txt  = f"{fmt_g(vpp,1)} {unit}" if unit == "µg" else f"{fmt_mg(vpp)} {unit}"
        v100_txt = f"{fmt_g(v100,1)} {unit}" if unit == "µg" else f"{fmt_mg(v100)} {unit}"
        add_pair(name, vpp_txt, v100_txt)

    # Dimensiones
    W = 1650
    H = 560 if len(items) <= 8 else 720 if len(items) <= 14 else 900

    img = Image.new("RGB", (W, H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # Marco
    draw.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

    # Header
    cur_y = header_block(draw, W, BORDER_W+10)

    # Texto lineal
    left_x = BORDER_W + 28
    y = cur_y + 30

    # Construimos cadena con separadores
    stream = "  •  ".join(items)
    max_width = W - left_x - 30
    words = stream.split(" ")
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

    y += 10
    draw.text((left_x, y), footnote_ns, fill=TEXT_COLOR, font=FONT_SMALL)
    return img

# ---------------------------------------------------------------------------------------
# PREVISUALIZACIÓN Y EXPORTACIÓN
# ---------------------------------------------------------------------------------------
st.header("Previsualización")
preview_col, controls_col = st.columns([0.72, 0.28])

with controls_col:
    st.caption("Elige el formato y exporta la imagen PNG (fondo blanco).")
    export_btn = st.button("Generar PNG con fondo blanco")

with preview_col:
    if format_choice.startswith("Fig. 1"):
        img_prev = draw_table_fig1_vertical()
    elif format_choice.startswith("Fig. 3"):
        img_prev = draw_table_fig3_simple()
    elif format_choice.startswith("Fig. 4"):
        img_prev = draw_table_fig4_tabular()
    else:
        img_prev = draw_table_fig5_linear()

    st.image(img_prev, caption="Vista previa (escala reducida)", use_column_width=True)

# Exportar
if export_btn:
    buf = BytesIO()
    img_prev.save(buf, format="PNG")
    buf.seek(0)
    fname = f"tabla_nutricional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    st.download_button("Descargar imagen PNG", data=buf, file_name=fname, mime="image/png")
