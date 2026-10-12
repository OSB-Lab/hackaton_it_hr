"""Drop demo/real status fields (content_status, taxonomy form status)."""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ck_test_attempts_content_status', 'test_attempts', type_='check')
    op.drop_column('test_attempts', 'content_status')
    op.drop_constraint('ck_taxonomy_question_form_status', 'taxonomy_question_forms', type_='check')
    op.drop_column('taxonomy_question_forms', 'status')


def downgrade():
    op.add_column('test_attempts', sa.Column('content_status', sa.String(), nullable=True))
    op.create_check_constraint('ck_test_attempts_content_status', 'test_attempts', "content_status IN ('DEMO', 'APPROVED')")
    op.add_column('taxonomy_question_forms', sa.Column('status', sa.String(16), nullable=False, server_default='DEMO'))
    op.create_check_constraint('ck_taxonomy_question_form_status', 'taxonomy_question_forms', "status = 'DEMO'")
