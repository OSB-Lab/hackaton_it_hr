"""v3 evidence and explicit qualification; never certify historical rows."""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("verified_grade", "verified_specialization"):
        op.add_column("candidate_profiles", sa.Column(name, sa.String(), nullable=True))
    op.add_column("candidate_profiles", sa.Column("verified_attempt_id", sa.Integer(), nullable=True))
    op.add_column("candidate_profiles", sa.Column("last_grade_change_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_candidate_verified_attempt", "candidate_profiles", "test_attempts", ["verified_attempt_id"], ["id"])
    op.create_check_constraint("ck_candidate_verified_grade", "candidate_profiles", "verified_grade IN ('junior', 'middle', 'senior')")
    op.drop_constraint("ck_test_attempts_variant", "test_attempts", type_="check")
    op.create_check_constraint("ck_test_attempts_variant", "test_attempts", "variant IN ('A', 'B', 'C')")
    op.add_column("competency_scores", sa.Column("evidence_count", sa.Integer(), nullable=True))
    op.add_column("competency_scores", sa.Column("blueprint_version", sa.String(), nullable=True))
    op.add_column("competency_scores", sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("test_attempts.id"), nullable=True))
    op.drop_constraint("ck_competency_scores_source", "competency_scores", type_="check")
    op.create_check_constraint("ck_competency_scores_source", "competency_scores", "source IN ('test', 'fsp', 'manual', 'assessment_diagnostic')")


def downgrade():
    # Refuse destructive downgrade when v3 data exists; never delete evidence.
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM test_attempts WHERE variant = 'C' OR snapshot->'blueprint'->>'schemaVersion' = '3') OR EXISTS (SELECT 1 FROM candidate_profiles WHERE verified_attempt_id IS NOT NULL) OR EXISTS (SELECT 1 FROM competency_scores WHERE source = 'assessment_diagnostic')")):
        raise RuntimeError("v3 data exists; downgrade would lose qualification/evidence")
    op.drop_constraint("ck_competency_scores_source", "competency_scores", type_="check")
    op.create_check_constraint("ck_competency_scores_source", "competency_scores", "source IN ('test', 'fsp', 'manual')")
    for name in ("attempt_id", "blueprint_version", "evidence_count"):
        op.drop_column("competency_scores", name)
    op.drop_constraint("ck_test_attempts_variant", "test_attempts", type_="check")
    op.create_check_constraint("ck_test_attempts_variant", "test_attempts", "variant IN ('A', 'B')")
    op.drop_constraint("fk_candidate_verified_attempt", "candidate_profiles", type_="foreignkey")
    op.drop_constraint("ck_candidate_verified_grade", "candidate_profiles", type_="check")
    for name in ("last_grade_change_at", "verified_attempt_id", "verified_specialization", "verified_grade"):
        op.drop_column("candidate_profiles", name)
