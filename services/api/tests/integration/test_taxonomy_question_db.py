from sqlalchemy import func, select
from sqlalchemy.orm import Session
import pytest

from app.models import TaxonomyQuestionForm
from app.modules.assessments.taxonomy_bank import load_bank, load_seed_bank
from app.commands.import_taxonomy_questions import seed_bank
from conftest import migrated_engine


def test_fixed_bank_requires_database_import_and_is_idempotent(migrated_engine):
    with Session(migrated_engine) as session:
        with pytest.raises(ValueError):
            load_bank(session)
        seed_bank(session)
        session.commit()
        assert session.scalar(select(func.count()).select_from(TaxonomyQuestionForm)) == 45
        bank = load_bank(session)
        assert len(bank.cells) == 15
        assert set(bank.cells) == set(load_seed_bank().cells)
        assert {form.id for cell in bank.cells.values() for form in cell.forms} == {'A','B','C'}
        seed_bank(session)
        session.commit()
        assert session.scalar(select(func.count()).select_from(TaxonomyQuestionForm)) == 45
