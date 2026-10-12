import json
import shutil
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path

import pytest

from app.modules.recommendations.taxonomy_filter import (
    Candidate, FilterInputError, FilterNeed, SkillRequirement, filter_candidates, load_runtime,
)


def test_related_roles_grades_skills_and_aliases_are_directional():
    taxonomy, policy = load_runtime()
    need = FilterNeed('backend', 'middle', skills=(SkillRequirement('python'), SkillRequirement('postgres')))
    candidates = [Candidate('exact', ('backend',), 'middle', skill_ids=('Python', 'PostgreSQL')),
                  Candidate('near', ('fullstack',), 'junior', skill_ids=('python', 'mysql')),
                  Candidate('remote-role', ('data_engineer',), 'middle', skill_ids=('python',))]
    result = filter_candidates(need, candidates, taxonomy, policy)
    assert [c.candidate_id for c in result.selected] == ['exact', 'near', 'remote-role']
    assert result.selected[0].filter_fit == D('1.000000')
    assert D('0') < result.selected[1].filter_fit < D('1')
    factors = {f.code: f.coefficient for f in result.selected[1].factors}
    assert factors['role'] == D('.9') and factors['grade'] == D('.8')
    assert D('0') < factors['stack'] < D('1')
    assert taxonomy.grade_fit['middle']['junior'] > taxonomy.grade_fit['junior']['middle']
    assert filter_candidates(FilterNeed('frontend', 'middle'), [candidates[2]], taxonomy, policy).excluded
    role_alias = filter_candidates(FilterNeed('back-end', 'mid', skills=(SkillRequirement('postgres'),)),
        [Candidate('alias', ('бэкенд',), 'middle', skill_ids=('postgresql',))], taxonomy, policy)
    assert role_alias.selected[0].filter_fit == D('1.000000')


@pytest.mark.parametrize('file,mutate', [
    ('roles.v1.json', lambda d: d['roles'][0]['related_roles'].append({'role_id': 'missing', 'coefficient': .8})),
    ('skills.v1.json', lambda d: d['skills'][1]['aliases'].append('python')),
    ('grades.v1.json', lambda d: d['candidate_to_requested_fit']['junior'].update({'middle': 1.5})),
    ('filtering-policy.v1.json', lambda d: d.update(minimum_filter_fit=-1)),
    ('filtering-policy.v1.json', lambda d: d.update(policy_version='unexpected')),
    ('roles.v1.json', lambda d: d['roles'][1]['aliases'].append('бэкенд')),
])
def test_corrupt_taxonomy_fails_closed(tmp_path, file, mutate):
    source = Path(__file__).resolve().parents[1] / 'app/modules/recommendations/config'
    for path in source.glob('*.json'):
        shutil.copy(path, tmp_path / path.name)
    path = tmp_path / file
    payload = json.loads(path.read_text())
    mutate(payload)
    path.write_text(json.dumps(payload))
    with pytest.raises(FilterInputError):
        load_runtime(tmp_path)


def test_verified_hard_gate_cannot_be_overridden_by_soft_fit():
    result = filter_candidates(FilterNeed('backend', 'middle'), [
        Candidate('no-proof', ('backend',), 'middle', submitted_category_attempt=False),
        Candidate('no-consent', ('backend',), 'middle', publication_consent=False)])
    assert not result.selected and len(result.excluded) == 2


def test_role_coefficient_sensitivity_does_not_change_exact_candidate():
    taxonomy, policy = load_runtime()
    need = FilterNeed('backend', 'middle', skills=(SkillRequirement('python'),))
    candidates = [Candidate('exact', ('backend',), 'middle', skill_ids=('python',)),
                  Candidate('near', ('fullstack',), 'middle', skill_ids=('python',))]
    baseline = filter_candidates(need, candidates, taxonomy, policy)
    for factor in (D('.9'), D('1.1')):
        graph = {role: dict(edges) for role, edges in taxonomy.role_edges.items()}
        graph['fullstack']['backend'] = D('.9') * factor
        result = filter_candidates(need, candidates, replace(taxonomy, role_edges=graph), policy)
        assert result.selected[0].candidate_id == 'exact'
        assert result.selected[0].filter_fit == D('1.000000')
        assert result.selected[1].filter_fit != baseline.selected[1].filter_fit
        assert result.selected[1].filter_fit < D('1')
