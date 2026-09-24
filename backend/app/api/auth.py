from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from app.db.database import get_db
from app.core.security import create_access_token, create_refresh_token, verify_refresh_token
from app.core.config import settings
from app.core.deps import get_current_active_user
from app.models.models import User
from app.services.crud import user_service
from app.services.audit_service import audit_service
from app.schemas.schemas import Token, RefreshTokenRequest
from app.core.limiter import limiter

router = APIRouter()


def _build_tokens(user: User) -> dict:
    token_data = {"sub": user.username, "token_version": user.token_version}
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(
        data=token_data,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


def _get_request_meta(request: Request) -> tuple:
    rid = getattr(request.state, "request_id", None)
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return rid, ua, ip


@router.post("/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    rid, ua, ip = _get_request_meta(request)
    user = user_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        audit_service.log_failure(db, action="login", resource="auth",
                                  details=f"Failed login attempt for username: {form_data.username}",
                                  ip=ip, request_id=rid, user_agent=ua)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    audit_service.log(db, action="login", resource="auth",
                      user_id=user.id, username=user.username,
                      ip=ip, request_id=rid, user_agent=ua)
    return _build_tokens(user)


@router.post("/refresh", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_REFRESH)
async def refresh_access_token(
    request: Request,
    body: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    rid, ua, ip = _get_request_meta(request)
    payload = verify_refresh_token(body.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = user_service.get_user_by_username(db, username=payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    if user.token_version != payload["token_version"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _build_tokens(user)


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    user_service.increment_token_version(db, current_user.id)
    rid, ua, ip = _get_request_meta(request)
    audit_service.log(db, action="logout", resource="auth",
                      user_id=current_user.id, username=current_user.username,
                      ip=ip, request_id=rid, user_agent=ua)
    return {"message": "Logged out successfully"}
