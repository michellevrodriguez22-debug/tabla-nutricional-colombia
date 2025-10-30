# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# -----------------------------------------------------------
# CONFIGURACIÓN INICIAL
# -----------------------------------------------------------
st.set_page_config(page_title="Generador de Tabla Nutricional — Resoluciones 810/2021, 2492/2022 y 254/2023", layout="wide")
st.title("🧾 Generador de Tabla Nutricional — Basado en las Resoluciones 810 de 2021, 2492 de 2022 y 254 de 2023")

# -----------------------------------------------------------
# FUNCIÓN DE RENDERIZADO SEGURO HTML
# -----------------------------------------------------------
def render_html(html: str):
    html += "</table>"

    # --- FIX de renderizado seguro ---
    def render_html_safely(raw_html: str):
        """Evita errores de import JS y renderiza HTML sin romper el frontend"""
        try:
            st.components.v1.html(raw_html, height=600, scrolling=True)
        except Exception:
            st.markdown(raw_html, unsafe_allow_html=True)

    render_html_safely(html)


# -----------------------------------------------------------
# ESTILOS CSS SEGÚN REQUISITOS DE LA RESOLUCIÓN
# -----------------------------------------------------------
CSS_NUTRI = """
<style>
.nutri-table {
    border-collapse: collapse;
    width: 100%;
    font-family: Arial, Helvetica, sans-serif;
}
.nutri-cell {
    border: 1px solid #000;
    padding: 4px;
    font-size: 12px;
    line-height: 1.2;
}
.nutri-title {
    font-weight: 700;
    font-size: 13px;
}
.nutri-bold-13 {
    font-weight: 700;
    font-size: 13px;
}
.nutri-divider {
    border-top: 2px solid #000;
    height: 0;
    line-height: 0;
}
.nutri-right {
    text-align: right;
}
</style>
"""
st.markdown(CSS_NUTRI, unsafe_allow_html=True)

# -----------------------------------------------------------
# ENTRADAS DEL PRODUCTO
# -----------------------------------------------------------
with st.expander("📦 Información general del producto"):
    nombre_producto = st.text_input("Nombre del producto:")
    porcion = st.text_input("Tamaño de porción (g o mL):")
    porciones_envase = st.number_input("Número de porciones por envase:", min_value=1, value=1)
    categoria = st.selectbox("Categoría del producto:", ["Sólido", "Semisólido", "Líquido"])
    tipo_producto = st.radio("Tipo de producto:", ["Producto terminado", "Materia prima", "Aplica a ambos"])

# -----------------------------------------------------------
# ENTRADA DE NUTRIENTES SEGÚN RESOLUCIONES
# -----------------------------------------------------------
st.subheader("💪 Ingrese la información nutricional (por 100 g/mL)")
cols = st.columns(3)
energia = cols[0].number_input("Energía (kcal)", min_value=0.0, value=200.0)
grasas = cols[1].number_input("Grasa total (g)", min_value=0.0, value=10.0)
saturadas = cols[2].number_input("Grasa saturada (g)", min_value=0.0, value=4.0)
trans = st.number_input("Grasas trans (g)", min_value=0.0, value=0.0)
carbo = st.number_input("Carbohidratos (g)", min_value=0.0, value=40.0)
azucares = st.number_input("Azúcares totales (g)", min_value=0.0, value=20.0)
azucares_add = st.number_input("Azúcares añadidos (g)", min_value=0.0, value=16.0)
fibra = st.number_input("Fibra dietaria (g)", min_value=0.0, value=4.0)
proteina = st.number_input("Proteína (g)", min_value=0.0, value=6.0)
sodio = st.number_input("Sodio (mg)", min_value=0.0, value=300.0)
vit_a = st.number_input("Vitamina A (µg)", min_value=0.0, value=0.0)
vit_d = st.number_input("Vitamina D (µg)", min_value=0.0, value=0.0)
calcio = st.number_input("Calcio (mg)", min_value=0.0, value=0.0)
hierro = st.number_input("Hierro (mg)", min_value=0.0, value=0.0)
zinc = st.number_input("Zinc (mg)", min_value=0.0, value=0.0)

# -----------------------------------------------------------
# CÁLCULO POR PORCIÓN
# -----------------------------------------------------------
energia_p = round(energia / porciones_envase, 2)
grasas_p = round(grasas / porciones_envase, 2)
saturadas_p = round(saturadas / porciones_envase, 2)
trans_p = round(trans / porciones_envase, 2)
carbo_p = round(carbo / porciones_envase, 2)
azucares_p = round(azucares / porciones_envase, 2)
azucares_add_p = round(azucares_add / porciones_envase, 2)
fibra_p = round(fibra / porciones_envase, 2)
proteina_p = round(proteina / porciones_envase, 2)
sodio_p = round(sodio / porciones_envase, 2)
vit_a_p = round(vit_a / porciones_envase, 2)
vit_d_p = round(vit_d / porciones_envase, 2)
calcio_p = round(calcio / porciones_envase, 2)
hierro_p = round(hierro / porciones_envase, 2)
zinc_p = round(zinc / porciones_envase, 2)

# -----------------------------------------------------------
# TABLA HTML NUTRICIONAL COMPLETA
# -----------------------------------------------------------
tabla_html = f"""
<table class="nutri-table">
<tr><td colspan="3" class="nutri-cell nutri-title">Información nutricional</td></tr>
<tr><td colspan="3" class="nutri-cell">
Tamaño de porción: {porcion}<br>Porciones por envase: {porciones_envase}<br>Tipo: {tipo_producto}
</td></tr>
<tr><td colspan="3" class="nutri-cell"><div class="nutri-divider"></div></td></tr>

<tr><td class="nutri-cell nutri-bold-13">Energía (kcal)</td><td class="nutri-cell nutri-right">{energia}</td><td class="nutri-cell nutri-right">{energia_p}</td></tr>
<tr><td class="nutri-cell">Grasa total</td><td class="nutri-cell nutri-right">{grasas} g</td><td class="nutri-cell nutri-right">{grasas_p} g</td></tr>
<tr><td class="nutri-cell"><span class="nutri-bold-13">  de las cuales Grasa saturada</span></td><td class="nutri-cell nutri-right">{saturadas} g</td><td class="nutri-cell nutri-right">{saturadas_p} g</td></tr>
<tr><td class="nutri-cell"><span class="nutri-bold-13">  Grasas trans</span></td><td class="nutri-cell nutri-right">{trans} g</td><td class="nutri-cell nutri-right">{trans_p} g</td></tr>
<tr><td class="nutri-cell">Carbohidratos</td><td class="nutri-cell nutri-right">{carbo} g</td><td class="nutri-cell nutri-right">{carbo_p} g</td></tr>
<tr><td class="nutri-cell">  Azúcares totales</td><td class="nutri-cell nutri-right">{azucares} g</td><td class="nutri-cell nutri-right">{azucares_p} g</td></tr>
<tr><td class="nutri-cell"><span class="nutri-bold-13">  Azúcares añadidos</span></td><td class="nutri-cell nutri-right">{azucares_add} g</td><td class="nutri-cell nutri-right">{azucares_add_p} g</td></tr>
<tr><td class="nutri-cell">  Fibra dietaria</td><td class="nutri-cell nutri-right">{fibra} g</td><td class="nutri-cell nutri-right">{fibra_p} g</td></tr>
<tr><td class="nutri-cell">Proteína</td><td class="nutri-cell nutri-right">{proteina} g</td><td class="nutri-cell nutri-right">{proteina_p} g</td></tr>
<tr><td class="nutri-cell nutri-bold-13">Sodio</td><td class="nutri-cell nutri-right">{sodio} mg</td><td class="nutri-cell nutri-right">{sodio_p} mg</td></tr>

<tr><td class="nutri-cell" colspan="3"><div class="nutri-divider"></div></td></tr>
<tr><td class="nutri-cell">Vitamina A</td><td class="nutri-cell nutri-right">{vit_a} µg</td><td class="nutri-cell nutri-right">{vit_a_p} µg</td></tr>
<tr><td class="nutri-cell">Vitamina D</td><td class="nutri-cell nutri-right">{vit_d} µg</td><td class="nutri-cell nutri-right">{vit_d_p} µg</td></tr>
<tr><td class="nutri-cell">Calcio</td><td class="nutri-cell nutri-right">{calcio} mg</td><td class="nutri-cell nutri-right">{calcio_p} mg</td></tr>
<tr><td class="nutri-cell">Hierro</td><td class="nutri-cell nutri-right">{hierro} mg</td><td class="nutri-cell nutri-right">{hierro_p} mg</td></tr>
<tr><td class="nutri-cell">Zinc</td><td class="nutri-cell nutri-right">{zinc} mg</td><td class="nutri-cell nutri-right">{zinc_p} mg</td></tr>
<tr><td class="nutri-cell" colspan="3">No es fuente significativa de otros nutrientes.</td></tr>
</table>
"""

# -----------------------------------------------------------
# VISTA PREVIA RENDERIZADA
# -----------------------------------------------------------
st.subheader("Vista previa (no a escala)")
render_html(tabla_html)

# -----------------------------------------------------------
# GENERACIÓN DE PDF
# -----------------------------------------------------------
def exportar_pdf_desde_html_crudo(titulo: str, html: str) -> BytesIO:
    """Exporta texto plano desde HTML a PDF básico."""
    plano = (
        html.replace("</tr>", "\n")
            .replace("<br>", "\n")
            .replace("<td", "\t<td")
            .replace("<span", "")
            .replace("</span>", "")
            .replace("<div", "")
            .replace("</div>", "")
    )
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 9)
    y = 770
    for linea in plano.splitlines():
        if y < 60:
            c.showPage()
            c.setFont("Helvetica", 9)
            y = 770
        c.drawString(40, y, linea[:120])
        y -= 13
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# -----------------------------------------------------------
# DESCARGA DEL PDF
# -----------------------------------------------------------
if st.button("📄 Generar PDF"):
    pdf_buffer = exportar_pdf_desde_html_crudo("Tabla nutricional", tabla_html)
    st.download_button(
        label="⬇️ Descargar tabla nutricional en PDF",
        data=pdf_buffer,
        file_name=f"Tabla_Nutricional_{nombre_producto or 'producto'}.pdf",
        mime="application/pdf"
    )
