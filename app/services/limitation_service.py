"""Limitation helper. Explicit date rules; NOT legal advice."""

import datetime as dt
import uuid

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import today_in
from app.core.deps import Pagination
from app.core.errors import conflict, not_found
from app.models import Case
from app.models import Holiday
from app.models import CaseDeadline, LimitationRule
from app.models import User
from app.schemas import CalculateIn, DeadlineCreate, DeadlineUpdate
from app.services.common import count, get_owned_case, get_owned_deadline

DISCLAIMER = (
    "Helper only, not legal advice. Certified-copy time exclusion and special exemptions "
    "(for example sections 4 to 24 of the Limitation Act) are not applied. "
    "Verify against the Limitation Act before relying on this date."
)
MAX_ROLL_DAYS = 60


def fmt(d: dt.date) -> str:
    return f"{d:%a} {d.day} {d:%b %Y}"


def period_text(rule: LimitationRule) -> str:
    unit = rule.period_unit.rstrip("s") if rule.period_value == 1 else rule.period_unit
    label = rule.trigger_label
    basis = label[8:] if label.startswith("Date of ") else label[:1].lower() + label[1:]
    return f"{rule.period_value} {unit} from {basis}"


def compute_last_date(
    trigger: dt.date,
    value: int,
    unit: str,
    holidays: dict[dt.date, str] | None = None,
) -> tuple[dt.date, bool, list[str]]:
    """Return (last_date, adjusted_for_holiday, steps).

    1. The trigger day is excluded, so counting starts the next day.
    2. days: trigger + N days. months/years: trigger + relativedelta (clamps month ends).
    3. If the result is a Sunday or a holiday, move forward to the next working day.
    """
    holidays = holidays or {}
    steps = [
        f"Trigger date is {fmt(trigger)}. The trigger day is excluded, so counting starts on "
        f"{fmt(trigger + dt.timedelta(days=1))}."
    ]
    if unit == "days":
        raw = trigger + dt.timedelta(days=value)
    elif unit == "months":
        raw = trigger + relativedelta(months=value)
    elif unit == "years":
        raw = trigger + relativedelta(years=value)
    else:  # pragma: no cover - guarded by the data model
        raise ValueError(f"Unknown period unit: {unit}")
    steps.append(f"Period is {value} {unit}, which ends on {fmt(raw)}.")

    last = raw
    adjusted = False
    for _ in range(MAX_ROLL_DAYS):
        reason = None
        if last in holidays:
            reason = f"a holiday ({holidays[last]})"
        elif last.weekday() == 6:
            reason = "a Sunday"
        if reason is None:
            break
        nxt = last + dt.timedelta(days=1)
        steps.append(f"{fmt(last)} is {reason}, so the date rolls forward to {fmt(nxt)}.")
        last, adjusted = nxt, True
    steps.append(f"Last date to file: {fmt(last)}.")
    return last, adjusted, steps


def holiday_map(db: Session, user: User, start: dt.date) -> dict[dt.date, str]:
    rows = db.execute(
        select(Holiday.holiday_date, Holiday.label).where(
            (Holiday.owner_id.is_(None)) | (Holiday.owner_id == user.id),
            Holiday.holiday_date.between(start, start + dt.timedelta(days=MAX_ROLL_DAYS)),
        )
    ).all()
    return {d: label for d, label in rows}


def get_rule(db: Session, rule_id: uuid.UUID) -> LimitationRule:
    rule = db.scalar(
        select(LimitationRule).where(
            LimitationRule.id == rule_id, LimitationRule.is_active.is_(True)
        )
    )
    if rule is None:
        raise not_found("Limitation rule not found.")
    return rule


def list_rules(db: Session) -> list[dict]:
    rules = db.scalars(
        select(LimitationRule)
        .where(LimitationRule.is_active.is_(True))
        .order_by(LimitationRule.label)
    )
    return [
        {
            "id": r.id,
            "code": r.code,
            "label": r.label,
            "period_text": period_text(r),
            "trigger_label": r.trigger_label,
            "legal_ref": r.legal_ref,
        }
        for r in rules
    ]


def _calc(db: Session, user: User, rule: LimitationRule, trigger: dt.date):
    # First pass finds the raw end date; then load holidays in the window after it and recompute.
    raw, _, _ = compute_last_date(trigger, rule.period_value, rule.period_unit)
    hmap = holiday_map(db, user, raw)
    return compute_last_date(trigger, rule.period_value, rule.period_unit, hmap)


def calculate(db: Session, user: User, data: CalculateIn) -> dict:
    rule = get_rule(db, data.rule_id)
    last, adjusted, steps = _calc(db, user, rule, data.trigger_date)
    today = today_in(user.timezone)
    return {
        "rule_id": rule.id,
        "label": rule.label,
        "trigger_date": data.trigger_date,
        "last_date": last,
        "weekday": last.strftime("%A"),
        "days_left": (last - today).days,
        "adjusted_for_holiday": adjusted,
        "steps": steps,
        "disclaimer": DISCLAIMER,
    }


def _deadline_out(d: CaseDeadline, case: Case, rule: LimitationRule, today: dt.date) -> dict:
    return {
        "id": d.id,
        "case_id": d.case_id,
        "case_title": case.title,
        "rule_id": d.rule_id,
        "label": rule.label,
        "trigger_date": d.trigger_date,
        "last_date": d.last_date,
        "adjusted_for_holiday": d.adjusted_for_holiday,
        "status": d.status,
        "days_left": (d.last_date - today).days,
    }


def save_deadline(db: Session, user: User, case_id: uuid.UUID, data: DeadlineCreate) -> dict:
    case = get_owned_case(db, user, case_id)
    rule = get_rule(db, data.rule_id)
    dup = db.scalar(
        select(CaseDeadline.id).where(
            CaseDeadline.case_id == case.id,
            CaseDeadline.owner_id == user.id,
            CaseDeadline.rule_id == rule.id,
            CaseDeadline.trigger_date == data.trigger_date,
            CaseDeadline.status == "active",
        )
    )
    if dup:
        raise conflict("This deadline is already saved for the case.")
    last, adjusted, _ = _calc(db, user, rule, data.trigger_date)  # always recomputed server-side
    deadline = CaseDeadline(
        owner_id=user.id,
        case_id=case.id,
        rule_id=rule.id,
        trigger_date=data.trigger_date,
        last_date=last,
        adjusted_for_holiday=adjusted,
    )
    db.add(deadline)
    try:
        db.commit()
    except IntegrityError as exc:  # pragma: no cover
        db.rollback()
        raise conflict("Could not save the deadline.") from exc
    return _deadline_out(deadline, case, rule, today_in(user.timezone))


def list_deadlines(
    db: Session, user: User, status: str, page: Pagination, case_id: uuid.UUID | None = None
) -> dict:
    if case_id is not None:
        get_owned_case(db, user, case_id)
    base = (
        select(CaseDeadline, Case, LimitationRule)
        .join(Case, Case.id == CaseDeadline.case_id)
        .join(LimitationRule, LimitationRule.id == CaseDeadline.rule_id)
        .where(CaseDeadline.owner_id == user.id, Case.deleted_at.is_(None))
    )
    if case_id is not None:
        base = base.where(CaseDeadline.case_id == case_id)
    if status != "all":
        base = base.where(CaseDeadline.status == status)
    today = today_in(user.timezone)
    rows = db.execute(
        base.order_by(CaseDeadline.last_date, CaseDeadline.id).limit(page.limit).offset(page.offset)
    ).all()
    return {
        "items": [_deadline_out(d, c, r, today) for d, c, r in rows],
        "total": count(db, base),
        "limit": page.limit,
        "offset": page.offset,
    }


def update_deadline(db: Session, user: User, deadline_id: uuid.UUID, data: DeadlineUpdate) -> dict:
    d = get_owned_deadline(db, user, deadline_id)
    d.status = data.status.value
    db.commit()
    case = db.get(Case, d.case_id)
    rule = db.get(LimitationRule, d.rule_id)
    return _deadline_out(d, case, rule, today_in(user.timezone))
