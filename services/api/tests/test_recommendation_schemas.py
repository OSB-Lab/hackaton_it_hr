import pytest
from pydantic import ValidationError

from app.modules.recommendations.schemas import CandidateDTO, Components, ItemDTO, SnapshotPayload, ranking_order_key


@pytest.mark.parametrize("field", ["email", "phone", "answerKey", "rubric", "scoring", "fullName"])
def test_candidate_rejects_private_or_free_text_fields(field):
    assert set(CandidateDTO.model_fields) == {"id"}
    with pytest.raises(ValidationError):
        CandidateDTO.model_validate({"id": 1, field: "secret@example.com"})


def test_immutable_payload_and_tie_breaker():
    values = Components(skillFit=1, assessmentStrength=2, fspBonus=0)
    items = tuple(ItemDTO(candidate=CandidateDTO(id=i), rank=i, score=10, components=values) for i in (1, 2))
    payload = SnapshotPayload(algorithmVersion="fixture-v1", weights=values, items=items)
    with pytest.raises(ValidationError): payload.items[0].candidate.id = 99
    with pytest.raises(ValidationError): payload.weights.skillFit = 99
    with pytest.raises(TypeError): payload.items[0] = items[1]
    assert sorted([(10, 2), (10, 1), (20, 3)], key=lambda pair: ranking_order_key(*pair)) == [(20, 3), (10, 1), (10, 2)]
    with pytest.raises(ValidationError):
        SnapshotPayload(algorithmVersion="fixture-v1", weights=values, items=(
            items[0].model_copy(update={"candidate": CandidateDTO(id=2)}),
            items[1].model_copy(update={"candidate": CandidateDTO(id=1)})))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "secret@example.com"])
def test_components_reject_non_numeric_or_nonfinite(value):
    with pytest.raises(ValidationError): Components(skillFit=value, assessmentStrength=1, fspBonus=0)
