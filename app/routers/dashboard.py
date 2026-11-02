from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.core.errors import ERROR_RESPONSES
from app.schemas import CalendarDay, DashboardToday
from app.services import dashboard_service

router = APIRouter(tags=["Dashboard & Calendar"], responses=ERROR_RESPONSES)


@router.get(
    "/dashboard/today",
    response_model=DashboardToday,
    summary="Today screen. 'Today' is the lawyer's own timezone, not the server's",
)
def dashboard_today(user: CurrentUser, db: DbSession):
    return dashboard_service.today_screen(db, user)


@router.get(
    "/calendar",
    response_model=list[CalendarDay],
    summary="Days with hearings in a month (the dots). Use GET /hearings?date= for a day's list",
)
def calendar_month(
    user: CurrentUser,
    db: DbSession,
    month: Annotated[
        str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-10"], description="YYYY-MM")
    ],
):
    return dashboard_service.month_dots(db, user, month)
