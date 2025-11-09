app.py
============================================================
Generador de Tabla Nutricional (Colombia) -> PNG (solo PNG)
Cumple visualmente con Res. 810/2021, 2492/2022 y 254/2023
Fig.1 (Vertical), Fig.3 (Simplificado), Fig.4 (Tabular), Fig.5 (Lineal)
Entradas por 100 g / 100 mL. Cálculo por porción y kcal corregidos.
Bloque "Calorías" con celda combinada (título centrado verticalmente),
manteniendo columnas "Por 100" y "Por porción" independientes.
Validación interna de sellos (no se imprime) + "Contiene edulcorantes".
============================================================
from io import BytesIO from datetime import datetime import streamlit as st from PIL import Image, ImageDraw, ImageFont

--- Parche seguro: helpers de líneas por si no están en global ---
if 'draw_hline' not in globals(): def draw_hline(draw, x0, x1, y, color, width): draw.line((x0, y, x1, y), fill=color, width=width)

if 'draw_vline' not in globals(): def draw_vline(draw, x, y0, y1, color, width): draw.line((x, y0, x, y1), fill=color, width=width)

--- Fin parche ---
============================================================
FUNCIÓN PARA CARGAR FUENTES — AÑADIDO POR EL PATCHER
============================================================
def get_font(size, bold=False): try: font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" return ImageFont.truetype(font_path, size) except: return ImageFont.load_default()

============================================================
CONFIG
============================================================
st.set_page_config(page_title="Generador de Tabla Nutricional (Colombia)", layout="wide") st.title("Generador de Tabla de Información Nutricional — (Res. 810/2021, 2492/2022, 254/2023)")

============================================================
UTILIDADES
============================================================
def as_num(x): try: if x is None or str(x).strip() == "": return 0.0 return float(x) except: return 0.0

def kcal_from_macros(fat_g, carb_g, protein_g, organic_acids_g=0.0, alcohol_g=0.0): """ 9 kcal/g grasa; 4 kcal/g carb y proteína; 7 kcal/g alcohol; 3 kcal/g ácidos orgánicos """ fat_g = fat_g or 0.0 carb_g = carb_g or 0.0 protein_g = protein_g or 0.0 organic_acids_g = organic_acids_g or 0.0 alcohol_g = alcohol_g or 0.0 kcal = 9fat_g + 4carb_g + 4protein_g + 7alcohol_g + 3*organic_acids_g return float(kcal)

def portion_from_per100(value_per100, portion_size): """ Convierte un valor por 100 g/mL al valor por porción (g o mL). """ if portion_size and portion_size > 0: return (value_per100 * portion_size) / 100.0 return 0.0

---- Reglas de redondeo/aproximación (criterios prácticos acordes a 810) ----
def round_kcal(v): # Valores < 5 kcal pueden declararse 0 (criterio de no significativo) if v < 5: return 0 # Energía en entero return int(round(v))

def round_g(v): """ Regla práctica por magnitud: - <0.5 → 0.0 si aplica "no significativo" (se evalúa afuera por nutriente) - [0.5, 100) → 1 decimal (consistencia visual de esta app) - >=100 → entero """ av = abs(v) if av >= 100: return float(int(round(v, 0))) else: return float(round(v, 1))

def round_mg(v_mg): # Sodio < 5 mg → 0 mg (no significativo). En general mg a entero. if v_mg < 5: return 0 return int(round(v_mg))

--------- Formatos solicitados por nutriente (solo impresión, no cambia cálculos) ---------
def fmt_one_decimal(v): try: return f"{float(v):.1f}" except: return "0.0"

def fmt_carbs_rule(v): """ Carbohidratos totales: sin decimales si tiene 2 cifras (10-99), si solo tiene una cifra (<10) lleva un decimal. >=100 sin decimales. """ try: v = float(v) except: return "0" av = abs(v) if av < 10: return f"{v:.1f}".rstrip('0').rstrip('.') if v % 1 != 0 else f"{v:.1f}" if av < 100: return f"{int(round(v))}" return f"{int(round(v))}"

def fmt_int(v): try: return f"{int(round(float(v)))}" except: return "0"

def fmt_default_g(x): """Imprime g sin ceros de cola: 3.0 -> 3 ; 3.5 -> 3.5""" try: x = float(x) except: return "0" if float(x).is_integer(): return f"{int(x)}" return f"{x:.1f}".rstrip('0').rstrip('.')

Micronutrientes (reglas de visualización)
def fmt_micro_value(name, unit, v): """ Reglas pedidas: - Vitamina A: si tiene menos de 2 cifras (<10) incluir un decimal. Unidad: µg ER. - Vitamina D: si <1 incluir 2 decimales; si una cifra (<10) 1 decimal; si 3 cifras (>=100) sin decimales. - Resto: si 3 cifras (>=100) sin decimales; si una cifra (<10) 1 decimal; en otros casos 0 o 1 decimal según magnitud. """ try: v = float(v) except: return f"0 {unit}" # Unidad especial para Vitamina A if name == "Vitamina A": unit = "µg ER" if abs(v) < 10: return f"{v:.1f} {unit}" if abs(v) >= 100: return f"{int(round(v))} {unit}" return f"{int(round(v))} {unit}" if name == "Vitamina D": if abs(v) < 1: return f"{v:.2f} {unit}" if abs(v) < 10: return f"{v:.1f} {unit}" if abs(v) >= 100: return f"{int(round(v))} {unit}" return f"{int(round(v))} {unit}" # Otros micronutrientes if abs(v) >= 100: return f"{int(round(v))} {unit}" if abs(v) < 10: return f"{v:.1f} {unit}" return f"{int(round(v))} {unit}"

============================================================
SIDEBAR (estructura como tu código)
============================================================
st.sidebar.header("Configuración")

format_choice = st.sidebar.selectbox( "Formato a exportar", ["Fig. 1 — Vertical estándar", "Fig. 3 — Simplificado", "Fig. 4 — Tabular", "Fig. 5 — Lineal"], index=0 )

physical_state = st.sidebar.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"]) portion_unit = "g" if "Sólido" in physical_state else "mL"

st.sidebar.subheader("Porción") household_name = st.sidebar.text_input("Medida casera (p. ej. 1 unidad, 1 taza)", value="1 unidad") household_mass = as_num(st.sidebar.text_input(f"Equivalencia en {portion_unit} (número)", value="40")) servings_per_pack = as_num(st.sidebar.text_input("Número de porciones por envase", value="2"))

Validación no impresa
st.sidebar.subheader("Validación interna (no se imprime)") contains_sweeteners = st.sidebar.checkbox("Contiene edulcorantes", value=False)

st.sidebar.subheader("Micronutrientes a declarar") vm_options = [ "Vitamina A", "Vitamina D", "Vitamina B1", "Vitamina B12", "Vitamina C", "Vitamina E", "Calcio", "Hierro", "Zinc", "Potasio" ] selected_vm = st.sidebar.multiselect( "Selecciona los que declararás", vm_options, default=["Vitamina A","Calcio","Hierro","Vitamina D","Zinc"] )

st.sidebar.subheader("Texto al pie") footnote_tail = st.sidebar.text_input( "Completa: No es fuente significativa de ...", value="" )

============================================================
ENTRADAS (CUERPO PRINCIPAL) — por 100 g/mL
============================================================
st.header("Ingreso de datos por 100 g / 100 mL")

c1, c2, c3 = st.columns([0.33, 0.33, 0.34]) with c1: st.subheader("Macronutrientes (por 100)") fat_total_100 = as_num(st.text_input("Grasa total (g/100)", value="13")) sat_fat_100 = as_num(st.text_input("Grasa saturada (g/100)", value="6")) trans_fat_100_mg = as_num(st.text_input("Grasas trans (mg/100)", value="820")) with c2: carb_100 = as_num(st.text_input("Carbohidratos totales (g/100)", value="31")) sug_total_100 = as_num(st.text_input("Azúcares totales (g/100)", value="5")) sug_added_100 = as_num(st.text_input("Azúcares añadidos (g/100)", value="2")) with c3: fiber_100 = as_num(st.text_input("Fibra dietaria (g/100)", value="0.8")) protein_100 = as_num(st.text_input("Proteína (g/100)", value="5")) sodium_100_mg = as_num(st.text_input("Sodio (mg/100)", value="560"))

st.markdown("---") st.subheader("Valores de micronutrientes seleccionados (por 100)") vm_values = {} vm_col1, vm_col2 = st.columns([0.5, 0.5]) with vm_col1: for i, vm in enumerate(selected_vm): if i % 2 == 0: unit = ("µg ER" if vm == "Vitamina A" else ("µg" if vm in ("Vitamina D","Vitamina B12") else "mg")) vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0")) with vm_col2: for i, vm in enumerate(selected_vm): if i % 2 == 1: unit = ("µg ER" if vm == "Vitamina A" else ("µg" if vm in ("Vitamina D","Vitamina B12") else "mg")) vm_values[(vm, unit)] = as_num(st.text_input(f"{vm} ({unit}/100)", value="0"))

============================================================
CÁLCULOS (porción, calorías, redondeos/no significativas)
============================================================
portion_size = household_mass is_liquid = "Líquido" in physical_state

Por porción (sin redondear)
fat_total_pp = portion_from_per100(fat_total_100, portion_size) sat_fat_pp = portion_from_per100(sat_fat_100, portion_size) trans_fat_pp_mg = portion_from_per100(trans_fat_100_mg, portion_size) # sigue en mg carb_pp = portion_from_per100(carb_100, portion_size) sug_total_pp = portion_from_per100(sug_total_100, portion_size) sug_added_pp = portion_from_per100(sug_added_100, portion_size) fiber_pp = portion_from_per100(fiber_100, portion_size) protein_pp = portion_from_per100(protein_100, portion_size) sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_size)

Energía (antes de redondear)
kcal_100_raw = kcal_from_macros(fat_total_100, carb_100, protein_100) kcal_pp_raw = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)

Aplicar “no significativas” por nutriente (criterios prácticos)
def nonsig_zero_g(name, v): # Cero solo para grasas clave; no anular carbohidratos/azúcares/fibra/proteína if name == "Grasa total" and v < 0.5: return 0.0 if name in ("Grasa saturada","Grasas trans") and v < 0.1: return 0.0 return v

def nonsig_zero_mg(name, vmg): if name == "Sodio" and vmg < 5: return 0 return vmg

Por 100 (redondeados)
fat_total_100_r = round_g(nonsig_zero_g("Grasa total", fat_total_100)) sat_fat_100_r = round_g(nonsig_zero_g("Grasa saturada", sat_fat_100)) carb_100_r = round_g(nonsig_zero_g("Carbohidratos totales", carb_100)) sug_total_100_r = round_g(nonsig_zero_g("Azúcares totales", sug_total_100)) sug_added_100_r = round_g(nonsig_zero_g("Azúcares añadidos", sug_added_100)) fiber_100_r = round_g(nonsig_zero_g("Fibra dietaria", fiber_100)) protein_100_r = round_g(nonsig_zero_g("Proteína", protein_100)) sodium_100_mg_r = round_mg(nonsig_zero_mg("Sodio", sodium_100_mg))

trans por 100: entra en mg, convertimos a g para evaluar no significativo y regresamos a mg
_trans_g_100 = (trans_fat_100_mg or 0.0)/1000.0 _trans_g_100 = nonsig_zero_g("Grasas trans", _trans_g_100) trans_fat_100_mg_r = round_mg(_trans_g_100*1000.0)

Por porción (redondeados)
fat_total_pp_r = round_g(nonsig_zero_g("Grasa total", fat_total_pp)) sat_fat_pp_r = round_g(nonsig_zero_g("Grasa saturada", sat_fat_pp)) carb_pp_r = round_g(nonsig_zero_g("Carbohidratos totales", carb_pp)) sug_total_pp_r = round_g(nonsig_zero_g("Azúcares totales", sug_total_pp)) sug_added_pp_r = round_g(nonsig_zero_g("Azúcares añadidos", sug_added_pp)) fiber_pp_r = round_g(nonsig_zero_g("Fibra dietaria", fiber_pp)) protein_pp_r = round_g(nonsig_zero_g("Proteína", protein_pp)) sodium_pp_mg_r = round_mg(nonsig_zero_mg("Sodio", sodium_pp_mg))

trans por porción (mg)
_trans_g_pp = (trans_fat_pp_mg or 0.0)/1000.0 _trans_g_pp = nonsig_zero_g("Grasas trans", _trans_g_pp) trans_fat_pp_mg_r = round_mg(_trans_g_pp*1000.0)

Calorías finales redondeadas
kcal_100 = round_kcal(kcal_100_raw) kcal_pp = round_kcal(kcal_pp_raw)

Micronutrientes por porción (mg/µg -> guardamos valores, el formato aplica al imprimir)
vm_pp = {} vm_values_rounded = {} for (name, unit), v100 in vm_values.items(): vpp = portion_from_per100(v100, portion_size) vm_values_rounded[(name, unit)] = v100 # mantener valor crudo, formateo abajo vm_pp[(name, unit)] = vpp

============================================================
VALIDACIÓN DE SELLOS (no impresa)
============================================================
def pct_kcal_from(nutrient_kcal, total_kcal_pp): if total_kcal_pp <= 0: return 0.0 return 100.0 * nutrient_kcal / total_kcal_pp

sat_pct = pct_kcal_from(9 * max(sat_fat_pp, 0), max(kcal_pp_raw, 1e-9)) trans_pct = pct_kcal_from(9 * max((trans_fat_pp_mg or 0)/1000.0, 0), max(kcal_pp_raw, 1e-9)) sugadd_pct = pct_kcal_from(4 * max(sug_added_pp, 0), max(kcal_pp_raw, 1e-9))

if is_liquid: sodium_rule = (sodium_100_mg >= 40.0) or ((sodium_pp_mg / max(kcal_pp_raw,1e-9)) >= 1.0) else: sodium_rule = (sodium_100_mg >= 300.0) or ((sodium_pp_mg / max(kcal_pp_raw,1e-9)) >= 1.0)

fop_sugar = sugadd_pct >= 10.0 fop_sat = sat_pct >= 10.0 fop_trans = trans_pct >= 1.0 fop_s
