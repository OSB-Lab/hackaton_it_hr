from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ID = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}")


class Approval(FrozenModel):
    reference: Text
    approvedBy: Text


class Versioned(FrozenModel):
    schemaVersion: Literal[1]
    id: ID
    version: ID
    status: Literal["DEMO", "APPROVED"]
    provenance: Literal["DEMO", "DS"]
    approval: Approval | None = None

    @model_validator(mode="after")
    def approval_required(self):
        if self.status == "APPROVED" and (self.provenance != "DS" or self.approval is None):
            raise ValueError("APPROVED requires DS provenance and explicit approval")
        if self.status == "DEMO" and self.approval is not None:
            raise ValueError("DEMO cannot carry approval")
        return self


class Skill(FrozenModel):
    id: ID
    name: Text


class Grade(FrozenModel):
    id: ID
    name: Text
    order: Annotated[int, Field(ge=0)]


class Specialization(FrozenModel):
    id: ID
    name: Text
    skillIds: tuple[ID, ...] = Field(min_length=1)


class Catalog(Versioned):
    specializations: tuple[Specialization, ...] = Field(min_length=1)
    grades: tuple[Grade, ...] = Field(min_length=1)
    skills: tuple[Skill, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def references(self):
        for name in ("specializations", "grades", "skills"):
            unique([item.id for item in getattr(self, name)], name)
        unique([g.order for g in self.grades], "grade order")
        skills = {s.id for s in self.skills}
        for spec in self.specializations:
            unique(spec.skillIds, "specialization skill")
            if not set(spec.skillIds) <= skills:
                raise ValueError("Unknown specialization skill")
        return self


class Rubric(FrozenModel):
    id: ID
    kind: Literal["single_choice_exact"]
    correctFraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    incorrectFraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    unansweredFraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]

    @model_validator(mode="after")
    def fractions(self):
        if self.correctFraction != 1 or max(self.incorrectFraction, self.unansweredFraction) >= 1:
            raise ValueError("Exact-choice rubric must award full score only for correct answers")
        return self


class Slot(FrozenModel):
    id: ID
    skillId: ID
    questionType: Literal["single_choice"]
    maxScore: Positive
    weight: Positive
    rubricId: ID


class Option(FrozenModel):
    id: ID
    text: Text


class ChoiceKey(FrozenModel):
    optionId: ID


class ChoiceQuestion(FrozenModel):
    id: ID
    slotId: ID
    type: Literal["single_choice"]
    prompt: Text
    options: tuple[Option, ...] = Field(min_length=2)
    answerKey: ChoiceKey = Field(repr=False)

    @model_validator(mode="after")
    def key_exists(self):
        unique([o.id for o in self.options], "option id")
        if self.answerKey.optionId not in {o.id for o in self.options}:
            raise ValueError("Answer key references unknown option")
        return self


class Variant(FrozenModel):
    id: Literal["A", "B"]
    questions: tuple[ChoiceQuestion, ...] = Field(min_length=1)


class Thresholds(FrozenModel):
    passScore: Finite
    highScore: Finite
    passInclusive: Literal[True]
    highInclusive: Literal[True]


class ScoringRules(FrozenModel):
    formula: Literal["weighted_normalized_sum"]
    scaleMin: Literal[0]
    scaleMax: Positive
    thresholds: Thresholds

    @model_validator(mode="after")
    def bounds(self):
        if not 0 < self.thresholds.passScore < self.thresholds.highScore <= self.scaleMax:
            raise ValueError("Thresholds must satisfy 0 < pass < high <= scaleMax")
        return self


class Blueprint(Versioned):
    catalogVersion: ID
    specialization: ID
    grade: ID
    slots: tuple[Slot, ...] = Field(min_length=1)
    rubric: tuple[Rubric, ...] = Field(min_length=1)
    scoring: ScoringRules
    variants: tuple[Variant, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def equivalent_variants(self):
        if {v.id for v in self.variants} != {"A", "B"}:
            raise ValueError("Exactly A and B are required")
        unique([s.id for s in self.slots], "slot")
        unique([r.id for r in self.rubric], "rubric")
        rubrics = {r.id for r in self.rubric}
        if any(s.rubricId not in rubrics for s in self.slots):
            raise ValueError("Unknown rubric")
        expected = {s.id for s in self.slots}
        question_ids = []
        for variant in self.variants:
            actual = [q.slotId for q in variant.questions]
            unique(actual, "variant slot")
            if set(actual) != expected:
                raise ValueError("Variants must fill identical slots exactly once")
            question_ids.extend(q.id for q in variant.questions)
        unique(question_ids, "question id")
        # Max scores, weights, types and rubric live in shared slots, not variants.
        return self


class ArtifactRef(FrozenModel):
    key: ID
    kind: Literal["catalog", "blueprint"]
    id: ID
    version: ID
    path: Text
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class Manifest(FrozenModel):
    schemaVersion: Literal[1]
    activeCatalog: ID
    activeBlueprints: tuple[ID, ...]
    artifacts: tuple[ArtifactRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def refs(self):
        unique([r.key for r in self.artifacts], "artifact key")
        unique([(r.kind, r.id, r.version) for r in self.artifacts], "artifact version")
        unique([r.path for r in self.artifacts], "artifact path")
        unique(self.activeBlueprints, "active blueprint")
        refs = {r.key: r for r in self.artifacts}
        if self.activeCatalog not in refs or refs[self.activeCatalog].kind != "catalog":
            raise ValueError("Unknown active catalog")
        if any(key not in refs or refs[key].kind != "blueprint" for key in self.activeBlueprints):
            raise ValueError("Unknown active blueprint")
        return self
