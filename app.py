def generar_pdf(rows, no_signif_text, width_table_mm=100, fixed_height=False):
    page_w, page_h = A4
    table_w = mm_to_pt(width_table_mm)

    # Parámetros base (mm)
    row_h_mm = 7.0
    margin_sup_mm = 6
    margin_lat_mm = 6
    separacion_mm = 4
    footer_h_mm = 8
    n_rows = len(rows)
    table_h_mm = max(75, 35 + n_rows * row_h_mm + footer_h_mm)
    table_h = mm_to_pt(table_h_mm)

    # Centrado de tabla
    table_x = (page_w - table_w) / 2
    table_y = (page_h - table_h) / 2

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Recuadro principal
    c.setLineWidth(1)
    c.rect(table_x, table_y, table_w, table_h)

    # Fuentes y tamaños
    font_reg = "Helvetica"
    font_bold = "Helvetica-Bold"
    size_titulo = 10
    size_normal = 9
    size_destacado = int(size_normal * 1.3)

    # ---- Título ----
    y_actual = table_y + table_h - mm_to_pt(margin_sup_mm)
    c.setFont(font_bold, size_titulo)
    c.drawString(table_x + mm_to_pt(margin_lat_mm), y_actual, "Información Nutricional")

    # ---- Tamaño de porción (línea aparte) ----
    y_actual -= mm_to_pt(separacion_mm + 4)
    c.setFont(font_reg, size_normal)
    c.drawString(table_x + mm_to_pt(margin_lat_mm),
                 y_actual,
                 f"Tamaño de porción: {porcion_text} ({int(porcion_val)} {unidad_100})")

    # ---- Número de porciones (línea aparte) ----
    y_actual -= mm_to_pt(separacion_mm + 4)
    c.drawString(table_x + mm_to_pt(margin_lat_mm),
                 y_actual,
                 f"Número de porciones por envase: {num_porciones if num_porciones else '-'}")

    # ---- Línea divisoria gruesa debajo ----
    y_actual -= mm_to_pt(separacion_mm)
    c.setLineWidth(1)
    c.line(table_x + mm_to_pt(3), y_actual, table_x + table_w - mm_to_pt(3), y_actual)

    # ---- Encabezado de columnas ----
    y_actual -= mm_to_pt(6)
    col_nutr_x = table_x + mm_to_pt(6)
    col_100_x = table_x + table_w * 0.55
    col_por_x = table_x + table_w * 0.85

    c.setFont(font_bold, size_normal)
    c.drawString(col_100_x, y_actual, f"Por 100 {unidad_100}")
    c.drawString(col_por_x, y_actual, f"Por porción ({int(porcion_val)} {unidad_100})")

    # Línea bajo encabezado
    y_actual -= mm_to_pt(3)
    c.setLineWidth(0.75)
    c.line(table_x + mm_to_pt(3), y_actual, table_x + table_w - mm_to_pt(3), y_actual)

    # ---- Filas ----
    y_actual -= mm_to_pt(5)
    row_h = mm_to_pt(row_h_mm)
    important_labels = {"Calorías (kcal)", "Grasa saturada", "Grasas trans", "Azúcares añadidos", "Sodio"}

    for name, v100, vpor in rows:
        if name in important_labels:
            c.setFont(font_bold, size_destacado)
        else:
            c.setFont(font_reg, size_normal)

        c.drawString(col_nutr_x, y_actual, name)
        c.setFont(font_reg, size_normal)
        c.drawRightString(col_100_x + mm_to_pt(22), y_actual, v100)
        c.drawRightString(col_por_x + mm_to_pt(22), y_actual, vpor)

        # Línea separadora
        y_actual -= row_h
        c.setLineWidth(0.5)
        c.line(table_x + mm_to_pt(3), y_actual + mm_to_pt(2.5), table_x + table_w - mm_to_pt(3), y_actual + mm_to_pt(2.5))

    # Línea gruesa tras “Sodio” (macro vs micro)
    idx_sodio = next((i for i, (n, _, _) in enumerate(rows) if n.strip().lower().startswith("sodio")), None)
    if idx_sodio is not None:
        sep_y = y_actual + mm_to_pt(row_h_mm * (len(rows) - idx_sodio - 1))
        c.setLineWidth(1)
        c.line(table_x + mm_to_pt(3), sep_y, table_x + table_w - mm_to_pt(3), sep_y)

    # ---- Líneas verticales completas ----
    c.setLineWidth(0.75)
    x_v1 = table_x + mm_to_pt(3)
    x_v2 = table_x + table_w * 0.52
    x_v3 = table_x + table_w * 0.82
    c.line(x_v1, table_y + mm_to_pt(2), x_v1, table_y + table_h - mm_to_pt(2))
    c.line(x_v2, table_y + mm_to_pt(2), x_v2, table_y + table_h - mm_to_pt(2))
    c.line(x_v3, table_y + mm_to_pt(2), x_v3, table_y + table_h - mm_to_pt(2))

    # ---- Frase inferior ----
    if no_signif_text:
        c.setFont(font_reg, 8)
        ns_y = table_y + mm_to_pt(4)
        max_chars = 80
        for i, line in enumerate([no_signif_text[i:i+max_chars] for i in range(0, len(no_signif_text), max_chars)]):
            c.drawString(table_x + mm_to_pt(margin_lat_mm), ns_y + mm_to_pt(4) * i, line)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
