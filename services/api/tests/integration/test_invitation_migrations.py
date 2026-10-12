from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import inspect, text

from conftest import alembic_config


def legacy(connection, duplicate=False):
    config = alembic_config(connection)
    command.upgrade(config, "0007")
    employer = connection.scalar(text("INSERT INTO users(email,password_hash,role) VALUES ('e@example.com','fixture','employer') RETURNING id"))
    candidate_user = connection.scalar(text("INSERT INTO users(email,password_hash,role) VALUES ('c@example.com','fixture','candidate') RETURNING id"))
    company = connection.scalar(text("INSERT INTO companies(user_id,name) VALUES (:id,'Company') RETURNING id"), {"id": employer})
    candidate = connection.scalar(text("INSERT INTO candidate_profiles(user_id) VALUES (:id) RETURNING id"), {"id": candidate_user})
    for status in (("sent", "viewed") if duplicate else ("sent", "accepted", "rejected")):
        connection.execute(text("INSERT INTO invitations(company_id,candidate_id,title,salary_from,salary_to,status) VALUES (:c,:p,'Legacy',100,200,:s)"), {"c": company, "p": candidate, "s": status})
    connection.commit()
    return config


def test_invitation_migration_preserves_legacy(migration_connection):
    c = migration_connection
    config = legacy(c)
    before = [dict(row) for row in c.execute(text("SELECT * FROM invitations ORDER BY id")).mappings()]
    c.commit()
    command.upgrade(config, "head")
    after = [dict(row) for row in c.execute(text("SELECT * FROM invitations ORDER BY id")).mappings()]
    for old, new in zip(before, after):
        assert all(new[k] == v for k, v in old.items())
        assert new["currency"] is new["contact_method"] is None
        assert isinstance(new["salary_from"], Decimal)
    assert len(before) == len(after)
    assert c.scalar(text("SELECT count(*) FROM audit_events")) == 0
    c.commit()
    command.check(config)
    c.commit()
    command.downgrade(config, "0007")
    assert [dict(row) for row in c.execute(text("SELECT * FROM invitations ORDER BY id")).mappings()] == before
    c.commit()
    command.upgrade(config, "head")
    command.check(config)


def test_duplicate_legacy_migration_aborts_without_rewriting(migration_connection):
    c = migration_connection
    config = legacy(c, duplicate=True)
    with pytest.raises(RuntimeError, match="Duplicate active"):
        command.upgrade(config, "head")
    c.rollback()
    assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0007"
    assert c.scalar(text("SELECT count(*) FROM invitations")) == 2
    assert "contact_method" not in {col["name"] for col in inspect(c).get_columns("invitations")}


def test_downgrade_refuses_money_loss(migration_connection):
    c = migration_connection
    config = legacy(c)
    command.upgrade(config, "head")
    c.execute(text("UPDATE invitations SET salary_from=100.01"))
    c.commit()
    with pytest.raises(RuntimeError, match="monetary precision"):
        command.downgrade(config, "0007")
    c.rollback()
    assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0012"
    assert c.scalar(text("SELECT salary_from FROM invitations LIMIT 1")) == Decimal("100.01")
