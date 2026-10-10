import pytest
from pydantic import ValidationError

from app.modules.recommendations.ranking import calculate, ALGORITHM_VERSION, WEIGHTS
from app.modules.recommendations.schemas import SnapshotPayload


@pytest.mark.parametrize("optional,expected", [([], 0.75), (["api"], 0.65)])
def test_continuous_coverage(optional, expected):
    score, components, _ = calculate(["python", "sql"], optional,
                                     {"python": 100, "sql": 50, "api": 25}, 80)
    assert components["skillFit"] == pytest.approx(expected)
    assert score == pytest.approx(0.5 * expected + 0.35 * 0.8)
    assert components["fspBonus"] == 0


def test_missing_evidence_and_empty_required():
    assert calculate(["python", "sql"], [], {"python": 100}, 100)[1]["skillFit"] == 0.5
    assert calculate([], [], {}, 100)[1]["skillFit"] == 0


def test_confirmed_bonus_is_bounded_and_never_changes_evidence():
    base = calculate(["python"], [], {"python": 100}, 100)
    confirmed = calculate(["python"], [], {"python": 100}, 100, confirmed_fsp=True)
    assert base[0] == 0.85 and confirmed[0] == 1
    assert confirmed[1] == {**base[1], "fspBonus": 1}


@pytest.mark.parametrize("value", [-1, 101, float("nan"), float("inf"), True])
def test_invalid_evidence_not_silently_clamped(value):
    with pytest.raises(ValueError): calculate(["python"], [], {"python": value}, 100)


def test_equal_score_orders_by_technical_then_id_and_legacy_unchanged():
    def item(candidate, rank, strength):
        return {"candidate": {"id": candidate}, "rank": rank, "score": 0.7,
                "components": {"skillFit": 0.7, "assessmentStrength": strength, "fspBonus": 0}}
    items = [item(3, 1, 0.9), item(1, 2, 0.8), item(2, 3, 0.8)]
    assert SnapshotPayload(algorithmVersion=ALGORITHM_VERSION, weights=WEIGHTS, items=items)
    with pytest.raises(ValidationError):
        SnapshotPayload(algorithmVersion="legacy-v1", weights=WEIGHTS, items=items)
    with pytest.raises(ValidationError):
        SnapshotPayload(algorithmVersion=ALGORITHM_VERSION, weights=WEIGHTS, items=[item(1, 1, 0.8), item(3, 2, 0.9)])
