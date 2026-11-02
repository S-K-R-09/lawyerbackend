import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.errors import AppError, conflict, unauthorized, validation_error
from app.core.security import (
    create_token,
    decode_token,
    dummy_verify,
    hash_password,
    sha256_hex,
    verify_password,
)
from app.models import RefreshToken
from app.models import User, UserSettings
from app.schemas import RegisterIn, TokenOut

BAD_CREDENTIALS = "Incorrect email or password."


def register(db: Session, data: RegisterIn) -> User:
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise conflict(
            "An account with this email already exists.", {"email": "Already registered."}
        )
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        enrollment_number=data.enrollment_number,
        timezone=get_settings().DEFAULT_TIMEZONE,
    )
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id))
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent duplicate
        db.rollback()
        raise conflict(
            "An account with this email already exists.", {"email": "Already registered."}
        ) from exc
    return user


def _issue_tokens(
    db: Session, user: User, family_id: uuid.UUID | None, user_agent: str | None
) -> tuple[TokenOut, RefreshToken]:
    access, _ = create_token(user.id, "access")
    refresh, refresh_exp = create_token(user.id, "refresh")
    row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=sha256_hex(refresh),
        family_id=family_id or uuid.uuid4(),
        expires_at=refresh_exp,
        user_agent=(user_agent or "")[:300] or None,
    )
    db.add(row)
    return TokenOut(access_token=access, refresh_token=refresh), row


def login(db: Session, email: str, password: str, user_agent: str | None) -> TokenOut:
    s = get_settings()
    now = now_utc()
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email).with_for_update())

    if user is None:
        dummy_verify(password)  # keep timing similar for unknown emails
        raise unauthorized(BAD_CREDENTIALS)

    if user.locked_until and user.locked_until > now:
        db.rollback()
        minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise AppError(
            429,
            "rate_limited",
            f"Too many failed attempts. Try again in about {minutes} minutes.",
            headers={"Retry-After": str(minutes * 60)},
        )

    if not verify_password(password, user.password_hash) or not user.is_active:
        user.failed_login_count += 1
        if user.failed_login_count >= s.MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=s.LOCKOUT_MINUTES)
            user.failed_login_count = 0
        db.commit()  # persist the counter before answering
        raise unauthorized(BAD_CREDENTIALS)

    user.failed_login_count = 0
    user.locked_until = None
    tokens, _ = _issue_tokens(db, user, None, user_agent)
    db.commit()
    return tokens


def _revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )


def refresh(db: Session, token: str, user_agent: str | None) -> TokenOut:
    invalid = unauthorized("Invalid or expired refresh token.")
    claims = decode_token(token, "refresh")
    if claims is None:
        raise invalid
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(token)).with_for_update()
    )
    if row is None:
        raise invalid
    if row.revoked_at is not None:
        # A revoked token came back: assume theft and kill the whole family.
        _revoke_family(db, row.family_id)
        db.commit()
        raise invalid
    now = now_utc()
    user = db.get(User, row.user_id)
    if row.expires_at <= now or user is None or not user.is_active:
        raise invalid
    tokens, new_row = _issue_tokens(db, user, row.family_id, user_agent)
    row.revoked_at = now
    row.replaced_by = new_row.id
    db.commit()
    return tokens


def logout(db: Session, user: User, token: str) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(token)))
    if row is not None and row.user_id == user.id:
        _revoke_family(db, row.family_id)
        db.commit()


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise validation_error(
            "Current password is incorrect.", {"current_password": "Current password is incorrect."}
        )
    user.password_hash = hash_password(new)
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )
    db.commit()
