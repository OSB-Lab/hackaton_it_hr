from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmpty = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


class NeedCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: NonEmpty
    teamDescription: str | None = None
    specialization: NonEmpty
    minGrade: NonEmpty
    targetGrade: NonEmpty
    requiredSkills: list[NonEmpty] = Field(default_factory=list)
    optionalSkills: list[NonEmpty] = Field(default_factory=list)


class NeedPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: NonEmpty | None = None
    teamDescription: str | None = None
    specialization: NonEmpty | None = None
    minGrade: NonEmpty | None = None
    targetGrade: NonEmpty | None = None
    requiredSkills: list[NonEmpty] | None = None
    optionalSkills: list[NonEmpty] | None = None

    @model_validator(mode="after")
    def reject_null(self):
        for field in self.model_fields_set - {"teamDescription"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class NeedDTO(BaseModel):
    id: int
    title: str | None
    teamDescription: str | None
    specialization: str | None
    minGrade: str | None
    targetGrade: str | None
    requiredSkills: list[str]
    optionalSkills: list[str] | None
