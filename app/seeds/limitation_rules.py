"""Common limitation periods. HELPER VALUES ONLY: verify against the Limitation Act, 1963."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LimitationRule

HELPER = "helper value, verify against the Limitation Act"

RULES: list[dict] = [
    {
        "code": "suit_recovery_of_money",
        "label": "Suit for recovery of money",
        "trigger_label": "Date of cause of action",
        "period_value": 3,
        "period_unit": "years",
        "legal_ref": f"Limitation Act, 1963 (e.g. Art. 19 / 113) - {HELPER}",
    },
    {
        "code": "suit_breach_of_contract",
        "label": "Suit on breach of contract",
        "trigger_label": "Date of breach",
        "period_value": 3,
        "period_unit": "years",
        "legal_ref": f"Limitation Act, 1963, Art. 55 - {HELPER}",
    },
    {
        "code": "suit_specific_performance",
        "label": "Suit for specific performance",
        "trigger_label": "Date fixed for performance",
        "period_value": 3,
        "period_unit": "years",
        "legal_ref": f"Limitation Act, 1963, Art. 54 - {HELPER}",
    },
    {
        "code": "appeal_decree_high_court",
        "label": "Appeal from decree to High Court",
        "trigger_label": "Date of decree",
        "period_value": 90,
        "period_unit": "days",
        "legal_ref": f"Limitation Act, 1963, Art. 116 - {HELPER}",
    },
    {
        "code": "appeal_decree_district_court",
        "label": "Appeal from decree to district court",
        "trigger_label": "Date of decree",
        "period_value": 30,
        "period_unit": "days",
        "legal_ref": f"Limitation Act, 1963, Art. 116 - {HELPER}",
    },
    {
        "code": "cheque_bounce_legal_notice",
        "label": "Cheque bounce legal notice",
        "trigger_label": "Date of bank return memo",
        "period_value": 30,
        "period_unit": "days",
        "legal_ref": f"Negotiable Instruments Act, 1881, s.138(b) - {HELPER}",
    },
    {
        "code": "execution_of_decree",
        "label": "Execution of a decree",
        "trigger_label": "Date of decree",
        "period_value": 12,
        "period_unit": "years",
        "legal_ref": f"Limitation Act, 1963, Art. 136 - {HELPER}",
    },
    {
        "code": "suit_possession_immovable_property",
        "label": "Suit for possession of immovable property",
        "trigger_label": "Date possession became adverse",
        "period_value": 12,
        "period_unit": "years",
        "legal_ref": f"Limitation Act, 1963, Art. 65 - {HELPER}",
    },
]


def seed_limitation_rules(db: Session) -> int:
    """Insert missing rules by code; never overwrites existing rows. Returns rows added."""
    existing = set(db.scalars(select(LimitationRule.code)))
    added = 0
    for rule in RULES:
        if rule["code"] not in existing:
            db.add(LimitationRule(**rule, is_active=True))
            added += 1
    db.flush()
    return added
