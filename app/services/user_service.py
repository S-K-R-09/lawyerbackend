from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import conflict
from app.models import User, UserSettings
from app.schemas import MeUpdate, SettingsUpdate


def update_profile(db: Session, user: User, data: MeUpdate) -> User:
    changes = data.model_dump(exclude_unset=True)
    if changes.get("full_name") is None:
        changes.pop("full_name", None)
    if changes.get("timezone") is None:
        changes.pop("timezone", None)
    email = changes.get("email")
    if email is None:
        changes.pop("email", None)
    elif email != user.email and db.scalar(select(User.id).where(User.email == email)):
        raise conflict("An account with this email already exists.", {"email": "Already in use."})
    for k, v in changes.items():
        setattr(user, k, v)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict(
            "An account with this email already exists.", {"email": "Already in use."}
        ) from exc
    return user


def get_settings_row(db: Session, user: User) -> UserSettings:
    row = db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    if row is None:  # defensive: users created outside register()
        row = UserSettings(user_id=user.id)
        db.add(row)
        db.flush()
    return row


def update_settings(db: Session, user: User, data: SettingsUpdate) -> UserSettings:
    row = get_settings_row(db, user)
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(row, k, v)
    db.commit()
    return row
