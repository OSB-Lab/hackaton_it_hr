from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy.orm import Session

from app.models import CandidateProfile, TestAttempt as Attempt
from app.modules.assessments import service
from test_assessments import prepare, START, BODY
from test_candidate_profile import env as assessment_env


def started(env, correct=2):
    client, headers, ids, engine = prepare(env)
    data = client.post(START, headers=headers[0], json=BODY).json()
    with Session(engine) as session:
        row = session.get(Attempt, data['id'])
        questions = next(v['questions'] for v in row.snapshot['blueprint']['variants'] if v['id'] == row.variant)
        answers = [{'questionId': q['id'], 'optionId': q['answerKey']['optionId'] if i < correct else
                    next(o['id'] for o in q['options'] if o['id'] != q['answerKey']['optionId'])}
                   for i, q in enumerate(questions)]
    return data, {'answers': answers}


@pytest.mark.parametrize('correct,total,outcome', [(0, 0, 'fail'), (1, 50, 'pass'), (2, 100, 'high')])
@pytest.mark.parametrize('variant', ['A', 'B'])
def test_submit_boundaries_and_persistence(assessment_env, monkeypatch, correct, total, outcome, variant):
    monkeypatch.setattr(service.secrets, 'choice', lambda _: variant)
    data, body = started(assessment_env, correct)
    client, headers, _, engine = assessment_env
    with Session(engine) as session, session.begin():
        row = session.get(Attempt, data['id'])
        profile = session.get(CandidateProfile, row.candidate_id)
        profile.grade = 'senior'
        profile.self_declared_grade = 'middle'
        profile.specialization = 'backend'
        snapshot = row.snapshot
    def unavailable():
        raise AssertionError('Submit must use saved snapshot')
    monkeypatch.setattr(service, 'CatalogRepository', unavailable)
    path = f"/assessments/{data['id']}/submit"
    response = client.post(path, headers=headers[0], json=body)
    assert response.status_code == 200
    result = response.json()['result']
    assert result['totalScore'] == total and result['outcome'] == outcome and result['status'] == 'DEMO'
    expected = {slot['skillId']: (100 if i < correct else 0) for i, slot in enumerate(snapshot['blueprint']['slots'])}
    assert result['subscores'] == expected
    for forbidden in ('answerKey', 'rubric', 'scoring', 'threshold', 'weight', 'maxScore', 'optionId'):
        assert forbidden not in response.text
        assert forbidden not in client.get(f"/assessments/{data['id']}", headers=headers[0]).text
    monkeypatch.setattr(service, 'score_answers', unavailable)
    assert client.post(path, headers=headers[0], json={'answers': []}).json() == response.json()
    with Session(engine) as session:
        row = session.get(Attempt, data['id'])
        assert row.status == 'submitted' and row.submitted_at is not None
        assert row.answers == body['answers'] and row.score == total and row.result == result
        assert row.snapshot == snapshot and row.grade is None
        profile = session.get(CandidateProfile, row.candidate_id)
        assert (profile.grade, profile.self_declared_grade, profile.specialization) == ('senior', 'middle', 'backend')


@pytest.mark.parametrize('case', ['missing', 'extra', 'duplicate', 'option', 'type', 'unknown_field', 'missing_option'])
def test_invalid_answers_leave_attempt_active(assessment_env, case):
    data, body = started(assessment_env)
    client, headers, _, engine = assessment_env
    if case == 'missing': body['answers'].pop()
    elif case == 'extra': body['answers'].append({'questionId': 'unknown', 'optionId': None})
    elif case == 'duplicate': body['answers'][1] = body['answers'][0]
    elif case == 'option': body['answers'][0]['optionId'] = 'unknown'
    elif case == 'type': body['answers'][0]['optionId'] = 1
    elif case == 'unknown_field': body['answers'][0]['score'] = 100
    elif case == 'missing_option': del body['answers'][0]['optionId']
    assert client.post(f"/assessments/{data['id']}/submit", headers=headers[0], json=body).status_code == 422
    with Session(engine) as session:
        row = session.get(Attempt, data['id'])
        assert row.status == 'active' and row.answers == []
        assert row.result is row.score is row.submitted_at is None


def test_submit_access_and_legacy(assessment_env):
    data, body = started(assessment_env)
    client, headers, _, engine = assessment_env
    path = f"/assessments/{data['id']}/submit"
    for actor, status in [(1, 404), (2, 403)]:
        assert client.post(path, headers=headers[actor], json=body).status_code == status
    assert client.post(path, json=body).status_code == 401
    assert client.post('/assessments/999999/submit', headers=headers[0], json=body).status_code == 404
    with Session(engine) as session, session.begin():
        row = session.get(Attempt, data['id'])
        row.snapshot = None
        row.status = 'legacy'
    assert client.post(path, headers=headers[0], json=body).status_code == 409
    with Session(engine) as session:
        row = session.get(Attempt, data['id'])
        assert row.status == 'legacy' and row.answers == [] and row.result is None


def test_concurrent_submit_first_result_wins(assessment_env):
    data, body = started(assessment_env)
    client, headers, _, engine = assessment_env
    other = {'answers': [dict(a, optionId=None) for a in body['answers']]}
    barrier = Barrier(2)
    def submit(payload):
        barrier.wait(timeout=10)
        return client.post(f"/assessments/{data['id']}/submit", headers=headers[0], json=payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit, payload) for payload in (body, other)]
        responses = [f.result(timeout=20) for f in futures]
    assert all(r.status_code == 200 for r in responses)
    assert responses[0].json() == responses[1].json()
    with Session(engine) as session:
        row = session.get(Attempt, data['id'])
        assert row.answers in (body['answers'], other['answers'])
        assert row.result == responses[0].json()['result']
        assert row.score == (100 if row.answers == body['answers'] else 0)


@pytest.fixture(autouse=True)
def legacy_catalog(monkeypatch, tmp_path):
    import json, shutil
    from app.modules.catalog.repository import CatalogRepository, DATA_ROOT
    root = tmp_path / 'legacy_catalog'
    shutil.copytree(DATA_ROOT, root)
    path = root / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['activeCatalog'] = next(r['key'] for r in manifest['artifacts'] if r['kind'] == 'catalog' and r['version'] == 'v1-demo')
    manifest['activeBlueprints'] = [r['key'] for r in manifest['artifacts'] if r['kind'] == 'blueprint' and r['version'] == 'v1-demo']
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(service, 'CatalogRepository', lambda: CatalogRepository(root))
