"""Enforce invitation salary/currency without rewriting historical data."""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL validates existing rows. Any violation aborts transactionally;
    # never silently repair salaries/currencies or invent legacy currency.
    # SQL CHECK permits legacy NULL currency (unknown), but no non-RUB value.
    op.create_check_constraint('ck_invitations_salary_positive', "invitations", "salary_from > 0 AND salary_from <> 'NaN'::numeric")
    op.create_check_constraint('ck_invitations_salary_range', "invitations", "salary_to >= salary_from AND salary_to <> 'NaN'::numeric")
    op.create_check_constraint('ck_invitations_currency', "invitations", "currency = 'RUB'")


def downgrade():
    op.drop_constraint('ck_invitations_currency', "invitations", type_="check")
    op.drop_constraint('ck_invitations_salary_range', "invitations", type_="check")
    op.drop_constraint('ck_invitations_salary_positive', "invitations", type_="check")
