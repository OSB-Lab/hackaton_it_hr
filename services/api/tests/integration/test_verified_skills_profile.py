from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, CompetencyScore
from test_ranking_create import setup, certify
from test_candidate_profile import env
from test_assessment_v3_lifecycle import approved


def test_verified_skill_levels_from_certifying_attempt_not_mutable_cache(env, approved):
    client, headers, ids, engine = env
    setup(env)
    certify(env, 0, 18)
    profile = client.get('/me/candidate-profile', headers=headers[0])
    assert profile.status_code == 200
    data = profile.json()
    assert data['verifiedGrade'] == 'junior' and data['verifiedSpecialization'] == 'backend'
    assert data['verifiedSkills'] == {'python': 100.0, 'sql': 100.0, 'api': 100.0}
    with Session(engine) as session, session.begin():
        candidate = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        cid = candidate.id
        for row in session.scalars(select(CompetencyScore).where(CompetencyScore.candidate_id == cid)):
            row.score = 0
    assert client.get('/me/candidate-profile', headers=headers[0]).json()['verifiedSkills'] == data['verifiedSkills']
    # v4 reads the certifying attempt for employer filters too, not profile.stack.
    with Session(engine) as session, session.begin():
        session.get(CandidateProfile, cid).stack = ['made-up']
    need_id = next(iter(client.get('/employer/needs', headers=headers[2]).json()))['id']
    snapshot = client.post(f'/employer/needs/{need_id}/recommendations/similar', headers=headers[2]).json()
    filtered = client.get(f"/employer/needs/{need_id}/recommendations/{snapshot['id']}/items",
                          headers=headers[2], params={'stack': 'python'})
    assert filtered.status_code == 200
    assert filtered.json()['items'][0]['candidate']['verifiedSkills'] == data['verifiedSkills']


def test_demo_diagnostic_never_sets_verified_skills(env):
    client, headers, _, _ = env
    assert client.get('/me/candidate-profile', headers=headers[0]).json()['verifiedSkills'] == {}
