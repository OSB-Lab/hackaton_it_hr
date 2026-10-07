"""Extend hiring needs without inventing values for existing rows."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hiring_needs", sa.Column("team_description", sa.Text(), nullable=True))
    op.add_column("hiring_needs", sa.Column("min_grade", sa.String(), nullable=True))
    op.add_column("hiring_needs", sa.Column("optional_skills", sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    for name in ("optional_skills", "min_grade", "team_description"):
        op.drop_column("hiring_needs", name)
