"""Locked v3 structural contract; content approval is independently required."""
from collections import Counter
from itertools import combinations
from typing import Literal

from pydantic import Field, model_validator

from app.modules.catalog.schemas import (
    ChoiceQuestion, FrozenModel, ID, Rubric, Versioned, unique,
)


class TaggedSlot(FrozenModel):
    id: ID
    skillTags: tuple[ID, ...] = Field(min_length=1, max_length=3)
    questionType: Literal["single_choice"]
    maxScore: Literal[1.0]
    weight: Literal[1.0]
    rubricId: ID


class TaggedQuestion(ChoiceQuestion):
    # Authored v3 question IDs contain uppercase form letters; preserve them.
    id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9._-]+$")
    skillTags: tuple[ID, ...] = Field(min_length=1, max_length=3)


class TaggedVariant(FrozenModel):
    id: Literal["A", "B", "C"]
    questions: tuple[TaggedQuestion, ...] = Field(min_length=20, max_length=20)


class EvidenceThresholds(FrozenModel):
    passCorrect: Literal[13]
    highCorrect: Literal[16]
    minimumCoreSkillPass: Literal[50]
    minimumCoreSkillHigh: Literal[70]


class EvidenceRules(FrozenModel):
    formula: Literal["weighted_normalized_sum"]
    scaleMin: Literal[0]
    scaleMax: Literal[100.0]
    thresholds: EvidenceThresholds


class BlueprintV3(Versioned):
    schemaVersion: Literal[3]
    catalogVersion: ID
    specialization: Literal["backend", "frontend"]
    grade: Literal["junior", "middle"]
    slots: tuple[TaggedSlot, ...] = Field(min_length=20, max_length=20)
    rubric: tuple[Rubric, ...] = Field(min_length=1)
    scoring: EvidenceRules
    variants: tuple[TaggedVariant, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def equivalent(self):
        if {v.id for v in self.variants} != {"A", "B", "C"}:
            raise ValueError("Exactly A/B/C required")
        core = ({"python", "sql", "api"} if self.specialization == "backend"
                else {"javascript", "typescript", "react"})
        expected = Counter({frozenset([s]): 4 for s in core})
        expected.update({frozenset(pair): 1 for pair in combinations(core, 2)})
        expected[frozenset(core)] = 3
        expected[frozenset(["teamwork"])] = 2
        if Counter(frozenset(s.skillTags) for s in self.slots) != expected:
            raise ValueError("Expected 18 technical, 2 diagnostic, nine observations per core skill")
        unique([s.id for s in self.slots], "slot")
        unique([r.id for r in self.rubric], "rubric")
        for rubric in self.rubric:
            if (rubric.correctFraction, rubric.incorrectFraction, rubric.unansweredFraction) != (1, 0, 0):
                raise ValueError("v3 exact rubric required")
        slots = {s.id: s for s in self.slots}
        for slot in self.slots:
            unique(slot.skillTags, "skill tag")
            if slot.rubricId not in {r.id for r in self.rubric}:
                raise ValueError("Unknown rubric")
        ids = []
        for variant in self.variants:
            unique([q.slotId for q in variant.questions], "variant slot")
            if {q.slotId for q in variant.questions} != set(slots):
                raise ValueError("Missing shared slot")
            for question in variant.questions:
                if question.skillTags != slots[question.slotId].skillTags or len(question.options) != 4:
                    raise ValueError("Tag matrix/options mismatch")
                unique(question.skillTags, "question tag")
                ids.append(question.id)
        unique(ids, "question id")
        return self
