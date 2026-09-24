"""Planilla de liquidación en Excel y PDF, a partir del resumen (`armar_resumen`)."""
import io
from decimal import Decimal
from typing import Any, Dict, List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

TITULOS = {"retiro": "ALTA DE BENEFICIO RETIRO", "pension": "ALTA DE BENEFICIO PENSION", "reajuste": "REAJUSTE"}


def _num(s: str) -> float:
    return float(Decimal(s))


def _money(s: str) -> str:
    """1234567.8 -> '1.234.567,80' (formato es-AR)."""
    d = Decimal(s).quantize(Decimal("0.01"))
    txt = f"{d:,.2f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def _fecha(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"


def _titular(resumen: Dict[str, Any], rec: Dict[str, Any]) -> Dict[str, Any]:
    b = rec.get("beneficiario")
    return b if b else resumen["causante"]


def _nombre(p: Dict[str, Any]) -> str:
    return f"{p['apellido']}, {p['nombre']}"


def _fila_tramo(t: Dict[str, Any]) -> List[Any]:
    if t["es_sac"]:
        return [_num(t["haber_mensual"]) / 2, "SAC", t["descripcion"] or "", "", _num(t["importe"])]
    return [_num(t["haber_mensual"]), _fecha(t["desde"]), _fecha(t["hasta"]), _num(t["meses"]), _num(t["importe"])]


# ------------------------------------------------------------------ Excel

def _texto(ws, ref: str, valor: Any, **fmt) -> None:
    """Escribe siempre como texto (un apellido que empiece con '=' no debe interpretarse como fórmula)."""
    c = ws[ref]
    c.value = valor
    if isinstance(valor, str):
        c.data_type = "s"
    for k, v in fmt.items():
        setattr(c, k, v)


def a_xlsx(resumen: Dict[str, Any]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    liq = resumen["liquidacion"]
    dinero = "#,##0.00"
    negrita = Font(bold=True)
    borde = Border(bottom=Side(style="thin"))
    for rec in resumen["recibos"]:
        titular = _titular(resumen, rec)
        ws = wb.create_sheet(f"Recibo {rec['numero']}"[:31])
        _texto(ws, "A1", TITULOS.get(liq["tipo"], "LIQUIDACION"), font=Font(bold=True, size=13))
        _texto(ws, "A3", "Expte:"); _texto(ws, "B3", resumen["causante"]["expediente"] or "")
        _texto(ws, "A4", "Causante:"); _texto(ws, "B4", _nombre(resumen["causante"]))
        _texto(ws, "A5", "Beneficiario:" if rec.get("beneficiario") else "Titular:"); _texto(ws, "B5", _nombre(titular))
        _texto(ws, "A6", "DNI:"); _texto(ws, "B6", titular.get("dni") or "")
        _texto(ws, "A7", "Período:"); _texto(ws, "B7", liq["periodo"])
        _texto(ws, "A8", "Rango liquidado:")
        if rec["rango"]:
            _texto(ws, "B8", f"{_fecha(rec['rango']['desde'])} al {_fecha(rec['rango']['hasta'])}")
        if rec.get("beneficiario"):
            _texto(ws, "A9", "Porcentaje:"); _texto(ws, "B9", f"{Decimal(str(rec['beneficiario']['porcentaje'])):.2f}%")
        _texto(ws, "A11", "PLANILLA DE RESUMEN DE LIQUIDACION", font=negrita)
        for i, h in enumerate(["NOMINAL", "DESDE", "HASTA", "MESES", "TOTALES"], start=1):
            _texto(ws, f"{get_column_letter(i)}12", h, font=negrita, border=borde, alignment=Alignment(horizontal="center"))
        fila = 13
        for t in rec["tramos"]:
            for i, v in enumerate(_fila_tramo(t), start=1):
                ref = f"{get_column_letter(i)}{fila}"
                _texto(ws, ref, v)
                if i in (1, 5):
                    ws[ref].number_format = dinero
                if i == 4 and v != "":
                    ws[ref].number_format = "0.00"
            fila += 1
        fila += 1
        _texto(ws, f"C{fila}", "Subtotal crédito", font=negrita); _texto(ws, f"E{fila}", _num(rec["credito"]), font=negrita)
        ws[f"E{fila}"].number_format = dinero
        fila += 2
        for d in rec["descuentos"]:
            if Decimal(d["importe"]) == 0 and d["codigo"] == "ANTICIPO":
                continue
            _texto(ws, f"A{fila}", d["descripcion"]); _texto(ws, f"E{fila}", _num(d["importe"]))
            ws[f"E{fila}"].number_format = dinero
            fila += 1
        _texto(ws, f"A{fila}", "Total débito", font=negrita); _texto(ws, f"E{fila}", _num(rec["total_descuentos"]), font=negrita)
        ws[f"E{fila}"].number_format = dinero
        fila += 2
        _texto(ws, f"A{fila}", "Total crédito líquido", font=Font(bold=True, size=12)); _texto(ws, f"E{fila}", _num(rec["liquido"]), font=Font(bold=True, size=12))
        ws[f"E{fila}"].number_format = dinero
        for col, ancho in zip("ABCDE", (18, 13, 13, 9, 18)):
            ws.column_dimensions[col].width = ancho

        det = wb.create_sheet(f"Haber {rec['numero']}"[:31])
        _texto(det, "A1", f"Detalle del haber mensual vigente ({_fecha(rec['tramos'][-1]['desde'])})" if rec["tramos"] else "Detalle", font=negrita)
        for i, h in enumerate(["Secuencia", "Código", "Concepto", "Columna", "Unidad", "Importe"], start=1):
            _texto(det, f"{get_column_letter(i)}3", h, font=negrita, border=borde)
        n = 4
        for c in rec["conceptos_haber"]:
            _texto(det, f"A{n}", c["secuencia"] if c["secuencia"] is not None else "Beneficio")
            _texto(det, f"B{n}", c["codigo"]); _texto(det, f"C{n}", c["descripcion"]); _texto(det, f"D{n}", c["columna"])
            if c["unidad"] is not None:
                _texto(det, f"E{n}", _num(c["unidad"]))
            _texto(det, f"F{n}", _num(c["importe"]))
            det[f"F{n}"].number_format = dinero
            n += 1
        if len(rec["cargos"]) > 1:
            n += 1
            _texto(det, f"A{n}", "Haber ponderado de los cargos", font=negrita)
            n += 1
            for c in rec["cargos"]:
                _texto(det, f"A{n}", f"Secuencia {c['secuencia']}")
                _texto(det, f"C{n}", f"{Decimal(c['porcentaje']):.2f}% de {_money(c['total'])}")
                _texto(det, f"F{n}", _num(c["total"]) * _num(c["porcentaje"]) / 100)
                det[f"F{n}"].number_format = dinero
                n += 1
            _texto(det, f"A{n}", "Total ponderado", font=negrita); _texto(det, f"F{n}", _num(rec["haber_ponderado"]), font=negrita)
            det[f"F{n}"].number_format = dinero
        for col, ancho in zip("ABCDEF", (12, 24, 38, 18, 12, 18)):
            det.column_dimensions[col].width = ancho
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ PDF

def a_pdf(resumen: Dict[str, Any]) -> bytes:
    liq = resumen["liquidacion"]
    estilos = getSampleStyleSheet()
    normal, titulo = estilos["Normal"], estilos["Heading2"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Liquidación {liq['periodo']}", author="online-otp")
    story: List[Any] = []
    p = lambda txt, st=normal: Paragraph(escape(str(txt)), st)
    for n, rec in enumerate(resumen["recibos"]):
        if n:
            story.append(Spacer(1, 10 * mm))
        titular = _titular(resumen, rec)
        story.append(p(TITULOS.get(liq["tipo"], "LIQUIDACION"), titulo))
        cabecera = [
            ["Expte:", resumen["causante"]["expediente"] or "-", "Período:", liq["periodo"]],
            ["Causante:", _nombre(resumen["causante"]), "DNI:", resumen["causante"]["dni"]],
        ]
        if rec.get("beneficiario"):
            cabecera.append(["Beneficiario:", _nombre(titular), "DNI:", titular.get("dni") or "-"])
        if rec["rango"]:
            cabecera.append(["Rango:", f"{_fecha(rec['rango']['desde'])} al {_fecha(rec['rango']['hasta'])}",
                             "Estado:", liq["estado"]])
        if len(rec["cargos"]) > 1:
            cabecera.append(["Secuencias:", " / ".join(f"{c['secuencia']}: {Decimal(c['porcentaje']):.2f}%" for c in rec["cargos"]),
                             "Haber pond.:", _money(rec["haber_ponderado"])])
        story.append(Table([[p(c) for c in fila] for fila in cabecera], colWidths=[26 * mm, 70 * mm, 22 * mm, 50 * mm],
                           style=TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)])))
        story.append(Spacer(1, 5 * mm))

        filas = [["NOMINAL", "DESDE", "HASTA", "MESES", "TOTALES"]]
        for t in rec["tramos"]:
            v = _fila_tramo(t)
            filas.append([_money(str(v[0])), v[1], v[2], "" if v[3] == "" else f"{v[3]:.2f}", _money(str(v[4]))])
        filas.append(["", "", "", "Subtotal crédito", _money(rec["credito"])])
        for d in rec["descuentos"]:
            if Decimal(d["importe"]) == 0 and d["codigo"] == "ANTICIPO":
                continue
            filas.append(["", "", "", d["descripcion"], _money(d["importe"])])
        filas.append(["", "", "", "Total débito", _money(rec["total_descuentos"])])
        filas.append(["", "", "", "TOTAL CRÉDITO LÍQUIDO", _money(rec["liquido"])])
        n_tramos = len(rec["tramos"])
        t = Table(filas, colWidths=[32 * mm, 22 * mm, 22 * mm, 48 * mm, 36 * mm], repeatRows=1)
        estilo = [
            ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7e5e4")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (0, 0), (0, -1), "RIGHT"), ("ALIGN", (3, 0), (4, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey), ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1), ("LEADING", (0, 0), (-1, -1), 9.5),
            ("FONTNAME", (3, n_tramos + 1), (4, -1), "Helvetica-Bold"),
            ("LINEABOVE", (3, n_tramos + 1), (4, n_tramos + 1), 0.5, colors.grey),
            ("LINEABOVE", (3, -1), (4, -1), 0.8, colors.black),
        ]
        for i, tr in enumerate(rec["tramos"], start=1):
            if tr["es_sac"]:
                estilo.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f5f4")))
        t.setStyle(TableStyle(estilo))
        story.append(t)
    doc.build(story)
    return buf.getvalue()
