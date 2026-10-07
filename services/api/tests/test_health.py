import asyncio
import time

import httpx
from fastapi.testclient import TestClient
from psycopg import OperationalError

from app import main

client = TestClient(main.app)


def test_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_success(monkeypatch):
    async def available():
        pass

    monkeypatch.setattr(main, "check_database", available)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_ready_unavailable(monkeypatch):
    async def unavailable():
        raise OperationalError("Database unavailable")

    monkeypatch.setattr(main, "check_database", unavailable)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "unavailable"}


def test_ready_timeout(monkeypatch):
    async def stalled():
        await asyncio.sleep(10)

    monkeypatch.setattr(main, "check_database", stalled)
    start = time.monotonic()
    response = client.get("/health/ready")
    duration = time.monotonic() - start
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "unavailable"}
    assert duration < 1.0


def test_ready_timeout_does_not_wait_for_driver_cleanup(monkeypatch):
    async def slow_cleanup():
        try:
            await asyncio.sleep(10)
        finally:
            await asyncio.sleep(1.2)

    monkeypatch.setattr(main, "check_database", slow_cleanup)

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            start = time.monotonic()
            response = await client.get("/health/ready")
            assert time.monotonic() - start < 1.0
            assert response.status_code == 503
            assert response.json() == {"status": "error", "db": "unavailable"}

    asyncio.run(request())
