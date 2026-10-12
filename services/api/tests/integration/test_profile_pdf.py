from io import BytesIO

import pytest
from pypdf import PdfReader
from pypdf.generic import IndirectObject, DictionaryObject, ArrayObject, StreamObject
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import CandidateProfile
from test_candidate_profile import env
from test_assessment_v3_lifecycle import approved, start, submit

URL = "/me/profile-pdf"
PROFILE = "/me/candidate-profile"


def read(response):
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="candidate-profile.pdf"'
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"%PDF-")
    reader = PdfReader(BytesIO(response.content), strict=True)
    return reader, "\n".join(page.extract_text() for page in reader.pages)


def inspect_objects(reader):
    """Inspect decoded streams, strings, metadata and the entire reachable object graph."""
    seen = set()
    values = []

    def walk(value):
        if isinstance(value, IndirectObject):
            key = (value.idnum, value.generation)
            if key in seen:
                return
            seen.add(key)
            return walk(value.get_object())
        if isinstance(value, StreamObject):
            values.append(value.get_data())
        if isinstance(value, DictionaryObject):
            for key, child in value.items():
                values.append(str(key).encode())
                walk(child)
        elif isinstance(value, ArrayObject):
            for child in value:
                walk(child)
        elif isinstance(value, bytes):
            values.append(value)
        else:
            values.append(str(value).encode())

    walk(reader.trailer)
    return b"\n".join(values)


@pytest.mark.parametrize("actor,status", [(None, 401), (2, 403)])
def test_pdf_access(env, actor, status):
    client, headers, _, _ = env
    assert client.get(URL, headers=headers[actor] if actor is not None else {}).status_code == status


def test_pdf_fields_unicode_escaping_ownership_and_private_data(env):
    client, headers, ids, engine = env
    payload = {"fullName": 'Иван <script> & «Петров»', "specialization": "Бэкенд",
               "stack": ["Python", "Базы данных", '<a href="https://example.org">SQL</a>'],
               "phone": "+7 999 123-45-67", "selfDeclaredGrade": "senior"}
    assert client.patch(PROFILE, headers=headers[0], json=payload).status_code == 200
    response = client.get(URL, headers=headers[0])
    reader, text = read(response)
    for value in (payload["fullName"], "Бэкенд", "Python", "Базы данных", payload["stack"][2]):
        assert value in text
    assert "Квалификация не подтверждена" in text
    assert "senior" not in text and "Other owner" not in text
    decoded = inspect_objects(reader)
    for secret in ("user0@example.com", "+7 999 123-45-67", "user1@example.com", "Other owner"):
        assert secret not in text
        for encoded in (secret.encode(), secret.encode("utf-16-be"), secret.encode("utf-16-le")):
            assert encoded not in decoded
    assert all(not page.get("/Annots") for page in reader.pages)
    assert b"/JavaScript" not in decoded and b"/EmbeddedFiles" not in decoded
    for parameter in ("candidate_id", "user_id", "profileId"):
        assert client.get(URL, headers=headers[0], params={parameter: ids[1]}).status_code == 422
    # A GET body also cannot select another identity.
    _, own = read(client.request("GET", URL, headers=headers[0], json={"candidate_id": ids[1]}))
    assert "Other owner" not in own
    with Session(engine) as session:
        other = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[1]))
        assert other.full_name == "Other owner"


@pytest.mark.parametrize("permission", [False, True])
def test_contacts_never_exported_even_in_free_text(env, permission):
    client, headers, _, _ = env
    client.patch(PROFILE, headers=headers[0], json={
        "fullName": "user0@example.com", "phone": "+7 999 123-45-67",
        "stack": ["Python", "+7 999 123-45-67", "user0@example.com"],
        "privacy": {"showContacts": permission},
        "consents": {"publication": permission, "processing": permission}})
    reader, text = read(client.get(URL, headers=headers[0]))
    assert "Python" in text
    for secret in ("user0@example.com", "+7 999 123-45-67"):
        assert secret not in text and secret.encode() not in inspect_objects(reader)


def test_missing_profile_and_openapi(env):
    client, headers, _, _ = env
    assert client.get(URL, headers=headers[0]).status_code == 404
    assert "application/pdf" in app.openapi()["paths"][URL]["get"]["responses"]["200"]["content"]


def test_qualification_requires_approved_submitted_evidence(env, approved):
    client, headers, _, _ = env
    client.patch(PROFILE, headers=headers[0], json={"fullName": "Кандидат"})
    attempt = start(env).json()
    _, before = read(client.get(URL, headers=headers[0]))
    assert "Квалификация не подтверждена" in before
    assert submit(env, attempt["id"]).status_code == 200
    _, after = read(client.get(URL, headers=headers[0]))
    assert "backend — junior" in after
    assert "Квалификация не подтверждена" not in after
    assert "answerKey" not in after and "correctTechnical" not in after
