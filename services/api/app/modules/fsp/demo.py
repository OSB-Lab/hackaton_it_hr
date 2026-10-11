"""Synthetic registry adapter. This is NOT a real FSP attestation or integration."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.models import FspLink

DEFAULT_FILE = Path(__file__).with_name("demo_registry.v1.json")
CANONICAL_SKILLS = frozenset({"python", "sql", "api", "javascript", "typescript", "react"})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Achievement(StrictModel):
    recordId: str = Field(min_length=1, max_length=80)
    kind: Literal["competition_result", "sport_rank"]
    result: Literal["winner", "prizewinner", "finalist", "participant", "awarded"]
    role: Literal["lead", "contributor", "participant"]
    skillIds: tuple[str, ...] = Field(min_length=1, max_length=6)
    achievedAt: date

    @model_validator(mode="after")
    def coherent(self):
        if (self.kind == "sport_rank") != (self.result == "awarded"):
            raise ValueError("Sport rank requires awarded result")
        if len(set(self.skillIds)) != len(self.skillIds) or not set(self.skillIds) <= CANONICAL_SKILLS:
            raise ValueError("Unknown or duplicate canonical skill")
        return self


class Participant(StrictModel):
    fspId: str = Field(min_length=1, max_length=80)
    achievements: tuple[Achievement, ...] = ()

    @model_validator(mode="after")
    def unique_records(self):
        ids = [a.recordId for a in self.achievements]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate achievement record")
        return self


class Registry(StrictModel):
    schemaVersion: Literal[1]
    source: Literal["synthetic-demo-not-fsp"]
    participants: tuple[Participant, ...]

    @model_validator(mode="after")
    def unique_participants(self):
        ids = [p.fspId for p in self.participants]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate FSP ID")
        return self


def load_registry(path: Path = DEFAULT_FILE) -> dict[str, Participant]:
    try:
        registry = Registry.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise ValueError("Synthetic FSP registry unavailable or invalid") from exc
    return {p.fspId: p for p in registry.participants}


def active_registry() -> dict[str, Participant]:
    """Disabled outside explicitly opted-in demo deployments."""
    from app.core.config import get_settings
    settings = get_settings()
    return load_registry(settings.FSP_DEMO_REGISTRY_PATH or DEFAULT_FILE) if settings.FSP_DEMO_MODE else {}


def achievements_for(session, candidate_id: int, registry: dict[str, Participant]) -> tuple[Achievement, ...]:
    """Only a linked ID present in the file supplies evidence; database achievement rows are untrusted."""
    link = session.scalar(select(FspLink).where(FspLink.candidate_id == candidate_id))
    if not link or link.status != "linked" or not link.fsp_id or link.linked_at is None:
        return ()
    participant = registry.get(link.fsp_id)
    return participant.achievements if participant else ()


def score_achievements(achievements, required_skills, as_of: date) -> float:
    """Best single achievement, no stacking; type × role × stack × age, in [0,1]."""
    scores = []
    required = set(required_skills)
    for achievement in achievements:
        if not isinstance(achievement, Achievement):
            achievement = Achievement.model_validate(achievement)
        age_days = (as_of - achievement.achievedAt).days
        if age_days < 0:
            raise ValueError("Future achievement")
        type_factor = {"winner": "1", "prizewinner": ".85", "finalist": ".6",
                       "participant": ".25", "awarded": ".65"}[achievement.result]
        role_factor = {"lead": "1", "contributor": ".85", "participant": ".65"}[achievement.role]
        overlap = len(required.intersection(achievement.skillIds)) / len(required) if required else 0
        stack_factor = Decimal(".2") + Decimal(".8") * Decimal(str(overlap))
        age_factor = "1" if age_days <= 730 else ".7" if age_days <= 1825 else ".4"
        scores.append(Decimal(type_factor) * Decimal(role_factor) * stack_factor * Decimal(age_factor))
    return float(max(scores, default=Decimal(0)))
