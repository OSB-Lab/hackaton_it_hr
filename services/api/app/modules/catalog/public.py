from typing import Literal

from app.modules.catalog.repository import Loaded
from app.modules.catalog.schemas import Blueprint, FrozenModel, Option


class PublicQuestion(FrozenModel):
    id: str
    slotId: str
    type: Literal["single_choice"]
    prompt: str
    options: tuple[Option, ...]
    skillTags: tuple[str, ...] = ()


class PublicVariant(FrozenModel):
    blueprintId: str
    blueprintVersion: str
    catalogVersion: str
    status: Literal["DEMO", "APPROVED"]
    variant: Literal["A", "B", "C"]
    questions: tuple[PublicQuestion, ...]


def public_variant(loaded: Loaded[Blueprint], variant_id: str) -> PublicVariant:
    blueprint = loaded.document
    variant = next((v for v in blueprint.variants if v.id == variant_id), None)
    if variant is None:
        raise ValueError("Unknown variant")
    return PublicVariant(
        blueprintId=blueprint.id, blueprintVersion=blueprint.version,
        catalogVersion=blueprint.catalogVersion, status=blueprint.status, variant=variant.id,
        questions=tuple(PublicQuestion(id=q.id, slotId=q.slotId, type=q.type,
                                       prompt=q.prompt, options=q.options, skillTags=getattr(q, "skillTags", ())) for q in variant.questions),
    )
