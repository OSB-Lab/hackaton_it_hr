from test_ranking_create import setup, certify
from test_candidate_profile import env
from test_assessment_v3_lifecycle import approved
from sqlalchemy.orm import Session
from app.models import RecommendationSnapshot, CandidateProfile
from sqlalchemy import select


def test_similar_lane_keeps_strict_lane_unchanged(env, approved):
    client, headers, _, _ = env
    url, _ = setup(env)
    certify(env, 0, 18)
    strict = client.post(url, headers=headers[2])
    assert strict.status_code == 200
    similar = client.post(url + '/similar', headers=headers[2])
    assert similar.status_code == 200, similar.text
    assert similar.json()['algorithmVersion'].startswith('v4-')
    assert similar.json()['items'][0]['filterFit'] == 1
    assert similar.json()['items'][0]['score'] == strict.json()['items'][0]['score']
    assert client.get(f"{url}/{similar.json()['id']}", headers=headers[2]).json() == similar.json()
    view = client.get(f"{url}/{similar.json()['id']}/items", headers=headers[2])
    assert view.status_code == 200
    assert view.json()['items'][0]['filterFit'] == 1
    assert view.json()['items'][0]['filterFactors'][0]['code'] == 'role'


def test_similar_invalid_hard_skill_and_snapshot_tamper_fail_closed(env, approved):
    client, headers, ids, engine = env
    url, _ = setup(env)
    certify(env, 0, 18)
    assert client.post(url + '/similar', headers=headers[2],
                       json={'hardSkillIds': ['invented']}).status_code == 422
    assert client.post(url + '/similar', headers=headers[2],
                       json={'hardSkillIds': ['react']}).status_code == 422
    snapshot = client.post(url + '/similar', headers=headers[2]).json()
    with Session(engine) as session, session.begin():
        row = session.get(RecommendationSnapshot, snapshot['id'])
        altered = [dict(item) for item in row.ordered_items]
        altered[0] = {**altered[0], 'score': 1.0}
        row.ordered_items = altered
    assert client.get(f"{url}/{snapshot['id']}", headers=headers[2]).status_code == 503


def test_similar_disclosure_revocation_still_blocks_snapshot(env, approved):
    client, headers, ids, engine = env
    url, _ = setup(env)
    certify(env, 0, 18)
    snapshot = client.post(url + '/similar', headers=headers[2]).json()
    with Session(engine) as session, session.begin():
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == ids[0]))
        profile.privacy_settings = {'publish_profile': False}
    assert client.get(f"{url}/{snapshot['id']}", headers=headers[2]).status_code == 409
    assert client.get(f"{url}/{snapshot['id']}/items", headers=headers[2]).status_code == 409
