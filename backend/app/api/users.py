import json
from math import ceil
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session
from app.db.database import get_db
from app.services.crud import user_service, user_scope_service
from app.services.audit_service import audit_service
from app.models.models import User, UserRead, UserCreate, UserUpdate
from app.schemas.schemas import (
    UserRoleAssignment, PaginatedResponse, UserProfileUpdate, PasswordChange,
    UserScopeAssignment,
)
from app.core.deps import (
    get_current_active_user,
    require_user_read,
    require_user_create,
    require_user_update,
    require_user_delete,
    has_permission,
)

router = APIRouter()


def _get_request_meta(request: Request) -> tuple:
    rid = getattr(request.state, "request_id", None)
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return rid, ua, ip


@router.get("/", response_model=PaginatedResponse[UserRead])
def read_users(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=1000),
    search: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_read()),
):
    total = user_service.count_users(db, search=search, is_active=is_active)
    items = user_service.get_users(db, skip=(page - 1) * size, limit=size, search=search, is_active=is_active)
    user_reads = [UserRead.model_validate(u) for u in items]
    return PaginatedResponse(items=user_reads, total=total, page=page, size=size, pages=ceil(total / size) if total else 1)


@router.post("/", response_model=UserRead)
def create_user(
    request: Request,
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_create()),
):
    if user_service.get_user_by_username(db, username=user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    if user_service.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    result = user_service.create_user(db=db, user=user, created_by=current_user.id)
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="create", resource="user", resource_id=result.id,
                      user_id=current_user.id, username=current_user.username, subject_id=result.id,
                      after_data=json.dumps({"username": result.username, "email": result.email}),
                      ip=ip, request_id=rid, user_agent=ua)
    return result


@router.get("/me", response_model=UserRead)
def read_user_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.put("/me", response_model=UserRead)
def update_user_me(
    request: Request,
    profile_update: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if profile_update.email:
        existing = user_service.get_user_by_email(db, email=profile_update.email)
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="Email already taken")
    before = json.dumps({"email": current_user.email, "full_name": current_user.full_name})
    update = UserUpdate(**profile_update.model_dump(exclude_unset=True))
    result = user_service.update_user(db, current_user.id, update)
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="update", resource="user", resource_id=current_user.id,
                      user_id=current_user.id, username=current_user.username, subject_id=current_user.id,
                      before_data=before,
                      after_data=json.dumps(profile_update.model_dump(exclude_unset=True)),
                      ip=ip, request_id=rid, user_agent=ua)
    return result


@router.put("/me/password")
def change_password_me(
    request: Request,
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not user_service.change_password(db, current_user.id, password_data.current_password, password_data.new_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="password_change", resource="user", resource_id=current_user.id,
                      user_id=current_user.id, username=current_user.username, subject_id=current_user.id,
                      ip=ip, request_id=rid, user_agent=ua)
    return {"message": "Password updated successfully"}


@router.get("/me/scopes")
def read_my_scopes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    items = user_scope_service.list_for_user(db, current_user.id)
    return {"items": [{"dimension": s.dimension, "value": s.value} for s in items]}


@router.get("/{user_id}/scopes")
def read_user_scopes(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_read()),
):
    if user_service.get_user(db, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    items = user_scope_service.list_for_user(db, user_id)
    return {"items": [{"dimension": s.dimension, "value": s.value} for s in items]}


@router.put("/{user_id}/scopes")
def set_user_scopes(
    request: Request,
    user_id: int,
    assignment: UserScopeAssignment,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_update()),
):
    if user_service.get_user(db, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    items = user_scope_service.replace_for_user(db, user_id, assignment.items)
    payload = [{"dimension": s.dimension, "value": s.value} for s in items]
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="set_scopes", resource="user", resource_id=user_id,
                      user_id=current_user.id, username=current_user.username, subject_id=user_id,
                      after_data=json.dumps(payload),
                      ip=ip, request_id=rid, user_agent=ua)
    return {"items": payload}


@router.get("/{user_id}", response_model=UserRead)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    db_user = user_service.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    allowed = has_permission(
        current_user, "users", "read", db=db,
        context={"resource_owner_id": db_user.id},
    )
    if not allowed and db_user.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied. Required: users:read")
    return db_user


@router.put("/{user_id}", response_model=UserRead)
def update_user(
    request: Request,
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    target = user_service.get_user(db, user_id=user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    allowed = has_permission(
        current_user, "users", "update", db=db,
        context={"resource_owner_id": target.id},
    )
    if not allowed and target.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied. Required: users:update")
    if user_update.username:
        existing = user_service.get_user_by_username(db, username=user_update.username)
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Username already taken")
    if user_update.email:
        existing = user_service.get_user_by_email(db, email=user_update.email)
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Email already taken")
    before = json.dumps({"username": target.username, "email": target.email,
                         "full_name": target.full_name, "is_active": target.is_active})
    result = user_service.update_user(db, user_id, user_update)
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="update", resource="user", resource_id=user_id,
                      user_id=current_user.id, username=current_user.username, subject_id=user_id,
                      before_data=before,
                      after_data=json.dumps(user_update.model_dump(exclude_unset=True, exclude={"password"})),
                      ip=ip, request_id=rid, user_agent=ua)
    return result


@router.delete("/{user_id}")
def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_delete()),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own user account")
    target = user_service.get_user(db, user_id)
    before = json.dumps({"username": target.username if target else None})
    if not user_service.delete_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="delete", resource="user", resource_id=user_id,
                      user_id=current_user.id, username=current_user.username, subject_id=user_id,
                      before_data=before,
                      ip=ip, request_id=rid, user_agent=ua)
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/roles", response_model=UserRead)
def assign_roles_to_user(
    request: Request,
    user_id: int,
    role_assignment: UserRoleAssignment,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_update()),
):
    if role_assignment.user_id != user_id:
        raise HTTPException(status_code=400, detail="User ID in path and body must match")
    target = user_service.get_user(db, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    before = json.dumps({"role_ids": [r.id for r in target.roles]})
    updated_user = user_service.assign_roles_to_user(db, user_id, role_assignment.role_ids)
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="assign_roles", resource="user", resource_id=user_id,
                      user_id=current_user.id, username=current_user.username, subject_id=user_id,
                      before_data=before,
                      after_data=json.dumps({"role_ids": role_assignment.role_ids}),
                      ip=ip, request_id=rid, user_agent=ua)
    return updated_user
