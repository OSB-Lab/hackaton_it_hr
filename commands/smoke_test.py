#!/usr/bin/env python3
"""HTTP smoke test for a running «ФСП | ИТ-подбор» stack.

Read-only checks against a live API (no data is created). Demo credentials are
read from the seed fixtures in the repository, never hard-coded here.

Usage::

    python commands/smoke_test.py --base-url http://localhost:8000

Exit code 0 when every expectation matches, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED = REPO_ROOT / "services" / "api" / "app" / "commands" / "seed"


def credentials(name: str) -> str:
    return json.loads((SEED / name).read_text(encoding="utf-8"))["credentials"]["password"]


def call(base: str, path: str, method: str = "GET", body: dict | None = None,
         token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{base}{path}", data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw or b"null")
        except ValueError:
            return error.code, raw.decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    failures: list[str] = []

    def check(label: str, actual, expected):
        ok = actual == expected
        print(f"{'OK  ' if ok else 'FAIL'} {label}: {actual!r}" + ("" if ok else f" (expected {expected!r})"))
        if not ok:
            failures.append(label)

    status, live = call(base, "/health/live")
    check("GET /health/live", (status, live.get("status")), (200, "ok"))
    status, ready = call(base, "/health/ready")
    check("GET /health/ready", (status, ready.get("status")), (200, "ok"))

    status, _ = call(base, "/catalog")
    check("GET /catalog without token", status, 401)

    status, login = call(base, "/auth/login", "POST",
                         {"email": "candidate1@demo.example", "password": credentials("candidates.json")})
    check("POST /auth/login (candidate)", status, 200)
    candidate = login.get("access_token")

    status, login = call(base, "/auth/login", "POST",
                         {"email": "employer1@demo.example", "password": credentials("employers.json")})
    check("POST /auth/login (employer)", status, 200)
    employer = login.get("access_token")

    status, me = call(base, "/auth/me", token=candidate)
    check("GET /auth/me", (status, me.get("role")), (200, "candidate"))

    status, catalog = call(base, "/catalog", token=candidate)
    check("GET /catalog", status, 200)
    check("catalog tests count", len(catalog.get("tests", [])), 4)
    check("catalog statuses", {t["status"] for t in catalog.get("tests", [])}, {"DEMO"})
    check("catalog grades offered", sorted({t["grade"] for t in catalog.get("tests", [])}), ["junior", "middle"])

    status, profile = call(base, "/me/candidate-profile", token=candidate)
    check("GET /me/candidate-profile", status, 200)
    check("DEMO never certifies", profile.get("verifiedGrade"), None)

    status, _ = call(base, "/employer/needs", token=candidate)
    check("GET /employer/needs as candidate", status, 403)
    status, needs = call(base, "/employer/needs", token=employer)
    check("GET /employer/needs as employer", status, 200)
    check("employer needs are a list", isinstance(needs, list), True)

    status, inbox = call(base, "/invitations", token=candidate)
    check("GET /invitations (candidate inbox)", status, 200)

    print(f"\n{len(failures)} failed check(s)" if failures else "\nall smoke checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
