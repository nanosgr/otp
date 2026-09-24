import json
from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session
from app.db.database import get_db
from app.services.crud import permission_service
from app.services.audit_service import audit_service
from app.models.models import User, PermissionRead, PermissionCreate, PermissionUpdate
from app.schemas.schemas import PaginatedResponse
from app.api.prevision import RECURSOS_DOMINIO
from app.core.deps import (
    require_permission_read,
    require_permission_create,
    require_permission_update,
    require_permission_delete,
)

router = APIRouter()


def _get_request_meta(request: Request) -> tuple:
    rid = getattr(request.state, "request_id", None)
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return rid, ua, ip


@router.get("/", response_model=PaginatedResponse[PermissionRead])
def read_permissions(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=1000),
    search: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    resource: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission_read()),
):
    total = permission_service.count_permissions(db, search=search, is_active=is_active, resource=resource, action=action)
    items = permission_service.get_permissions(db, skip=(page - 1) * size, limit=size, search=search, is_active=is_active, resource=resource, action=action)
    return PaginatedResponse(items=items, total=total, page=page, size=size, pages=ceil(total / size) if total else 1)


@router.post("/", response_model=PermissionRead)
def create_permission(
    request: Request,
    permission: PermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission_create()),
):
    if permission_service.get_permission_by_name(db, name=permission.name):
        raise HTTPException(status_code=400, detail="Permission name already exists")
    result = permission_service.create_permission(db=db, permission=permission)
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="create", resource="permission", resource_id=result.id,
                      user_id=current_user.id, username=current_user.username,
                      after_data=json.dumps({"name": result.name, "resource": result.resource, "action": result.action}),
                      ip=ip, request_id=rid, user_agent=ua)
    return result


@router.get("/resources/available")
def get_available_resources(current_user: User = Depends(require_permission_read())):
    return {"resources": ["users", "roles", "permissions", "dashboard", "reports", "settings", "audit", *RECURSOS_DOMINIO]}


@router.get("/actions/available")
def get_available_actions(current_user: User = Depends(require_permission_read())):
    return {"actions": ["create", "read", "update", "delete", "list", "export"]}


@router.get("/{permission_id}", response_model=PermissionRead)
def read_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission_read()),
):
    db_permission = permission_service.get_permission(db, permission_id=permission_id)
    if db_permission is None:
        raise HTTPException(status_code=404, detail="Permission not found")
    return db_permission


@router.put("/{permission_id}", response_model=PermissionRead)
def update_permission(
    request: Request,
    permission_id: int,
    permission_update: PermissionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission_update()),
):
    target = permission_service.get_permission(db, permission_id=permission_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Permission not found")
    if permission_update.name:
        existing = permission_service.get_permission_by_name(db, name=permission_update.name)
        if existing and existing.id != permission_id:
            raise HTTPException(status_code=400, detail="Permission name already exists")
    before = json.dumps({"name": target.name, "resource": target.resource, "action": target.action, "is_active": target.is_active})
    result = permission_service.update_permission(db, permission_id, permission_update)
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="update", resource="permission", resource_id=permission_id,
                      user_id=current_user.id, username=current_user.username,
                      before_data=before,
                      after_data=json.dumps(permission_update.model_dump(exclude_unset=True)),
                      ip=ip, request_id=rid, user_agent=ua)
    return result


@router.delete("/{permission_id}")
def delete_permission(
    request: Request,
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission_delete()),
):
    target = permission_service.get_permission(db, permission_id)
    before = json.dumps({"name": target.name if target else None})
    if not permission_service.delete_permission(db, permission_id):
        raise HTTPException(status_code=404, detail="Permission not found")
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="delete", resource="permission", resource_id=permission_id,
                      user_id=current_user.id, username=current_user.username,
                      before_data=before,
                      ip=ip, request_id=rid, user_agent=ua)
    return {"message": "Permission deleted successfully"}
