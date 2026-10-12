"""Allowlisted taxonomy for forms; no blueprint/question/scoring serialization."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from app.models import User
from app.modules.auth.dependencies import current_user
from app.modules.catalog.repository import CatalogRepository

router = APIRouter(tags=["catalog"])


@router.get("/catalog")
def catalog(user: Annotated[User, Depends(current_user)]):
    try:
        repo = CatalogRepository()
        data = repo.catalog().document
        tests = []
        for key in repo.manifest.activeBlueprints:
            bp = repo.blueprint(key).document
            tests.append({"specialization": bp.specialization, "grade": bp.grade,
                          "version": bp.version})
        return {"version": data.version,
                "specializations": [{"id": s.id, "name": s.name, "skillIds": s.skillIds} for s in data.specializations],
                "grades": [{"id": g.id, "name": g.name, "order": g.order} for g in data.grades],
                "skills": [{"id": s.id, "name": s.name} for s in data.skills], "tests": tests}
    except (ValueError, OSError):
        raise HTTPException(503, "Catalog unavailable") from None
