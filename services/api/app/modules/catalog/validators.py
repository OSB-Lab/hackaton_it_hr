from app.modules.catalog.schemas import Blueprint, Catalog


def validate_specialization(catalog: Catalog, value: str) -> str:
    if value not in {s.id for s in catalog.specializations}:
        raise ValueError("Unknown specialization")
    return value


def validate_grade(catalog: Catalog, value: str) -> str:
    if value not in {g.id for g in catalog.grades}:
        raise ValueError("Unknown grade")
    return value


def validate_skills(catalog: Catalog, values, specialization: str | None = None):
    allowed = {s.id for s in catalog.skills}
    if specialization is not None:
        validate_specialization(catalog, specialization)
        allowed = set(next(s.skillIds for s in catalog.specializations if s.id == specialization))
    if not set(values) <= allowed:
        raise ValueError("Unknown or incompatible skill")


def validate_blueprint(catalog: Catalog, blueprint: Blueprint):
    if blueprint.catalogVersion != catalog.version:
        raise ValueError("Catalog version mismatch")
    if blueprint.status == "APPROVED" and catalog.status != "APPROVED":
        raise ValueError("APPROVED blueprint requires APPROVED catalog")
    validate_specialization(catalog, blueprint.specialization)
    validate_grade(catalog, blueprint.grade)
    validate_skills(catalog, [slot.skillId for slot in blueprint.slots], blueprint.specialization)
