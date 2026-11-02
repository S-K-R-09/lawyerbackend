from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import CurrentUser, DbSession
from app.core.errors import ERROR_RESPONSES, ErrorResponse
from app.core.ratelimit import auth_limit, limiter
from app.schemas import (
    ChangePasswordIn,
    RefreshIn,
    RegisterIn,
    TokenOut,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a lawyer account (no tokens returned; the app then asks the user to log in)",
    responses={409: {"model": ErrorResponse, "description": "Email already registered"}},
)
@limiter.limit(auth_limit)
def register(request: Request, body: RegisterIn, db: DbSession):
    return auth_service.register(db, body)


@router.post(
    "/token",
    response_model=TokenOut,
    summary="Log in (OAuth2 password flow). `username` is the email.",
    responses={
        401: {"model": ErrorResponse, "description": "Incorrect email or password"},
        429: {"model": ErrorResponse, "description": "Rate limited or account temporarily locked"},
    },
)
@limiter.limit(auth_limit)
def token(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    return auth_service.login(db, form.username, form.password, request.headers.get("user-agent"))


@router.post(
    "/refresh",
    response_model=TokenOut,
    summary="Rotate a refresh token: the old one is revoked and a new pair is issued",
    responses={401: {"model": ErrorResponse, "description": "Invalid, expired or reused token"}},
)
@limiter.limit(auth_limit)
def refresh(request: Request, body: RefreshIn, db: DbSession):
    return auth_service.refresh(db, body.refresh_token, request.headers.get("user-agent"))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the refresh token family (Settings > Log out)",
    responses=ERROR_RESPONSES,
)
def logout(body: RefreshIn, user: CurrentUser, db: DbSession) -> None:
    auth_service.logout(db, user, body.refresh_token)

@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the current user's password",
    responses=ERROR_RESPONSES,
)
def change_password(
    body: ChangePasswordIn,
    user: CurrentUser,
    db: DbSession,
) -> None:
    auth_service.change_password(
        db,
        user,
        body.current_password,
        body.new_password,
    )