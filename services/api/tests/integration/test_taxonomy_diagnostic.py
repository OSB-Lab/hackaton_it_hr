from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, TestAttempt as AssessmentAttempt, CompetencyScore
from app.commands.import_taxonomy_questions import seed_bank
from test_candidate_profile import env


def test_missing_db_bank_fails_closed_even_with_static_import_file(env):
    client, headers, _, _ = env
    assert client.get('/assessments/taxonomy/catalog', headers=headers[0]).status_code == 503
    assert client.patch('/me/candidate-profile', headers=headers[0],
                        json={'specialization': 'fullstack'}).status_code == 200
    assert client.post('/assessments/taxonomy/start', headers=headers[0],
                       json={'specialization': 'fullstack', 'grade': 'senior'}).status_code == 503


def test_only_selection_and_order_are_random_not_question_content(env, monkeypatch):
    from app.modules.assessments import taxonomy_service
    from app.modules.assessments.taxonomy_bank import load_seed_bank
    from app.models import TaxonomyQuestionForm
    client, headers, _, engine = env
    with Session(engine) as session, session.begin():
        seed_bank(session)
    assert client.patch('/me/candidate-profile', headers=headers[0],
                        json={'specialization': 'fullstack'}).status_code == 200
    class Reverse:
        def shuffle(self, values): values.reverse()
    monkeypatch.setattr(taxonomy_service.secrets, 'choice', lambda values: values[0])
    monkeypatch.setattr(taxonomy_service.secrets, 'SystemRandom', lambda: Reverse())
    source = load_seed_bank().cell('fullstack', 'senior').forms[0]
    response = client.post('/assessments/taxonomy/start', headers=headers[0],
                           json={'specialization': 'fullstack', 'grade': 'senior'})
    assert response.status_code == 201
    data = response.json()
    assert data['assessment']['variant'] == 'A'
    assert [q['id'] for q in data['assessment']['questions']] == [q.id for q in reversed(source.questions)]
    with Session(engine) as session:
        row = session.scalar(select(TaxonomyQuestionForm).where(
            TaxonomyQuestionForm.role_id == 'fullstack', TaxonomyQuestionForm.grade_id == 'senior',
            TaxonomyQuestionForm.variant == 'A'))
        assert [q['id'] for q in row.questions] == [q.id for q in source.questions]


def test_taxonomy_diagnostic_three_forms_scores_tags_but_never_certifies(env):
    client, headers, ids, engine = env
    with Session(engine) as session, session.begin():
        seed_bank(session)
    assert client.patch('/me/candidate-profile', headers=headers[0],
                        json={'specialization': 'fullstack'}).status_code == 200
    seen = []
    coverage = client.get('/assessments/taxonomy/catalog', headers=headers[0])
    assert coverage.status_code == 200
    assert len(coverage.json()['roles']) == 5 and len(coverage.json()['grades']) == 3
    for _ in range(3):
        response = client.post('/assessments/taxonomy/start', headers=headers[0],
                               json={'specialization': 'fullstack', 'grade': 'senior'})
        assert response.status_code == 201, response.text
        data = response.json()
        seen.append(data['assessment']['variant'])
        assert client.post('/assessments/start', headers=headers[0],
                           json={'specialization': 'fullstack', 'grade': 'senior'}).status_code == 409
        questions = data['assessment']['questions']
        assert len(questions) == len(data['assessment']['skillIds']) * 4
        assert 'answerKey' not in response.text
        read = client.get(f"/assessments/taxonomy/{data['id']}", headers=headers[0])
        assert read.status_code == 200 and read.json() == data
        assert client.get(f"/assessments/{data['id']}", headers=headers[0]).status_code == 409
        assert client.post(f"/assessments/{data['id']}/submit", headers=headers[0],
                           json={'answers': []}).status_code == 409
        with Session(engine) as session:
            attempt = session.get(AssessmentAttempt, data['id'])
            pinned = attempt.snapshot['form']['questions']
            answers = [{'questionId': q['id'], 'optionId': q['answerKey']} for q in pinned]
        result = client.post(f"/assessments/taxonomy/{data['id']}/submit", headers=headers[0],
                             json={'answers': answers})
        assert result.status_code == 200, result.text
        payload = result.json()['result']
        assert payload['outcome'] == 'high'
        assert set(payload['subscores']) == set(data['assessment']['skillIds'])
        assert all(value == 100 for value in payload['subscores'].values())
        assert client.post(f"/assessments/taxonomy/{data['id']}/submit", headers=headers[0],
                           json={'answers': answers}).json() == result.json()
    assert set(seen) == {'A', 'B', 'C'}
    own_profile = client.get('/me/candidate-profile', headers=headers[0]).json()
    assert own_profile['diagnosticRole'] == 'fullstack' and own_profile['diagnosticGrade'] == 'senior'
    assert set(own_profile['diagnosticSkills']) == set(data['assessment']['skillIds'])
    assert all(v == 100 for v in own_profile['diagnosticSkills'].values())
    assert own_profile['verifiedSkills'] == {}
    with Session(engine) as session:
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        assert profile.verified_grade is profile.verified_specialization is None
        assert list(session.scalars(select(CompetencyScore).where(CompetencyScore.candidate_id == profile.id))) == []
    assert client.post('/assessments/taxonomy/start', headers=headers[0],
                       json={'specialization': 'fullstack', 'grade': 'senior'}).status_code == 409
    assert client.get(f"/assessments/taxonomy/{data['id']}", headers=headers[1]).status_code == 404
