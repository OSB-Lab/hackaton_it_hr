from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.catalog.public import PublicVariant
from app.modules.catalog.schemas import Blueprint, Catalog, FrozenModel, ID


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    specialization: ID
    grade: ID


class AttemptSnapshot(FrozenModel):
    schemaVersion: Literal[1]
    blueprint: Blueprint
    catalog: Catalog


class AttemptDTO(BaseModel):
    id: int
    status: Literal["active", "submitted"]
    createdAt: datetime
    submittedAt: datetime | None
    assessment: PublicVariant


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    questionId: ID
    optionId: ID | None


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answers: list[Answer]


class ResultDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subscores: dict[str, float]
    totalScore: float
    outcome: Literal["fail", "pass", "high"]
    status: Literal["DEMO", "APPROVED"]


class SubmitDTO(BaseModel):
    id: int
    status: Literal["submitted"]
    submittedAt: datetime
    result: ResultDTO
