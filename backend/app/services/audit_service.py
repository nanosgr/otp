from datetime import datetime
from typing import Optional
from sqlmodel import Session, select, func
from app.models.models import AuditLog


class AuditService:
    def log(
        self,
        db: Session,
        action: str,
        resource: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[str] = None,
        ip: Optional[str] = None,
        request_id: Optional[str] = None,
        status: str = "success",
        before_data: Optional[str] = None,
        after_data: Optional[str] = None,
        subject_id: Optional[int] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=ip,
            request_id=request_id,
            status=status,
            before_data=before_data,
            after_data=after_data,
            subject_id=subject_id,
            user_agent=user_agent,
        )
        db.add(entry)
        db.commit()

    def log_failure(
        self,
        db: Session,
        action: str,
        resource: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        resource_id: Optional[int] = None,
        details: Optional[str] = None,
        ip: Optional[str] = None,
        request_id: Optional[str] = None,
        subject_id: Optional[int] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self.log(
            db=db,
            action=action,
            resource=resource,
            user_id=user_id,
            username=username,
            resource_id=resource_id,
            details=details,
            ip=ip,
            request_id=request_id,
            status="failure",
            subject_id=subject_id,
            user_agent=user_agent,
        )

    def get_logs(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 50,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ):
        query = select(AuditLog)
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource:
            query = query.where(AuditLog.resource == resource)
        if status:
            query = query.where(AuditLog.status == status)
        if from_date:
            query = query.where(AuditLog.timestamp >= from_date)
        if to_date:
            query = query.where(AuditLog.timestamp <= to_date)
        return db.exec(query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)).all()

    def count_logs(
        self,
        db: Session,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> int:
        query = select(func.count(AuditLog.id))
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource:
            query = query.where(AuditLog.resource == resource)
        if status:
            query = query.where(AuditLog.status == status)
        if from_date:
            query = query.where(AuditLog.timestamp >= from_date)
        if to_date:
            query = query.where(AuditLog.timestamp <= to_date)
        return db.exec(query).one()


audit_service = AuditService()
