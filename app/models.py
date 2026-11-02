import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk


# ============================================================
# CASE MODEL
# ============================================================

class Case(UUIDPk, Timestamps, Base):
    __tablename__ = "cases"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
    )

    case_number: Mapped[str] = mapped_column(String(100), nullable=False)
    court: Mapped[str] = mapped_column(String(200), nullable=False)
    court_room: Mapped[str | None] = mapped_column(String(50))
    case_type: Mapped[str] = mapped_column(
        String(20), default="other", nullable=False
    )
    petitioner: Mapped[str | None] = mapped_column(String(200))
    respondent: Mapped[str | None] = mapped_column(String(200))
    stage: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(10), default="open", nullable=False
    )
    closed_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    # Denormalized. Only hearing_service writes it,
    # in the same transaction as the hearing change.
    next_hearing_date: Mapped[date | None] = mapped_column(Date)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    @property
    def title(self) -> str:
        if self.petitioner and self.respondent:
            return f"{self.petitioner} v. {self.respondent}"
        return self.petitioner or self.respondent or self.case_number

    __table_args__ = (
        Index(
            "uq_cases_owner_court_number",
            "owner_id",
            "court",
            "case_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_cases_owner_status", "owner_id", "status"),
        Index("ix_cases_owner_next_hearing_date", "owner_id", "next_hearing_date"),
        Index("ix_cases_client_id", "client_id"),
        Index("ix_cases_owner_case_number", "owner_id", "case_number"),
    )


# ============================================================
# CLIENT MODEL
# ============================================================

class Client(UUIDPk, Timestamps, Base):
    __tablename__ = "clients"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    address: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    __table_args__ = (
        Index(
            "uq_clients_owner_phone",
            "owner_id",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_clients_owner_lower_name", "owner_id", text("lower(name)")),
    )


# ============================================================
# HEARING MODEL
# ============================================================

class Hearing(UUIDPk, Timestamps, Base):
    __tablename__ = "hearings"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )

    hearing_date: Mapped[date] = mapped_column(Date, nullable=False)
    hearing_time: Mapped[time | None] = mapped_column(Time)
    purpose: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(10), default="scheduled", nullable=False
    )
    outcome: Mapped[str | None] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    __table_args__ = (
        Index("ix_hearings_owner_hearing_date", "owner_id", "hearing_date"),
        Index("ix_hearings_case_hearing_date", "case_id", "hearing_date"),
    )


# ============================================================
# HOLIDAY MODEL
# ============================================================

class Holiday(UUIDPk, Timestamps, Base):
    """owner_id NULL means a global (seeded, read-only) holiday."""

    __tablename__ = "holidays"

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        Index("uq_holidays_owner_date", "owner_id", "holiday_date", unique=True),
        # NULLs are distinct in a normal unique index,
        # so guard global rows separately.
        Index(
            "uq_holidays_global_date",
            "holiday_date",
            unique=True,
            postgresql_where=text("owner_id IS NULL"),
        ),
    )


# ============================================================
# LIMITATION RULE AND CASE DEADLINE MODELS
# ============================================================

class LimitationRule(UUIDPk, Base):
    __tablename__ = "limitation_rules"

    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger_label: Mapped[str] = mapped_column(String(100), nullable=False)
    period_value: Mapped[int] = mapped_column(Integer, nullable=False)
    period_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    legal_ref: Mapped[str | None] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


class CaseDeadline(UUIDPk, Timestamps, Base):
    __tablename__ = "case_deadlines"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("limitation_rules.id"),
        nullable=False,
    )

    trigger_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_date: Mapped[date] = mapped_column(Date, nullable=False)
    adjusted_for_holiday: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(10), default="active", nullable=False
    )

    __table_args__ = (
        Index(
            "ix_case_deadlines_owner_last_date_active",
            "owner_id",
            "last_date",
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_case_deadlines_case_id", "case_id"),
    )


# ============================================================
# REFRESH TOKEN MODEL
# ============================================================

class RefreshToken(UUIDPk, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_family_id", "family_id"),
    )


# ============================================================
# USER MODEL
# ============================================================

class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enrollment_number: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Kolkata", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


# ============================================================
# USER SETTINGS MODEL
# ============================================================

class UserSettings(UUIDPk, Timestamps, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    hearing_reminder_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    hearing_reminder_time: Mapped[time] = mapped_column(
        Time, default=time(19, 0), nullable=False
    )
    deadline_reminder_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    deadline_reminder_days: Mapped[int] = mapped_column(
        Integer, default=7, nullable=False
    )