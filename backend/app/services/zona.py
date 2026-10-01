"""Anexo de zona inhóspita / desfavorable: % de zona a partir de los destinos del causante.

Por destino: días = hasta − desde, años = días / 365, años de permanencia = parte entera, porc = % de zona / divisor
(25 subalterno, 30 superior) y resultado = porc × años de permanencia. El total se redondea a 2 decimales (como
fracción: 0,0267 → 0,03 = 3%); si el total no llega al 1% el suplemento no se paga.
"""
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Dict, Iterable, List, Optional

DIVISOR = {"subalterno": 25, "superior": 30}
MINIMO = Decimal("0.01")


def calcular_zona(destinos: Iterable, tipo_personal: str, hasta_defecto: Optional[date] = None) -> Optional[Dict]:
    """Filas del anexo y % aplicado (0-100). None si el causante no tiene destinos cargados."""
    divisor = DIVISOR.get(tipo_personal, 30)
    filas: List[Dict] = []
    total = Decimal(0)
    for z in sorted(destinos, key=lambda z: z.fecha_desde):
        hasta = z.fecha_hasta or hasta_defecto or date.today()
        dias = max((hasta - z.fecha_desde).days, 0)
        anios = Decimal(dias) / Decimal(365)
        perm = int(anios.to_integral_value(rounding=ROUND_FLOOR))
        zona = Decimal(str(z.porcentaje_zona)) / Decimal(100)
        porc = zona / Decimal(divisor)
        final = porc * perm
        total += final
        filas.append({
            "desde": z.fecha_desde, "hasta": hasta, "dependencia": z.dependencia, "dias": dias,
            "anios": anios.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "zona": zona, "divisor": divisor,
            "porc": porc.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "anios_permanencia": perm,
            "porc_final": final.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        })
    if not filas:
        return None
    aplicado = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total >= MINIMO else Decimal(0)
    return {
        "filas": filas,
        "total": total.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        "aplicado": aplicado,
        "porcentaje_aplicado": aplicado * 100,   # 0-100, lo que recibe el motor como ZONA_PORC
        "alcanza_minimo": total >= MINIMO,
        "divisor": divisor,
    }
