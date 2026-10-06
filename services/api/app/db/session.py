from psycopg import AsyncConnection
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def check_database() -> None:
    # A dedicated async connection keeps readiness independent of pool exhaustion
    # and allows the endpoint to cancel DNS, connection and query waits.
    url = make_url(settings.DATABASE_URL).set(drivername="postgresql")
    async with await AsyncConnection.connect(
        url.render_as_string(hide_password=False),
        autocommit=True,
        options="-c statement_timeout=700",
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT 1")
            if await cursor.fetchone() != (1,):
                raise RuntimeError("Unexpected database readiness result")
