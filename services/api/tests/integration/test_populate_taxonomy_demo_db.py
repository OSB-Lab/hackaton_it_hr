import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.commands.populate_taxonomy_demo_db import populate
from app.models import CandidateProfile, Company, HiringNeed, TaxonomyQuestionForm, User
from conftest import migrated_engine


def test_populate_empty_isolated_database_from_fixed_synthetic_fixtures(migrated_engine):
    with Session(migrated_engine) as session, session.begin():
        result = populate(session, 'synthetic-test-password-123')
        assert result == {'candidates': 30, 'employers': 5, 'needs': 5, 'questionForms': 45}
    with Session(migrated_engine) as session:
        for model, expected in ((CandidateProfile,30),(Company,5),(HiringNeed,5),(TaxonomyQuestionForm,45)):
            assert session.scalar(select(func.count()).select_from(model)) == expected
        assert session.scalar(select(func.count()).select_from(User)) == 35
        from app.modules.auth.schemas import LoginRequest
        from app.modules.auth.service import authenticate_user
        authenticated = authenticate_user(session, LoginRequest(
            email='syn-c0002@demo.example.com', password='synthetic-test-password-123'))
        assert authenticated.role == 'candidate'
        assert all(p.verified_grade is None and p.verified_specialization is None
                   for p in session.scalars(select(CandidateProfile)))
        assert {p.specialization for p in session.scalars(select(CandidateProfile))} == {
            'backend','frontend','fullstack','ml_engineer','data_engineer'}
        assert {n.min_grade for n in session.scalars(select(HiringNeed))} == {'junior','middle','senior'}
        assert {n.specialization for n in session.scalars(select(HiringNeed))} == {
            'backend','frontend','fullstack','ml_engineer','data_engineer'}
        with pytest.raises(ValueError):
            populate(session, 'synthetic-test-password-123')
        session.rollback()
