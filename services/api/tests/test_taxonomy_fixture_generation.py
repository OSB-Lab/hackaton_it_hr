import json
from collections import Counter

from app.commands.generate_taxonomy_fixtures import generate


def test_generator_creates_reproducible_diverse_future_fixtures(tmp_path):
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    manifest_a = generate(first)
    manifest_b = generate(second)
    assert manifest_a == manifest_b
    candidates = [json.loads(line) for line in (first / 'candidates.v1.jsonl').read_text().splitlines()]
    needs = json.loads((first / 'needs.v1.json').read_text())['needs']
    assert len(candidates) == 1000 and len(needs) == 50
    assert len({c['candidateId'] for c in candidates}) == 1000
    assert len({n['needId'] for n in needs}) == 50
    assert len({c['roleId'] for c in candidates}) == 5
    assert all({c['personaStrength'] for c in candidates if c['roleId'] == role} == {'weak','typical','strong'}
               for role in {c['roleId'] for c in candidates})
    assert all({c['personaStrength'] for c in candidates if c['roleId'] == role and c['gradeId'] == grade}
               == {'weak','typical','strong'} for role in {c['roleId'] for c in candidates}
               for grade in {c['gradeId'] for c in candidates})
    assert len({c['gradeId'] for c in candidates}) == 3
    assert len({n['roleId'] for n in needs}) == 5
    assert all(c['skillLevels'] and all(0 <= v <= 100 for v in c['skillLevels'].values()) for c in candidates)
    assert any(not c['publicationConsent'] for c in candidates)
    assert any(c['selfDeclaredRoleId'] != c['roleId'] for c in candidates)
    assert any(c['syntheticFspAchievements'] for c in candidates)
    assert any(n['expectedRelevantIds'] for n in needs)
    assert (first / 'candidates.v1.jsonl').read_bytes() == (second / 'candidates.v1.jsonl').read_bytes()
    assert (first / 'needs.v1.json').read_bytes() == (second / 'needs.v1.json').read_bytes()
