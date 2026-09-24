"""Acceso al motor de fórmulas en Rust (`otp_engine`, compilado con maturin).

El motor es puro: recibe reglas y un contexto ya cargado y devuelve conceptos calculados.
Los Decimal y las fechas se envían tipados (`{"decimal": ".."}` / `{"date": ".."}`) para no
perder precisión ni confundir un texto numérico con un número.
"""
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

try:
    import otp_engine as _engine
except ImportError:  # el backend arranca aunque el motor no esté instalado
    _engine = None

FormulaError = _engine.FormulaError if _engine else ValueError


class MotorNoDisponible(RuntimeError):
    pass


def _motor():
    if _engine is None:
        raise MotorNoDisponible(
            "El motor de fórmulas no está instalado: cd engine/otp-formula-py && maturin develop --release"
        )
    return _engine


def _default(o: Any) -> Any:
    if isinstance(o, Decimal):
        return {"decimal": str(o)}
    if isinstance(o, datetime):
        return {"date": o.date().isoformat()}
    if isinstance(o, date):
        return {"date": o.isoformat()}
    raise TypeError(f"No se puede enviar al motor un valor de tipo {type(o).__name__}")


def _dumps(obj: Any) -> str:
    return json.dumps(obj, default=_default, ensure_ascii=False)


def version() -> str:
    return _motor().__version__


def calcular(reglas: Dict[str, Any], contexto: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula conceptos y totales. Los importes vuelven como str (usar Decimal en el llamador)."""
    return json.loads(_motor().calcular(_dumps(reglas), _dumps(contexto)))


def validar_reglas(reglas: Dict[str, Any], variables_conocidas: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    known = list(variables_conocidas) if variables_conocidas is not None else None
    return json.loads(_motor().validar_reglas(_dumps(reglas), known))


def validar_formula(formula: str, auxiliares: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Devuelve lo que referencia la fórmula; lanza FormulaError si es inválida."""
    return json.loads(_motor().validar_formula(formula, _dumps(auxiliares or [])))
