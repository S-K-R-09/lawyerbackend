# ===== From common.py =====
import re
from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, EmailStr, Field, StringConstraints

MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2100, 12, 31)


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


def _strip(v: object) -> object:
    return v.strip() if isinstance(v, str) else v


def _blank_to_none(v: object) -> object:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def req_str(max_length: int = 200):
    return Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)
    ]


def opt_str(max_length: int = 200):
    def _check(v: str | None) -> str | None:
        if v is not None and len(v) > max_length:
            raise ValueError(f"Must be at most {max_length} characters.")
        return v

    return Annotated[str | None, BeforeValidator(_blank_to_none), AfterValidator(_check)]


def _sane_date(v: date | None) -> date | None:
    if v is not None and not (MIN_DATE <= v <= MAX_DATE):
        raise ValueError("Date is outside the supported range (2000 to 2100).")
    return v


SaneDate = Annotated[date, AfterValidator(_sane_date)]
Email = Annotated[EmailStr, BeforeValidator(_strip), AfterValidator(lambda v: v.lower())]

OptEmail = Annotated[
    EmailStr | None,
    BeforeValidator(_blank_to_none),
    AfterValidator(lambda v: v.lower() if v else v),
]

_PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def _normalize_phone(v: object) -> object:
    if not isinstance(v, str):
        return v
    cleaned = re.sub(r"[\s\-().]", "", v.strip())
    if not _PHONE_RE.match(cleaned):
        raise ValueError("Enter digits with an optional country code, e.g. +919876543210.")
    return cleaned


Phone = Annotated[str, BeforeValidator(_normalize_phone)]


# ===== From auth.py =====
import uuid
from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.security import password_problem


def _check_password(v: str) -> str:
    problem = password_problem(v)
    if problem:
        raise ValueError(problem)
    return v


class RegisterIn(BaseModel):
    full_name: req_str(200)
    email: Email
    password: str
    enrollment_number: opt_str(100) = None

    _pw = field_validator("password")(_check_password)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "full_name": "Anita Verma",
                    "email": "anita@example.com",
                    "password": "S3cure-pass!",
                    "enrollment_number": "D/1234/2015",
                }
            ]
        }
    )


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    enrollment_number: str | None
    timezone: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=2000)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str

    _pw = field_validator("new_password")(_check_password)


class MeUpdate(BaseModel):
    full_name: req_str(200) | None = None
    email: Email | None = None
    enrollment_number: opt_str(100) = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValueError("Unknown timezone. Use an IANA name like Asia/Kolkata.") from exc
        return v


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hearing_reminder_enabled: bool
    hearing_reminder_time: time
    deadline_reminder_enabled: bool
    deadline_reminder_days: int


class SettingsUpdate(BaseModel):
    hearing_reminder_enabled: bool | None = None
    hearing_reminder_time: time | None = None
    deadline_reminder_enabled: bool | None = None
    deadline_reminder_days: int | None = Field(default=None, ge=0, le=365)


# ===== From cases.py =====
import datetime as dt
import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CaseType(StrEnum):
    civil = "civil"
    criminal = "criminal"
    family = "family"
    writ = "writ"
    other = "other"


class CaseStatus(StrEnum):
    open = "open"
    closed = "closed"


class CaseCreate(BaseModel):
    client_id: uuid.UUID
    case_number: req_str(100)
    court: req_str(200)
    case_type: CaseType
    court_room: opt_str(50) = None
    petitioner: opt_str(200) = None
    respondent: opt_str(200) = None
    stage: opt_str(100) = None
    notes: opt_str(5000) = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "client_id": "00000000-0000-0000-0000-000000000000",
                    "case_number": "CS(OS) 123/2026",
                    "court": "Delhi High Court",
                    "case_type": "civil",
                    "petitioner": "Sharma",
                    "respondent": "Rao",
                    "stage": "Evidence",
                }
            ]
        }
    )


class CaseUpdate(BaseModel):
    client_id: uuid.UUID | None = None
    case_number: req_str(100) | None = None
    court: req_str(200) | None = None
    case_type: CaseType | None = None
    court_room: opt_str(50) = None
    petitioner: opt_str(200) = None
    respondent: opt_str(200) = None
    stage: opt_str(100) = None
    notes: opt_str(5000) = None
    status: CaseStatus | None = None


class CaseListItem(BaseModel):
    id: uuid.UUID
    title: str
    case_number: str
    court: str
    status: str
    stage: str | None
    next_hearing_date: dt.date | None
    has_active_deadline: bool


class CaseMeta(BaseModel):
    active: int
    closed: int
    all: int


class CaseListOut(Page[CaseListItem]):
    meta: CaseMeta


class ClientSummary(BaseModel):
    id: uuid.UUID
    name: str
    phone: str


class NextHearingBrief(BaseModel):
    hearing_id: uuid.UUID
    hearing_date: dt.date
    hearing_time: dt.time | None
    purpose: str | None


class DeadlineBrief(BaseModel):
    id: uuid.UUID
    label: str
    last_date: dt.date
    days_left: int


class CaseCounts(BaseModel):
    hearings: int
    deadlines: int


class CaseDetail(BaseModel):
    id: uuid.UUID
    title: str
    case_number: str
    court: str
    court_room: str | None
    case_type: str
    status: str
    stage: str | None
    petitioner: str | None
    respondent: str | None
    notes: str | None
    closed_on: dt.date | None
    client: ClientSummary
    next_hearing: NextHearingBrief | None
    active_deadline: DeadlineBrief | None
    counts: CaseCounts


StatusFilter = Literal["active", "open", "closed", "all"]


# ===== From clients.py =====
import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict


class ClientCreate(BaseModel):
    name: req_str(200)
    phone: Phone
    email: OptEmail = None
    address: opt_str(1000) = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"name": "Ramesh Sharma", "phone": "+919876543210", "email": "ramesh@example.com"}
            ]
        }
    )


class ClientUpdate(BaseModel):
    name: req_str(200) | None = None
    phone: Phone | None = None
    email: OptEmail = None
    address: opt_str(1000) = None


class ClientListItem(BaseModel):
    id: uuid.UUID
    name: str
    phone: str
    cases_count: int
    latest_case_title: str | None


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    email: str | None
    address: str | None


class ClientCaseItem(BaseModel):
    id: uuid.UUID
    title: str
    case_number: str
    status: str
    stage: str | None
    next_hearing_date: dt.date | None


class ClientDetail(ClientOut):
    cases: list[ClientCaseItem]


# ===== From dashboard.py =====
import datetime as dt
import uuid

from pydantic import BaseModel


class NextUp(BaseModel):
    hearing_id: uuid.UUID
    time: dt.time | None
    case_id: uuid.UUID
    case_title: str
    court: str
    court_room: str | None
    purpose: str | None


class LaterToday(BaseModel):
    hearing_id: uuid.UUID
    case_id: uuid.UUID
    time: dt.time | None
    case_title: str
    court: str
    purpose: str | None


class AttentionDeadline(BaseModel):
    case_id: uuid.UUID
    case_title: str
    last_date: dt.date
    days_left: int


class Attention(BaseModel):
    deadlines: list[AttentionDeadline]


class DashboardToday(BaseModel):
    date: dt.date
    next_up: NextUp | None
    later_today: list[LaterToday]
    attention: Attention


class CalendarDay(BaseModel):
    date: dt.date
    hearing_count: int


# ===== From hearings.py =====
import datetime as dt
import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class Outcome(StrEnum):
    adjourned = "adjourned"
    evidence_recorded = "evidence_recorded"
    arguments_heard = "arguments_heard"
    reserved = "reserved"
    disposed = "disposed"
    other = "other"


OUTCOME_LABELS = {
    "adjourned": "Adjourned",
    "evidence_recorded": "Evidence recorded",
    "arguments_heard": "Arguments heard",
    "reserved": "Judgment reserved",
    "disposed": "Disposed",
    "other": "Other",
}


class HearingCreate(BaseModel):
    hearing_date: SaneDate
    hearing_time: dt.time | None = None
    purpose: opt_str(200) = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"hearing_date": "2026-11-05", "hearing_time": "10:30", "purpose": "Evidence"}
            ]
        }
    )


class HearingUpdate(BaseModel):
    hearing_date: SaneDate | None = None
    hearing_time: dt.time | None = None
    purpose: opt_str(200) = None
    outcome: Outcome | None = None
    note: opt_str(5000) = None


class RecordHearingIn(BaseModel):
    outcome: Outcome
    note: opt_str(5000) = None
    next_date: SaneDate | None = None
    next_time: dt.time | None = None
    next_purpose: opt_str(200) = None

    @model_validator(mode="after")
    def _next_parts_need_a_date(self) -> "RecordHearingIn":
        if self.next_date is None and (self.next_time or self.next_purpose):
            raise ValueError("next_date is required when next_time or next_purpose is given.")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "outcome": "adjourned",
                    "note": "Respondent sought time to file reply.",
                    "next_date": "2026-11-20",
                    "next_time": "11:00",
                    "next_purpose": "Reply",
                }
            ]
        }
    )


class HearingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    hearing_date: dt.date
    hearing_time: dt.time | None
    purpose: str | None
    status: str
    outcome: str | None
    note: str | None
    recorded_at: dt.datetime | None


class RecordHearingOut(BaseModel):
    hearing: HearingOut
    next_hearing: HearingOut | None
    case_next_hearing_date: dt.date | None
    suggest_close_case: bool
    suggestion: str | None


class DayHearing(BaseModel):
    hearing_id: uuid.UUID
    case_id: uuid.UUID
    case_title: str
    court: str
    court_room: str | None
    time: dt.time | None
    purpose: str | None
    status: str
    outcome: str | None


class TimelineItem(BaseModel):
    hearing_id: uuid.UUID
    date: dt.date
    time: dt.time | None
    status: str
    purpose: str | None
    outcome: str | None
    outcome_label: str | None
    note: str | None


class Timeline(BaseModel):
    items: list[TimelineItem]


# ===== From limitation.py =====
import datetime as dt
import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RuleOut(BaseModel):
    id: uuid.UUID
    code: str
    label: str
    period_text: str
    trigger_label: str
    legal_ref: str | None


class CalculateIn(BaseModel):
    rule_id: uuid.UUID
    trigger_date: SaneDate

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"rule_id": "00000000-0000-0000-0000-000000000000", "trigger_date": "2026-08-14"}
            ]
        }
    )


class CalculateOut(BaseModel):
    rule_id: uuid.UUID
    label: str
    trigger_date: dt.date
    last_date: dt.date
    weekday: str
    days_left: int
    adjusted_for_holiday: bool
    steps: list[str]
    disclaimer: str


class DeadlineStatus(StrEnum):
    active = "active"
    done = "done"
    dismissed = "dismissed"


class DeadlineCreate(BaseModel):
    """The server recomputes last_date; any date sent by the client is ignored."""

    rule_id: uuid.UUID
    trigger_date: SaneDate


class DeadlineUpdate(BaseModel):
    status: DeadlineStatus


class DeadlineOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    case_title: str
    rule_id: uuid.UUID
    label: str
    trigger_date: dt.date
    last_date: dt.date
    adjusted_for_holiday: bool
    status: str
    days_left: int


class HolidayCreate(BaseModel):
    holiday_date: SaneDate
    label: req_str(200)


class HolidayOut(BaseModel):
    id: uuid.UUID
    holiday_date: dt.date
    label: str
    is_global: bool


# ===== From reminders.py =====
import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel


class ReminderOut(BaseModel):
    type: Literal["hearing", "deadline"]
    case_id: uuid.UUID
    title: str
    event_date: dt.date
    remind_at: dt.datetime