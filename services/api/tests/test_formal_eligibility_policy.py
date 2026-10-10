from types import SimpleNamespace

import pytest

from app.modules.recommendations.eligibility import required_skill_failures


@pytest.mark.parametrize("score,count,expected", [
    (50, 2, []), (100, 2, []), (0, 2, ["REQUIRED_SKILL_BELOW_THRESHOLD"]),
    (49, 2, ["REQUIRED_SKILL_EVIDENCE_INVALID"]),
    (50, 0, ["REQUIRED_SKILL_EVIDENCE_INVALID"]),
    (50, True, ["REQUIRED_SKILL_EVIDENCE_INVALID"]),
    ("50", 2, ["REQUIRED_SKILL_EVIDENCE_INVALID"]),
    (float("nan"), 2, ["REQUIRED_SKILL_EVIDENCE_INVALID"]),
    (101, 2, ["REQUIRED_SKILL_EVIDENCE_INVALID"]),
])
def test_skill_threshold(score, count, expected):
    blueprint = SimpleNamespace(slots=[SimpleNamespace(skillTags=("python",))] * 2)
    reasons, missing = required_skill_failures(["python"], {
        "subscores": {"python": score}, "evidenceCounts": {"python": count}}, blueprint)
    assert reasons == expected
    assert missing == (["python"] if expected else [])


def test_all_required_canonical_and_missing():
    blueprint = SimpleNamespace(slots=[SimpleNamespace(skillTags=("python", "sql"))] * 2)
    result = {"subscores": {"python": 50, "SQL": 100}, "evidenceCounts": {"python": 2, "SQL": 2}}
    assert required_skill_failures(["sql", "python"], result, blueprint) == (
        ["REQUIRED_SKILL_EVIDENCE_MISSING"], ["sql"])
    assert required_skill_failures([], result, blueprint) == ([], [])


def test_valid_below_boundary():
    blueprint = SimpleNamespace(slots=[SimpleNamespace(skillTags=("python",))] * 9)
    assert required_skill_failures(["python"], {
        "subscores": {"python": 400 / 9}, "evidenceCounts": {"python": 9}}, blueprint)[0] == [
            "REQUIRED_SKILL_BELOW_THRESHOLD"]
