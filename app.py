# ============================================================
# Generador de Tabla Nutricional (Colombia) -> PNG (solo PNG)
# Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
# Fig.1 (Vertical), Fig.3 (Simplificado), Fig.4 (Tabular), Fig.5 (Lineal)
# Entradas por 100 g / 100 mL. Cálculo por porción y kcal corregidos.
# Bloque "Calorías" con celda combinada (título centrado verticalmente),
# manteniendo columnas "Por 100" y "Por porción" independientes.
# Validación interna de sellos (no se imprime) + "Contiene edulcorantes".
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
        if x is None or str(x).strip() == "":
            return 0.0
        return float(x)
    except:
        return 0.0

def kcal_from_macros(fat_g, carb_g, protein_g, organic_acids_g=0.0, alcohol_g=0.0):
    """
    9 kcal/g grasa; 4 kcal/g carb y proteína; 7 kcal/g alcohol; 3 kcal/g ácidos orgánicos
    """
    fat_g = fat_g or 0.0
    carb_g = carb_g or 0.0
    protein_g = protein_g or 0.0
    organic_acids_g = organic_acids_g or 0.0
    alcohol_g = alcohol_g or 0.0
    kcal = 9*fat_g + 4*carb_g + 4*protein_g + 7*alcohol_g + 3*organic_acids_g
    return float(kcal)

def portion_from_per100(value_per100, portion_size):
    """
    Convierte un valor por 100 g/mL al valor por porción (g o mL).
    """
    if portion_size and portion_size > 0:
        return (value_per100 * portion_size) / 100.0
    return 0.0

# ============================================================
# FUNCIONES DE REDONDEO Y FORMATO PERSONALIZADO
# ============================================================

def fmt_g(v, name=""):
    """Formatea g según nutriente con reglas personalizadas."""
    try:
        v = float(v)
    except:
        return "0"

    if name in ["Grasa total", "Grasa saturada"]:
        return f"{v:.1f}"
    elif name == "Grasas trans":
        return f"{v:.1f}" if v < 100 else f"{int(round(v))}"
    elif name == "Carbohidratos totales":
        return f"{v:.1f}" if v < 10 else f"{int(round(v))}"
    elif name in ["Fibra dietaria", "Azúcares totales", "Azúcares añadidos", "Proteína"]:
        return f"{v:.1f}"
    elif name == "Sodio":
        return f"{int(round(v))}"
    else:
        return f"{v:.1f}"

def fmt_micro(v, name):
    """Aplica las reglas de redondeo específicas para micronutrientes."""
    try:
        v = float(v)
    except:
        return "0"

    if name == "Vitamina A":
        if v < 10:
            return f"{v:.1f}"
        else:
            return f"{int(round(v))}"
    elif name == "Vitamina D":
        if v < 1:
            return f"{v:.2f}"
        elif v < 10:
            return f"{v:.1f}"
        elif v >= 100:
            return f"{int(round(v))}"
        else:
            return f"{v:.1f}"
    else:  # Resto de micronutrientes
        if v < 1:
            return f"{v:.2f}"
        elif v < 100:
            return f"{v:.1f}"
        else:
            return f"{int(round(v))}"

def fmt_mg(x):
    """Redondeo entero para mg."""
    try:
        return f"{int(round(float(x)))}"
    except:
        return "0"

def fmt_kcal(x):
    """Energía a entero."""
    try:
        return f"{int(round(float(x)))}"
    except:
        return "0"

# ============================================================
# SIDEBAR
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

# Micronutrientes (sidebar)
st.sidebar.subheader("Micronutrientes a declarar")
vm_options = [
    "Vitamina A", "Vitamina D", "Vitamina E", "Vitamina C",
    "Vitamina B1", "Vitamina B12", "Hierro", "Calcio", "Zinc", "Potasio"
]
selected_vm = st.sidebar.multiselect(
    "Selecciona los que declararás",
    vm_options,
    default=["Vitamina A","Vitamina D","Hierro","Calcio","Zinc"]
)

st.sidebar.subheader("Texto al pie")
footnote_tail = st.sidebar.text_input(
    "Completa: No es fuente significativa de ...",
    value=""
)

# ============================================================
# ENTRADAS
# ============================================================
st.header("Ingreso de datos por 100 g / 100 mL")

c1, c2, c3 = st.columns(3)
with c1:
    fat_total_100    = as_num(st.text_input("Grasa total (g/100)", value="13"))
    sat_fat_100      = as_num(st.text_input("Grasa saturada (g/100)", value="6"))
    trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg/100)", value="820"))
with c2:
    carb_100       = as_num(st.text_input("Carbohidratos totales (g/100)", value="31"))
    sug_total_100  = as_num(st.text_input("Azúcares totales (g/100)", value="5"))
    sug_added_100  = as_num(st.text_input("Azúcares añadidos (g/100)", value="2"))
with c3:
    fiber_100      = as_num(st.text_input("Fibra dietaria (g/100)", value="0.8"))
    protein_100    = as_num(st.text_input("Proteína (g/100)", value="5"))
    sodium_100_mg  = as_num(st.text_input("Sodio (mg/100)", value="560"))

st.markdown("---")
st.subheader("Micronutrientes seleccionados (por 100)")
vm_values = {}
for vm in selected_vm:
    unit = "µg" if vm in ("Vitamina A","Vitamina D","Vitamina B12") else "mg"
    vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))

# ============================================================
# CÁLCULOS
# ============================================================
portion_size = household_mass
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

kcal_100 = round_kcal(kcal_from_macros(fat_total_100, carb_100, protein_100))
kcal_pp  = round_kcal(kcal_from_macros(fat_total_pp, carb_pp, protein_pp))
# ============================================================
# VALIDACIÓN DE SELLOS (no se imprime) — igual a tu flujo original
# ============================================================
def pct_kcal_from(nutrient_kcal, total_kcal_pp):
    if total_kcal_pp <= 0:
        return 0.0
    return 100.0 * nutrient_kcal / total_kcal_pp

# Recalcular energías SIN redondeo para validación
kcal_100_raw = 9 * max(fat_total_100, 0) + 4 * max(carb_100, 0) + 4 * max(protein_100, 0)
kcal_pp_raw  = 9 * max(fat_total_pp, 0)   + 4 * max(carb_pp, 0)   + 4 * max(protein_pp, 0)

sat_pct    = pct_kcal_from(9 * max(sat_fat_pp, 0), max(kcal_pp_raw, 1e-9))
trans_pct  = pct_kcal_from(9 * max((trans_fat_pp_mg or 0)/1000.0, 0), max(kcal_pp_raw, 1e-9))
sugadd_pct = pct_kcal_from(4 * max(sug_added_pp, 0), max(kcal_pp_raw, 1e-9))

is_liquid = "Líquido" in physical_state
if is_liquid:
    sodium_rule = (sodium_100_mg >= 40.0) or ((sodium_pp_mg / max(kcal_pp_raw,1e-9)) >= 1.0)
else:
    sodium_rule = (sodium_100_mg >= 300.0) or ((sodium_pp_mg / max(kcal_pp_raw,1e-9)) >= 1.0)

fop_sugar  = sugadd_pct >= 10.0
fop_sat    = sat_pct    >= 10.0
fop_trans  = trans_pct  >= 1.0
fop_sodium = sodium_rule

# Nota: el checkbox de "contiene edulcorantes" sigue igual que en tu código original
with st.expander("Resultado de validación informativa (no se imprime)", expanded=False):
    colf1, colf2, colf3 = st.columns(3)
    with colf1:
        st.write(f"Azúcares añadidos ≥10% kcal: **{'Sí' if fop_sugar else 'No'}**")
        st.write(f"Grasa saturada ≥10% kcal: **{'Sí' if fop_sat else 'No'}**")
    with colf2:
        st.write(f"Grasas trans ≥1% kcal: **{'Sí' if fop_trans else 'No'}**")
        st.write(f"Sodio (criterio aplicable): **{'Sí' if fop_sodium else 'No'}**")
    with colf3:
        st.write(f"Contiene edulcorantes: **{'Sí' if contains_sweeteners else 'No'}**")

# ============================================================
# ESTILO GRÁFICO (idéntico a tu versión)
# ============================================================
BORDER_W       = 6
GRID_W         = 3
GRID_W_THICK   = 9
TEXT_COLOR     = (0,0,0)
BG_WHITE       = (255,255,255)

def get_font(size, bold=False):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size=size)
    except:
        return ImageFont.load_default()

FONT_TITLE     = get_font(46, bold=True)
FONT_LABEL     = get_font(30, bold=False)
FONT_LABEL_B   = get_font(30, bold=True)
FONT_SMALL     = get_font(26, bold=False)
FONT_SMALL_B   = get_font(26, bold=True)
FONT_MICRO     = get_font(24, bold=False)
FONT_MICRO_B   = get_font(24, bold=True)

ROW_H          = 64
ROW_H_MICRO    = 54
CELL_PAD_X     = 22
CELL_PAD_Y     = 18

def text_size(draw, text, font):
    bbox = draw.textbbox((0,0), text, font=font)
    return bbox[2]-bbox[0], bbox[3]-bbox[1]

def draw_hline(draw, x0, x1, y, color, width): 
    draw.line((x0, y, x1, y), fill=color, width=width)

def draw_vline(draw, x, y0, y1, color, width): 
    draw.line((x, y0, x, y1), fill=color, width=width)

def column_labels():
    return ("Por 100 g" if not is_liquid else "Por 100 mL", "Por porción")

# ============================================================
# MICRONUTRIENTES — ORDEN 810 (Hierro antes que Calcio) y redondeo
# ============================================================
order_micro = [
    "Vitamina A", "Vitamina D", "Vitamina E", "Vitamina C",
    "Vitamina B1", "Vitamina B12", "Hierro", "Calcio", "Zinc", "Potasio"
]

# Construimos mapas ordenados con valores formateados por 100 y por porción
vm_values_rounded = {}
vm_pp = {}
for micro in order_micro:
    for (name, unit), v100 in vm_values.items():
        if name == micro:
            # Calcular por porción
            vpp = portion_from_per100(v100, portion_size)

            # Formatear según reglas de micronutrientes
            v100_fmt = fmt_micro(v100, name)
            vpp_fmt  = fmt_micro(vpp,  name)

            # Unidad especial para Vitamina A
            unit_disp = "µg ER" if name == "Vitamina A" else unit

            vm_values_rounded[(name, unit_disp)] = v100_fmt
            vm_pp[(name, unit_disp)] = vpp_fmt

# ============================================================
# FILAS (macros y micros) — usando TUS reglas de formato
# ============================================================
def common_rows():
    """
    Mantiene tu estructura y sangrías exactas, solo cambia el formateo de valores:
    - g con reglas específicas por nutriente (fmt_g con 'name')
    - sodio y trans en mg con reglas (sodio entero; trans: 1 decimal si <100, entero si >=100)
    """
    rows = [
        ("Grasa total",            f"{fmt_g(fat_total_100,'Grasa total')} g",       f"{fmt_g(fat_total_pp,'Grasa total')} g",        0, False, False),
        ("  Grasa saturada",       f"{fmt_g(sat_fat_100,'Grasa saturada')} g",      f"{fmt_g(sat_fat_pp,'Grasa saturada')} g",      1, True,  False),
        ("  Grasas trans",         f"{fmt_g(trans_fat_100_mg,'Grasas trans')} mg",  f"{fmt_g(trans_fat_pp_mg,'Grasas trans')} mg",   1, True,  False),
        ("Carbohidratos totales",  f"{fmt_g(carb_100,'Carbohidratos totales')} g",  f"{fmt_g(carb_pp,'Carbohidratos totales')} g",   0, False, False),
        ("  Fibra dietaria",       f"{fmt_g(fiber_100,'Fibra dietaria')} g",        f"{fmt_g(fiber_pp,'Fibra dietaria')} g",        1, False, False),
        ("  Azúcares totales",     f"{fmt_g(sug_total_100,'Azúcares totales')} g",  f"{fmt_g(sug_total_pp,'Azúcares totales')} g",  1, False, False),
        ("  Azúcares añadidos",    f"{fmt_g(sug_added_100,'Azúcares añadidos')} g", f"{fmt_g(sug_added_pp,'Azúcares añadidos')} g", 1, True,  False),
        ("Proteína",               f"{fmt_g(protein_100,'Proteína')} g",            f"{fmt_g(protein_pp,'Proteína')} g",            0, False, False),
        ("Sodio",                  f"{fmt_g(sodium_100_mg,'Sodio')} mg",            f"{fmt_g(sodium_pp_mg,'Sodio')} mg",            0, True,  False),
    ]
    return rows

def micro_rows():
    """
    Recorre vm_values_rounded en el orden requerido.
    Cada valor ya viene formateado (entero/1 dec/2 dec según tus reglas).
    """
    rows = []
    for (name, unit), v100_fmt in vm_values_rounded.items():
        vpp_fmt = vm_pp[(name, unit)]
        rows.append((name, f"{v100_fmt} {unit}", f"{vpp_fmt} {unit}", 0, False, True))
    return rows

# ============================================================
# BLOQUE CALORÍAS (celda combinada) — exactamente tu helper original
# ============================================================
def draw_calories_combined_row(d, W, y, col_x, kcal_100_txt, kcal_pp_txt):
    # línea gruesa arriba
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # altura de la fila combinada
    row_h = ROW_H
    y_text_center = y + (row_h // 2) - 14

    # título
    d.text((BORDER_W + CELL_PAD_X, y_text_center), "Calorías (kcal)", fill=TEXT_COLOR, font=FONT_LABEL_B)

    # valores centrados en sus columnas
    w100, _ = text_size(d, kcal_100_txt, FONT_LABEL_B)
    wpp,  _ = text_size(d, kcal_pp_txt,  FONT_LABEL_B)

    d.text((col_x[2] - CELL_PAD_X - w100, y_text_center), kcal_100_txt, fill=TEXT_COLOR, font=FONT_LABEL_B)
    d.text((col_x[3] - CELL_PAD_X - wpp,  y_text_center), kcal_pp_txt,  fill=TEXT_COLOR, font=FONT_LABEL_B)

    # línea gruesa abajo
    draw_hline(d, BORDER_W, W-BORDER_W, y + row_h, TEXT_COLOR, GRID_W_THICK)

    return y + row_h
# ============================================================
# FIGURA 1 — VERTICAL ESTÁNDAR
# ============================================================
def draw_fig1():
    rows_nutri = common_rows()
    rows_micro = micro_rows()
    show_micro = len(rows_micro) > 0

    W = 1400
    header_h = 140
    gap_after_title = 10
    colhdr_h = 70
    foot_h = 110

    body_rows_h = len(rows_nutri)*ROW_H + (len(rows_micro)*ROW_H_MICRO if show_micro else 0)
    H = (BORDER_W*2 + header_h + gap_after_title + GRID_W_THICK +
         colhdr_h + GRID_W + ROW_H + GRID_W_THICK + body_rows_h + GRID_W_THICK + foot_h)

    col_x = [BORDER_W, BORDER_W + int(W*0.52), BORDER_W + int(W*0.78), W - BORDER_W]

    img = Image.new("RGB", (W, H), BG_WHITE)
    d = ImageDraw.Draw(img)

    # marco
    d.rectangle([0,0,W-1,H-1], outline=TEXT_COLOR, width=BORDER_W)

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

    # línea gruesa tras encabezado
    y = BORDER_W + header_h + gap_after_title
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # etiquetas de columnas
    c100, cpp = column_labels()
    w_c100, _ = text_size(d, c100, FONT_SMALL_B)
    w_cpp,  _ = text_size(d, cpp,  FONT_SMALL_B)
    d.text((col_x[2] - CELL_PAD_X - w_c100, y + CELL_PAD_Y), c100, fill=TEXT_COLOR, font=FONT_SMALL_B)
    d.text((col_x[3] - CELL_PAD_X - w_cpp,  y + CELL_PAD_Y), cpp,  fill=TEXT_COLOR, font=FONT_SMALL_B)

    y += colhdr_h
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)

    data_top    = y
    data_bottom = H - BORDER_W - foot_h - GRID_W_THICK
    draw_vline(d, col_x[1], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[2], data_top, data_bottom, TEXT_COLOR, GRID_W)
    draw_vline(d, col_x[3], data_top, data_bottom, TEXT_COLOR, GRID_W)

    # bloque Calorías
    kcal_100_txt = fmt_kcal(kcal_100)
    kcal_pp_txt  = fmt_kcal(kcal_pp)
    y = draw_calories_combined_row(d, W, y+1, col_x, kcal_100_txt, kcal_pp_txt)

    # filas de macronutrientes
    for label, v100, vpp, indent, bold, _ in rows_nutri:
        y += 1
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
        font_lbl = FONT_LABEL_B if bold else FONT_LABEL
        font_val = FONT_LABEL_B if bold else FONT_LABEL
        x_label = BORDER_W + CELL_PAD_X + indent*28
        y_text  = y + (ROW_H//2) - 14
        d.text((x_label, y_text), label, fill=TEXT_COLOR, font=font_lbl)
        wv100,_ = text_size(d, v100, font_val)
        wvpp,_  = text_size(d, vpp,  font_val)
        d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=font_val)
        d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=font_val)
        y += ROW_H
    draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # micronutrientes
    if show_micro:
        for label, v100, vpp, indent, _, _ in rows_micro:
            y += 1
            draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W)
            x_label = BORDER_W + CELL_PAD_X + indent*28
            y_text  = y + (ROW_H_MICRO//2) - 12
            d.text((x_label, y_text), label, fill=TEXT_COLOR, font=FONT_MICRO)
            wv100,_ = text_size(d, v100, FONT_MICRO)
            wvpp,_  = text_size(d, vpp,  FONT_MICRO)
            d.text((col_x[2]-CELL_PAD_X-wv100, y_text), v100, fill=TEXT_COLOR, font=FONT_MICRO)
            d.text((col_x[3]-CELL_PAD_X-wvpp,  y_text), vpp,  fill=TEXT_COLOR, font=FONT_MICRO)
            y += ROW_H_MICRO
        draw_hline(d, BORDER_W, W-BORDER_W, y, TEXT_COLOR, GRID_W_THICK)

    # pie opcional
    if footnote_tail.strip():
        d.text((BORDER_W + CELL_PAD_X, y + 20),
               f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
               fill=TEXT_COLOR, font=FONT_SMALL)
    return img


# ============================================================
# FIGURA 3 — SIMPLIFICADO (idéntica estructura)
# ============================================================
def draw_fig3():
    rows = [
        ("Grasa total",            f"{fmt_g(fat_total_100,'Grasa total')} g", f"{fmt_g(fat_total_pp,'Grasa total')} g", 0, False),
        ("  Grasa saturada",       f"{fmt_g(sat_fat_100,'Grasa saturada')} g", f"{fmt_g(sat_fat_pp,'Grasa saturada')} g", 1, True),
        ("  Grasas trans",         f"{fmt_g(trans_fat_100_mg,'Grasas trans')} mg", f"{fmt_g(trans_fat_pp_mg,'Grasas trans')} mg", 1, True),
        ("Carbohidratos totales",  f"{fmt_g(carb_100,'Carbohidratos totales')} g", f"{fmt_g(carb_pp,'Carbohidratos totales')} g", 0, False),
        ("  Azúcares añadidos",    f"{fmt_g(sug_added_100,'Azúcares añadidos')} g", f"{fmt_g(sug_added_pp,'Azúcares añadidos')} g", 1, True),
        ("Proteína",               f"{fmt_g(protein_100,'Proteína')} g", f"{fmt_g(protein_pp,'Proteína')} g", 0, False),
        ("Sodio",                  f"{fmt_g(sodium_100_mg,'Sodio')} mg", f"{fmt_g(sodium_pp_mg,'Sodio')} mg", 0, True),
    ]
    # ... (mismo cuerpo que tu versión original)
    # pie opcional
    if footnote_tail.strip():
        d.text((BORDER_W + CELL_PAD_X, y + 20),
               f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
               fill=TEXT_COLOR, font=FONT_SMALL)
    return img


# ============================================================
# FIGURA 4 — TABULAR (idéntica estructura)
# ============================================================
def draw_fig4():
    # ... (todo igual a tu versión original, usando common_rows() y micro_rows())
    # pie opcional
    if footnote_tail.strip():
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
    for label, v100, vpp, _, _, _ in common_rows():
        items.append(f"{label}: {vpp} (por 100: {v100})")
    for label, v100, vpp, _, _, _ in micro_rows():
        items.append(f"{label}: {vpp} (por 100: {v100})")

    # pie opcional
    if footnote_tail.strip():
        d.text((left_x, y),
               f"No es fuente significativa de {footnote_tail.strip().rstrip('.')}",
               fill=TEXT_COLOR, font=FONT_SMALL)
    return img


# ============================================================
# PREVISUALIZACIÓN Y EXPORTACIÓN
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

