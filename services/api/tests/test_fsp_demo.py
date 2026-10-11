from datetime import date
import json

import pytest

from app.modules.fsp.demo import load_registry, score_achievements


def record(**changes):
    return {"recordId": "r1", "kind": "competition_result", "result": "winner",
            "role": "contributor", "skillIds": ["python", "sql"], "achievedAt": "2025-04-03", **changes}


def test_registry_requires_explicit_demo_provenance_and_unique_ids(tmp_path):
    path = tmp_path / "fsp.json"
    path.write_text(json.dumps({"schemaVersion": 1, "source": "synthetic-demo-not-fsp",
        "participants": [{"fspId": "f1", "achievements": [record()]}]}))
    assert load_registry(path)["f1"].achievements[0].recordId == "r1"
    for payload in (
        {"schemaVersion": 1, "source": "real-fsp", "participants": []},
        {"schemaVersion": 1, "source": "synthetic-demo-not-fsp", "participants": [
            {"fspId": "f1", "achievements": []}, {"fspId": "f1", "achievements": []}]},
        {"schemaVersion": 1, "source": "synthetic-demo-not-fsp", "participants": [
            {"fspId": "f1", "achievements": [record(skillIds=["unknown"])]}]},
    ):
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError): load_registry(path)


def test_scoring_is_bounded_secondary_and_uses_best_record_only(tmp_path):
    path = tmp_path / "fsp.json"
    path.write_text(json.dumps({"schemaVersion": 1, "source": "synthetic-demo-not-fsp",
        "participants": [{"fspId": "f1", "achievements": [record(),
            record(recordId="r2", result="participant", role="participant", skillIds=["react"], achievedAt="2018-01-01")]}]}))
    achievements = load_registry(path)["f1"].achievements
    bonus = score_achievements(achievements, ["python", "sql"], date(2026, 10, 11))
    assert bonus == pytest.approx(0.85)
    assert score_achievements(achievements * 3, ["python", "sql"], date(2026, 10, 11)) == bonus
    assert score_achievements([], ["python"], date(2026, 10, 11)) == 0
    assert score_achievements(achievements, ["react"], date(2026, 10, 11)) < bonus


def test_future_dated_record_is_rejected():
    with pytest.raises(ValueError):
        score_achievements([record()], ["python"], date(2020, 1, 1))


def test_twenty_synthetic_candidates_keep_eligibility_and_test_dominant(tmp_path):
    path = tmp_path / "fsp.json"
    participants = [{"fspId": f"demo-{i:02}", "achievements": [record(
        recordId=f"result-{i}", result="winner" if i % 2 else "participant",
        role="lead" if i % 5 else "participant",
        skillIds=["python"] if i % 3 else ["react"], achievedAt=f"{2025-i%8}-01-01")] if i % 4 else []}
        for i in range(20)]
    path.write_text(json.dumps({"schemaVersion": 1, "source": "synthetic-demo-not-fsp", "participants": participants}))
    registry = load_registry(path)
    from app.modules.recommendations.ranking import calculate
    assert len(registry) == 20
    scores = []
    for i in range(20):
        bonus = score_achievements(registry[f"demo-{i:02}"].achievements, ["python"], date(2026, 10, 11))
        score, components, _ = calculate(["python"], [], {"python": 80}, 80, fsp_bonus=bonus)
        assert 0 <= bonus <= 1 and 0.68 <= score <= 0.83
        assert components["skillFit"] == 0.8 and components["assessmentStrength"] == 0.8
        scores.append(score)
    assert len(set(scores)) > 2
    assert calculate(["python"], [], {"python": 100}, 100)[0] > max(scores)
