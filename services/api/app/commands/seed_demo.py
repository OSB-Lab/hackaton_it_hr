import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    CandidateProfile, Company, CompetencyScore, Consent, FspAchievement,
    FspLink, HiringNeed, User,
)

SEED_DIR = Path(__file__).with_name("seed")


def _read_json(name: str) -> Any:
    return json.loads((SEED_DIR / name).read_text(encoding="utf-8"))


def _ensure(session: Session, model, key: dict, values: dict) -> int:
    # Database constraints also prevent duplicates from concurrent seed runs.
    statement = (
        insert(model)
        .values(**key, **values)
        .on_conflict_do_nothing(index_elements=list(key))
        .returning(model.id)
    )
    record_id = session.scalar(statement)
    if record_id is None:
        record_id = session.scalars(
            select(model.id).where(
                *(getattr(model, column) == value for column, value in key.items())
            )
        ).one()
    return record_id


def _seed_consents(session: Session, user_id: int, consents: list[dict]) -> None:
    for consent in consents:
        _ensure(
            session, Consent, {"user_id": user_id, "kind": consent["kind"]},
            {
                "granted": consent["granted"],
                "granted_at": (
                    datetime.fromisoformat(consent["granted_at"])
                    if consent["granted_at"] else None
                ),
            },
        )


def seed_demo(session: Session) -> None:
    catalog = _read_json("catalog.json")
    candidate_data = _read_json("candidates.json")
    employer_data = _read_json("employers.json")
    evidence_data = _read_json("fsp_evidence.json")
    evidence_by_email = {entry["email"]: entry for entry in evidence_data}
    specializations = {entry["id"] for entry in catalog["specializations"]}

    for candidate in candidate_data["candidates"]:
        if candidate["specialization"] not in specializations:
            raise ValueError(f"Unknown specialization: {candidate['specialization']}")
        if candidate["grade"] not in catalog["grades"]:
            raise ValueError(f"Unknown grade: {candidate['grade']}")
        for score in candidate["competency_scores"]:
            if score["competency"] not in catalog["competencies"]:
                raise ValueError(f"Unknown competency: {score['competency']}")

        user_id = _ensure(
            session, User, {"email": candidate["email"]},
            {
                "password_hash": candidate_data["credentials"]["password_hash"],
                "role": "candidate",
                "is_verified": True,
            },
        )
        candidate_id = _ensure(
            session, CandidateProfile, {"user_id": user_id},
            {key: candidate[key] for key in (
                "full_name", "stack", "grade", "specialization", "privacy_settings"
            )},
        )
        _seed_consents(session, user_id, candidate_data["consents"])

        for score in candidate["competency_scores"]:
            _ensure(
                session, CompetencyScore,
                {
                    "candidate_id": candidate_id,
                    "competency": score["competency"],
                    "source": score["source"],
                },
                {"score": score["score"]},
            )

        evidence = evidence_by_email.get(candidate["email"])
        _ensure(
            session, FspLink, {"candidate_id": candidate_id},
            {
                "status": "linked" if evidence else "no_history",
                "fsp_id": evidence["fsp_id"] if evidence else None,
                "linked_at": datetime.fromisoformat(evidence["linked_at"]) if evidence else None,
            },
        )
        for achievement in evidence["achievements"] if evidence else []:
            _ensure(
                session, FspAchievement,
                {
                    "candidate_id": candidate_id,
                    "discipline": achievement["discipline"],
                    "competition": achievement["competition"],
                },
                {key: achievement[key] for key in ("result", "role", "rank")},
            )

    for employer in employer_data["employers"]:
        user_id = _ensure(
            session, User, {"email": employer["email"]},
            {
                "password_hash": employer_data["credentials"]["password_hash"],
                "role": "employer",
                "is_verified": True,
            },
        )
        company_id = _ensure(
            session, Company, {"user_id": user_id},
            {key: employer[key] for key in ("name", "description", "contacts")},
        )
        _seed_consents(session, user_id, employer_data["consents"])
        for need in employer["hiring_needs"]:
            _ensure(
                session, HiringNeed,
                {"company_id": company_id, "title": need["title"]},
                {key: need[key] for key in ("stack", "grade", "specialization")},
            )


def main() -> None:
    # A failed seed rolls back all changes; existing records are preserved.
    with SessionLocal.begin() as session:
        seed_demo(session)
    print("seed completed")


if __name__ == "__main__":
    main()
