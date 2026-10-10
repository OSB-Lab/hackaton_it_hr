from pydantic import BaseModel, ConfigDict, Field

from app.modules.catalog.schemas import ID
from app.modules.recommendations.schemas import CandidateDTO, FrozenDTO, ItemDTO


class TalentFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    specialization: str | None = None
    grade: str | None = None
    category: str | None = None
    stack: list[str] = Field(default_factory=list)
    hasFspAchievements: bool | None = None


class TalentCandidateDTO(CandidateDTO):
    # Catalog IDs only; profile attributes are not proof of qualification.
    specialization: ID | None
    stack: tuple[ID, ...]
    grade: ID | None = None
    category: None = None
    hasFspAchievements: bool


class TalentItemDTO(ItemDTO):
    candidate: TalentCandidateDTO


class TalentViewDTO(FrozenDTO):
    baseSnapshotId: int
    needId: int
    items: tuple[TalentItemDTO, ...]
