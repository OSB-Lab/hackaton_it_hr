"""Add nullable recommendation payload; preserve legacy items unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("recommendation_snapshots", sa.Column("algorithm_version", sa.String(), nullable=True))
    op.add_column("recommendation_snapshots", sa.Column("weights", sa.JSON(none_as_null=True), nullable=True))
    op.add_column("recommendation_snapshots", sa.Column("ordered_items", sa.JSON(none_as_null=True), nullable=True))


def downgrade():
    op.drop_column("recommendation_snapshots", "ordered_items")
    op.drop_column("recommendation_snapshots", "weights")
    op.drop_column("recommendation_snapshots", "algorithm_version")
