import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.db.session import check_database
from app.modules.auth.router import router as auth_router
from app.modules.candidate.router import router as candidate_router
from app.modules.employer.router import router as employer_router
from app.modules.employer.needs_router import router as needs_router
from app.modules.assessments.router import router as assessments_router

app = FastAPI(title="FSP Platform API")
app.include_router(auth_router)
app.include_router(candidate_router)
app.include_router(employer_router)
app.include_router(needs_router)
app.include_router(assessments_router)


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    probe = asyncio.create_task(check_database())
    try:
        async with asyncio.timeout(0.8):
            # Do not wait for driver cancellation/cleanup on the HTTP path.
            await asyncio.shield(probe)
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": "unavailable"},
        )
    finally:
        if not probe.done():
            probe.cancel()
        probe.add_done_callback(_consume_probe_result)
    return {"status": "ok", "db": "ok"}


def _consume_probe_result(probe: asyncio.Task) -> None:
    if not probe.cancelled():
        probe.exception()
