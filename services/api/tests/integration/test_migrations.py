from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings


@pytest.fixture
def migration_connection():
    url = make_url(get_settings().DATABASE_URL)
    database = f"fsp_test_{uuid4().hex}"
    admin = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},
    )
    test_engine = None
    created = False
    try:
        with admin.connect() as connection:
            # The name is generated internally, contains only ASCII letters,
            # digits and underscores, and is quoted as an SQL identifier.
            connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
        created = True
        test_engine = create_engine(
            url.set(database=database), connect_args={"connect_timeout": 5}
        )
        with test_engine.connect() as connection:
            yield connection
    finally:
        if test_engine is not None:
            test_engine.dispose()
        if created:
            with admin.connect() as connection:
                connection.exec_driver_sql(
                    f'DROP DATABASE "{database}" WITH (FORCE)'
                )
        admin.dispose()


def test_migrations(migration_connection):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = migration_connection

    assert inspect(migration_connection).get_table_names() == []
    migration_connection.commit()

    command.upgrade(config, "head")
    version = migration_connection.scalar(
        text("SELECT version_num FROM alembic_version")
    )
    assert version
    migration_connection.commit()

    command.upgrade(config, "head")
    assert migration_connection.scalar(
        text("SELECT version_num FROM alembic_version")
    ) == version
    migration_connection.commit()

    command.downgrade(config, "base")
    assert inspect(migration_connection).get_table_names() == ["alembic_version"]
    assert migration_connection.scalar(
        text("SELECT count(*) FROM alembic_version")
    ) == 0
