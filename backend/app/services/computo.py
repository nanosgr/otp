"""2. Cómputo de servicios: suma de años/meses/días (año de 360 días, mes de 30) y antigüedad final.

Filas (`ComputoServicio.concepto`): cuadro_servicio + hasta_renuncia = total de servicios; + servicios_adicionales +
beneficio_titulo = subtotal; − suspensiones = corresponde. Antigüedad final = años de "corresponde" + 1 si los meses son
6 o más (verificado en las 10 liquidaciones de renuncia condicionada).
"""
from typing import Dict, Iterable, Optional, Tuple

AMD = Tuple[int, int, int]

ETIQUETAS = {
    "cuadro_servicio": "Período cuadro de servicio",
    "hasta_renuncia": "Hasta renuncia condicionada",
    "servicios_adicionales": "Servicios adicionales",
    "beneficio_titulo": "Beneficio por título",
    "suspensiones": "Suspensiones",
}


def a_dias(a: int, m: int, d: int) -> int:
    return a * 360 + m * 30 + d


def de_dias(n: int) -> AMD:
    signo = -1 if n < 0 else 1
    n = abs(n)
    return signo * (n // 360), signo * (n % 360 // 30), signo * (n % 30)


def computo(filas: Iterable) -> Optional[Dict]:
    """Totales del cómputo a partir de las filas (objetos o dicts con concepto/anios/meses/dias). None si no hay filas."""
    suma: Dict[str, int] = {k: 0 for k in ETIQUETAS}
    hay = False
    for f in filas:
        g = (lambda k: f[k]) if isinstance(f, dict) else (lambda k: getattr(f, k))
        suma[g("concepto")] += a_dias(int(g("anios") or 0), int(g("meses") or 0), int(g("dias") or 0))
        hay = True
    if not hay:
        return None
    total = suma["cuadro_servicio"] + suma["hasta_renuncia"]
    subtotal = total + suma["servicios_adicionales"] + suma["beneficio_titulo"]
    corresponde = subtotal - abs(suma["suspensiones"])
    a, m, _ = de_dias(corresponde)
    return {
        "filas": {k: de_dias(v) for k, v in suma.items()},
        "total_servicios": de_dias(total),
        "subtotal": de_dias(subtotal),
        "corresponde": de_dias(corresponde),
        "antiguedad_final": a + (1 if m >= 6 else 0),
    }
