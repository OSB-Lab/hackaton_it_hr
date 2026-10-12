import json
from pathlib import Path

from app.modules.assessments.taxonomy_bank import load_seed_bank
from app.modules.recommendations.taxonomy_filter import load_runtime, FilterNeed, FilterInputError, filter_candidates
import pytest

ROLES = {'backend', 'frontend', 'fullstack', 'ml_engineer', 'data_engineer'}
GRADES = {'junior', 'middle', 'senior'}
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'app/modules/recommendations/config'


def test_legacy_similar_snapshot_remains_readable_after_taxonomy_scope_change():
    from app.modules.recommendations.schemas import SnapshotPayload
    from app.modules.recommendations.ranking import WEIGHTS
    factors = [{'code': code, 'coefficient': 1, 'reason': 'fixture'} for code in
               ('role','grade','experience','stack','achievements','salary','work_format','location')]
    item = {'candidate': {'id': 1}, 'rank': 1, 'score': .85,
            'components': {'skillFit': 1, 'assessmentStrength': 1, 'fspBonus': 0},
            'qualityScore': .85, 'rankingFit': 1, 'filterFit': 1,
            'filterFactors': factors, 'taxonomyVersion': 'talent-taxonomy-v1',
            'filterPolicyVersion': 'formal-filter-v1'}
    payload = SnapshotPayload(algorithmVersion='v4-similar-taxonomy-v1', weights=WEIGHTS, items=[item])
    assert payload.items[0].taxonomyVersion == 'talent-taxonomy-v1'


def test_only_requested_roles_grades_and_skills_remain():
    roles = json.loads((CONFIG/'roles.v1.json').read_text())['roles']
    grades = json.loads((CONFIG/'grades.v1.json').read_text())
    skills = json.loads((CONFIG/'skills.v1.json').read_text())
    assert {r['id'] for r in roles} == ROLES
    assert {g['id'] for g in grades['grades']} == GRADES
    assert set(grades['candidate_to_requested_fit']) == GRADES
    assert all(set(row) == GRADES for row in grades['candidate_to_requested_fit'].values())
    assert all({edge['role_id'] for edge in role['related_roles']} <= ROLES for role in roles)
    skill_ids = {item['id'] for item in skills['skills']}
    assert all(item['role_ids'] and set(item['role_ids']) <= ROLES for item in skills['skills'])
    assert all({edge['a'],edge['b']} <= skill_ids for edge in skills['relations'])
    taxonomy, policy = load_runtime()
    assert set(taxonomy.role_edges) == ROLES and set(taxonomy.grade_fit) == GRADES
    for invalid in ('intern','lead'):
        with pytest.raises(FilterInputError):
            filter_candidates(FilterNeed('backend', invalid), [], taxonomy, policy)
    with pytest.raises(FilterInputError):
        filter_candidates(FilterNeed('devops', 'junior'), [], taxonomy, policy)


def test_question_bank_and_saved_fixtures_contain_no_removed_categories():
    bank = load_seed_bank()
    assert set(bank.cells) == {(role,grade) for role in ROLES for grade in GRADES}
    assert sum(len(cell.forms) for cell in bank.cells.values()) == 45
    fixture = ROOT/'tests/fixtures/taxonomy'
    candidates = [json.loads(line) for line in (fixture/'candidates.v1.jsonl').read_text().splitlines()]
    needs = json.loads((fixture/'needs.v1.json').read_text())['needs']
    assert len(candidates) == 1000 and len(needs) == 50
    assert all({c['roleId'],c['selfDeclaredRoleId']} <= ROLES and
               {c['gradeId'],c['selfDeclaredGradeId']} <= GRADES for c in candidates)
    assert all(n['roleId'] in ROLES and n['gradeId'] in GRADES for n in needs)
    rows = [json.loads(line) for line in (ROOT/'app/data/taxonomy/questions.v4.jsonl').read_text().splitlines()]
    assert {(row['role'],row['grade']) for row in rows} == set(bank.cells)
