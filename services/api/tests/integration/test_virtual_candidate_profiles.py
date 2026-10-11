"""Deterministic virtual-candidate profiles over the shipped question bank.

NOT an LLM run and NOT grade validation. Each profile is a hand-written
competency model: a declared per-skill probability of answering correctly.
The harness only verifies that the platform's measurement pipeline behaves
consistently with those declared levels (scoring, thresholds, grade pointer,
DEMO refusal, senior availability).

Deterministic: every choice comes from a seeded RNG keyed by profile and
question id, so runs are reproducible.
"""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.models import CandidateProfile, Consent, TestAttempt, User
from app.modules.auth import security
from test_candidate_profile import env as assessment_env  # noqa: F401

# Declared competency model: skill tag -> probability of a correct answer.
# Values are author assumptions, never measured human performance.
PROFILES = {
    "backend_junior": {
        "specialization": "backend", "declared": "junior", "experience_months": 8,
        "knowledge": {"python": 0.45, "sql": 0.30, "api": 0.25, "teamwork": 0.55},
        "weak": ("sql", "api"),
    },
    "backend_middle": {
        "specialization": "backend", "declared": "middle", "experience_months": 36,
        "knowledge": {"python": 0.80, "sql": 0.70, "api": 0.65, "teamwork": 0.75},
        "weak": ("api",),
    },
    "backend_senior": {
        "specialization": "backend", "declared": "senior", "experience_months": 96,
        "knowledge": {"python": 0.95, "sql": 0.90, "api": 0.90, "teamwork": 0.90},
        "weak": (),
    },
    "frontend_junior": {
        "specialization": "frontend", "declared": "junior", "experience_months": 8,
        "knowledge": {"javascript": 0.45, "typescript": 0.30, "react": 0.35, "teamwork": 0.55},
        "weak": ("typescript", "react"),
    },
    "frontend_middle": {
        "specialization": "frontend", "declared": "middle", "experience_months": 36,
        "knowledge": {"javascript": 0.80, "typescript": 0.70, "react": 0.70, "teamwork": 0.75},
        "weak": ("react",),
    },
    "frontend_senior": {
        "specialization": "frontend", "declared": "senior", "experience_months": 96,
        "knowledge": {"javascript": 0.95, "typescript": 0.90, "react": 0.90, "teamwork": 0.90},
        "weak": (),
    },
}


def _candidate(engine, name, profile):
    with Session(engine) as session, session.begin():
        user = User(email=f"virtual-{name}@example.test", password_hash="fixture",
                    role="candidate", is_verified=True)
        session.add(user)
        session.flush()
        session.add(CandidateProfile(user_id=user.id, full_name="Virtual profile",
                                     specialization=profile["specialization"],
                                     stack=[profile["specialization"]],
                                     experience_months=profile["experience_months"],
                                     self_declared_grade=profile["declared"],
                                     privacy_settings={"publish_profile": True}))
        session.add(Consent(user_id=user.id, kind="publish_profile", granted=True))
        session.flush()
        header = {"Authorization": "Bearer " + security.create_access_token(user.id, "candidate")}
    return header


def _answers(engine, attempt_id, profile, seed):
    with Session(engine) as session:
        attempt = session.get(TestAttempt, attempt_id)
        questions = next(v["questions"] for v in attempt.snapshot["blueprint"]["variants"]
                         if v["id"] == attempt.variant)
    rng = random.Random(seed)
    body = []
    for question in questions:
        tags = question["skillTags"]
        accuracy = min(profile["knowledge"].get(tag, 0.5) for tag in tags)
        correct = question["answerKey"]["optionId"]
        if rng.random() < accuracy:
            body.append({"questionId": question["id"], "optionId": correct})
        else:
            wrong = [o["id"] for o in question["options"] if o["id"] != correct]
            body.append({"questionId": question["id"], "optionId": rng.choice(wrong)})
    return body


def _attempt(client, engine, header, profile, grade, seed):
    start = client.post("/assessments/start", headers=header,
                        json={"specialization": profile["specialization"], "grade": grade})
    if start.status_code != 201:
        return {"start": start.status_code, "detail": start.json()}
    attempt_id = start.json()["id"]
    variant = start.json()["assessment"]["variant"]
    submitted = client.post(f"/assessments/{attempt_id}/submit", headers=header,
                            json={"answers": _answers(engine, attempt_id, profile, seed)})
    result = submitted.json()["result"]
    profile_state = client.get("/me/candidate-profile", headers=header).json()
    return {"start": 201, "variant": variant, "outcome": result["outcome"],
            "correct": result["correctTechnical"], "subscores": result["subscores"],
            "status": result["status"], "retestOffer": result["retestOffer"],
            "verifiedGrade": profile_state["verifiedGrade"]}


def _assert_outcome_matches_thresholds(attempt):
    """The published outcome must follow the LOCKED 13/16 + 50/70 gates."""
    technical = {k: v for k, v in attempt["subscores"].items() if k != "teamwork"}
    low = min(technical.values())
    if attempt["outcome"] == "high":
        assert attempt["correct"] >= 16 and low >= 70, attempt
    elif attempt["outcome"] == "pass":
        assert attempt["correct"] >= 13 and low >= 50, attempt
    else:
        assert attempt["correct"] < 13 or low < 50, attempt


def test_virtual_profiles_are_deterministic_and_never_certified(assessment_env):
    client, _headers, _ids, engine = assessment_env
    observed = {}
    for index, (name, profile) in enumerate(PROFILES.items()):
        header = _candidate(engine, name, profile)
        if profile["declared"] == "senior":
            # The catalog knows 'senior', but no blueprint is published for it.
            outcome = _attempt(client, engine, header, profile, "senior", seed=index)
            assert outcome["start"] == 422, outcome
            observed[name] = outcome
            continue
        first = _attempt(client, engine, header, profile, profile["declared"], seed=index * 10)
        second = _attempt(client, engine, header, profile, profile["declared"], seed=index * 10 + 1)
        assert first["start"] == second["start"] == 201
        # Retests never reuse a recently seen form.
        assert first["variant"] != second["variant"]
        for attempt in (first, second):
            assert attempt["status"] == "DEMO"
            assert attempt["verifiedGrade"] is None
            _assert_outcome_matches_thresholds(attempt)
        observed[name] = first
    print("\nVIRTUAL_PROFILES=" + repr(observed))
    # A weaker declared profile must not outscore a stronger one on the same grade.
    assert observed["backend_junior"]["correct"] <= observed["backend_middle"]["correct"]
    assert observed["frontend_junior"]["correct"] <= observed["frontend_middle"]["correct"]


def test_senior_modelled_candidate_on_middle_form(assessment_env):
    """Ceiling check: the hardest shipped form is solvable by a senior profile."""
    client, _headers, _ids, engine = assessment_env
    header = _candidate(engine, "backend_senior_on_middle", PROFILES["backend_senior"])
    outcome = _attempt(client, engine, header, PROFILES["backend_senior"], "middle", seed=4242)
    print("\nSENIOR_ON_MIDDLE=" + repr(outcome))
    assert outcome["start"] == 201
    assert outcome["verifiedGrade"] is None  # DEMO content still cannot certify

