from copy import deepcopy

import pytest
from sqlalchemy import MetaData, Table, func, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.commands import seed_demo
from app.models import (
    CandidateProfile, Company, CompetencyScore, Consent, FspAchievement,
    FspLink, HiringNeed, User,
)


@pytest.fixture
def seed_database(migrated_engine, monkeypatch):
    # main() uses the same SessionLocal API, bound only to our temporary DB.
    monkeypatch.setattr(
        seed_demo, "SessionLocal",
        sessionmaker(bind=migrated_engine, autoflush=False, expire_on_commit=False),
    )
    return migrated_engine


def table_counts(engine):
    with engine.connect() as connection:
        return {
            name: connection.scalar(
                select(func.count()).select_from(
                    Table(name, MetaData(), autoload_with=connection)
                )
            )
            for name in inspect(connection).get_table_names()
        }


def test_seed_is_idempotent(seed_database, capsys):
    seed_demo.main()
    first = table_counts(seed_database)
    seed_demo.main()
    assert table_counts(seed_database) == first
    assert capsys.readouterr().out == "seed completed\nseed completed\n"

    assert 8 <= first["candidate_profiles"] <= 12
    assert first["companies"] == 2
    assert first["hiring_needs"] >= 1
    assert first["consents"] > 0
    assert first["competency_scores"] > 0

    with Session(seed_database) as session:
        assert session.scalar(
            select(func.count()).select_from(FspLink).where(FspLink.status == "no_history")
        ) >= 1
        assert session.scalar(
            select(func.count()).select_from(FspAchievement)
            .join(FspLink, FspLink.candidate_id == FspAchievement.candidate_id)
            .where(FspLink.status == "linked")
        ) >= 1
        assert session.scalar(
            select(func.count()).select_from(FspAchievement)
            .where(FspAchievement.competition.is_(None))
        ) == 1
        assert set(session.scalars(select(CandidateProfile.specialization))) == {"backend", "frontend"}
        assert set(session.scalars(select(CandidateProfile.grade))) == {"junior", "middle"}
        assert session.scalar(
            select(func.count()).select_from(Company)
            .join(User, User.id == Company.user_id).where(User.role == "employer")
        ) == 2
        assert session.scalar(
            select(func.count()).select_from(HiringNeed)
        ) >= 1
        assert session.scalar(
            select(func.count()).select_from(User)
        ) == session.scalar(select(func.count(func.distinct(User.email))))
        for user in session.scalars(select(User)):
            assert user.password_hash.startswith("$2b$")
            assert len(user.password_hash) == 60

        for model, keys in (
            (Consent, [Consent.user_id, Consent.kind]),
            (CompetencyScore, [
                CompetencyScore.candidate_id, CompetencyScore.competency, CompetencyScore.source
            ]),
            (HiringNeed, [HiringNeed.company_id, HiringNeed.title]),
            (FspAchievement, [
                FspAchievement.candidate_id, FspAchievement.discipline, FspAchievement.competition
            ]),
        ):
            assert session.execute(
                select(*keys).select_from(model).group_by(*keys).having(func.count() > 1)
            ).all() == []


def test_seed_preserves_existing_records(seed_database):
    seed_demo.main()
    with Session(seed_database) as session, session.begin():
        user = session.scalar(select(User).where(User.email == "candidate1@demo.example"))
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        profile.full_name = "Edited profile"
        consent = session.scalar(
            select(Consent).where(Consent.user_id == user.id, Consent.kind == "publish_profile")
        )
        consent.granted = False
        consent.granted_at = None
        user_id = user.id
    seed_demo.main()
    with Session(seed_database) as session:
        assert session.scalar(
            select(CandidateProfile.full_name).where(CandidateProfile.user_id == user_id)
        ) == "Edited profile"
        assert session.scalar(
            select(Consent.granted).where(
                Consent.user_id == user_id, Consent.kind == "publish_profile"
            )
        ) is False


def test_seed_rolls_back_on_failure(seed_database, monkeypatch):
    read_json = seed_demo._read_json

    def invalid_fixture(name):
        data = deepcopy(read_json(name))
        if name == "candidates.json":
            data["candidates"][1]["grade"] = "invalid-grade"
        return data

    monkeypatch.setattr(seed_demo, "_read_json", invalid_fixture)
    with pytest.raises(ValueError, match="Unknown grade"):
        seed_demo.main()
    counts = table_counts(seed_database)
    assert all(count == 0 for name, count in counts.items() if name != "alembic_version")
