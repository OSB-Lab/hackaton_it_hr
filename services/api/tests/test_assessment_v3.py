import json
from copy import deepcopy
from itertools import combinations

import pytest

from app.modules.assessments.schemas import SubmitRequest
from app.modules.assessments.scoring_v3 import score_v3
from app.modules.catalog.public import public_variant
from app.modules.catalog.repository import CatalogRepository, Loaded, decode
from app.modules.catalog.v3 import BlueprintV3


def answers_for(bp, variant="A", count=18, teamwork=True):
    questions = next(v.questions for v in bp.variants if v.id == variant)
    # Spread missed single-tag items so each core retains sufficient evidence.
    order = [0, 4, 8, 1, 5, 9, 2, 6, 10, 3, 7, 11, 12, 13, 14, 15, 16, 17]
    wrong = set(order[:18 - count])
    return SubmitRequest(answers=[{"questionId": q.id, "optionId":
        q.answerKey.optionId if (i not in wrong and (i < 18 or teamwork)) else None}
        for i, q in enumerate(questions)])


@pytest.mark.parametrize("cell", ["backend-junior", "backend-middle", "frontend-junior", "frontend-middle"])
@pytest.mark.parametrize("variant", ["A", "B", "C"])
@pytest.mark.parametrize("count,outcome", [(12, "fail"), (13, "pass"), (16, "high")])
def test_exact_boundaries_and_diagnostic_independence(cell, variant, count, outcome):
    bp = CatalogRepository().blueprint(cell + "-v3-demo").document
    results = [score_v3(bp, variant, answers_for(bp, variant, count, teamwork)) for teamwork in (False, True)]
    for result in results:
        assert result.outcome == outcome
        assert result.correctTechnical == count
        assert result.technicalTotal == pytest.approx(count / 18 * 100)
        assert result.evidenceCounts["teamwork"] == 2
        assert all(n == 9 for s, n in result.evidenceCounts.items() if s != "teamwork")
    assert [r.teamworkSubscore for r in results] == [0, 100]


def test_core_gate_can_fail_a_passing_total():
    bp = CatalogRepository().blueprint("backend-middle-v3-demo").document
    body = answers_for(bp)
    # Five wrong python-tagged questions => 13 total but 4/9 Python evidence.
    tagged = [i for i, q in enumerate(bp.variants[0].questions) if "python" in q.skillTags][:5]
    for i in tagged:
        body.answers[i].optionId = None
    result = score_v3(bp, "A", body)
    assert result.correctTechnical == 13 and result.outcome == "fail"
    assert result.subscores["python"] == pytest.approx(400 / 9)


@pytest.mark.parametrize("case", ["missing_c", "tags", "duplicate_tag", "teamwork_mix", "options", "weight", "threshold", "rubric"])
def test_strict_structure(case):
    data = CatalogRepository().blueprint("backend-junior-v3-demo").document.model_dump(mode="json")
    if case == "missing_c": data["variants"].pop()
    if case == "tags": data["variants"][2]["questions"][0]["skillTags"] = ["sql"]
    if case == "duplicate_tag": data["slots"][0]["skillTags"] = ["python", "python"]
    if case == "teamwork_mix": data["slots"][0]["skillTags"] = ["python", "teamwork"]
    if case == "options": data["variants"][0]["questions"][0]["options"].append({"id": "o5", "text": "extra"})
    if case == "weight": data["slots"][0]["weight"] = 2
    if case == "threshold": data["scoring"]["thresholds"]["passCorrect"] = 12
    if case == "rubric": data["rubric"][0]["unansweredFraction"] = .5
    with pytest.raises(ValueError): decode(BlueprintV3, json.dumps(data))


def test_all_public_variants_are_key_independent():
    repo = CatalogRepository()
    for key in repo.manifest.activeBlueprints:
        loaded = repo.blueprint(key)
        for variant in loaded.document.variants:
            public = public_variant(loaded, variant.id)
            data = loaded.document.model_dump(mode="json")
            for form in data["variants"]:
                for q in form["questions"]:
                    q["answerKey"]["optionId"] = next(o["id"] for o in q["options"] if o["id"] != q["answerKey"]["optionId"])
            changed = Loaded(decode(BlueprintV3, json.dumps(data)), "private")
            assert public == public_variant(changed, variant.id)
            for secret in ("answerKey", "optionId", "rubric", "scoring", "threshold", "weight", "maxScore"):
                assert secret not in public.model_dump_json()
            assert len(public.questions) == 20 and public.questions[0].skillTags
