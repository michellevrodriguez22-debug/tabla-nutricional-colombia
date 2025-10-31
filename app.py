# app.py
# -*- coding: utf-8 -*-
"""
Generador de Tabla de Información Nutricional (COL)
Fig. 1 (Vertical estándar), Fig. 3 (Simplificada), Fig. 4 (Tabular), Fig. 5 (Lineal)
Exporta PNG con fondo blanco, listo para empaque.
"""

import math
import os
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd

# --- PIL para render a PNG ---
from PIL import Image, ImageDraw, ImageFont

# =========================
# Configuración general
# =========================
st.set_page_config(page_title="Generador Tabla Nutricional (COL) — PNG", layout="wide")

# =========================
# Utilidades numéricas
# =========================
def as_num(x):
    try:
        if x is None or str(x).strip() == "":
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

# =========================
# Tipografías (PIL)
# =========================
def load_font(size, bold=False):
    """
    Intenta DejaVu Sans (soporta µ). Si no, usa la fuente por defecto de PIL.
    """
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",  # macOS fallback
    ]
    # Si bold, probamos primero la bold
    if bold:
        bold_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
        for p in bold_candidates:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size=size)
                except:
                    pass
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size=size)
            except:
                continue
    # Último recurso
    return ImageFont.load_default()

def safe_micro(s: str) -> str:
    """
    Asegura que el micro 'µ' se muestre: si no, usamos 'μ'.
    (Muchos fonts soportan ambos, pero por si acaso.)
    """
    return s.replace("µ", "µ")  # deja el micro original; si vieras problema, puedes: .replace("µ", "μ")

# =========================
# Dibujo de tablas a PNG
# =========================
class Canvas:
    def __init__(self, width=1500, height=1000, bg="white"):
        self.im = Image.new("RGB", (width, height), bg)
        self.draw = ImageDraw.Draw(self.im)
        self.width = width
        self.height = height

    def text(self, xy, text, font, fill=(0,0,0), anchor=None):
        self.draw.text(xy, text, font=font, fill=fill, anchor=anchor)

    def line(self, xy1, xy2, width=2, fill=(0,0,0)):
        self.draw.line([xy1, xy2], fill=fill, width=width)

    def rect(self, xy, outline=(0,0,0), width=2):
        x0,y0,x1,y1 = xy
        # Dibuja 4 lados para controlar grosor
        self.line((x0,y0),(x1,y0), width=width, fill=outline)  # top
        self.line((x0,y1),(x1,y1), width=width, fill=outline)  # bottom
        self.line((x0,y0),(x0,y1), width=width, fill=outline)  # left
        self.line((x1,y0),(x1,y1), width=width, fill=outline)  # right

    def textsize(self, text, font):
        return self.draw.textbbox((0,0), text, font=font)

    def crop_to_content(self, margin=40):
        # Busca el bbox del contenido negro para recortar (simple: dejamos tamaño fijo controlado)
        # En esta app, preferimos dimensiones calculadas con “layout_width” al construir la tabla,
        # así que normalmente no recortamos automáticamente.
        return

    def to_bytes(self):
        buf = BytesIO()
        self.im.save(buf, format="PNG")
        buf.seek(0)
        return buf

# -------------------------
# Parámetros de estilo
# -------------------------
BLACK = (0,0,0)
THIN = 2
THICK = 6  # grosor triplicado respecto a líneas "normales"
BG = "white"

# Tipos de letra
FONT_TITLE = load_font(36, bold=True)       # "Información Nutricional"
FONT_LABEL = load_font(26, bold=False)      # etiquetas normales
FONT_LABEL_B = load_font(26, bold=True)     # etiquetas en negrilla
FONT_SMALL = load_font(22, bold=False)      # textos pequeños
FONT_SMALL_B = load_font(22, bold=True)
FONT_NUM = load_font(26, bold=False)
FONT_NUM_B = load_font(26, bold=True)

# =========================
# Layout helpers
# =========================
def draw_row(canvas, x0, y, w_name, w_100, w_pp, name, v100, vpp, unit_100, unit_pp,
             bold=False, indent=False, h=46, line_top=False, line_bottom=True,
             colline_left=True, colline_mid=True, colline_right=True,
             thick_top=False, thick_bottom=False):
    """
    Dibuja una fila (nombre + 2 columnas de números).
    Ajusta vertical lines para no atravesar el texto (las dibujamos por fuera).
    """
    font_label = FONT_LABEL_B if bold else FONT_LABEL
    font_num = FONT_NUM_B if bold else FONT_NUM
    pad_x = 12
    pad_y = 8

    name_txt = ("  " + name) if indent else name
    # Texto: nombre
    canvas.text((x0 + pad_x, y + pad_y), safe_micro(name_txt), font=font_label, fill=BLACK)
    # Texto: valores derecha
    v100_txt = f"{v100} {unit_100}".strip()
    vpp_txt  = f"{vpp} {unit_pp}".strip()
    # alineación derecha: estimamos x inicio por ancho del texto
    x_name_end = x0 + w_name
    # Col 100
    bbox100 = canvas.textsize(v100_txt, font=font_num)
    txt_w100 = bbox100[2] - bbox100[0]
    canvas.text((x_name_end + w_100 - pad_x - txt_w100, y + pad_y), safe_micro(v100_txt), font=font_num, fill=BLACK)
    # Col porción
    bboxpp = canvas.textsize(vpp_txt, font=font_num)
    txt_wpp = bboxpp[2] - bboxpp[0]
    canvas.text((x_name_end + w_100 + w_pp - pad_x - txt_wpp, y + pad_y), safe_micro(vpp_txt), font=font_num, fill=BLACK)

    # Líneas horizontales (bajo la fila)
    if line_top:
        canvas.line((x0, y), (x0 + w_name + w_100 + w_pp, y), width=THICK if thick_top else THIN, fill=BLACK)
    if line_bottom:
        yb = y + h
        canvas.line((x0, yb), (x0 + w_name + w_100 + w_pp, yb), width=THICK if thick_bottom else THIN, fill=BLACK)

    # Líneas verticales solo a los bordes de columnas (no sobre texto)
    if colline_left:
        canvas.line((x0, y), (x0, y + h), width=THIN, fill=BLACK)
    if colline_mid:
        canvas.line((x0 + w_name, y), (x0 + w_name, y + h), width=THIN, fill=BLACK)
    if colline_right:
        canvas.line((x0 + w_name + w_100, y), (x0 + w_name + w_100, y + h), width=THIN, fill=BLACK)
    # Borde derecho total se dibuja por fuera

    return y + h

def fmt_g(v, decimals=1):
    try:
        f = float(v)
        return f"{f:.{decimals}f}".rstrip("0").rstrip(".")
    except:
        return "0"

def fmt_mg(v):
    try:
        f = float(v)
        return f"{int(round(f,0))}"
    except:
        return "0"

def kcal_kj_line(kcal, kj, include_kj=True):
    if include_kj:
        return f"{int(round(kcal))} kcal ({int(round(kj))} kJ)"
    return f"{int(round(kcal))} kcal"

# =========================
# FIG. 1 / 3 / 4 / 5
# =========================
def render_fig1_vertical(canvas, payload):
    """
    Formato vertical estándar (Fig. 1)
    Encabezados "por 100 g" y "por porción" ARRIBA de Calorías.
    """
    # Medidas base
    margin = 60
    x0 = margin
    y0 = margin
    # Anchos de columnas
    w_name = 720
    w_100  = 360
    w_pp   = 360
    total_w = w_name + w_100 + w_pp
    # Marco exterior ajustado
    x1 = x0 + total_w
    # Alturas
    row_h = 56

    # Caja exterior
    canvas.rect((x0, y0, x1, y0 + 800), outline=BLACK, width=THICK)

    # Título
    y = y0
    title = "Información Nutricional"
    canvas.text((x0 + 12, y + 10), title, font=FONT_TITLE, fill=BLACK)
    canvas.line((x0, y + 60), (x1, y + 60), width=THICK, fill=BLACK)
    y += 60

    # Tamaño porción + porciones
    top_line = f"Tamaño de porción: {int(round(payload['portion_size']))} {payload['portion_unit']}    "
    top_line += f"Porciones por envase: {int(round(payload['servings_per_pack']))}"
    canvas.text((x0 + 12, y + 8), top_line, font=FONT_SMALL, fill=BLACK)
    canvas.line((x0, y + 46), (x1, y + 46), width=THICK, fill=BLACK)
    y += 46

    # Encabezados (ARRIBA de calorías)
    per100_label = "por 100 g" if not payload['is_liquid'] else "por 100 mL"
    perportion_label = f"por porción ({int(round(payload['portion_size']))} {payload['portion_unit']})"

    # Fila encabezados columnas
    # nombre col vacío (o etiqueta)
    canvas.text((x0 + 12, y + 10), per100_label, font=FONT_SMALL_B, fill=BLACK)
    # alinear a derecha en col 2:
    bbox = canvas.textsize(perportion_label, FONT_SMALL_B); wtxt = bbox[2]-bbox[0]
    canvas.text((x0 + w_name + w_100 + w_pp - 12 - wtxt, y + 10), perportion_label, font=FONT_SMALL_B, fill=BLACK)
    # línea bajo encabezados
    canvas.line((x0, y + row_h), (x1, y + row_h), width=THICK, fill=BLACK)
    y += row_h

    # Calorías (negrita, con línea gruesa arriba)
    kcal_100_txt = kcal_kj_line(payload["kcal_100"], payload["kj_100"], payload["include_kj"])
    kcal_pp_txt  = kcal_kj_line(payload["kcal_pp"], payload["kj_pp"], payload["include_kj"])
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Calorías", kcal_100_txt, kcal_pp_txt, "", "",
                 bold=True, indent=False, h=row_h,
                 line_top=True, thick_top=True, line_bottom=True, thick_bottom=False)

    # Grasa total, saturada, trans (trans en mg visual)
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Grasa total", fmt_g(payload["fat_total_100"]), fmt_g(payload["fat_total_pp"]), "g", "g",
                 bold=False, indent=False, h=row_h)
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Grasa saturada", fmt_g(payload["sat_fat_100"]), fmt_g(payload["sat_fat_pp"]), "g", "g",
                 bold=True, indent=True, h=row_h)
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Grasas trans", fmt_mg(payload["trans_100_mg"]), fmt_mg(payload["trans_pp_mg"]), "mg", "mg",
                 bold=True, indent=True, h=row_h)

    # Carbohidratos, azúcares totales, añadidos, fibra
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Carbohidratos", fmt_g(payload["carb_100"]), fmt_g(payload["carb_pp"]), "g", "g",
                 bold=False, indent=False, h=row_h)
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Azúcares totales", fmt_g(payload["sugars_total_100"]), fmt_g(payload["sugars_total_pp"]), "g", "g",
                 bold=False, indent=True, h=row_h)
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Azúcares añadidos", fmt_g(payload["sugars_added_100"]), fmt_g(payload["sugars_added_pp"]), "g", "g",
                 bold=True, indent=True, h=row_h)
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Fibra dietaria", fmt_g(payload["fiber_100"]), fmt_g(payload["fiber_pp"]), "g", "g",
                 bold=False, indent=True, h=row_h)

    # Proteína
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Proteína", fmt_g(payload["protein_100"]), fmt_g(payload["protein_pp"]), "g", "g",
                 bold=False, indent=False, h=row_h)

    # Sodio (mg)
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Sodio", fmt_mg(payload["sodium_100_mg"]), fmt_mg(payload["sodium_pp_mg"]), "mg", "mg",
                 bold=True, indent=False, h=row_h)

    # Línea gruesa antes de vitaminas/minerales (si hay)
    if payload["vm_rows"]:
        canvas.line((x0, y), (x1, y), width=THICK, fill=BLACK)
        for (name, v100, vpp, unit) in payload["vm_rows"]:
            y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                         name, v100, vpp, unit, unit, bold=False, indent=False, h=row_h)

    # Pie
    y += 6
    foot = f"No es fuente significativa de {payload['footnote_tail']}".strip()
    canvas.text((x0 + 12, y + 10), foot, font=FONT_SMALL, fill=BLACK)

    # Borde derecho y líneas verticales exteriores (para cerrar caja)
    # Ya dibujamos borde exterior al inicio con rect(); no es necesario repetir.

def render_fig3_simplificada(canvas, payload):
    """
    Formato simplificado (Fig. 3) — Estructura similar pero con filas reducidas.
    Se mantienen encabezados ARRIBA de Calorías y líneas gruesas triplicadas.
    """
    margin = 60
    x0 = margin
    y0 = margin
    w_name = 720
    w_100  = 360
    w_pp   = 360
    total_w = w_name + w_100 + w_pp
    x1 = x0 + total_w
    row_h = 56

    canvas.rect((x0, y0, x1, y0 + 620), outline=BLACK, width=THICK)

    y = y0
    title = "Información Nutricional"
    canvas.text((x0 + 12, y + 10), title, font=FONT_TITLE, fill=BLACK)
    canvas.line((x0, y + 60), (x1, y + 60), width=THICK, fill=BLACK)
    y += 60

    top_line = f"Tamaño de porción: {int(round(payload['portion_size']))} {payload['portion_unit']}    "
    top_line += f"Porciones por envase: {int(round(payload['servings_per_pack']))}"
    canvas.text((x0 + 12, y + 8), top_line, font=FONT_SMALL, fill=BLACK)
    canvas.line((x0, y + 46), (x1, y + 46), width=THICK, fill=BLACK)
    y += 46

    per100_label = "por 100 g" if not payload['is_liquid'] else "por 100 mL"
    perportion_label = f"por porción ({int(round(payload['portion_size']))} {payload['portion_unit']})"
    canvas.text((x0 + 12, y + 10), per100_label, font=FONT_SMALL_B, fill=BLACK)
    bbox = canvas.textsize(perportion_label, FONT_SMALL_B); wtxt = bbox[2]-bbox[0]
    canvas.text((x0 + w_name + w_100 + w_pp - 12 - wtxt, y + 10), perportion_label, font=FONT_SMALL_B, fill=BLACK)
    canvas.line((x0, y + row_h), (x1, y + row_h), width=THICK, fill=BLACK)
    y += row_h

    kcal_100_txt = kcal_kj_line(payload["kcal_100"], payload["kj_100"], payload["include_kj"])
    kcal_pp_txt  = kcal_kj_line(payload["kcal_pp"], payload["kj_pp"], payload["include_kj"])
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Calorías", kcal_100_txt, kcal_pp_txt, "", "",
                 bold=True, indent=False, h=row_h, line_top=True, thick_top=True)

    # Versión simplificada típica: Grasa total, Carbohidratos totales, Proteína, Sodio
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Grasa total", fmt_g(payload["fat_total_100"]), fmt_g(payload["fat_total_pp"]), "g", "g",
                 bold=False, indent=False, h=row_h)

    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Carbohidratos", fmt_g(payload["carb_100"]), fmt_g(payload["carb_pp"]), "g", "g",
                 bold=False, indent=False, h=row_h)

    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Proteína", fmt_g(payload["protein_100"]), fmt_g(payload["protein_pp"]), "g", "g",
                 bold=False, indent=False, h=row_h)

    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Sodio", fmt_mg(payload["sodium_100_mg"]), fmt_mg(payload["sodium_pp_mg"]), "mg", "mg",
                 bold=True, indent=False, h=row_h)

    # Pie
    y += 6
    foot = f"No es fuente significativa de {payload['footnote_tail']}".strip()
    canvas.text((x0 + 12, y + 10), foot, font=FONT_SMALL, fill=BLACK)

def render_fig4_tabular(canvas, payload):
    """
    Formato tabular (Fig. 4) — Tabla 'apretada' al texto, con negrillas normativas en:
    - Calorías
    - Grasa saturada
    - Grasas trans
    - Azúcares añadidos
    - Sodio
    Encabezados ARRIBA de Calorías; líneas gruesas triplicadas en marco, cabecera y separador antes de calorías.
    """
    margin = 60
    x0 = margin
    y0 = margin

    # Calcular anchos a partir de los textos (para ajustar al contenido)
    name_col_items = [
        "Información Nutricional",  # ancho de título no cuenta, pero sirve de referencia visual
        "Tamaño de porción:", "Porciones por envase:",
        "Calorías", "Grasa total", "Grasa saturada", "Grasas trans",
        "Carbohidratos", "Azúcares totales", "Azúcares añadidos", "Fibra dietaria",
        "Proteína", "Sodio",
    ] + [nm for (nm, _, _, _) in payload["vm_rows"]]

    # Texto de valores más largos para col 100 y porción:
    per100_label = "por 100 g" if not payload['is_liquid'] else "por 100 mL"
    perportion_label = f"por porción ({int(round(payload['portion_size']))} {payload['portion_unit']})"
    samples_100 = [
        kcal_kj_line(payload["kcal_100"], payload["kj_100"], payload["include_kj"]),
        f"{fmt_g(payload['fat_total_100'])} g",
        f"{fmt_g(payload['sat_fat_100'])} g",
        f"{fmt_mg(payload['trans_100_mg'])} mg",
        f"{fmt_g(payload['carb_100'])} g",
        f"{fmt_g(payload['sugars_total_100'])} g",
        f"{fmt_g(payload['sugars_added_100'])} g",
        f"{fmt_g(payload['fiber_100'])} g",
        f"{fmt_g(payload['protein_100'])} g",
        f"{fmt_mg(payload['sodium_100_mg'])} mg",
    ] + [f"{v100} {unit}" for (_, v100, _, unit) in payload["vm_rows"]]

    samples_pp = [
        kcal_kj_line(payload["kcal_pp"], payload["kj_pp"], payload["include_kj"]),
        f"{fmt_g(payload['fat_total_pp'])} g",
        f"{fmt_g(payload['sat_fat_pp'])} g",
        f"{fmt_mg(payload['trans_pp_mg'])} mg",
        f"{fmt_g(payload['carb_pp'])} g",
        f"{fmt_g(payload['sugars_total_pp'])} g",
        f"{fmt_g(payload['sugars_added_pp'])} g",
        f"{fmt_g(payload['fiber_pp'])} g",
        f"{fmt_g(payload['protein_pp'])} g",
        f"{fmt_mg(payload['sodium_pp_mg'])} mg",
    ] + [f"{vpp} {unit}" for (_, _, vpp, unit) in payload["vm_rows"]]

    # Estimación de anchos
    def text_w(s, font):
        bbox = canvas.textsize(safe_micro(s), font)
        return bbox[2]-bbox[0]

    w_name = max([text_w(n, FONT_LABEL) for n in name_col_items] + [420]) + 40
    w_100  = max([text_w(t, FONT_NUM) for t in ([per100_label]+samples_100)]) + 40
    w_pp   = max([text_w(t, FONT_NUM) for t in ([perportion_label]+samples_pp)]) + 40

    total_w = w_name + w_100 + w_pp
    x1 = x0 + total_w
    # Alturas
    row_h = 56

    # Marco exterior ajustado
    canvas.rect((x0, y0, x1, y0 + 820), outline=BLACK, width=THICK)

    y = y0
    # Título
    canvas.text((x0 + 12, y + 10), "Información Nutricional", font=FONT_TITLE, fill=BLACK)
    canvas.line((x0, y + 60), (x1, y + 60), width=THICK, fill=BLACK)
    y += 60

    # Porción + porciones
    top_line = f"Tamaño de porción: {int(round(payload['portion_size']))} {payload['portion_unit']}    "
    top_line += f"Porciones por envase: {int(round(payload['servings_per_pack']))}"
    canvas.text((x0 + 12, y + 8), top_line, font=FONT_SMALL, fill=BLACK)
    canvas.line((x0, y + 46), (x1, y + 46), width=THICK, fill=BLACK)
    y += 46

    # Encabezados ARRIBA de calorías
    canvas.text((x0 + 12, y + 10), per100_label, font=FONT_SMALL_B, fill=BLACK)
    bbox = canvas.textsize(perportion_label, FONT_SMALL_B); wtxt = bbox[2]-bbox[0]
    canvas.text((x0 + w_name + w_100 + w_pp - 12 - wtxt, y + 10), perportion_label, font=FONT_SMALL_B, fill=BLACK)
    canvas.line((x0, y + row_h), (x1, y + row_h), width=THICK, fill=BLACK)
    y += row_h

    # Calorías
    kcal_100_txt = kcal_kj_line(payload["kcal_100"], payload["kj_100"], payload["include_kj"])
    kcal_pp_txt  = kcal_kj_line(payload["kcal_pp"], payload["kj_pp"], payload["include_kj"])
    y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                 "Calorías", kcal_100_txt, kcal_pp_txt, "", "",
                 bold=True, indent=False, h=row_h, line_top=True, thick_top=True)

    # Filas con normativas en negrilla (saturada, trans, añadidos, sodio)
    lines = [
        ("Grasa total", fmt_g(payload["fat_total_100"]), fmt_g(payload["fat_total_pp"]), "g", "g", False, False),
        ("Grasa saturada", fmt_g(payload["sat_fat_100"]), fmt_g(payload["sat_fat_pp"]), "g", "g", True, True),
        ("Grasas trans", fmt_mg(payload["trans_100_mg"]), fmt_mg(payload["trans_pp_mg"]), "mg", "mg", True, True),
        ("Carbohidratos", fmt_g(payload["carb_100"]), fmt_g(payload["carb_pp"]), "g", "g", False, False),
        ("Azúcares totales", fmt_g(payload["sugars_total_100"]), fmt_g(payload["sugars_total_pp"]), "g", "g", False, True),
        ("Azúcares añadidos", fmt_g(payload["sugars_added_100"]), fmt_g(payload["sugars_added_pp"]), "g", "g", True, True),
        ("Fibra dietaria", fmt_g(payload["fiber_100"]), fmt_g(payload["fiber_pp"]), "g", "g", False, True),
        ("Proteína", fmt_g(payload["protein_100"]), fmt_g(payload["protein_pp"]), "g", "g", False, False),
        ("Sodio", fmt_mg(payload["sodium_100_mg"]), fmt_mg(payload["sodium_pp_mg"]), "mg", "mg", True, False),
    ]
    for (nm, v100, vpp, u100, upp, bold, indent) in lines:
        y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                     nm, v100, vpp, u100, upp,
                     bold=bold, indent=indent, h=row_h)

    if payload["vm_rows"]:
        canvas.line((x0, y), (x1, y), width=THICK, fill=BLACK)
        for (name, v100, vpp, unit) in payload["vm_rows"]:
            y = draw_row(canvas, x0, y, w_name, w_100, w_pp,
                         name, v100, vpp, unit, unit,
                         bold=False, indent=False, h=row_h)

    y += 6
    foot = f"No es fuente significativa de {payload['footnote_tail']}".strip()
    canvas.text((x0 + 12, y + 10), foot, font=FONT_SMALL, fill=BLACK)

def render_fig5_lineal(canvas, payload):
    """
    Formato lineal (Fig. 5). Presentación en una sola línea con separadores.
    Mantiene grosor triplicado en marcos/separadores principales.
    """
    margin = 60
    x0 = margin
    y0 = margin
    # ancho total fijo grande
    total_w = 1500 - 2*margin
    x1 = x0 + total_w

    canvas.rect((x0, y0, x1, y0 + 240), outline=BLACK, width=THICK)

    y = y0
    title = "Información Nutricional"
    canvas.text((x0 + 12, y + 10), title, font=FONT_TITLE, fill=BLACK)
    canvas.line((x0, y + 60), (x1, y + 60), width=THICK, fill=BLACK)
    y += 60

    # Encabezados ARRIBA (para mantener consistencia con pedido)
    per100_label = "por 100 g" if not payload['is_liquid'] else "por 100 mL"
    perportion_label = f"por porción ({int(round(payload['portion_size']))} {payload['portion_unit']})"
    canvas.text((x0 + 12, y + 6), per100_label + " / " + perportion_label, font=FONT_SMALL_B, fill=BLACK)
    canvas.line((x0, y + 36), (x1, y + 36), width=THICK, fill=BLACK)
    y += 40

    # Línea de nutrientes (formato: Nombre: 100 | porción  ·  Nombre: ...)
    items = []
    def add_pair(label, v100, u100, vpp, upp, bold=False):
        name = label
        left = f"{name}: {v100} {u100}".strip()
        right = f"{vpp} {upp}".strip()
        return (left, right, bold)

    items.append(add_pair("Calorías",
                          int(round(payload["kcal_100"])), "kcal", int(round(payload["kcal_pp"])), "kcal", True))
    # Grasa total, saturada (en lineal no hacemos subnivel; mantenemos orden y negrillas normativas donde aplique)
    items.append(add_pair("Grasa total", fmt_g(payload["fat_total_100"]), "g", fmt_g(payload["fat_total_pp"]), "g", False))
    items.append(add_pair("Grasa saturada", fmt_g(payload["sat_fat_100"]), "g", fmt_g(payload["sat_fat_pp"]), "g", True))
    items.append(add_pair("Grasas trans", fmt_mg(payload["trans_100_mg"]), "mg", fmt_mg(payload["trans_pp_mg"]), "mg", True))
    items.append(add_pair("Carbohidratos", fmt_g(payload["carb_100"]), "g", fmt_g(payload["carb_pp"]), "g", False))
    items.append(add_pair("Azúcares totales", fmt_g(payload["sugars_total_100"]), "g", fmt_g(payload["sugars_total_pp"]), "g", False))
    items.append(add_pair("Azúcares añadidos", fmt_g(payload["sugars_added_100"]), "g", fmt_g(payload["sugars_added_pp"]), "g", True))
    items.append(add_pair("Fibra dietaria", fmt_g(payload["fiber_100"]), "g", fmt_g(payload["fiber_pp"]), "g", False))
    items.append(add_pair("Proteína", fmt_g(payload["protein_100"]), "g", fmt_g(payload["protein_pp"]), "g", False))
    items.append(add_pair("Sodio", fmt_mg(payload["sodium_100_mg"]), "mg", fmt_mg(payload["sodium_pp_mg"]), "mg", True))

    # Construcción de la línea formateada con separadores " · "
    x = x0 + 12
    y_text = y + 10
    sep = "  ·  "
    for (left, right, bold) in items:
        label_font = FONT_LABEL_B if bold else FONT_LABEL
        num_font   = FONT_NUM_B if bold else FONT_NUM
        chunk = f"{left} | {right}"
        canvas.text((x, y_text), safe_micro(chunk), font=label_font, fill=BLACK)
        w = canvas.textsize(safe_micro(chunk), label_font)[2] - canvas.textsize(safe_micro(chunk), label_font)[0]
        x = x + w + canvas.textsize(sep, FONT_LABEL)[2]
        canvas.text((x - canvas.textsize(sep, FONT_LABEL)[2], y_text), sep, font=FONT_LABEL, fill=BLACK)

    # Pie
    y2 = y0 + 180
    foot = f"No es fuente significativa de {payload['footnote_tail']}".strip()
    canvas.text((x0 + 12, y2), foot, font=FONT_SMALL, fill=BLACK)

# =========================
# Cálculo de payload común
# =========================
def compute_payload(inputs):
    portion_size = inputs["portion_size"]
    is_liquid = inputs["physical_state"].startswith("Líquido")
    portion_unit = "mL" if is_liquid else "g"

    # Normalización
    if inputs["input_basis"] == "Por porción":
        fat_total_pp = inputs["fat_total"]
        sat_fat_pp   = inputs["sat_fat"]
        trans_pp_g   = inputs["trans_fat_g"]          # g (entrada en mg convertida a g)
        carb_pp      = inputs["carb"]
        sugars_total_pp = inputs["sugars_total"]
        sugars_added_pp = inputs["sugars_added"]
        fiber_pp     = inputs["fiber"]
        protein_pp   = inputs["protein"]
        sodium_pp_mg = inputs["sodium_mg"]

        fat_total_100 = per100_from_portion(fat_total_pp, portion_size)
        sat_fat_100   = per100_from_portion(sat_fat_pp, portion_size)
        trans_fat_100 = per100_from_portion(trans_pp_g, portion_size)
        carb_100      = per100_from_portion(carb_pp, portion_size)
        sugars_total_100 = per100_from_portion(sugars_total_pp, portion_size)
        sugars_added_100 = per100_from_portion(sugars_added_pp, portion_size)
        fiber_100     = per100_from_portion(fiber_pp, portion_size)
        protein_100   = per100_from_portion(protein_pp, portion_size)
        sodium_100_mg = per100_from_portion(sodium_pp_mg, portion_size)
    else:
        fat_total_100 = inputs["fat_total"]
        sat_fat_100   = inputs["sat_fat"]
        trans_fat_100 = inputs["trans_fat_g"]  # g
        carb_100      = inputs["carb"]
        sugars_total_100 = inputs["sugars_total"]
        sugars_added_100 = inputs["sugars_added"]
        fiber_100     = inputs["fiber"]
        protein_100   = inputs["protein"]
        sodium_100_mg = inputs["sodium_mg"]

        fat_total_pp = portion_from_per100(fat_total_100, portion_size)
        sat_fat_pp   = portion_from_per100(sat_fat_100, portion_size)
        trans_pp_g   = portion_from_per100(trans_fat_100, portion_size)
        carb_pp      = portion_from_per100(carb_100, portion_size)
        sugars_total_pp = portion_from_per100(sugars_total_100, portion_size)
        sugars_added_pp = portion_from_per100(sugars_added_100, portion_size)
        fiber_pp     = portion_from_per100(fiber_100, portion_size)
        protein_pp   = portion_from_per100(protein_100, portion_size)
        sodium_pp_mg = portion_from_per100(sodium_100_mg, portion_size)

    # Energía
    kcal_pp  = kcal_from_macros(fat_total_pp, carb_pp, protein_pp)
    kcal_100 = kcal_from_macros(fat_total_100, carb_100, protein_100)
    kj_pp = round(kcal_pp * 4.184) if inputs["include_kj"] else None
    kj_100 = round(kcal_100 * 4.184) if inputs["include_kj"] else None

    # Vitaminas/minerales normalizados
    vm_rows = []
    for vm_name in inputs["selected_vm"]:
        val = inputs["vm_values"].get(vm_name, 0.0)
        if inputs["input_basis"] == "Por porción":
            vpp = val
            v100 = per100_from_portion(val, portion_size)
        else:
            v100 = val
            vpp = portion_from_per100(val, portion_size)
        unit = "mg"
        if "µg" in vm_name:
            unit = "µg"
        name_clean = vm_name.replace(" (µg ER)", "").replace(" (µg)", "").replace(" (mg)", "")
        if vm_name.startswith("Vitamina A"):
            name_clean = "Vitamina A (µg ER)"  # mantener etiqueta normativa con ER
        vm_rows.append((name_clean, v100 if unit!="mg" else fmt_mg(v100), vpp if unit!="mg" else fmt_mg(vpp), unit))

    payload = dict(
        is_liquid=is_liquid,
        portion_size=portion_size,
        portion_unit=portion_unit,
        servings_per_pack=inputs["servings_per_pack"],
        include_kj=inputs["include_kj"],
        footnote_tail=inputs["footnote_tail"].strip(),

        kcal_pp=kcal_pp, kj_pp=kj_pp,
        kcal_100=kcal_100, kj_100=kj_100,

        fat_total_pp=fat_total_pp, fat_total_100=fat_total_100,
        sat_fat_pp=sat_fat_pp, sat_fat_100=sat_fat_100,
        trans_pp_mg=trans_pp_g*1000.0, trans_100_mg=trans_fat_100*1000.0,
        carb_pp=carb_pp, carb_100=carb_100,
        sugars_total_pp=sugars_total_pp, sugars_total_100=sugars_total_100,
        sugars_added_pp=sugars_added_pp, sugars_added_100=sugars_added_100,
        fiber_pp=fiber_pp, fiber_100=fiber_100,
        protein_pp=protein_pp, protein_100=protein_100,
        sodium_pp_mg=sodium_pp_mg, sodium_100_mg=sodium_100_mg,

        vm_rows=vm_rows,
    )
    return payload

# =========================
# UI
# =========================
st.title("Generador de Tabla Nutricional — PNG (Res. 810/2021, 2492/2022, 254/2023)")

# Barra lateral: selección de figura + exportar
st.sidebar.header("Formato")
fig_choice = st.sidebar.selectbox(
    "Figura",
    ["Fig. 1 – Vertical estándar", "Fig. 3 – Simplificada", "Fig. 4 – Tabular", "Fig. 5 – Lineal"],
    index=0
)
export_btn = st.sidebar.button("Exportar PNG")

# Cuerpo: entradas (como antes)
colA, colB = st.columns([0.55, 0.45])

with colA:
    st.subheader("Datos del producto")
    product_name = st.text_input("Producto", value="")
    brand_name = st.text_input("Marca (opcional)", value="")
    provider = st.text_input("Proveedor/Fabricante (opcional)", value="")

    colAA, colAB, colAC = st.columns([1,1,1])
    with colAA:
        physical_state = st.selectbox("Estado físico", ["Sólido (g)", "Líquido (mL)"])
    with colAB:
        input_basis = st.selectbox("Modo de ingreso", ["Por porción", "Por 100 g/mL"])
    with colAC:
        portion_size = as_num(st.text_input("Tamaño de porción (número)", value="50"))

    servings_per_pack = as_num(st.text_input("Porciones por envase (número)", value="1"))
    include_kj = st.checkbox("Mostrar también kJ", value=True)

with colB:
    st.subheader("“No es fuente significativa de…”")
    st.caption("Siempre se mostrará el prefijo. Personaliza el contenido:")
    footnote_tail = st.text_input("Completa la frase:", value="grasas trans, colesterol, vitamina C")

st.markdown("---")
st.subheader("Ingreso de nutrientes (solo números)")

c1, c2 = st.columns(2)
with c1:
    fat_total = as_num(st.text_input("Grasa total (g)", value="5"))
    sat_fat   = as_num(st.text_input("Grasa saturada (g)", value="2"))
    trans_mg  = as_num(st.text_input("Grasas trans (mg)", value="0"))
    trans_g   = trans_mg/1000.0
    carb      = as_num(st.text_input("Carbohidratos totales (g)", value="20"))
    sugars_total = as_num(st.text_input("Azúcares totales (g)", value="10"))

with c2:
    sugars_added  = as_num(st.text_input("Azúcares añadidos (g)", value="8"))
    fiber         = as_num(st.text_input("Fibra dietaria (g)", value="2"))
    protein       = as_num(st.text_input("Proteína (g)", value="3"))
    sodium_mg     = as_num(st.text_input("Sodio (mg)", value="150"))

st.subheader("Vitaminas y minerales")
vm_options = [
    "Vitamina A (µg ER)",
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
selected_vm = st.multiselect("Selecciona micronutrientes a incluir", vm_options,
                             default=["Vitamina A (µg ER)", "Vitamina D (µg)", "Calcio (mg)", "Hierro (mg)", "Zinc (mg)"])

vm_values = {}
vm_cols = st.columns(3)
for i, vm in enumerate(selected_vm):
    with vm_cols[i % 3]:
        vm_values[vm] = as_num(st.text_input(vm, value="0"))

# =========================
# Previsualización y exportación
# =========================
# Computar payload común
inputs = dict(
    physical_state=physical_state,
    input_basis=input_basis,
    portion_size=portion_size,
    servings_per_pack=servings_per_pack,
    include_kj=include_kj,
    footnote_tail=footnote_tail,

    fat_total=fat_total,
    sat_fat=sat_fat,
    trans_fat_g=trans_g,  # almacenamos en g
    carb=carb,
    sugars_total=sugars_total,
    sugars_added=sugars_added,
    fiber=fiber,
    protein=protein,
    sodium_mg=sodium_mg,

    selected_vm=selected_vm,
    vm_values=vm_values,
)
payload = compute_payload(inputs)

st.markdown("---")
st.subheader("Vista previa")

# Renderizar a PNG en memoria
canvas = Canvas(width=1500, height=1000, bg=BG)

if fig_choice.startswith("Fig. 1"):
    render_fig1_vertical(canvas, payload)
    fig_tag = "fig1_vertical"
elif fig_choice.startswith("Fig. 3"):
    render_fig3_simplificada(canvas, payload)
    fig_tag = "fig3_simplificada"
elif fig_choice.startswith("Fig. 4"):
    render_fig4_tabular(canvas, payload)
    fig_tag = "fig4_tabular"
else:
    render_fig5_lineal(canvas, payload)
    fig_tag = "fig5_lineal"

# Mostrar previsualización
png_bytes = canvas.to_bytes()
st.image(png_bytes, caption=None, use_column_width=True)

# Exportar
if export_btn:
    fname = f"tabla_nutricional_{fig_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    st.download_button(
        label="Descargar PNG",
        data=png_bytes,
        file_name=fname,
        mime="image/png"
    )

