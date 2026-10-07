"""Candidate-owned profile fields; tested grade remains separate."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_profiles", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("candidate_profiles", sa.Column("professional_role", sa.String(), nullable=True))
    op.add_column("candidate_profiles", sa.Column("experience_months", sa.Integer(), nullable=True))
    op.add_column("candidate_profiles", sa.Column("soft_skills", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
    op.add_column("candidate_profiles", sa.Column("self_declared_grade", sa.String(), nullable=True))


def downgrade():
    for name in ("self_declared_grade", "soft_skills", "experience_months", "professional_role", "phone"):
        op.drop_column("candidate_profiles", name)
