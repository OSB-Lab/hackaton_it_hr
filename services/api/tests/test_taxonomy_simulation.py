import hashlib
import json
from app.commands.evaluate_taxonomy_bank import evaluate
from app.commands.generate_taxonomy_fixtures import generate


def test_checked_in_static_bank_and_fixtures_are_consistent(tmp_path):
    from pathlib import Path
    source = Path(__file__).resolve().parents[1]
    bank = source / 'app/data/taxonomy'
    manifest = json.loads((bank/'manifest.v4.json').read_text())
    assert hashlib.sha256((bank/'questions.v4.jsonl').read_bytes()).hexdigest() == manifest['sha256']
    generate(tmp_path / 'fixtures')
    for name in ('candidates.v1.jsonl','needs.v1.json','manifest.v1.json'):
        assert (tmp_path / 'fixtures' / name).read_bytes() == (source / 'tests/fixtures/taxonomy' / name).read_bytes()


def test_simulation_report_is_reproducible_and_reports_limits(tmp_path):
    a = evaluate(tmp_path / 'a')
    b = evaluate(tmp_path / 'b')
    assert a == b
    assert a['candidateCount'] == 1000 and a['cellCount'] == 15
    assert a['formCount'] == 45
    assert a['lexicalAnswerLeaks'] == 0
    assert a['duplicateOrAmbiguousOptions'] == 0
    assert a['semanticStatus'] == 'NOT_VALIDATED'
    assert a['categoryShortcutItemFraction'] == 0
    assert a['reusedMvpItems'] > 0
    assert 0 <= a['sameGradePassRate'] <= 1
    assert 0 <= a['adjacentLowerPassRate'] <= 1
    assert 0 <= a['formDecisionStability'] <= 1
    from pathlib import Path
    canonical = Path(__file__).resolve().parents[1] / 'docs/validation'
    for name in ('taxonomy_simulation_v2.json', 'taxonomy_simulation_v2.md'):
        assert (tmp_path / 'a' / name).read_bytes() == (canonical / name).read_bytes()
