"""Question-bank quality gate.

Two layers:

* inline assertions that always run inside the API container (they only need
  ``app.modules.catalog``), covering the invariants the QA audit flagged;
* an optional run of the fuller standalone gate ``commands/check_question_bank.py``
  when the repository root is reachable (the tool lives outside ``services/api``).

Heuristics such as distractor plausibility, technical correctness and real
difficulty cannot be asserted here — they belong to expert review.
"""
from __future__ import annotations

import collections
import importlib.util
import itertools
import json
import re
import unicodedata
from pathlib import Path

import pytest

from app.modules.catalog.repository import CatalogRepository

CORE = {"backend": ("python", "sql", "api"),
        "frontend": ("javascript", "typescript", "react")}
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]+")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "").casefold()).strip()


def active_blueprints():
    repository = CatalogRepository()
    repository.validate_all()
    return [(key, repository.blueprint(key).document)
            for key in repository.manifest.activeBlueprints]


def test_active_cells_and_artifact_integrity():
    repository = CatalogRepository()
    repository.validate_all()
    keys = list(repository.manifest.activeBlueprints)
    loaded = {key: repository.blueprint(key) for key in keys}
    cells = {(entry.document.specialization, entry.document.grade) for entry in loaded.values()}
    assert cells == {(spec, grade) for spec in ("backend", "frontend")
                     for grade in ("junior", "middle")}
    for key, entry in loaded.items():
        document = entry.document
        assert document.status == document.provenance == "DEMO"
        assert document.schemaVersion == 3
        assert {v.id for v in document.variants} == {"A", "B", "C"}
        assert len(document.slots) == 20
        assert all(len(v.questions) == 20 for v in document.variants)
        assert len(entry.checksum) == 64


@pytest.mark.parametrize("spec", ["backend", "frontend"])
@pytest.mark.parametrize("grade", ["junior", "middle"])
def test_forms_are_content_distinct_and_well_formed(spec, grade):
    document = next(bp for _, bp in active_blueprints()
                    if (bp.specialization, bp.grade) == (spec, grade))
    by_variant = {v.id: v.questions for v in document.variants}
    prompts = {form: {normalize(q.prompt) for q in questions} for form, questions in by_variant.items()}

    # A/B/C must not be permutations of one item set.
    for left, right in itertools.combinations(("A", "B", "C"), 2):
        assert prompts[left].isdisjoint(prompts[right]), f"{spec}-{grade}: forms {left}/{right} overlap"
    # No literal duplicate wording inside a single form.
    for form, questions in by_variant.items():
        assert len({normalize(q.prompt) for q in questions}) == len(questions), f"{spec}-{grade}-{form}: duplicates"
    # Every question and option is well formed, ids and prompts are globally unique per cell.
    ids = [q.id for questions in by_variant.values() for q in questions]
    assert len(set(ids)) == len(ids) == 60
    assert len(set().union(*prompts.values())) == 60
    for questions in by_variant.values():
        for question in questions:
            assert len(question.options) == 4
            assert question.answerKey.optionId in {o.id for o in question.options}
            assert question.type == "single_choice"


@pytest.mark.parametrize("spec", ["backend", "frontend"])
@pytest.mark.parametrize("grade", ["junior", "middle"])
def test_evidence_matrix_is_preserved(spec, grade):
    document = next(bp for _, bp in active_blueprints()
                    if (bp.specialization, bp.grade) == (spec, grade))
    expected = collections.Counter()
    for tag in CORE[spec]:
        expected[tag] = 9
    expected["teamwork"] = 2
    for variant in document.variants:
        counts = collections.Counter(tag for q in variant.questions for tag in q.skillTags)
        assert counts == expected, f"{spec}-{grade}-{variant.id}: {dict(counts)}"


def test_answer_positions_are_not_predictable():
    positions = collections.Counter()
    for _, document in active_blueprints():
        for variant in document.variants:
            for question in variant.questions:
                ids = [o.id for o in question.options]
                positions[ids.index(question.answerKey.optionId)] += 1
    total = sum(positions.values())
    assert set(positions) == {0, 1, 2, 3}
    for share in (count / total for count in positions.values()):
        assert abs(share - 0.25) < 0.15, f"position distribution is skewed: {dict(positions)}"


def test_no_audited_absurd_distractors_remain():
    banned = {"хранить ключи в ui", "повторять запрос бесконечно", "отключить типы", "скрыть ошибку",
              "обвинить коллегу", "молчать до дедлайна", "удалить задачу", "зависит от css"}
    internal = ("answerkey", "optionid", "slotid", "maxscore", "rubricid", "checksum")
    for _, document in active_blueprints():
        for variant in document.variants:
            for question in variant.questions:
                text = normalize(question.prompt)
                assert not any(word in text for word in internal), question.id
                for option in question.options:
                    normalized = normalize(option.text)
                    assert normalized not in banned, f"{question.id}: {option.text}"
                    assert not any(word in normalized for word in internal), f"{question.id}: {option.text}"


def test_standalone_gate_reports_no_errors_when_available():
    """Run commands/check_question_bank.py when the repository root is mounted."""
    tool = Path(__file__).resolve().parents[3] / "commands" / "check_question_bank.py"
    if not tool.exists():
        pytest.skip("standalone QA gate is outside the mounted service directory")
    spec = importlib.util.spec_from_file_location("check_question_bank", tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.run(CatalogRepository().root)
    assert report.errors == [], json.dumps(report.errors, ensure_ascii=False, indent=2)
