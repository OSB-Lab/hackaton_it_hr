"""Invitation money and active uniqueness; never rewrite historical statuses."""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    # Abort rather than delete, merge or terminate any legacy invitations.
    if op.get_bind().scalar(sa.text("""SELECT EXISTS (
        SELECT 1 FROM invitations WHERE status IN ('sent', 'viewed')
        GROUP BY company_id, candidate_id HAVING count(*) > 1)""")):
        raise RuntimeError("Duplicate active invitations require explicit reconciliation")
    op.alter_column("invitations", "title", existing_type=sa.String(), type_=sa.Text(), existing_nullable=True)
    for name in ("salary_from", "salary_to"):
        op.alter_column("invitations", name, existing_type=sa.Integer(), type_=sa.Numeric(18, 2), existing_nullable=False)
    op.add_column("invitations", sa.Column("contact_method", sa.String(), nullable=True))
    op.add_column("invitations", sa.Column("currency", sa.String(), nullable=True))
    op.create_index("uq_invitations_active_pair", "invitations", ["company_id", "candidate_id"],
                    unique=True, postgresql_where=sa.text("status IN ('sent', 'viewed')"))


def downgrade():
    if op.get_bind().scalar(sa.text("""SELECT EXISTS (SELECT 1 FROM invitations
        WHERE salary_from <> trunc(salary_from) OR salary_to <> trunc(salary_to)
        OR salary_from NOT BETWEEN -2147483648 AND 2147483647
        OR salary_to NOT BETWEEN -2147483648 AND 2147483647)""")):
        raise RuntimeError("Downgrade would lose monetary precision or overflow")
    op.drop_index("uq_invitations_active_pair", table_name="invitations")
    op.drop_column("invitations", "currency")
    op.drop_column("invitations", "contact_method")
    for name in ("salary_from", "salary_to"):
        op.alter_column("invitations", name, existing_type=sa.Numeric(18, 2), type_=sa.Integer(), existing_nullable=False)
    op.alter_column("invitations", "title", existing_type=sa.Text(), type_=sa.String(), existing_nullable=True)
