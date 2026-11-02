"""Idempotent seed step: `python -m app.seeds.run`."""

import logging

from sqlalchemy.orm import Session

from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.seeds.holidays import seed_holidays
from app.seeds.limitation_rules import seed_limitation_rules

logger = logging.getLogger("app.seeds")


def run_seeds(db: Session) -> dict[str, int]:
    result = {
        "limitation_rules_added": seed_limitation_rules(db),
        "holidays_added": seed_holidays(db),
    }
    db.commit()
    return result


def main() -> None:
    configure_logging("INFO")
    with SessionLocal() as db:
        result = run_seeds(db)
    logger.info("seed complete", extra=result)


if __name__ == "__main__":
    main()
