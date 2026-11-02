from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.core.errors import ERROR_RESPONSES
from app.schemas import ReminderOut
from app.services import reminder_service

router = APIRouter(prefix="/reminders", tags=["Reminders"], responses=ERROR_RESPONSES)


@router.get(
    "/upcoming",
    response_model=list[ReminderOut],
    summary="Upcoming reminders with remind_at already computed from your settings and timezone",
)
def upcoming(user: CurrentUser, db: DbSession, days: Annotated[int, Query(ge=1, le=365)] = 30):
    return reminder_service.upcoming(db, user, days)
