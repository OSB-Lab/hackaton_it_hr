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
    "hiring_needs": "id company_id title stack grade specialization created_at team_description min_grade optional_skills",
    "test_attempts": "id candidate_id test_id answers score result grade created_at specialization requested_grade blueprint_version catalog_version blueprint_checksum catalog_checksum snapshot_schema_version snapshot variant content_status status submitted_at",
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


def test_hiring_needs_0004_preserves_rows(migration_connection):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = migration_connection
    command.upgrade(config, "0003")
    user_id = migration_connection.scalar(text(
        "INSERT INTO users (email, password_hash, role) "
        "VALUES ('migration@example.com', 'fixture', 'employer') RETURNING id"
    ))
    company_id = migration_connection.scalar(text(
        "INSERT INTO companies (user_id, name) VALUES (:id, 'Existing') RETURNING id"
    ), {"id": user_id})
    migration_connection.execute(text(
        "INSERT INTO hiring_needs (company_id, title, stack, grade, specialization) "
        "VALUES (:id, 'Existing need', '[\"Python\"]', 'middle', 'backend')"
    ), {"id": company_id})
    before = list(migration_connection.execute(text("SELECT * FROM hiring_needs ORDER BY id")).mappings())
    migration_connection.commit()
    command.upgrade(config, "0004")
    assert migration_connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
    after = list(migration_connection.execute(text("SELECT * FROM hiring_needs ORDER BY id")).mappings())
    assert len(after) == len(before)
    for old, new in zip(before, after):
        assert all(new[key] == value for key, value in old.items())
        assert all(new[key] is None for key in ("team_description", "min_grade", "optional_skills"))
    columns = {col["name"]: col for col in inspect(migration_connection).get_columns("hiring_needs")}
    for name, sql_type in (("team_description", "TEXT"), ("min_grade", "VARCHAR"), ("optional_skills", "JSON")):
        assert str(columns[name]["type"]) == sql_type
        assert columns[name]["nullable"] is True
        assert columns[name]["default"] is None
    migration_connection.commit()
    command.upgrade(config, "head")
    command.check(config)


def test_assessment_migration_preserves_legacy(migration_connection):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = migration_connection
    command.upgrade(config, "0004")
    user_id = migration_connection.scalar(text(
        "INSERT INTO users (email, password_hash, role) VALUES ('legacy@example.com', 'fixture', 'candidate') RETURNING id"
    ))
    candidate_id = migration_connection.scalar(text(
        "INSERT INTO candidate_profiles (user_id) VALUES (:id) RETURNING id"
    ), {"id": user_id})
    migration_connection.execute(text(
        "INSERT INTO test_attempts (candidate_id, test_id, answers, score, grade) "
        "VALUES (:id, 'old-test', '[1,2]', 42, 'junior')"
    ), {"id": candidate_id})
    before = dict(migration_connection.execute(text("SELECT * FROM test_attempts")).mappings().one())
    migration_connection.commit()
    command.upgrade(config, "0005")
    after = dict(migration_connection.execute(text("SELECT * FROM test_attempts")).mappings().one())
    assert all(after[k] == v for k, v in before.items())
    assert after["status"] == "legacy"
    assert all(v is None for k, v in after.items() if k not in before and k != "status")
    migration_connection.commit()
    command.upgrade(config, "head")
    command.check(config)


def test_migrations(migration_connection):
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["connection"] = migration_connection

    assert inspect(migration_connection).get_table_names() == []
    migration_connection.commit()

    command.upgrade(config, "head")
    assert migration_connection.scalar(
        text("SELECT version_num FROM alembic_version")
    ) == "0006"
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
    ) == "0006"
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
