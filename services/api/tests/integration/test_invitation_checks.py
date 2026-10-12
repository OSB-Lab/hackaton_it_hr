from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from test_invitation_migrations import legacy


def setup_0008(connection):
    config = legacy(connection)
    command.upgrade(config, "0008")
    return config


def test_0009_preserves_legacy_and_validates_constraints(migration_connection):
    c = migration_connection
    config = setup_0008(c)
    before = [dict(row) for row in c.execute(text("SELECT * FROM invitations ORDER BY id")).mappings()]
    c.commit()
    command.upgrade(config, "head")
    assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0012"
    assert [dict(row) for row in c.execute(text("SELECT * FROM invitations ORDER BY id")).mappings()] == before
    assert all(row["currency"] is None for row in before)  # No invented RUB backfill.
    checks = {row["name"] for row in inspect(c).get_check_constraints("invitations")}
    assert {"ck_invitations_salary_positive", "ck_invitations_salary_range", "ck_invitations_currency"} <= checks
    assert c.scalar(text("SELECT bool_and(convalidated) FROM pg_constraint WHERE conrelid='invitations'::regclass AND contype='c'"))
    c.commit()
    command.check(config)
    c.commit()
    command.downgrade(config, "0008")
    assert [dict(row) for row in c.execute(text("SELECT * FROM invitations ORDER BY id")).mappings()] == before
    c.commit()
    command.upgrade(config, "head")
    command.check(config)


@pytest.mark.parametrize("method", ["insert", "update"])
@pytest.mark.parametrize("minimum,maximum,currency", [
    (0, 200, "RUB"), (-1, 200, "RUB"), (100, 99, "RUB"),
    (100, 200, "USD"), (100, 200, "rub"), ("NaN", "NaN", "RUB"), (100, "NaN", "RUB"),
])
def test_direct_sql_checks(migration_connection, method, minimum, maximum, currency):
    c = migration_connection
    config = setup_0008(c)
    command.upgrade(config, "head")
    row = dict(c.execute(text("SELECT * FROM invitations ORDER BY id LIMIT 1")).mappings().one())
    c.commit()
    with pytest.raises(IntegrityError) as exc:
        if method == "insert":
            c.execute(text("INSERT INTO invitations(company_id,candidate_id,salary_from,salary_to,currency,status) VALUES (:co,:ca,:lo,:hi,:cur,'accepted')"),
                      {"co": row["company_id"], "ca": row["candidate_id"], "lo": Decimal(str(minimum)), "hi": Decimal(str(maximum)), "cur": currency})
        else:
            c.execute(text("UPDATE invitations SET salary_from=:lo,salary_to=:hi,currency=:cur WHERE id=:id"),
                      {"id": row["id"], "lo": Decimal(str(minimum)), "hi": Decimal(str(maximum)), "cur": currency})
        c.commit()
    assert exc.value.orig.sqlstate == "23514"
    c.rollback()
    assert c.scalar(text("SELECT count(*) FROM invitations")) == 3
    assert dict(c.execute(text("SELECT * FROM invitations ORDER BY id LIMIT 1")).mappings().one()) == row


@pytest.mark.parametrize("expression", ["salary_from=0", "salary_to=1", "currency='USD'"])
def test_invalid_legacy_aborts_without_rewriting(migration_connection, expression):
    c = migration_connection
    config = setup_0008(c)
    c.execute(text("UPDATE invitations SET " + expression))  # Internally fixed test cases only.
    c.commit()
    before = [dict(row) for row in c.execute(text("SELECT * FROM invitations ORDER BY id")).mappings()]
    c.commit()
    with pytest.raises(IntegrityError): command.upgrade(config, "head")
    c.rollback()
    assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0008"
    assert [dict(row) for row in c.execute(text("SELECT * FROM invitations ORDER BY id")).mappings()] == before
