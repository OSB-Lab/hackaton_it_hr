from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Annotated
from app.modules.catalog.v3 import BlueprintV3

from app.modules.catalog.public import PublicVariant
from app.modules.catalog.schemas import Blueprint, Catalog, FrozenModel, ID


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    specialization: ID
    grade: ID


class AttemptSnapshot(FrozenModel):
    schemaVersion: Literal[1]
    blueprint: Annotated[Blueprint | BlueprintV3, Field(discriminator="schemaVersion")]
    catalog: Catalog

    @model_validator(mode="after")
    def pinned_catalog(self):
        from app.modules.catalog.validators import validate_blueprint
        validate_blueprint(self.catalog, self.blueprint)
        return self


class AttemptDTO(BaseModel):
    id: int
    status: Literal["active", "submitted"]
    createdAt: datetime
    submittedAt: datetime | None
    assessment: PublicVariant


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    questionId: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9._-]+$")
    optionId: ID | None


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answers: list[Answer]


class ResultDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscores: dict[str, float]
    totalScore: float
    technicalTotal: float | None = None
    correctTechnical: int | None = None
    teamworkSubscore: float | None = None
    evidenceCounts: dict[str, int] | None = None
    verifiedGrade: str | None = None
    verifiedSpecialization: str | None = None
    retestTargetGrade: str | None = None
    retestAvailableAt: datetime | None = None
    retestOffer: Literal["lower_retest_offered", "higher_retest_offered"] | None = None
    outcome: Literal["fail", "pass", "high"]


class SubmitDTO(BaseModel):
    id: int
    status: Literal["submitted"]
    submittedAt: datetime
    result: ResultDTO
