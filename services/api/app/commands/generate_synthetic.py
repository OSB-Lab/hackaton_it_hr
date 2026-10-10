"""Explicitly isolated, fail-closed synthetic profiles; no fabricated qualification."""
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.db.base import Base
from app.modules.assessments.schemas import Answer, AttemptSnapshot, SubmitRequest
from app.modules.assessments.scoring_v3 import score_v3
from app.modules.auth.security import hash_password
from app.modules.catalog.repository import CatalogRepository
from app.modules.employer.needs_service import validate_values
from app.modules.recommendations.eligibility import POLICY_VERSION, evaluate_candidate

CONFIRMATION = "ISOLATED_SYNTHETIC_DATABASE_ONLY"
VERSION = "synthetic-profiles-v1"
GROUPS = [("ready_except_qualification", 20), ("specialization", 10),
          ("grade", 10), ("required_skills", 10), ("publication", 12),
          ("email", 12), ("qualification", 24)]
# Deterministic, clearly synthetic enrichment (no real personal data).
SOFT_SKILLS = ["Коммуникация", "Работа в команде", "Самоорганизация",
               "Критическое мышление", "Инициативность", "Наставничество"]


def validate_target(url, confirmation):
    target = make_url(url)
    normal = make_url(get_settings().DATABASE_URL)
    if (confirmation != CONFIRMATION or target.drivername != "postgresql+psycopg"
            or target.host not in {"localhost", "127.0.0.1", "postgres"}
            or target.query or not re.fullmatch(r"fsp_(?:synthetic|test)_[0-9a-f]{32}", target.database or "")
            or target.database == normal.database):
        raise ValueError("Refusing non-isolated database or missing confirmation")
    return target


def fingerprint(session):
    # Whole-domain fingerprint detects collisions/drift; no passwords/PII exported.
    data = {}
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        data[table.name] = [dict(row) for row in session.execute(select(table).order_by(table.c.id)).mappings()]
    raw = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def generate(url, manifest_path, password, confirmation, batch="mvp100"):
    target = validate_target(url, confirmation)
    if not re.fullmatch(r"[a-z0-9-]{1,32}", batch) or len(password) < 12:
        raise ValueError("Invalid batch or password shorter than 12 characters")
    repo = CatalogRepository()
    repo.validate_all()
    catalog = repo.catalog()
    if catalog.document.status != "DEMO":
        raise ValueError("This safe-profile fixture is defined for the current DEMO catalog")
    specs = sorted(catalog.document.specializations, key=lambda s: s.id)
    grades = sorted(catalog.document.grades, key=lambda g: g.order)
    if len(specs) < 2 or len(grades) < 2:
        raise ValueError("Fixture requires two specializations and grades")
    skills = [s for s in specs[0].skillIds if s != "teamwork"]
    if len(skills) < 3:
        raise ValueError("Fixture requires three technical skills")
    manifest_path = Path(manifest_path)
    engine = create_engine(target, connect_args={"connect_timeout": 5})
    try:
        with Session(engine) as session, session.begin():
            # Serialize generator runs without creating schema objects.
            session.execute(text("SELECT pg_advisory_xact_lock(781901100)"))
            if session.scalar(text("SELECT current_database()")) != target.database:
                raise ValueError("Unexpected connected database")
            if session.scalar(text("SELECT version_num FROM alembic_version")) != "0010":
                raise ValueError("Expected pre-provisioned schema 0010; no migrations are run")
            if manifest_path.exists():
                saved = json.loads(manifest_path.read_text(encoding="utf-8"))
                expected = (VERSION, target.database, batch, catalog.checksum, POLICY_VERSION)
                actual = tuple(saved.get(k) for k in ("version", "database", "batch", "catalogChecksum", "policyVersion"))
                if actual != expected or saved.get("databaseFingerprint") != fingerprint(session):
                    raise ValueError("Manifest conflict or database drift; no existing records changed")
                return saved
            if any(session.scalar(select(t.c.id).limit(1)) is not None for t in Base.metadata.tables.values()):
                raise ValueError("Initial run requires empty domain tables; refusing existing accounts/data")
            need_values = dict(title="Synthetic backend team", teamDescription="Synthetic fixture team",
                               specialization=specs[0].id, minGrade=grades[1].id, targetGrade=grades[1].id,
                               requiredSkills=skills[:2], optionalSkills=skills[2:3])
            validate_values(need_values, set(need_values))
            candidates, employers = [], []
            ordinal = 0
            for group, count in GROUPS:
                for _ in range(count):
                    ordinal += 1
                    user = models.User(email=f"{batch}-candidate-{ordinal:03}@example.test",
                                       password_hash=hash_password(password), role="candidate",
                                       is_verified=group != "email")
                    session.add(user)
                    session.flush()
                    spec_id = specs[1].id if group == "specialization" else specs[0].id
                    roles = (["Backend-разработчик", "Python-инженер", "Бэкенд-разработчик", "DevOps-инженер"]
                             if spec_id == specs[0].id else
                             ["Frontend-разработчик", "React-разработчик", "Веб-разработчик", "UI-инженер"])
                    profile = models.CandidateProfile(user_id=user.id, full_name=f"Синтетический кандидат {ordinal:03}",
                        specialization=spec_id,
                        self_declared_grade=grades[0 if group == "grade" else 1].id,
                        stack=[] if group == "required_skills" else list((specs[1] if spec_id == specs[1].id else specs[0]).skillIds),
                        professional_role=roles[ordinal % len(roles)],
                        experience_months=6 + (ordinal * 7) % 96,
                        phone=f"+7 900 {ordinal:03d} {ordinal:03d} {ordinal:03d}",
                        soft_skills=[SOFT_SKILLS[(ordinal + i) % len(SOFT_SKILLS)] for i in range(2 + ordinal % 3)],
                        privacy_settings={"publish_profile": group != "publication", "show_contacts": False})
                    session.add(profile)
                    session.add_all([models.Consent(user_id=user.id, kind="privacy", granted=True),
                        models.Consent(user_id=user.id, kind="publish_profile", granted=group != "publication")])
                    session.flush()
                    reasons = (["EMAIL_UNVERIFIED"] if group == "email" else
                               ["PUBLICATION_NOT_ALLOWED"] if group == "publication" else [])
                    reasons.append("QUALIFICATION_UNCONFIRMED")
                    # Independent expected labels, never inferred from evaluator output.
                    candidates.append(dict(userId=user.id, candidateId=profile.id, group=group,
                        expected={"eligible": False, "reasonCodes": reasons, "missingRequiredSkills": [],
                                  "policyVersion": POLICY_VERSION}))
            # DEMO test scenarios: an active attempt and a submitted (non-certifying)
            # DEMO attempt. DEMO content never sets a verified grade.
            demo_attempts = []
            demo_spec, demo_grade = specs[0].id, grades[1].id
            demo_loaded = next(loaded for key in repo.manifest.activeBlueprints
                               if (loaded := repo.blueprint(key)).document.specialization == demo_spec
                               and loaded.document.grade == demo_grade)
            demo_blueprint = demo_loaded.document
            demo_catalog = repo.catalog(demo_blueprint.catalogVersion)
            snapshot = AttemptSnapshot(schemaVersion=1, blueprint=demo_blueprint, catalog=demo_catalog.document)
            variant = demo_blueprint.variants[0].id
            questions = next(v.questions for v in demo_blueprint.variants if v.id == variant)
            correct_answers = [Answer(questionId=q.id, optionId=q.answerKey.optionId) for q in questions]
            for index, cand in enumerate([c for c in candidates if c["group"] == "qualification"][:6]):
                pid = cand["candidateId"]
                common = dict(candidate_id=pid, test_id=demo_blueprint.id,
                              specialization=demo_spec, requested_grade=demo_grade,
                              blueprint_version=demo_blueprint.version, catalog_version=demo_catalog.document.version,
                              blueprint_checksum=demo_loaded.checksum, catalog_checksum=demo_catalog.checksum,
                              snapshot_schema_version=1, snapshot=snapshot.model_dump(mode="json"),
                              variant=variant, content_status="DEMO")
                if index % 2 == 0:
                    attempt = models.TestAttempt(**common, status="active", submitted_at=None)
                    session.add(attempt)
                    session.flush()
                    demo_attempts.append(dict(candidateId=pid, attemptId=attempt.id, status="active"))
                else:
                    result = score_v3(demo_blueprint, variant, SubmitRequest(answers=correct_answers))
                    attempt = models.TestAttempt(**common, status="submitted",
                        answers=[a.model_dump(mode="json") for a in correct_answers],
                        score=result.totalScore, result=result.model_dump(mode="json"),
                        submitted_at=datetime.now(timezone.utc))
                    session.add(attempt)
                    session.flush()
                    demo_attempts.append(dict(candidateId=pid, attemptId=attempt.id, status="submitted",
                                              outcome=result.outcome))
            for index in range(2):
                user = models.User(email=f"{batch}-employer-{index + 1}@example.test",
                    password_hash=hash_password(password), role="employer", is_verified=True)
                session.add(user)
                session.flush()
                company = models.Company(user_id=user.id, name=f"Синтетическая компания {index + 1}")
                session.add(company)
                session.flush()
                need = models.HiringNeed(company_id=company.id, title=need_values["title"],
                    team_description=need_values["teamDescription"], specialization=need_values["specialization"],
                    min_grade=need_values["minGrade"], grade=need_values["targetGrade"],
                    stack=need_values["requiredSkills"], optional_skills=need_values["optionalSkills"])
                session.add(need)
                session.flush()
                employers.append(dict(userId=user.id, companyId=company.id, needId=need.id))
            reference = session.get(models.HiringNeed, employers[0]["needId"])
            for candidate in candidates:
                if evaluate_candidate(session, candidate["candidateId"], reference).model_dump(mode="json") != candidate["expected"]:
                    raise ValueError("Eligibility differs from independent fixture labels")
            saved = dict(version=VERSION, database=target.database, batch=batch, catalogVersion=catalog.document.version,
                         catalogChecksum=catalog.checksum, policyVersion=POLICY_VERSION,
                         candidates=candidates, employers=employers, eligibleCount=0,
                         demoAttempts=demo_attempts,
                         positiveScenarios="BLOCKED: no real APPROVED qualification",
                         databaseFingerprint=fingerprint(session))
            # Exclusive creation: never overwrite another manifest. Written before
            # commit; failed commit leaves a nonmatching manifest and rerun fails closed.
            with manifest_path.open("x", encoding="utf-8") as output:
                json.dump(saved, output, ensure_ascii=False, indent=2)
            return saved
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-isolated", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--batch", default="mvp100")
    args = parser.parse_args()
    try:
        result = generate(os.environ["SYNTHETIC_DATABASE_URL"], args.manifest,
                          os.environ["SYNTHETIC_PASSWORD"], args.confirm_isolated, args.batch)
    except Exception:
        # Do not print SQL parameters, connection strings, password hashes or secrets.
        parser.exit(1, "Generation refused/failed. Check isolation, empty schema, manifest and catalog; no automatic repair.\n")
    print(json.dumps({"users": len(result["candidates"]) + len(result["employers"]),
                      "eligible": result["eligibleCount"], "positiveScenarios": result["positiveScenarios"]}))


if __name__ == "__main__":
    main()
