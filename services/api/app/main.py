import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.db.session import check_database

app = FastAPI(title="FSP Platform API")


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
