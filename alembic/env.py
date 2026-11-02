import logging
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (register all tables)
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
logging.getLogger("alembic").setLevel(logging.INFO)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001
    """Trigram indexes are optional and managed by raw SQL in the migration."""
    return not (type_ == "index" and name and name.startswith("ix_trgm_"))


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().DATABASE_URL,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_settings().DATABASE_URL, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
