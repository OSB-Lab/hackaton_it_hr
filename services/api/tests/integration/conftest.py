from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def alembic_config(connection):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def database_engine():
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
            # Only an internally generated identifier is interpolated.
            connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
        created = True
        test_engine = create_engine(
            url.set(database=database), connect_args={"connect_timeout": 5}
        )
        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        try:
            if created:
                with admin.connect() as connection:
                    connection.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
        finally:
            admin.dispose()


@pytest.fixture
def migration_connection(database_engine):
    with database_engine.connect() as connection:
        yield connection


@pytest.fixture
def migrated_engine(database_engine):
    with database_engine.connect() as connection:
        command.upgrade(alembic_config(connection), "head")
    return database_engine
