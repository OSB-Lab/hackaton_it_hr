from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, model_validator

from app.modules.candidate.schemas import ContactsDTO


def exact_money(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("Money must be a decimal string or integer, never float")
    return value


Money = Annotated[Decimal, BeforeValidator(exact_money), Field(gt=0, le=Decimal("9999999999999999.99"), max_digits=18, decimal_places=2, allow_inf_nan=False)]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companyId: Annotated[int, Field(strict=True, gt=0)]
    candidateId: Annotated[int, Field(strict=True, gt=0)]
    offerDescription: NonEmpty
    contactMethod: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    salaryMin: Money
    salaryMax: Money
    currency: Literal["RUB"] = "RUB"

    @model_validator(mode="after")
    def ordered_salary(self):
        if self.salaryMax < self.salaryMin:
            raise ValueError("salaryMax must be at least salaryMin")
        return self


class InvitationDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: int
    companyId: int
    candidateId: int
    offerDescription: str | None
    contactMethod: str | None
    salaryMin: Decimal
    salaryMax: Decimal
    currency: str | None
    status: Literal["sent", "viewed", "accepted", "declined"]
    createdAt: datetime
    updatedAt: datetime


class InvitationDetailDTO(InvitationDTO):
    contacts: ContactsDTO | None = None
