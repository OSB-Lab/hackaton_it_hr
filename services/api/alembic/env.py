from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.db.base import Base
from app import models  # noqa: F401 -- register all tables in Base.metadata

config = context.config
settings = get_settings()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests can supply a connection to their isolated database.
    connection = config.attributes.get("connection")
    if connection is not None:
        run_migrations(connection)
        return

    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 5},
    )
    try:
        with engine.connect() as connection:
            run_migrations(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
