from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app import models  # noqa: F401
from app.db.base import Base

DOMAIN_COLUMNS = {
    "users": "id email password_hash role is_verified created_at",
    "consents": "id user_id kind granted granted_at created_at",
    "candidate_profiles": "id user_id full_name stack grade specialization privacy_settings created_at updated_at phone professional_role experience_months soft_skills self_declared_grade",
    "companies": "id user_id name description contacts created_at",
    "hiring_needs": "id company_id title stack grade specialization created_at",
    "test_attempts": "id candidate_id test_id answers score grade created_at",
    "competency_scores": "id candidate_id competency score source created_at",
    "fsp_links": "id candidate_id fsp_id linked_at status",
    "fsp_achievements": "id candidate_id discipline competition result role rank created_at",
    "recommendation_snapshots": "id need_id created_at",
    "recommendation_items": "id snapshot_id candidate_id score reason rank",
    "invitations": "id company_id candidate_id title salary_from salary_to status created_at updated_at",
    "contact_disclosures": "id invitation_id revealed_at",
    "audit_events": "id user_id action payload created_at",
}


def test_candidate_extension_preserves_existing_data(migration_connection):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = migration_connection
    command.upgrade(config, "0002")
    user_id = migration_connection.scalar(text(
        "INSERT INTO users (email, password_hash, role) "
        "VALUES ('migration@example.com', 'fixture', 'candidate') RETURNING id"
    ))
    migration_connection.execute(text(
        "INSERT INTO candidate_profiles (user_id, full_name, grade) VALUES (:id, 'Existing', 'senior')"
    ), {"id": user_id})
    migration_connection.commit()
    command.upgrade(config, "head")
    row = migration_connection.execute(text(
        "SELECT full_name, grade, self_declared_grade, soft_skills FROM candidate_profiles WHERE user_id=:id"
    ), {"id": user_id}).one()
    assert tuple(row) == ("Existing", "senior", None, [])
    migration_connection.commit()
    command.check(config)


def test_migrations(migration_connection):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = migration_connection

    assert inspect(migration_connection).get_table_names() == []
    migration_connection.commit()

    command.upgrade(config, "head")
    assert migration_connection.scalar(
        text("SELECT version_num FROM alembic_version")
    ) == "0003"
    inspector = inspect(migration_connection)
    assert set(inspector.get_table_names()) == set(DOMAIN_COLUMNS) | {"alembic_version"}
    assert set(Base.metadata.tables) == set(DOMAIN_COLUMNS)
    for table, columns in DOMAIN_COLUMNS.items():
        assert {column["name"] for column in inspector.get_columns(table)} == set(columns.split())
    migration_connection.commit()

    command.check(config)  # Migrations and ORM metadata must agree.
    migration_connection.commit()
    command.upgrade(config, "head")
    assert migration_connection.scalar(
        text("SELECT version_num FROM alembic_version")
    ) == "0003"
    migration_connection.commit()

    command.downgrade(config, "base")
    assert inspect(migration_connection).get_table_names() == ["alembic_version"]
    assert migration_connection.scalar(
        text("SELECT count(*) FROM alembic_version")
    ) == 0
    migration_connection.commit()

    command.upgrade(config, "head")
    assert set(inspect(migration_connection).get_table_names()) == (
        set(DOMAIN_COLUMNS) | {"alembic_version"}
    )
