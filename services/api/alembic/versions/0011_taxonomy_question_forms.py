"""Store immutable static taxonomy question forms (content seeded separately)."""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('taxonomy_question_forms',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('role_id', sa.String(64), nullable=False),
        sa.Column('grade_id', sa.String(32), nullable=False),
        sa.Column('variant', sa.String(1), nullable=False),
        sa.Column('version', sa.String(80), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('skill_ids', sa.JSON(), nullable=False),
        sa.Column('questions', sa.JSON(), nullable=False),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('role_id','grade_id','variant','version',name='uq_taxonomy_question_form_identity'),
        sa.CheckConstraint("variant IN ('A', 'B', 'C')",name='ck_taxonomy_question_form_variant'),
        sa.CheckConstraint("status = 'DEMO'",name='ck_taxonomy_question_form_status'),
    )


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM taxonomy_question_forms)')):
        raise RuntimeError('Refusing to delete saved question forms')
    op.drop_table('taxonomy_question_forms')
