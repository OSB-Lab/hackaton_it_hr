from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints


class CompanyPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    description: str | None = None
    contacts: dict[str, Any] | None = None


class CompanyDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    contacts: dict[str, Any] | None
