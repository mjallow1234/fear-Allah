import pytest
from app.core.config import settings
from app.api.health import healthz, readyz
from app.core import redis
from app.db.database import get_db
from fastapi import HTTPException

pytestmark = pytest.mark.integration

@pytest.mark.anyio
async def test_healthz():
    assert healthz() == {"status": "ok"}

@pytest.mark.anyio
async def test_readyz_db_ok(monkeypatch, client):
    # With the test DB fixture, readyz should return ready
    res = await client.get('/readyz')
    assert res.status_code == 200
    assert res.json() == {"status": "ready"}

@pytest.mark.anyio
async def test_readyz_skips_redis_when_ws_disabled(monkeypatch, client):
    # Ensure WS disabled
    monkeypatch.setattr(settings, 'WS_ENABLED', False)
    # Even if redis health is bad, readyz should pass
    class FakeRedis:
        def health_check(self):
            return False
    monkeypatch.setattr('app.api.health.redis_client', FakeRedis())

    res = await client.get('/readyz')
    assert res.status_code == 200

@pytest.mark.anyio
async def test_readyz_fails_when_redis_bad_and_ws_enabled(monkeypatch, client):
    monkeypatch.setattr(settings, 'WS_ENABLED', True)
    class FakeRedis:
        def health_check(self):
            return False
    monkeypatch.setattr('app.api.health.redis_client', FakeRedis())

    res = await client.get('/readyz')
    assert res.status_code == 503