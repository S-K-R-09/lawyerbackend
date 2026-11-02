from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.core.errors import ERROR_RESPONSES
from app.schemas import (
    ChangePasswordIn,
    MeUpdate,
    SettingsOut,
    SettingsUpdate,
    UserOut,
)
from app.services import auth_service, user_service

router = APIRouter(prefix="/me", tags=["Me & Settings"], responses=ERROR_RESPONSES)


@router.get("", response_model=UserOut, summary="Current lawyer profile")
def get_me(user: CurrentUser):
    return user


@router.patch("", response_model=UserOut, summary="Edit name, email, enrollment number, timezone")
def patch_me(body: MeUpdate, user: CurrentUser, db: DbSession):
    return user_service.update_profile(db, user, body)


@router.get("/settings", response_model=SettingsOut, summary="Reminder settings")
def get_settings_(user: CurrentUser, db: DbSession):
    return user_service.get_settings_row(db, user)


@router.patch("/settings", response_model=SettingsOut, summary="Update reminder settings")
def patch_settings(body: SettingsUpdate, user: CurrentUser, db: DbSession):
    return user_service.update_settings(db, user, body)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password (revokes all refresh tokens)",
)
def change_password(body: ChangePasswordIn, user: CurrentUser, db: DbSession) -> None:
    auth_service.change_password(db, user, body.current_password, body.new_password)
