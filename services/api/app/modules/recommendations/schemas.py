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


class FactorDTO(FrozenDTO):
    code: str
    coefficient: Annotated[FiniteFloat, Field(ge=0, le=1)]
    reason: Annotated[str, Field(max_length=200)]


class ItemDTO(FrozenDTO):
    candidate: CandidateDTO
    rank: Annotated[int, Field(strict=True, gt=0)] | None
    score: FiniteFloat
    components: Components | None
    filterFit: Annotated[FiniteFloat, Field(ge=0, le=1)] | None = Field(default=None, exclude_if=lambda v: v is None)
    rankingFit: Annotated[FiniteFloat, Field(ge=0, le=1)] | None = Field(default=None, exclude_if=lambda v: v is None)
    qualityScore: Annotated[FiniteFloat, Field(ge=0, le=1)] | None = Field(default=None, exclude_if=lambda v: v is None)
    filterFactors: tuple[FactorDTO, ...] = Field(default=(), exclude_if=lambda v: not v)
    taxonomyVersion: str | None = Field(default=None, exclude_if=lambda v: v is None)
    filterPolicyVersion: str | None = Field(default=None, exclude_if=lambda v: v is None)
    reasons: tuple[Annotated[str, Field(pattern=r"^(Required skill evidence|Technical test|Verified FSP bonus|Demo FSP bonus): (?:100|[0-9]{1,2})\.[0-9]%$")], ...] = ()


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
        from app.modules.recommendations.ranking import ALGORITHM_VERSION, WEIGHTS
        from app.modules.recommendations.similar_service import SIMILAR_VERSION, FACTOR_CODES, TAXONOMY_VERSION, FILTER_VERSION
        if self.algorithmVersion == SIMILAR_VERSION:
            if self.weights.model_dump() != WEIGHTS:
                raise ValueError("Invalid similar-ranking weights")
            for item in self.items:
                if (item.filterFit is None or item.rankingFit is None or item.qualityScore is None
                        or item.taxonomyVersion != TAXONOMY_VERSION or item.filterPolicyVersion != FILTER_VERSION
                        or tuple(f.code for f in item.filterFactors) != FACTOR_CODES
                        or not 0 <= item.score <= 1
                        or any(not 0 <= v <= 1 for v in item.components.model_dump().values())):
                    raise ValueError("Incomplete similar-ranking snapshot")
                product = 1.0
                ranking_product = 1.0
                for factor in item.filterFactors:
                    product *= factor.coefficient
                    if factor.code not in ("stack", "achievements"):
                        ranking_product *= factor.coefficient
                expected_quality = (self.weights.skillFit * item.components.skillFit
                                    + self.weights.assessmentStrength * item.components.assessmentStrength
                                    + self.weights.fspBonus * item.components.fspBonus)
                if (abs(item.qualityScore - expected_quality) > 1e-9
                        or abs(item.filterFit - product) > 0.0000011
                        or abs(item.rankingFit - ranking_product) > 1e-9
                        or abs(item.score - item.qualityScore * item.rankingFit) > 1e-9):
                    raise ValueError("Inconsistent similar-ranking components")
            keys = [(-item.score, -item.qualityScore, -item.filterFit,
                     -item.components.assessmentStrength, item.candidate.id) for item in self.items]
        elif self.algorithmVersion == ALGORITHM_VERSION:
            if self.weights.model_dump() != WEIGHTS:
                raise ValueError("Invalid v3 weights")
            if any(not 0 <= item.score <= 1 or any(not 0 <= v <= 1 for v in item.components.model_dump().values()) for item in self.items):
                raise ValueError("Invalid normalized components")
            keys = [(-item.score, -item.components.assessmentStrength, item.candidate.id) for item in self.items]
        else:
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
