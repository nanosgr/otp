import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models.models import PasswordResetToken, User
from app.core.security import get_password_hash
from app.core.config import settings


def _hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(token.encode()).hexdigest()


class PasswordResetService:
    def create_token(self, db: Session, user: User, ip: Optional[str] = None) -> str:
        """
        Invalidate any pending reset tokens for the user, create a new one,
        persist its hash, and return the raw (unhashed) token.
        """
        # Invalidate existing unused tokens for this user
        old_tokens = db.exec(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id)
            .where(PasswordResetToken.used == False)  # noqa: E712
        ).all()
        for t in old_tokens:
            db.delete(t)

        # Generate a new cryptographically-strong token (256 bits entropy)
        raw_token = secrets.token_urlsafe(32)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
            ip_requested=ip,
        )
        db.add(reset_token)
        db.commit()
        return raw_token

    def get_valid_token(
        self, db: Session, raw_token: str
    ) -> Optional[PasswordResetToken]:
        """
        Look up a token by its hash and verify it has not been used and has not expired.
        Returns the ORM object or None.
        """
        token = db.exec(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == _hash_token(raw_token))
            .where(PasswordResetToken.used == False)  # noqa: E712
        ).first()
        if token is None:
            return None

        # Ensure the expiry datetime is timezone-aware for comparison
        expires = token.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires:
            return None

        return token

    def use_token(
        self, db: Session, token: PasswordResetToken, new_password: str
    ) -> User:
        """
        Mark the token as used, hash and store the new password, and bump
        token_version so that all existing JWTs for the user are invalidated.
        """
        token.used = True
        token.used_at = datetime.now(timezone.utc)

        user = db.get(User, token.user_id)
        user.hashed_password = get_password_hash(new_password)
        user.token_version += 1

        db.add(token)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


password_reset_service = PasswordResetService()
