from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class FrozenDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CandidateDTO(FrozenDTO):
    # No user-supplied free text, contacts or assessment internals.
    id: Annotated[int, Field(strict=True, gt=0)]


class Components(FrozenDTO):
    skillFit: FiniteFloat
    assessmentStrength: FiniteFloat
    fspBonus: FiniteFloat


class ItemDTO(FrozenDTO):
    candidate: CandidateDTO
    rank: Annotated[int, Field(strict=True, gt=0)] | None
    score: FiniteFloat
    components: Components | None


def ranking_order_key(score: float, candidate_id: int) -> tuple[float, int]:
    """Future ordering only: no score calculation or normalization."""
    return (-score, candidate_id)


class SnapshotPayload(FrozenDTO):
    algorithmVersion: Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_.-]{0,63}$")]
    weights: Components
    items: tuple[ItemDTO, ...]

    @model_validator(mode="after")
    def ordered_unique_items(self):
        ids = [item.candidate.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate candidate")
        if any(item.components is None or item.rank != i for i, item in enumerate(self.items, 1)):
            raise ValueError("Components and contiguous ranks are required")
        keys = [ranking_order_key(item.score, item.candidate.id) for item in self.items]
        if keys != sorted(keys):
            raise ValueError("Items must preserve descending score and candidate ID tie-breaker")
        return self


class SnapshotDTO(FrozenDTO):
    id: int
    needId: int
    createdAt: datetime
    algorithmVersion: str | None
    weights: Components | None
    items: tuple[ItemDTO, ...]
