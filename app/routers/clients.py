import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, Paging
from app.core.errors import ERROR_RESPONSES, ErrorResponse
from app.schemas import (
    ClientCreate,
    ClientDetail,
    ClientListItem,
    ClientOut,
    ClientUpdate,
)
from app.schemas import Page
from app.services import client_service

router = APIRouter(prefix="/clients", tags=["Clients"], responses=ERROR_RESPONSES)
DUP = {409: {"model": ErrorResponse, "description": "Duplicate phone"}}


@router.get(
    "", response_model=Page[ClientListItem], summary="Clients, sorted by name (`total` = count)"
)
def list_clients(
    user: CurrentUser,
    db: DbSession,
    page: Paging,
    q: Annotated[str | None, Query(max_length=100, description="Name or phone")] = None,
):
    return client_service.list_clients(db, user, q, page)


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED, responses=DUP)
def create_client(body: ClientCreate, user: CurrentUser, db: DbSession):
    return client_service.create_client(db, user, body)


@router.get("/{client_id}", response_model=ClientDetail, summary="Client with their cases")
def get_client(client_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return client_service.client_detail(db, user, client_id)


@router.patch("/{client_id}", response_model=ClientOut, responses=DUP)
def patch_client(client_id: uuid.UUID, body: ClientUpdate, user: CurrentUser, db: DbSession):
    return client_service.update_client(db, user, client_id, body)


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete (blocked while the client has open cases)",
    responses={409: {"model": ErrorResponse, "description": "Client has open cases"}},
)
def delete_client(client_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    client_service.delete_client(db, user, client_id)
