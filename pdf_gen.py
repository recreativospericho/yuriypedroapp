# -*- coding: utf-8 -*-
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

AMBER  = colors.HexColor("#F59E0B")
DARK   = colors.HexColor("#111827")
GREY   = colors.HexColor("#6B7280")
WHITE  = colors.white

EMISOR = {
    "nombre":   "Retail Service",
    "nif":      "20517937M",
    "dir":      "Calle Villajoyosa 41, Pilar de la Horadada (Alicante)",
    "tel":      "655 09 76 18",
}


def generar_factura(f, cfg=None):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    N  = ParagraphStyle("n",  fontSize=10, leading=14)
    NB = ParagraphStyle("nb", fontSize=10, leading=14, fontName="Helvetica-Bold")
    SM = ParagraphStyle("sm", fontSize=8,  leading=12, textColor=GREY)
    elems = []

    # ── Cabecera
    hdr_data = [[
        Paragraph(f"<font color='#F59E0B' size='20'><b>Retail</b></font>"
                  f"<font color='#111827' size='20'><b>Service</b></font>", styles["Normal"]),
        Paragraph(f"<b>FACTURA</b><br/>"
                  f"<font size='18' color='#F59E0B'>{f.numero}</font>", styles["Normal"]),
    ]]
    t = Table(hdr_data, colWidths=[10*cm, 7*cm])
    t.setStyle(TableStyle([
        ("ALIGN", (1,0), (1,0), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
    ]))
    elems += [t, HRFlowable(width="100%", thickness=2, color=AMBER), Spacer(1, 0.4*cm)]

    # ── Datos emisor / cliente
    datos_data = [[
        Paragraph(f"<b>{EMISOR['nombre']}</b><br/>"
                  f"NIF: {EMISOR['nif']}<br/>"
                  f"{EMISOR['dir']}<br/>"
                  f"Tel: {EMISOR['tel']}", N),
        Paragraph(f"<b>Cliente</b><br/>"
                  f"JYSK – {f.tienda}<br/><br/>"
                  f"<b>Fecha:</b> {f.fecha.strftime('%d/%m/%Y')}<br/>"
                  f"<b>Estado:</b> {'✅ Cobrada' if f.estado=='cobrada' else '⏳ Pendiente'}", N),
    ]]
    t2 = Table(datos_data, colWidths=[8.5*cm, 8.5*cm])
    t2.setStyle(TableStyle([
        ("BOX",       (0,0), (0,0), 0.5, GREY),
        ("BOX",       (1,0), (1,0), 0.5, GREY),
        ("PADDING",   (0,0), (-1,-1), 8),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
    ]))
    elems += [t2, Spacer(1, 0.6*cm)]

    # ── Líneas de factura
    head = [["Concepto", "Unidades", "Precio s/IVA", "Total s/IVA"]]
    rows = [[f.concepto, "1", f"{f.base:.2f} €", f"{f.base:.2f} €"]]
    tabla = Table(head + rows, colWidths=[10*cm, 2.5*cm, 3*cm, 3*cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), DARK),
        ("TEXTCOLOR",    (0,0), (-1,0), AMBER),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN",        (1,0), (-1,-1), "RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#F9FAFB"), WHITE]),
        ("GRID",         (0,0), (-1,-1), 0.3, colors.HexColor("#E5E7EB")),
        ("PADDING",      (0,0), (-1,-1), 8),
    ]))
    elems += [tabla, Spacer(1, 0.4*cm)]

    # ── Totales
    iva_pct = round(f.iva / f.base * 100) if f.base else 21
    tot_data = [
        ["Base imponible",          f"{f.base:.2f} €"],
        [f"IVA {iva_pct}%",         f"{f.iva:.2f} €"],
        ["TOTAL FACTURA",           f"{f.total_iva:.2f} €"],
    ]
    t3 = Table(tot_data, colWidths=[13*cm, 4*cm])
    t3.setStyle(TableStyle([
        ("ALIGN",       (1,0), (1,-1), "RIGHT"),
        ("FONTNAME",    (0,2), (-1,2), "Helvetica-Bold"),
        ("FONTSIZE",    (0,2), (-1,2), 12),
        ("TEXTCOLOR",   (0,2), (-1,2), AMBER),
        ("BACKGROUND",  (0,2), (-1,2), DARK),
        ("LINEABOVE",   (0,2), (-1,2), 1.5, AMBER),
        ("PADDING",     (0,0), (-1,-1), 6),
    ]))
    elems += [t3, Spacer(1, 1*cm)]

    # ── Pie
    elems.append(HRFlowable(width="100%", thickness=1, color=AMBER))
    elems.append(Paragraph(
        "Retail Service · NIF 20517937M · Calle Villajoyosa 41, Pilar de la Horadada · Tel 655 09 76 18",
        ParagraphStyle("pie", fontSize=7, textColor=GREY, alignment=TA_CENTER)
    ))

    doc.build(elems)
    buf.seek(0)
    return buf
