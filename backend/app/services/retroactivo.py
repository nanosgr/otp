"""Aritmética de fechas del retroactivo: tramos, meses comerciales (30 días) y SAC.

Reproduce la planilla de liquidación: cada tramo es (haber nominal) x (meses); tras cada semestre completo
(30/06 y 31/12) se agrega el SAC, que es la mitad del haber vigente al cierre del semestre.
"""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, List, Tuple

Tramo = Tuple[date, date]


def fin_de_mes(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def days360(d1: date, d2: date) -> int:
    """Días entre fechas con meses de 30 días (`d2` exclusivo)."""
    return (d2.year - d1.year) * 360 + (d2.month - d1.month) * 30 + (min(d2.day, 30) - min(d1.day, 30))


def meses(desde: date, hasta: date) -> Decimal:
    """Meses comerciales entre `desde` y `hasta` (ambos inclusive). Un mes calendario completo = 1."""
    if hasta < desde:
        return Decimal(0)
    return Decimal(days360(desde, hasta + timedelta(days=1))) / Decimal(30)


def dividir_en_tramos(desde: date, hasta: date, cortes: Iterable[date]) -> List[Tramo]:
    """Parte [desde, hasta] en tramos que empiezan en cada fecha de corte comprendida en (desde, hasta]."""
    puntos = sorted({c for c in cortes if desde < c <= hasta})
    inicios = [desde] + puntos
    return [(a, (inicios[i + 1] - timedelta(days=1)) if i + 1 < len(inicios) else hasta) for i, a in enumerate(inicios)]


def semestres_completos(desde: date, hasta: date) -> List[Tramo]:
    """(inicio_del_semestre, cierre) de cada semestre (30/06, 31/12) cuyo cierre cae dentro de [desde, hasta]."""
    out = []
    for anio in range(desde.year, hasta.year + 1):
        for inicio, cierre in ((date(anio, 1, 1), date(anio, 6, 30)), (date(anio, 7, 1), date(anio, 12, 31))):
            if desde <= cierre <= hasta:
                out.append((inicio, cierre))
    return out


def sac(haber_al_cierre: Decimal, desde: date, inicio_sem: date, cierre: date) -> Decimal:
    """SAC del semestre: 50% del haber al cierre, proporcional a los meses trabajados en el semestre (6 = completo)."""
    trabajados = meses(max(desde, inicio_sem), cierre)
    return haber_al_cierre / Decimal(2) * trabajados / Decimal(6)
