from math import ceil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from app.db.database import get_db
from app.models.models import User
from app.schemas.schemas import AuditLogRead, PaginatedResponse
from app.services.audit_service import audit_service
from app.core.deps import require_permissions

router = APIRouter()


@router.get("/logs", response_model=PaginatedResponse[AuditLogRead])
def get_audit_logs(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user_id: Optional[int] = Query(default=None),
    action: Optional[str] = Query(default=None),
    resource: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["audit:read"])),
):
    total = audit_service.count_logs(db, user_id=user_id, action=action, resource=resource,
                                     status=status, from_date=from_date, to_date=to_date)
    items = audit_service.get_logs(db, skip=(page - 1) * size, limit=size, user_id=user_id,
                                   action=action, resource=resource, status=status,
                                   from_date=from_date, to_date=to_date)
    return PaginatedResponse(items=items, total=total, page=page, size=size, pages=ceil(total / size) if total else 1)
