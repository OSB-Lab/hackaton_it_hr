"""Test-only synthetic cohort; approved assessment artifacts never enter the product seed."""
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CandidateProfile, Consent, FspLink, TestAttempt as AssessmentAttempt, User
from app.modules.assessments.qualification import qualification
from test_ranking_create import setup, certify
from test_candidate_profile import env
from test_assessment_v3_lifecycle import approved


def test_forty_diverse_candidates_joint_filter_fsp_ranking_and_snapshot(env, approved):
    client, headers, ids, engine = env
    url, need_id = setup(env)
    certify(env, 0, 18)
    # Second certifying blueprint: adjacent Frontend role, not a CV role claim.
    assert client.patch('/me/candidate-profile', headers=headers[1],
                        json={'specialization': 'frontend'}).status_code == 200
    start = client.post('/assessments/start', headers=headers[1],
                        json={'specialization': 'frontend', 'grade': 'junior'})
    assert start.status_code == 201, start.text
    with Session(engine) as session:
        attempt = session.get(AssessmentAttempt, start.json()['id'])
        questions = next(v['questions'] for v in attempt.snapshot['blueprint']['variants'] if v['id'] == attempt.variant)
        answers = [{'questionId': q['id'], 'optionId': q['answerKey']['optionId']} for q in questions]
    assert client.post(f"/assessments/{start.json()['id']}/submit", headers=headers[1],
                       json={'answers': answers}).status_code == 200
    with Session(engine) as session, session.begin():
        templates = [session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == uid)) for uid in ids[:2]]
        certified = [session.get(AssessmentAttempt, p.verified_attempt_id) for p in templates]
        assert all(qualification(session, p.id) for p in templates)
        cohort = [p.id for p in templates]
        for i in range(2, 40):
            source = templates[i % 2]
            attempt = certified[i % 2]
            user = User(email=f'taxonomy-candidate-{i}@example.test', password_hash='fixture',
                        role='candidate', is_verified=i not in (35, 36))
            session.add(user)
            session.flush()
            profile = CandidateProfile(user_id=user.id, verified_grade='junior',
                verified_specialization=source.verified_specialization, specialization=source.verified_specialization,
                experience_months=(i % 7) * 12, stack=['react'] if i % 2 == 0 else ['python'],
                professional_role='ML engineer' if i % 3 else 'backend',
                privacy_settings={'publish_profile': i not in (33, 34)},
                last_grade_change_at=source.last_grade_change_at)
            session.add(profile)
            session.add(Consent(user_id=user.id, kind='publish_profile', granted=i not in (33, 34)))
            session.flush()
            copied = AssessmentAttempt(candidate_id=profile.id, test_id=attempt.test_id, status='submitted',
                submitted_at=datetime.now(timezone.utc),
                specialization=attempt.specialization, requested_grade=attempt.requested_grade,
                blueprint_version=attempt.blueprint_version, catalog_version=attempt.catalog_version,
                snapshot=deepcopy(attempt.snapshot), result=deepcopy(attempt.result), variant=attempt.variant)
            session.add(copied)
            session.flush()
            profile.verified_attempt_id = copied.id if i not in (37, 38) else None
            cohort.append(profile.id)
        # Only records matched by a linked FSP ID in the synthetic registry earn bonus.
        for pid, fsp_id in ((cohort[0], 'demo-fsp-002'), (cohort[1], 'demo-fsp-006'),
                            (cohort[2], 'not-in-registry')):
            session.add(FspLink(candidate_id=pid, status='linked', fsp_id=fsp_id,
                                linked_at=datetime.now(timezone.utc)))
    strict = client.post(url, headers=headers[2])
    similar = client.post(url + '/similar', headers=headers[2])
    assert strict.status_code == similar.status_code == 200, similar.text
    a, b = strict.json(), similar.json()
    strict_ids = {row['candidate']['id'] for row in a['items']}
    similar_ids = {row['candidate']['id'] for row in b['items']}
    assert len(cohort) == 40 and len(strict_ids) == 17 and len(similar_ids) == 34
    assert cohort[1] not in strict_ids and cohort[1] in similar_ids
    assert all(pid not in similar_ids for pid in cohort[33:39])
    exact = next(item for item in b['items'] if item['candidate']['id'] == cohort[0])
    adjacent = next(item for item in b['items'] if item['candidate']['id'] == cohort[1])
    unlinked = next(item for item in b['items'] if item['candidate']['id'] == cohort[2])
    factors = {f['code']: f['coefficient'] for f in adjacent['filterFactors']}
    assert factors['role'] == .81 and 0 < factors['stack'] < 1
    assert adjacent['components']['fspBonus'] > 0 and unlinked['components']['fspBonus'] == 0
    assert exact['components']['fspBonus'] > 0
    assert adjacent['score'] == adjacent['qualityScore'] * adjacent['rankingFit']
    assert adjacent['rankingFit'] == .81  # stack only retrieves; not scored twice
    # Unverified CV roles and profile stack never influence filtering or quality.
    peer = next(item for item in b['items'] if item['candidate']['id'] == cohort[6])
    assert unlinked['score'] == peer['score'] and unlinked['filterFit'] == peer['filterFit']
    ranked = sorted(b['items'], key=lambda x: (-x['score'], -x['qualityScore'], -x['filterFit'],
                      -x['components']['assessmentStrength'], x['candidate']['id']))
    assert b['items'] == ranked
    true_view = client.get(f"{url}/{b['id']}/items", headers=headers[2],
                           params={'hasFspAchievements': 'true'})
    assert true_view.status_code == 200
    assert {row['candidate']['id'] for row in true_view.json()['items']} == {cohort[0], cohort[1]}
    with Session(engine) as session, session.begin():
        session.scalar(select(FspLink).where(FspLink.candidate_id == cohort[0])).status = 'no_history'
    assert client.get(f"{url}/{b['id']}/items", headers=headers[2],
                      params={'hasFspAchievements': 'true'}).json() == true_view.json()
    assert client.get(f"{url}/{b['id']}", headers=headers[2]).json() == b
    # Adjacent verified grade is allowed in v4; v3 remains strict.
    with Session(engine) as session, session.begin():
        from app.models import HiringNeed
        session.get(HiringNeed, need_id).min_grade = 'middle'
    assert client.post(url, headers=headers[2]).json()['items'] == []
    graded = client.post(url + '/similar', headers=headers[2]).json()['items']
    assert graded and all(next(f for f in item['filterFactors'] if f['code'] == 'grade')['coefficient'] == .8
                          for item in graded)
