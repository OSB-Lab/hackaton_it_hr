import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

Grade = Literal["junior", "middle", "senior"]


class ConsentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    processing: StrictBool | None = None
    publication: StrictBool | None = None

    @model_validator(mode="after")
    def reject_null(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Consent must be true or false")
        return self


class ConsentDTO(BaseModel):
    processing: bool = False
    publication: bool = False


class CandidateProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fullName: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    stack: list[str] = Field(default_factory=list, max_length=100)
    role: str | None = Field(default=None, max_length=200)
    experienceMonths: int | None = Field(default=None, ge=0, strict=True)
    softSkills: list[str] = Field(default_factory=list, max_length=100)
    specialization: str | None = Field(default=None, max_length=200)
    selfDeclaredGrade: Grade | None = None
    consents: ConsentPatch = Field(default_factory=ConsentPatch)


class SelfCandidateDTO(BaseModel):
    fullName: str | None = None
    email: str
    phone: str | None = None
    stack: list[str] = Field(default_factory=list)
    role: str | None = None
    experienceMonths: int | None = None
    softSkills: list[str] = Field(default_factory=list)
    specialization: str | None = None
    selfDeclaredGrade: Grade | None = None
    consents: ConsentDTO = Field(default_factory=ConsentDTO)
    eligibleForEmployerSearch: bool = False


def contact_free(value: str | None) -> str | None:
    # Drop contact-bearing free text as well as dedicated contact fields.
    if value is None or "@" in value or re.search(r"(?:\+?\d[\s().-]*){7,}", value):
        return None
    return value


class HiringCandidateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: int
    fullName: str | None = None
    stack: tuple[str, ...] = ()
    role: str | None = None
    experienceMonths: int | None = None
    softSkills: tuple[str, ...] = ()
    specialization: str | None = None
    selfDeclaredGrade: Grade | None = None

    @model_validator(mode="after")
    def reject_contacts(self):
        values = (self.fullName, self.role, self.specialization, *self.stack, *self.softSkills)
        if any(value is not None and contact_free(value) is None for value in values):
            raise ValueError("Contact details are not allowed in hiring profiles")
        return self
