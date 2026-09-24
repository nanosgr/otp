from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlmodel import Session

from app.db.database import get_db
from app.services.crud import user_service
from app.services.password_reset_service import password_reset_service
from app.services.email_service import email_service
from app.services.audit_service import audit_service
from app.schemas.schemas import PasswordResetRequest, PasswordResetConfirm
from app.core.limiter import limiter
from app.core.config import settings

router = APIRouter()

# Generic response used for both found and not-found cases to prevent user enumeration
_GENERIC_RESPONSE = {
    "message": "Si el usuario existe, recibirá un correo con instrucciones."
}


def _meta(request: Request) -> tuple:
    """Extract request metadata (request_id, user-agent, client IP) from the request."""
    return (
        getattr(request.state, "request_id", None),
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )


@router.post("/password-reset/request")
@limiter.limit(settings.RATE_LIMIT_RESET_REQUEST)
async def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Initiate a password-reset flow.

    Always returns the same generic response regardless of whether the
    identifier maps to a real user (anti-enumeration protection).
    The actual email is dispatched as a BackgroundTask.
    """
    rid, ua, ip = _meta(request)

    # Try to resolve by email first, then by username
    user = user_service.get_user_by_email(db, email=body.identifier)
    if user is None:
        user = user_service.get_user_by_username(db, username=body.identifier)

    if user is None or not user.is_active:
        audit_service.log_failure(
            db,
            action="password_reset_request",
            resource="auth",
            details=f"Reset request for unknown/inactive identifier: {body.identifier}",
            ip=ip,
            request_id=rid,
            user_agent=ua,
        )
        return _GENERIC_RESPONSE

    raw_token = password_reset_service.create_token(db, user, ip=ip)
    background_tasks.add_task(
        email_service.send_password_reset,
        to_email=user.email,
        username=user.username,
        reset_token=raw_token,
    )
    audit_service.log(
        db,
        action="password_reset_request",
        resource="auth",
        user_id=user.id,
        username=user.username,
        ip=ip,
        request_id=rid,
        user_agent=ua,
    )
    return _GENERIC_RESPONSE


@router.post("/password-reset/confirm")
@limiter.limit(settings.RATE_LIMIT_RESET_CONFIRM)
async def confirm_password_reset(
    request: Request,
    body: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """
    Consume a one-time reset token and update the user's password.

    On success, token_version is incremented which invalidates all
    currently active JWTs for that user.
    """
    rid, ua, ip = _meta(request)

    token = password_reset_service.get_valid_token(db, body.token)
    if token is None:
        audit_service.log_failure(
            db,
            action="password_reset_confirm",
            resource="auth",
            details="Invalid or expired reset token",
            ip=ip,
            request_id=rid,
            user_agent=ua,
        )
        raise HTTPException(status_code=400, detail="Token inválido o expirado.")

    user = password_reset_service.use_token(db, token, body.new_password)
    audit_service.log(
        db,
        action="password_reset_confirm",
        resource="auth",
        user_id=user.id,
        username=user.username,
        ip=ip,
        request_id=rid,
        user_agent=ua,
    )
    return {
        "message": "Contraseña actualizada correctamente. Iniciá sesión con tu nueva contraseña."
    }
