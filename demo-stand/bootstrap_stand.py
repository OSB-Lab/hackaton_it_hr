"""Bootstrap the TEST-ONLY demo stand with synthetic candidates and a positive cohort.

Runs INSIDE the stand's api container (has app code, DB access and network access):

  docker compose -p fsptest -f demo-stand/docker-compose.stand.yml run --rm api \
      python /stand/bootstrap_stand.py

Everything is created through the public HTTP API on the running stand:
registration, email verification (token read from Mailpit), profile + consents,
assessment start/submit, employer company, hiring need, ranking snapshot and
invitation acceptance. No eligibility rule, threshold or contract is bypassed:
candidates answer the real test and are certified by the real scorer because the
stand runs against a TEST-ONLY APPROVED catalog copy.

All accounts are clearly marked synthetic (email domain test-only.local,
"СИНТЕТИЧЕСКИЙ" in fullName).
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request

API = "http://api:8000"
MAILPIT = "http://mailpit:8025"
PASSWORD = "StandDemo2026!"
EMPLOYER_EMAIL = "stand-employer@test-only.local"
CANDIDATES = [
    ("stand-candidate-1@test-only.local", "СИНТЕТИЧЕСКИЙ Кандидат 1 (TEST-ONLY) · сильный", 60, []),
    ("stand-candidate-2@test-only.local", "СИНТЕТИЧЕСКИЙ Кандидат 2 (TEST-ONLY) · средний", 36, [("api", 1)]),
    ("stand-candidate-3@test-only.local", "СИНТЕТИЧЕСКИЙ Кандидат 3 (TEST-ONLY) · базовый", 24, [("python", 2)]),
]
REQUIRED_SKILLS = ["python", "sql", "api"]


def call(method, url, body=None, token=None, expect=(200, 201)):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw, status = response.read().decode(), response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read().decode(), error.code
    if status not in expect:
        raise SystemExit(f"{method} {url} -> {status}: {raw[:400]}")
    return json.loads(raw) if raw else {}


def mailpit_token(email):
    for _ in range(30):
        payload = call("GET", f"{MAILPIT}/api/v1/messages")
        for summary in payload.get("messages", []):
            recipients = [t.get("Address", "") for t in summary.get("To", [])]
            if email in recipients:
                message = call("GET", f"{MAILPIT}/api/v1/message/{summary['ID']}")
                text = " ".join(str(message.get(key) or "") for key in ("Text", "HTML"))
                match = re.search(r'"token"\s*:\s*"([^"\\]+)"', text) or re.search(
                    r"token=([A-Za-z0-9._\-]+)", text)
                if match:
                    return match.group(1)
        time.sleep(1)
    raise SystemExit(f"verification email for {email} not found in Mailpit")


def register_and_login(email, role):
    try:
        call("POST", f"{API}/auth/register", {"email": email, "password": PASSWORD, "role": role})
        call("POST", f"{API}/auth/verify-email", {"token": mailpit_token(email)})
    except SystemExit as error:
        if "409" not in str(error) and "400" not in str(error):
            raise
        print(f"  note: {email} already registered, reusing")
    return call("POST", f"{API}/auth/login", {"email": email, "password": PASSWORD})["access_token"]


def attempt_snapshot(attempt_id):
    from sqlalchemy import create_engine, text
    from app.core.config import get_settings
    engine = create_engine(get_settings().DATABASE_URL)
    with engine.connect() as connection:
        row = connection.execute(
            text("select snapshot, variant from test_attempts where id = :id"), {"id": attempt_id}).one()
    return row[0], row[1]


def plan_answers(snapshot, variant, wrong_plan):
    questions = next(v["questions"] for v in snapshot["blueprint"]["variants"] if v["id"] == variant)
    wrong_ids, plan = set(), list(wrong_plan)
    for question in questions:
        for tag, count in list(plan):
            if count and question["skillTags"] == [tag]:
                wrong_ids.add(question["id"])
                plan[plan.index((tag, count))] = (tag, count - 1)
                break
    answers = []
    for question in questions:
        options = [o["id"] for o in question["options"]]
        correct = question["answerKey"]["optionId"]
        chosen = next(o for o in options if o != correct) if question["id"] in wrong_ids else correct
        answers.append({"questionId": question["id"], "optionId": chosen})
    return answers


def certify(email, full_name, months, wrong_plan):
    token = register_and_login(email, "candidate")
    profile = call("PATCH", f"{API}/me/candidate-profile", {
        "fullName": full_name, "specialization": "backend", "stack": REQUIRED_SKILLS,
        "experienceMonths": months, "consents": {"processing": True, "publication": True},
        "privacy": {"showContacts": True}}, token=token)
    started = call("POST", f"{API}/assessments/start", {"specialization": "backend", "grade": "junior"}, token=token)
    snapshot, variant = attempt_snapshot(started["id"])
    submitted = call("POST", f"{API}/assessments/{started['id']}/submit",
                     {"answers": plan_answers(snapshot, variant, wrong_plan)}, token=token)
    result = submitted["result"]
    print(f"  {email}: outcome={result['outcome']} technical={result['correctTechnical']}/18 "
          f"verifiedGrade={result['verifiedGrade']} subscores="
          f"{ {k: round(v, 2) for k, v in result['subscores'].items()} }")
    if result.get("verifiedGrade") is None:
        raise SystemExit(f"{email} was not certified: {result}")
    return {"email": email, "token": token, "candidateId": profile["id"], "result": result}


def create_need(employer):
    return call("POST", f"{API}/employer/needs", {
        "title": "TEST-ONLY: Backend-разработчик (junior)", "specialization": "backend",
        "minGrade": "junior", "targetGrade": "middle",
        "requiredSkills": REQUIRED_SKILLS, "optionalSkills": []}, token=employer)


def main():
    print("== TEST-ONLY demo stand bootstrap (synthetic data) ==")
    print("1/5 candidates certified through the real API")
    candidates = [certify(email, name, months, plan) for email, name, months, plan in CANDIDATES]

    print("2/5 employer")
    employer = register_and_login(EMPLOYER_EMAIL, "employer")
    company = call("PUT", f"{API}/employer/company",
                   {"name": "Тестовый работодатель (TEST-ONLY)",
                    "description": "Изолированный демонстрационный стенд",
                    "contacts": {"email": "hr@test-only.local"}}, token=employer)

    print("3/5 hiring need")
    need = create_need(employer)

    print("4/5 ranking snapshot")
    snapshot = call("POST", f"{API}/employer/needs/{need['id']}/recommendations", token=employer)
    items = snapshot["items"]
    print(f"  cohort size: {len(items)}")
    for item in items:
        print(f"  #{item['rank']} candidate {item['candidate']['id']} score={item['score']:.4f} "
              f"components={ {k: round(v, 4) for k, v in item['components'].items()} }")
    scores = [item["score"] for item in items]
    if len(items) != len(CANDIDATES) or len(set(scores)) != len(scores):
        raise SystemExit("cohort is empty or scores are not distinct")
    if [item["rank"] for item in items] != list(range(1, len(items) + 1)):
        raise SystemExit("ranks are not sequential")

    print("5/5 invitation + acceptance + contact disclosure")
    top = items[0]["candidate"]["id"]
    invitation = call("POST", f"{API}/invitations", {
        "companyId": company["id"], "candidateId": top,
        "offerDescription": "TEST-ONLY: backend junior offer", "contactMethod": "email",
        "salaryMin": "120000.00", "salaryMax": "180000.00", "currency": "RUB"}, token=employer)
    winner = next(c for c in candidates if c["candidateId"] == top)
    inbox = call("GET", f"{API}/invitations", token=winner["token"])
    accepted = call("POST", f"{API}/invitations/{invitation['id']}/accept", token=winner["token"])
    disclosed = call("GET", f"{API}/invitations/{invitation['id']}", token=employer)
    print(f"  invitation {invitation['id']}: status={accepted['status']} contacts={disclosed['contacts']}")
    if disclosed.get("contacts") is None:
        raise SystemExit("contacts were not disclosed after acceptance")

    print("\n== READY ==")
    print("stand UI       : http://localhost:3100")
    print("stand API      : http://localhost:8100")
    print("stand Mailpit  : http://localhost:8125")
    print(f"employer login : {EMPLOYER_EMAIL} / {PASSWORD}")
    for email, _name, _months, _plan in CANDIDATES:
        print(f"candidate login: {email} / {PASSWORD}")
    print(f"need id {need['id']} | snapshot {snapshot['id']} | company {company['id']} | "
          f"candidate inbox {len(inbox)} invitation(s)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as error:  # keep failures visible in the stand log
        print(f"BOOTSTRAP FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        raise
