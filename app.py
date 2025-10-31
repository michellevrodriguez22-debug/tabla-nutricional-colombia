# ===========================
# Generación de IMAGEN (PNG)
# ===========================
from PIL import Image, ImageDraw, ImageFont
import textwrap

# -------- utilidades de texto / fuentes ----------
def _load_font(size=18, bold=False):
    """
    Intenta DejaVuSans/DejaVuSans-Bold (disponibles en la mayoría de despliegues).
    Si no existen, cae a la fuente por defecto de PIL.
    """
    try:
        if bold:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except:
        f = ImageFont.load_default()
        return f

def _text_size(draw, text, font):
    w, h = draw.textbbox((0,0), text, font=font)[2:]
    return w, h

def _draw_text(draw, xy, text, font, fill=(0,0,0)):
    draw.text(xy, text, font=font, fill=fill)

def _draw_centered(draw, x_center, y, text, font):
    w, h = _text_size(draw, text, font)
    draw.text((x_center - w//2, y), text, font=font, fill=(0,0,0))
    return h

def _hr(draw, x0, x1, y, width=2):
    draw.line([(x0, y), (x1, y)], fill=(0,0,0), width=width)

# -------- formatos numéricos ----------
def _fmt_g(x, nd=1):
    try:
        return f"{float(x):.{nd}f}".rstrip("0").rstrip(".")
    except:
        return "0"
def _fmt_mg(x):
    try:
        return f"{int(round(float(x)))}"
    except:
        return "0"

# Nota: trans para mostrar en mg; para cálculos ya usaste g
trans_100_mg = trans_fat_100 * 1000.0
trans_pp_mg  = trans_fat_pp  * 1000.0

# -------- construcción de filas por formato (según 810) ----------
BOLD_KEYS = {"Calorías", "Grasa saturada", "Grasas trans", "Azúcares añadidos", "Sodio"}

def filas_fig1():
    """
    FIGURA 1 - Formato vertical estándar (sin título de formato).
    Bloque principal con calorías + nutrientes y un bloque separado para Sodio.
    Incluye opcionalmente micronutrientes debajo.
    """
    bloque1 = [
        ("Calorías",        (f"{int(round(kcal_100))}", f"{int(round(kcal_pp))}"), ("", "")),
        ("Grasa total",     (_fmt_g(fat_total_100), _fmt_g(fat_total_pp)), ("g","g")),
        # poliinsaturada es opcional en norma; se muestra si el usuario la ingresara (no la tenemos como campo separado)
        ("Grasa saturada",  (_fmt_g(sat_fat_100), _fmt_g(sat_fat_pp)), ("g","g")),
        ("Grasas trans",    (_fmt_mg(trans_100_mg), _fmt_mg(trans_pp_mg)), ("mg","mg")),
        ("Carbohidratos totales", (_fmt_g(carb_100), _fmt_g(carb_pp)), ("g","g")),
        ("Fibra dietaria",  (_fmt_g(fiber_100), _fmt_g(fiber_pp)), ("g","g")),
        ("Azúcares totales",(_fmt_g(sugars_total_100), _fmt_g(sugars_total_pp)), ("g","g")),
        ("Azúcares añadidos",(_fmt_g(sugars_added_100), _fmt_g(sugars_added_pp)), ("g","g")),
        ("Proteína",        (_fmt_g(protein_100), _fmt_g(protein_pp)), ("g","g")),
    ]
    bloque_sodio = [
        ("Sodio", (_fmt_mg(sodium_100_mg), _fmt_mg(sodium_pp_mg)), ("mg","mg"))
    ]
    # micronutrientes (en la misma caja, debajo)
    micron = []
    for vm in selected_vm:
        name = vm.split(" (")[0]
        unit = "mg"
        if "µg" in vm:
            unit = "µg"
        # ajustar nombre para A
        if name == "Vitamina A":
            unit = "µg ER"
        micron.append((name, (_fmt_g(vm_100.get(vm,0.0), 1) if unit!="mg" else _fmt_mg(vm_100.get(vm,0.0))),
                              (_fmt_g(vm_pp.get(vm,0.0), 1)  if unit!="mg" else _fmt_mg(vm_pp.get(vm,0.0)) ),
                              unit))
    return bloque1, bloque_sodio, micron

def filas_fig3():
    """
    FIGURA 3 - Formato simplificado.
    Conjunto mínimo ilustrado por la norma.
    """
    return [
        ("Calorías",        (f"{int(round(kcal_100))}", f"{int(round(kcal_pp))}"), ("", "")),
        ("Grasa total",     (_fmt_g(fat_total_100), _fmt_g(fat_total_pp)), ("g","g")),
        ("Grasa saturada",  (_fmt_g(sat_fat_100), _fmt_g(sat_fat_pp)), ("g","g")),
        ("Grasas trans",    (_fmt_mg(trans_100_mg), _fmt_mg(trans_pp_mg)), ("mg","mg")),
        ("Carbohidratos totales", (_fmt_g(carb_100), _fmt_g(carb_pp)), ("g","g")),
        ("Azúcares totales",(_fmt_g(sugars_total_100), _fmt_g(sugars_total_pp)), ("g","g")),
        ("Azúcares añadidos",(_fmt_g(sugars_added_100), _fmt_g(sugars_added_pp)), ("g","g")),
        ("Sodio",           (_fmt_mg(sodium_100_mg), _fmt_mg(sodium_pp_mg)), ("mg","mg")),
    ]

def filas_fig4():
    """
    FIGURA 4 - Formato tabular (cabeceras 'Calorías', 'Por 100 g/mL', 'Por porción').
    """
    return [
        ("Calorías",        (f"{int(round(kcal_100))} kcal", f"{int(round(kcal_pp))} kcal")),
        ("Grasa total",     (_fmt_g(fat_total_100)+" g", _fmt_g(fat_total_pp)+" g")),
        ("Grasa saturada",  (_fmt_g(sat_fat_100)+" g", _fmt_g(sat_fat_pp)+" g")),
        ("Grasa Trans",     (_fmt_mg(trans_100_mg)+" mg", _fmt_mg(trans_pp_mg)+" mg")),
        ("Sodio",           (_fmt_mg(sodium_100_mg)+" mg", _fmt_mg(sodium_pp_mg)+" mg")),
        ("Carbohidratos totales", (_fmt_g(carb_100)+" g", _fmt_g(carb_pp)+" g")),
        ("Fibra dietaria",  (_fmt_g(fiber_100)+" g", _fmt_g(fiber_pp)+" g")),
        ("Azúcares totales",(_fmt_g(sugars_total_100)+" g", _fmt_g(sugars_total_pp)+" g")),
        ("Azúcares añadidos",(_fmt_g(sugars_added_100)+" g", _fmt_g(sugars_added_pp)+" g")),
        ("Proteína",        (_fmt_g(protein_100)+" g", _fmt_g(protein_pp)+" g")),
    ]

def parrafos_fig5():
    """
    FIGURA 5 - Formato lineal (dos párrafos: 100g/mL y porción).
    Negrilla en los mismos nutrientes clave.
    """
    # Construimos cadenas con marcas **...** para simular bold luego.
    parte1 = (
        f"Información nutricional (100 g o 100 mL): "
        f"**Calorías {int(round(kcal_100))}**, "
        f"Grasa total { _fmt_g(fat_total_100) } g, "
        f"**Sodio { _fmt_mg(sodium_100_mg) } mg**, "
        f"Carbohidratos totales { _fmt_g(carb_100) } g, "
        f"**Azúcares añadidos { _fmt_g(sugars_added_100) } g**, "
        f"Proteína { _fmt_g(protein_100) } g"
    )

    # Vitaminas (opcionales) al final del párrafo
    vm_snippets = []
    for vm in selected_vm:
        name = vm.split(" (")[0]
        unit = "mg" if "mg" in vm else "µg"
        if name == "Vitamina A":
            unit = "µg ER"
        val100 = vm_100.get(vm, 0.0)
        vm_snippets.append(f"{name} { _fmt_g(val100,1) if unit!='mg' else _fmt_mg(val100) } {unit}")
    if vm_snippets:
        parte1 += ", " + ", ".join(vm_snippets)

    parte2 = (
        f"Información nutricional (porción): Tamaño de porción: {int(round(portion_size))} {portion_unit} "
        f"Número de porciones por envase: {fmt(servings_per_pack,0)} "
        f"**Calorías {int(round(kcal_pp))}**, "
        f"Grasa total { _fmt_g(fat_total_pp) } g, "
        f"**Sodio { _fmt_mg(sodium_pp_mg) } mg**, "
        f"Carbohidratos totales { _fmt_g(carb_pp) } g, "
        f"**Azúcares añadidos { _fmt_g(sugars_added_pp) } g**, "
        f"Proteína { _fmt_g(protein_pp) } g"
    )

    # Vitaminas por porción
    vm_snippets2 = []
    for vm in selected_vm:
        name = vm.split(" (")[0]
        unit = "mg" if "mg" in vm else "µg"
        if name == "Vitamina A":
            unit = "µg ER"
        valpp = vm_pp.get(vm, 0.0)
        vm_snippets2.append(f"{name} { _fmt_g(valpp,1) if unit!='mg' else _fmt_mg(valpp) } {unit}")
    if vm_snippets2:
        parte2 += ", " + ", ".join(vm_snippets2)

    return parte1, parte2

# --------- renderizadores de imagen ----------
def generar_png_fig1(fig_w=1600, fig_h=1200):
    img = Image.new("RGB", (fig_w, fig_h), "white")
    d = ImageDraw.Draw(img)

    font_h  = _load_font(36, bold=True)
    font_b  = _load_font(30, bold=True)
    font    = _load_font(30, bold=False)
    font_s  = _load_font(26, bold=False)

    pad = 40
    x0, x1 = pad, fig_w - pad
    y = pad

    # Encabezado: "Información Nutricional" (solo texto, no título de formato)
    _hr(d, x0, x1, y, 3); y += 8
    y += _draw_centered(d, fig_w//2, y, "Información Nutricional", font_h) + 6
    _hr(d, x0, x1, y, 3); y += 16

    # Tamaño de porción y porciones
    d.text((x0+8, y), f"Tamaño de porción: {int(round(portion_size))} {portion_unit}", font=font_s, fill=(0,0,0))
    d.text((x0+8, y+34), f"Número de porciones por envase: {fmt(servings_per_pack,0)}", font=font_s, fill=(0,0,0))
    y += 34*2 + 10

    # Tabla 3 columnas: nombre | por 100 | por porción
    col1_w = int(0.46*(x1-x0))
    col2_w = int(0.27*(x1-x0))
    col3_w = (x1-x0) - col1_w - col2_w
    c1, c2, c3 = x0, x0+col1_w, x0+col1_w+col2_w

    # fila Calorías barra gruesa
    _hr(d, x0, x1, y, 4); y += 6
    _draw_text(d, (c1+10, y), "Calorías (kcal)", font_b, (0,0,0))
    _draw_centered(d, c2 + col2_w//2, y, f"{int(round(kcal_100))}", font_b)
    _draw_centered(d, c3 + col3_w//2, y, f"{int(round(kcal_pp))}", font_b)
    y += 48
    _hr(d, x0, x1, y, 3); y += 6

    # cabecera columnas
    _draw_centered(d, c2 + col2_w//2, y, "Por 100 g" if not is_liquid else "Por 100 mL", font_b)
    _draw_centered(d, c3 + col3_w//2, y, "Por porción", font_b)
    y += 40
    _hr(d, x0, x1, y, 2); y += 6

    bloque1, bloque_sodio, micron = filas_fig1()

    # filas bloque1
    for nombre, vals, units in bloque1:
        is_bold = nombre in BOLD_KEYS
        f = font_b if is_bold else font
        d.text((c1+10, y), nombre, font=f, fill=(0,0,0))
        v100, vpp = vals
        u100, upp = units
        _draw_centered(d, c2 + col2_w//2, y, f"{v100} {u100}".strip(), f)
        _draw_centered(d, c3 + col3_w//2, y, f"{vpp} {upp}".strip(), f)
        y += 42
        _hr(d, x0, x1, y, 2); y += 6

    # bloque Sodio separado con barra gruesa arriba y abajo
    y += 6
    _hr(d, x0, x1, y, 4); y += 10
    for nombre, vals, units in bloque_sodio:
        f = font_b
        d.text((c1+10, y), nombre, font=f, fill=(0,0,0))
        v100, vpp = vals
        u100, upp = units
        _draw_centered(d, c2 + col2_w//2, y, f"{v100} {u100}", f)
        _draw_centered(d, c3 + col3_w//2, y, f"{vpp} {upp}", f)
        y += 44
    _hr(d, x0, x1, y, 4); y += 12

    # micronutrientes (si hay)
    for name, v100, vpp, unit in micron:
        d.text((c1+10, y), name, font=font, fill=(0,0,0))
        _draw_centered(d, c2 + col2_w//2, y, f"{v100} {unit}", font)
        _draw_centered(d, c3 + col3_w//2, y, f"{vpp} {unit}", font)
        y += 36
        _hr(d, x0, x1, y, 1); y += 4

    # pie "No es fuente significativa de..." si lo configuraste
    if footnote_ns.strip():
        y += 10
        _hr(d, x0, x1, y, 2); y += 8
        d.text((x0+8, y), footnote_ns.strip(), font=font_s, fill=(0,0,0))

    return img

def generar_png_fig3(fig_w=1600, fig_h=1000):
    img = Image.new("RGB", (fig_w, fig_h), "white")
    d = ImageDraw.Draw(img)

    font_h = _load_font(36, bold=True)
    font_b = _load_font(30, bold=True)
    font   = _load_font(30, bold=False)
    font_s = _load_font(26, bold=False)

    pad = 40
    x0, x1 = pad, fig_w - pad
    y = pad

    _hr(d, x0, x1, y, 3); y += 8
    y += _draw_centered(d, fig_w//2, y, "Información Nutricional", font_h) + 6
    _hr(d, x0, x1, y, 3); y += 16

    d.text((x0+8, y), f"Tamaño de porción: 1 unidad ({int(round(portion_size))}{portion_unit})", font=font_s, fill=(0,0,0))
    d.text((x0+8, y+34), f"Número de porciones por envase: {fmt(servings_per_pack,0)}", font=font_s, fill=(0,0,0))
    y += 34*2 + 10

    col1_w = int(0.46*(x1-x0)); col2_w = int(0.27*(x1-x0)); col3_w = (x1-x0)-col1_w-col2_w
    c1, c2, c3 = x0, x0+col1_w, x0+col1_w+col2_w

    _hr(d, x0, x1, y, 4); y += 6
    _draw_text(d, (c1+10, y), "Calorías (kcal)", font_b, (0,0,0))
    _draw_centered(d, c2 + col2_w//2, y, f"{int(round(kcal_100))}", font_b)
    _draw_centered(d, c3 + col3_w//2, y, f"{int(round(kcal_pp))}", font_b)
    y += 48
    _hr(d, x0, x1, y, 3); y += 6

    _draw_centered(d, c2 + col2_w//2, y, "Por 100 g" if not is_liquid else "Por 100 mL", font_b)
    _draw_centered(d, c3 + col3_w//2, y, "Por porción", font_b)
    y += 40
    _hr(d, x0, x1, y, 2); y += 6

    for nombre, vals, units in filas_fig3():
        is_bold = nombre in BOLD_KEYS
        f = font_b if is_bold else font
        d.text((c1+10, y), nombre, font=f, fill=(0,0,0))
        v100, vpp = vals
        u100, upp = units
        _draw_centered(d, c2 + col2_w//2, y, f"{v100} {u100}".strip(), f)
        _draw_centered(d, c3 + col3_w//2, y, f"{vpp} {upp}".strip(), f)
        y += 42
        _hr(d, x0, x1, y, 2); y += 6

    if footnote_ns.strip():
        y += 6
        d.text((x0+8, y), footnote_ns.strip(), font=font_s, fill=(0,0,0))

    return img

def generar_png_fig4(fig_w=1800, fig_h=1000):
    img = Image.new("RGB", (fig_w, fig_h), "white")
    d = ImageDraw.Draw(img)

    font_h = _load_font(36, bold=True)
    font_b = _load_font(30, bold=True)
    font   = _load_font(30, bold=False)
    font_s = _load_font(26, bold=False)

    pad = 40
    x0, x1 = pad, fig_w - pad
    y = pad

    # Cabecera “Información Nutricional” en primera columna
    table_w = x1 - x0
    colA = int(0.35*table_w)
    colB = int(0.32*table_w)
    colC = table_w - colA - colB
    c1, c2, c3 = x0, x0+colA, x0+colA+colB

    # Fila de título de tabla
    _hr(d, x0, x1, y, 3); y += 8
    _draw_text(d, (c1+10, y), "Información Nutricional", font_h, (0,0,0))
    _draw_centered(d, c2 + colB//2, y, "Por 100 g" if not is_liquid else "Por 100 mL", font_b)
    _draw_centered(d, c3 + colC//2, y, "Por porción", font_b)
    y += 46
    _hr(d, x0, x1, y, 3); y += 10

    # Filas
    for nombre, (v100_txt, vpp_txt) in filas_fig4():
        is_bold = nombre.replace("Grasa Trans", "Grasas trans").replace("Calorías","Calorías") in BOLD_KEYS
        f = font_b if is_bold else font
        d.text((c1+10, y), nombre, font=f, fill=(0,0,0))
        _draw_centered(d, c2 + colB//2, y, v100_txt, f)
        _draw_centered(d, c3 + colC//2, y, vpp_txt, f)
        y += 42
        _hr(d, x0, x1, y, 2); y += 6

    if footnote_ns.strip():
        y += 6
        d.text((x0+8, y), footnote_ns.strip(), font=font_s, fill=(0,0,0))

    return img

def _draw_paragraph_with_bold(draw, x, y, text, font, font_b, max_width, line_height=36):
    """
    Renderiza un párrafo respetando **negrilla** y wrapping.
    """
    # Rompemos por espacios y rearmamos líneas
    words = text.split(" ")
    line = ""
    cur_y = y
    def render_line(line_str, cur_y):
        # Render de línea con bold tokens
        cx = x
        tokens = line_str.split("**")
        bold = False
        for t in tokens:
            if t == "":
                bold = not bold
                continue
            f = font_b if bold else font
            draw.text((cx, cur_y), t, font=f, fill=(0,0,0))
            w, _ = _text_size(draw, t, f)
            cx += w
            bold = not bold  # alterna tras token vacío; pero si no hay más **, volverá a normal con el próximo split
        return cur_y + line_height

    for w in words:
        probe = (line + " " + w).strip()
        tw, _ = _text_size(draw, probe.replace("**",""), font)  # ancho aproximado
        if tw > max_width and line:
            cur_y = render_line(line, cur_y)
            line = w
        else:
            line = probe
    if line:
        cur_y = render_line(line, cur_y)
    return cur_y

def generar_png_fig5(fig_w=1800, fig_h=520):
    img = Image.new("RGB", (fig_w, fig_h), "white")
    d = ImageDraw.Draw(img)

    font   = _load_font(28, bold=False)
    font_b = _load_font(28, bold=True)

    pad = 28
    x0, x1 = pad, fig_w - pad
    y = pad

    p1, p2 = parrafos_fig5()

    y = _draw_paragraph_with_bold(d, x0, y, p1, font, font_b, max_width=(x1-x0))
    y += 10
    y = _draw_paragraph_with_bold(d, x0, y, p2, font, font_b, max_width=(x1-x0))
    y += 10

    if footnote_ns.strip():
        d.text((x0, y), footnote_ns.strip(), font=font, fill=(0,0,0))

    # Marco fino alrededor (opcional)
    d.rectangle([(4,4), (fig_w-4, fig_h-4)], outline=(0,0,0), width=2)
    return img

# -------- selector de formato en la barra lateral --------
st.sidebar.header("Formato de etiqueta (PNG)")
format_choice = st.sidebar.selectbox(
    "Elige el formato (Res. 810)",
    ["Figura 1 - Vertical estándar", "Figura 3 - Simplificado", "Figura 4 - Tabular", "Figura 5 - Lineal"],
    index=1  # por defecto el simplificado
)

# --------- Exportar PNG ---------
st.header("Exportar como imagen (PNG)")
col_img_btn, _ = st.columns([0.5, 0.5])
with col_img_btn:
    if st.button("Generar PNG de la etiqueta"):
        if "Vertical" in format_choice:
            out_img = generar_png_fig1()
            suffix = "fig1_vertical"
        elif "Tabular" in format_choice:
            out_img = generar_png_fig4()
            suffix = "fig4_tabular"
        elif "Lineal" in format_choice:
            out_img = generar_png_fig5()
            suffix = "fig5_lineal"
        else:
            out_img = generar_png_fig3()
            suffix = "fig3_simplificado"

        buf = BytesIO()
        out_img.save(buf, format="PNG")
        buf.seek(0)
        fname = f"informacion_nutricional_{suffix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        st.download_button("Descargar PNG", data=buf.getvalue(), file_name=fname, mime="image/png")
