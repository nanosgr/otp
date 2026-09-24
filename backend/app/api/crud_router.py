"""Fábrica de routers CRUD para los recursos del dominio previsional."""
import json
from datetime import datetime
from math import ceil
from typing import Any, Callable, Dict, Optional, Sequence, Type

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError, create_model
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from app.core.deps import require_permissions
from app.db.database import get_db
from app.models.models import User
from app.schemas.schemas import PaginatedResponse
from app.services.audit_service import audit_service

Guard = Callable[[Session, Any, str], None]
Validator = Callable[[Session, dict, Optional[int]], None]


def _dump(obj: Any) -> str:
    data = obj.model_dump() if hasattr(obj, "model_dump") else dict(obj)
    return json.dumps(data, default=str)


def make_crud_router(
    *,
    resource: str,
    table: Type[SQLModel],
    base: Type[SQLModel],
    search_fields: Sequence[str] = (),
    filter_fields: Sequence[str] = (),
    order_by: Sequence[str] = ("id",),
    guard: Optional[Guard] = None,
    validate: Optional[Validator] = None,
    read_extra: Optional[Dict[str, Any]] = None,
) -> APIRouter:
    """Crea un router con list/get/create/update/delete protegido por `<resource>:<acción>`.

    `guard(db, obj, action)` puede lanzar HTTPException para vetar update/delete
    (p. ej. liquidaciones cerradas). `validate(db, datos, id)` valida el registro resultante
    antes de guardar en create/update (p. ej. fórmulas de conceptos).
    """
    router = APIRouter()
    name = table.__name__

    read_model = create_model(
        f"{name}Read",
        __base__=base,
        id=(int, ...),
        created_at=(Optional[datetime], None),
        updated_at=(Optional[datetime], None),
        **(read_extra or {}),
    )

    def _order_clauses():
        return [getattr(table, f) for f in order_by]

    def _meta(request: Request):
        rid = getattr(request.state, "request_id", None)
        ua = request.headers.get("user-agent")
        ip = request.client.host if request.client else None
        return rid, ua, ip

    def _audit(db, request, user, action, obj_id, after=None, before=None):
        rid, ua, ip = _meta(request)
        audit_service.log(
            db, action=action, resource=resource, resource_id=obj_id,
            user_id=user.id, username=user.username,
            before_data=before, after_data=after,
            ip=ip, request_id=rid, user_agent=ua,
        )

    def _commit(db: Session):
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=f"Violación de integridad: {exc.orig}")

    @router.get("/", response_model=PaginatedResponse[read_model])
    def list_items(
        request: Request,
        page: int = Query(default=1, ge=1),
        size: int = Query(default=10, ge=1, le=1000),
        search: Optional[str] = Query(default=None),
        db: Session = Depends(get_db),
        current_user: User = Depends(require_permissions([f"{resource}:read"])),
    ):
        conds = []
        if search and search_fields:
            conds.append(or_(*[getattr(table, f).ilike(f"%{search}%") for f in search_fields]))
        for f in filter_fields:
            raw = request.query_params.get(f)
            if raw is not None and raw != "":
                col = getattr(table, f)
                try:
                    value = col.type.python_type(raw) if col.type.python_type is not bool else raw.lower() in ("1", "true")
                except (NotImplementedError, ValueError):
                    value = raw
                conds.append(col == value)
        total = db.exec(select(func.count()).select_from(table).where(*conds)).one()
        stmt = select(table).where(*conds).order_by(*_order_clauses()).offset((page - 1) * size).limit(size)
        items = [read_model.model_validate(o, from_attributes=True) for o in db.exec(stmt).all()]
        return PaginatedResponse(items=items, total=total, page=page, size=size, pages=ceil(total / size) if total else 1)

    @router.post("/", response_model=read_model, status_code=201)
    def create_item(
        request: Request,
        payload: base,  # type: ignore[valid-type]
        db: Session = Depends(get_db),
        current_user: User = Depends(require_permissions([f"{resource}:create"])),
    ):
        if validate:
            validate(db, payload.model_dump(), None)
        obj = table(**payload.model_dump())
        if hasattr(obj, "created_by") and getattr(obj, "created_by", None) is None:
            obj.created_by = current_user.id
        db.add(obj)
        _commit(db)
        db.refresh(obj)
        _audit(db, request, current_user, "create", obj.id, after=_dump(obj))
        return obj

    @router.get("/{item_id}", response_model=read_model)
    def get_item(
        item_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_permissions([f"{resource}:read"])),
    ):
        obj = db.get(table, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{name} no encontrado")
        return obj

    @router.put("/{item_id}", response_model=read_model)
    def update_item(
        item_id: int,
        request: Request,
        payload: dict[str, Any],
        db: Session = Depends(get_db),
        current_user: User = Depends(require_permissions([f"{resource}:update"])),
    ):
        obj = db.get(table, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{name} no encontrado")
        if guard:
            guard(db, obj, "update")
        editable = set(base.model_fields)
        changes = {k: v for k, v in payload.items() if k in editable}
        current = {k: getattr(obj, k) for k in editable}
        try:
            merged = base.model_validate({**current, **changes})
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=json.loads(exc.json()))
        if validate:
            validate(db, merged.model_dump(), obj.id)
        before = _dump(obj)
        for k in changes:
            setattr(obj, k, getattr(merged, k))
        db.add(obj)
        _commit(db)
        db.refresh(obj)
        _audit(db, request, current_user, "update", obj.id, after=_dump(obj), before=before)
        return obj

    @router.delete("/{item_id}", status_code=204)
    def delete_item(
        item_id: int,
        request: Request,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_permissions([f"{resource}:delete"])),
    ):
        obj = db.get(table, item_id)
        if obj is None:
            raise HTTPException(status_code=404, detail=f"{name} no encontrado")
        if guard:
            guard(db, obj, "delete")
        before, obj_id = _dump(obj), obj.id
        db.delete(obj)
        _commit(db)
        _audit(db, request, current_user, "delete", obj_id, before=before)

    return router
