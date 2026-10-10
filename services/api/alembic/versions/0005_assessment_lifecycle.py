"""Assessment lifecycle; historical attempts retain unknown snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("specialization", "requested_grade", "blueprint_version", "catalog_version",
                 "blueprint_checksum", "catalog_checksum", "variant", "content_status"):
        op.add_column("test_attempts", sa.Column(name, sa.String(), nullable=True))
    op.add_column("test_attempts", sa.Column("snapshot_schema_version", sa.Integer(), nullable=True))
    op.add_column("test_attempts", sa.Column("snapshot", sa.JSON(none_as_null=True), nullable=True))
    op.add_column("test_attempts", sa.Column("status", sa.String(), nullable=False, server_default="legacy"))
    op.add_column("test_attempts", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_test_attempts_status", "test_attempts", "status IN ('legacy', 'active', 'submitted')")
    op.create_check_constraint("ck_test_attempts_variant", "test_attempts", "variant IN ('A', 'B')")
    op.create_check_constraint("ck_test_attempts_content_status", "test_attempts", "content_status IN ('DEMO', 'APPROVED')")
    op.create_index("uq_test_attempts_active_candidate", "test_attempts", ["candidate_id"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))


def downgrade():
    op.drop_index("uq_test_attempts_active_candidate", table_name="test_attempts")
    for name in ("content_status", "variant", "status"):
        op.drop_constraint("ck_test_attempts_" + name, "test_attempts", type_="check")
    for name in ("submitted_at", "status", "snapshot", "snapshot_schema_version", "content_status",
                 "variant", "catalog_checksum", "blueprint_checksum", "catalog_version",
                 "blueprint_version", "requested_grade", "specialization"):
        op.drop_column("test_attempts", name)
