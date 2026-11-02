from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(_settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=10)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def get_db() -> Iterator[Session]:
    """One session per request. Services commit; any exception rolls back."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
