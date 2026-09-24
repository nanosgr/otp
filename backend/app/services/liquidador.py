"""Liquidación de retiros y pensiones: tramos de retroactivo, SAC, descuentos y persistencia de recibos.

Por cada recibo (retiro: uno; pensión: uno por beneficiario):
  1. el rango [desde, hasta] se parte en tramos cada vez que cambia una regla (escala, parámetro o concepto);
  2. en cada tramo, con las reglas vigentes al inicio del tramo, el motor calcula:
     a. etapa "haber": el haber de cada cargo (secuencia) por separado;
     b. haber ponderado = suma de (haber del cargo x % de su secuencia / 100);
     c. etapa "beneficio": haber de retiro (ponderado x % de retiro) y, en pensiones, la pensión del beneficiario;
  3. importe del tramo = haber x meses comerciales; tras cada semestre completo se suma el SAC;
  4. sobre el subtotal se calculan los conceptos de etapa "liquidacion" (descuentos, anticipo) y el líquido.
Con un solo cargo (100%) el haber ponderado es el haber del cargo.
"""
import calendar
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import prevision as m
from app.services import motor, retroactivo as retro
from app.services.reglas import ReglasDB, SinReglas, variables_de_cargo

Q4 = Decimal("0.0001")
Q2 = Decimal("0.01")


def q(d: Decimal, exp: Decimal = Q4) -> Decimal:
    return d.quantize(exp, rounding=ROUND_HALF_UP)


def _err(msg: str, code: int = 422) -> HTTPException:
    return HTTPException(status_code=code, detail=msg)


def rango_de_liquidacion(liq: m.Liquidacion) -> Tuple[date, date]:
    anio, mes = int(liq.periodo[:4]), int(liq.periodo[5:7])
    desde = liq.fecha_desde or date(anio, mes, 1)
    hasta = liq.fecha_hasta or date(anio, mes, calendar.monthrange(anio, mes)[1])
    if hasta < desde:
        raise _err("La fecha 'hasta' de la liquidación es anterior a la fecha 'desde'")
    return desde, hasta


def _errores(res: Dict[str, Any]) -> List[str]:
    return [f"concepto {c['codigo']}: {c['message']}" for c in res["conceptos"] if c["error"]]


def _importe(res: Dict[str, Any], codigo: str) -> Optional[Decimal]:
    for c in res["conceptos"]:
        if c["codigo"] == codigo and c["condicion"]:
            return Decimal(c["importe"])
    return None


def haber_mensual(res: Dict[str, Any], tipo: str, fecha: date) -> Decimal:
    """Haber mensual del beneficio a partir del resultado del motor."""
    if tipo == "retiro":
        codigos = ["HABER_RETIRO"]
    else:
        codigos = ["PENSION_BENEFICIARIO", "ART37"]
    valores = [_importe(res, c) for c in codigos]
    if valores[0] is None:
        raise _err(f"Las reglas vigentes al {fecha.isoformat()} no calculan el concepto {codigos[0]}")
    return sum((v for v in valores if v is not None), Decimal(0))


def _json_safe(o: Any) -> Any:
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    return o


def _motor(reglas: ReglasDB, tipo: str, etapa: str, fecha: date, variables: Dict[str, Any], donde: str = "") -> Dict[str, Any]:
    """Ejecuta el motor para una etapa y una fecha; traduce los errores a HTTP 422."""
    try:
        res = motor.calcular(reglas.reglas_a(fecha, tipo, etapa), reglas.contexto_a(fecha, variables))
    except SinReglas as exc:
        raise _err(f"{exc}. Las reglas cargadas cubren desde el {_primera_vigencia(reglas)}.")
    except motor.FormulaError as exc:
        raise _err(f"Error en las reglas al {fecha.isoformat()}{donde}: {exc}")
    errores = _errores(res)
    if errores:
        raise _err(f"Error de cálculo al {fecha.isoformat()}{donde}: " + "; ".join(errores))
    return res


def calcular_recibo(
    reglas: ReglasDB, liq: m.Liquidacion, causante: m.Causante, cargos: List[m.CargoSecuencia],
    beneficiario: Optional[m.Beneficiario], desde: date, hasta: date, anticipo: Decimal,
) -> Dict[str, Any]:
    """Calcula tramos, SAC y liquidación final de un recibo. Devuelve estructuras listas para persistir."""
    tipo = liq.tipo
    principal = cargos[0]   # el % de retiro (manual o por tabla) y sus años salen del cargo principal (secuencia menor)
    varios = len(cargos) > 1

    tramos_def = retro.dividir_en_tramos(desde, hasta, reglas.cortes(desde, hasta))
    filas: List[Dict[str, Any]] = []
    haber_de_tramo: List[Tuple[date, date, Decimal]] = []
    ultimo: Dict[str, Any] = {}
    for a, b in tramos_def:
        por_cargo: List[Tuple[m.CargoSecuencia, Dict[str, Any], Decimal]] = []
        ponderado = Decimal(0)
        for cargo in cargos:
            res_c = _motor(reglas, tipo, "haber", a, variables_de_cargo(causante, cargo, beneficiario),
                           f" (secuencia {cargo.secuencia})" if varios else "")
            total = Decimal(res_c["totales"]["remunerativo"])
            ponderado += total * Decimal(str(cargo.porcentaje_secuencia)) / Decimal(100)
            por_cargo.append((cargo, res_c, total))
        vars_b = dict(variables_de_cargo(causante, principal, beneficiario), HABER_PONDERADO=ponderado)
        res_b = _motor(reglas, tipo, "beneficio", a, vars_b)
        h = haber_mensual(res_b, tipo, a)
        n = retro.meses(a, b)
        haber_de_tramo.append((a, b, h))
        filas.append({"desde": a, "hasta": b, "haber_mensual": h, "meses": n, "importe": h * n, "sac": Decimal(0),
                      "descripcion": None})
        ultimo = {"por_cargo": por_cargo, "beneficio": res_b, "ponderado": ponderado}

    for inicio, cierre in retro.semestres_completos(desde, hasta):
        h = next(h for a, b, h in haber_de_tramo if a <= cierre <= b)
        s = retro.sac(h, desde, inicio, cierre)
        filas.append({"desde": cierre, "hasta": cierre, "haber_mensual": h, "meses": Decimal(0), "importe": s, "sac": s,
                      "descripcion": f"SAC {'1er' if cierre.month == 6 else '2do'} semestre {cierre.year}"})
    filas.sort(key=lambda f: (f["desde"], f["sac"] != 0))

    credito = sum((f["importe"] for f in filas), Decimal(0))

    # Etapa "liquidación": descuentos y anticipo sobre el subtotal, con las reglas vigentes al cierre del rango
    vars_liq = dict(variables_de_cargo(causante, principal, beneficiario), SUBTOTAL_CREDITO=credito, ANTICIPO_IMPORTE=anticipo)
    fin = _motor(reglas, tipo, "liquidacion", hasta, vars_liq, " (liquidación final)")
    t = fin["totales"]
    return {
        "tramos": filas,
        "credito": credito,
        "descuentos": Decimal(t["descuento"]),
        "liquido": Decimal(t["neto"]),
        "detalle_haber": [(c.secuencia, res) for c, res, _ in ultimo["por_cargo"]],
        "totales_cargos": [{"secuencia": c.secuencia, "porcentaje": Decimal(str(c.porcentaje_secuencia)), "total": tot}
                           for c, _, tot in ultimo["por_cargo"]],
        "haber_ponderado": ultimo["ponderado"],
        "detalle_beneficio": ultimo["beneficio"],
        "detalle_liquidacion": fin,
        "haber_actual": haber_de_tramo[-1][2],
    }


def _primera_vigencia(reglas: ReglasDB) -> str:
    fechas = [v.vigencia_desde for lista in reglas.vigencias.values() for v in lista if v.vigencia_desde]
    return min(fechas).isoformat() if fechas else "(sin datos)"


def calcular_liquidacion(db: Session, liquidacion_id: int, user_id: Optional[int] = None) -> m.Liquidacion:
    liq = db.get(m.Liquidacion, liquidacion_id)
    if liq is None:
        raise HTTPException(status_code=404, detail="Liquidación no encontrada")
    if liq.estado == "CERRADA":
        raise _err("La liquidación está CERRADA y no puede recalcularse", 409)
    if liq.tipo == "reajuste":
        raise _err("El cálculo de reajustes todavía no está implementado (solo retiro y pensión)", 501)
    causante = db.get(m.Causante, liq.causante_id)
    cargos = db.exec(select(m.CargoSecuencia).where(m.CargoSecuencia.causante_id == causante.id)
                     .order_by(m.CargoSecuencia.secuencia)).all()
    if not cargos:
        raise _err("El causante no tiene un cargo cargado (clase, adicionales, antigüedad)")
    if len({c.secuencia for c in cargos}) != len(cargos):
        raise _err("Hay cargos con el mismo número de secuencia")
    suma_sec = sum((Decimal(str(c.porcentaje_secuencia)) for c in cargos), Decimal(0))
    if abs(suma_sec - Decimal(100)) > Decimal("0.0001"):
        raise _err(f"Los porcentajes de secuencia de los cargos suman {suma_sec}% (deben sumar 100%)")
    desde, hasta = rango_de_liquidacion(liq)

    if liq.tipo == "retiro":
        destinatarios: List[Optional[m.Beneficiario]] = [None]
    else:
        benef = db.exec(select(m.Beneficiario).where(m.Beneficiario.causante_id == causante.id,
                                                     m.Beneficiario.is_active == True)  # noqa: E712
                        .order_by(m.Beneficiario.id)).all()
        if not benef:
            raise _err("La pensión requiere al menos un beneficiario activo")
        total_pct = sum((Decimal(str(b.porcentaje)) for b in benef), Decimal(0))
        if total_pct > Decimal("100.0001"):
            raise _err(f"Los porcentajes de los beneficiarios suman {total_pct}% (máximo 100%)")
        if total_pct <= 0:
            raise _err("Los beneficiarios no tienen porcentaje asignado")
        destinatarios = list(benef)

    reglas = ReglasDB(db)

    # recálculo: se reemplaza lo anterior
    for t in db.exec(select(m.TramoRetroactivo).where(m.TramoRetroactivo.liquidacion_id == liq.id)).all():
        db.delete(t)
    for r in db.exec(select(m.Recibo).where(m.Recibo.liquidacion_id == liq.id)).all():
        for rc in db.exec(select(m.ReciboConcepto).where(m.ReciboConcepto.recibo_id == r.id)).all():
            db.delete(rc)
        db.delete(r)
    db.flush()

    anticipo_total = Decimal(str(liq.anticipo_importe))
    suma_pct = sum((Decimal(str(b.porcentaje)) for b in destinatarios if b), Decimal(0))
    ids_concepto = {c.codigo: c.id for c in reglas.conceptos.values()}
    tot_credito = tot_deb = tot_liq = Decimal(0)
    for n, b in enumerate(destinatarios, start=1):
        d_b, h_b = desde, hasta
        if b is not None:
            if b.fecha_alta and b.fecha_alta > d_b:
                d_b = b.fecha_alta
            if b.fecha_baja and b.fecha_baja < h_b:
                h_b = b.fecha_baja
            if h_b < d_b:
                continue  # el beneficiario no percibe en el rango
            anticipo = anticipo_total * Decimal(str(b.porcentaje)) / suma_pct if len(destinatarios) > 1 else anticipo_total
        else:
            anticipo = anticipo_total
        r = calcular_recibo(reglas, liq, causante, cargos, b, d_b, h_b, anticipo)
        recibo = m.Recibo(
            liquidacion_id=liq.id, beneficiario_id=b.id if b else None, numero=n,
            total_remunerativo=q(r["credito"], Q2), total_no_remunerativo=Decimal(0),
            total_descuento=q(r["descuentos"], Q2), total_contribucion=Decimal(0),
            sueldo_bruto=q(r["credito"], Q2), sueldo_neto=q(r["liquido"], Q2),
            snapshot=_json_safe({
                "causante": {"id": causante.id, "dni": causante.dni, "apellido": causante.apellido, "nombre": causante.nombre,
                             "expediente": causante.expediente, "tipo_personal": causante.tipo_personal},
                "beneficiario": None if b is None else {"id": b.id, "apellido": b.apellido, "nombre": b.nombre, "dni": b.dni,
                                                        "parentesco": b.parentesco, "porcentaje": b.porcentaje, "art37": b.art37},
                "cargos": [{k: getattr(c, k) for k in m.CargoSecuenciaBase.model_fields if k != "causante_id"} for c in cargos],
                "haber_ponderado_actual": r["haber_ponderado"],
                "totales_cargos_actual": r["totales_cargos"],
                "rango": {"desde": d_b, "hasta": h_b},
                "haber_mensual_actual": r["haber_actual"],
                "anticipo": anticipo,
            }),
        )
        db.add(recibo)
        db.flush()
        for f in r["tramos"]:
            db.add(m.TramoRetroactivo(
                liquidacion_id=liq.id, beneficiario_id=b.id if b else None,
                fecha_desde=f["desde"], fecha_hasta=f["hasta"], haber_mensual=q(f["haber_mensual"]), meses=q(f["meses"]),
                importe=q(f["importe"]), sac=q(f["sac"]), descripcion=f["descripcion"]))
        grupos = [(sec, res) for sec, res in r["detalle_haber"]] + [(None, r["detalle_beneficio"]), (None, r["detalle_liquidacion"])]
        for sec, res in grupos:
            for c in res["conceptos"]:
                if not c["condicion"]:
                    continue
                db.add(m.ReciboConcepto(
                    recibo_id=recibo.id, concepto_id=ids_concepto.get(c["codigo"]), secuencia=sec, codigo=c["codigo"],
                    descripcion=c["descripcion"], columna=c["columna"],
                    unidad=None if c["unidad"] is None else Decimal(c["unidad"]), importe=q(Decimal(c["importe"])),
                    condicion=True, warning=False, error=False, message=None))
        tot_credito += r["credito"]
        tot_deb += r["descuentos"]
        tot_liq += r["liquido"]

    liq.total_credito, liq.total_debitos, liq.total_liquido = q(tot_credito, Q2), q(tot_deb, Q2), q(tot_liq, Q2)
    liq.calculada_at = datetime.now(timezone.utc)
    db.add(liq)
    db.commit()
    db.refresh(liq)
    return liq
