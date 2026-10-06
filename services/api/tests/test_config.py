from sqlalchemy.engine import make_url

from app.core.config import Settings


def test_database_url_escapes_credentials():
    settings = Settings(
        _env_file=None,
        POSTGRES_USER="user@name",
        POSTGRES_PASSWORD="p@ss:/%# word",
        POSTGRES_DB="fsp",
        POSTGRES_HOST="postgres",
        POSTGRES_PORT=5432,
        JWT_SECRET="test-only",
    )
    url = make_url(settings.DATABASE_URL)
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "user@name"
    assert url.password == "p@ss:/%# word"
    assert url.database == "fsp"
    assert "p@ss:/%# word" not in repr(settings)
