import uuid
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import unauthorized
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession, token: Annotated[str | None, Depends(oauth2_scheme)]) -> User:
    if not token:
        raise unauthorized("Not authenticated.")
    claims = decode_token(token, "access")
    if claims is None:
        raise unauthorized("Invalid or expired token.")
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise unauthorized("Invalid or expired token.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


class Pagination:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=50, description="Page size (max 50)")] = 20,
        offset: Annotated[int, Query(ge=0, description="Rows to skip")] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


Paging = Annotated[Pagination, Depends()]
