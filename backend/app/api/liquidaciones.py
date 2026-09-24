"""Acciones sobre liquidaciones: calcular, cerrar/reabrir y consultar el resumen."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlmodel import Session

from app.core.deps import require_permissions
from app.db.database import get_db
from app.models.models import User
from app.models.prevision import Liquidacion
from app.services.audit_service import audit_service
from app.services.liquidador import calcular_liquidacion
from app.services.reportes import a_pdf, a_xlsx
from app.services.resumen import armar_resumen

router = APIRouter()


def _audit(db: Session, request: Request, user: User, action: str, liq_id: int, data: dict) -> None:
    audit_service.log(
        db, action=action, resource="liquidaciones", resource_id=liq_id, user_id=user.id, username=user.username,
        after_data=json.dumps(data, default=str), ip=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None), user_agent=request.headers.get("user-agent"),
    )


def _get(db: Session, liq_id: int) -> Liquidacion:
    liq = db.get(Liquidacion, liq_id)
    if liq is None:
        raise HTTPException(status_code=404, detail="Liquidación no encontrada")
    return liq


@router.post("/{liq_id}/calcular")
def calcular(
    liq_id: int, request: Request, db: Session = Depends(get_db),
    user: User = Depends(require_permissions(["liquidaciones:update"])),
):
    """Calcula (o recalcula, si está ABIERTA) recibos, tramos retroactivos, SAC y descuentos."""
    liq = calcular_liquidacion(db, liq_id, user.id)
    _audit(db, request, user, "calculate", liq.id, {"credito": liq.total_credito, "debitos": liq.total_debitos, "liquido": liq.total_liquido})
    return armar_resumen(db, liq_id)


@router.post("/{liq_id}/cerrar")
def cerrar(
    liq_id: int, request: Request, db: Session = Depends(get_db),
    user: User = Depends(require_permissions(["liquidaciones:update"])),
):
    """Cierra la liquidación: queda inmutable. Debe estar calculada."""
    liq = _get(db, liq_id)
    if liq.estado == "CERRADA":
        raise HTTPException(status_code=409, detail="La liquidación ya está CERRADA")
    if liq.calculada_at is None:
        raise HTTPException(status_code=409, detail="La liquidación todavía no fue calculada")
    liq.estado = "CERRADA"
    db.add(liq)
    db.commit()
    _audit(db, request, user, "close", liq.id, {"estado": "CERRADA", "liquido": liq.total_liquido})
    return armar_resumen(db, liq_id)


@router.post("/{liq_id}/reabrir")
def reabrir(
    liq_id: int, request: Request, db: Session = Depends(get_db),
    user: User = Depends(require_permissions(["liquidaciones:delete"])),
):
    """Reabre una liquidación CERRADA (requiere el permiso de eliminación: solo administradores)."""
    liq = _get(db, liq_id)
    if liq.estado != "CERRADA":
        raise HTTPException(status_code=409, detail="La liquidación no está CERRADA")
    liq.estado = "ABIERTA"
    db.add(liq)
    db.commit()
    _audit(db, request, user, "reopen", liq.id, {"estado": "ABIERTA"})
    return armar_resumen(db, liq_id)


@router.get("/{liq_id}/resumen")
def resumen(
    liq_id: int, db: Session = Depends(get_db),
    user: User = Depends(require_permissions(["liquidaciones:read"])),
):
    return armar_resumen(db, liq_id)


def _exigir_calculada(res: dict) -> None:
    if not res["liquidacion"]["calculada_at"]:
        raise HTTPException(status_code=409, detail="La liquidación todavía no fue calculada")


@router.get("/{liq_id}/planilla.xlsx")
def planilla_xlsx(
    liq_id: int, db: Session = Depends(get_db),
    user: User = Depends(require_permissions(["liquidaciones:read"])),
):
    res = armar_resumen(db, liq_id)
    _exigir_calculada(res)
    nombre = f"liquidacion_{res['liquidacion']['periodo']}_{liq_id}.xlsx"
    return Response(
        a_xlsx(res), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/{liq_id}/planilla.pdf")
def planilla_pdf(
    liq_id: int, db: Session = Depends(get_db),
    user: User = Depends(require_permissions(["liquidaciones:read"])),
):
    res = armar_resumen(db, liq_id)
    _exigir_calculada(res)
    nombre = f"liquidacion_{res['liquidacion']['periodo']}_{liq_id}.pdf"
    return Response(a_pdf(res), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
