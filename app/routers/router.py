from fastapi import APIRouter

from app.routers import (
    auth,
    cases,
    clients,
    dashboard,
    hearings,
    holidays,
    limitation,
    me,
    reminders,
)

api_router = APIRouter(prefix="/api/v1")

for module in (
    auth,
    me,
    dashboard,
    clients,
    cases,
    hearings,
    limitation,
    holidays,
    reminders,
):
    api_router.include_router(module.router)