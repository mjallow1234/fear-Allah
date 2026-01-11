import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy import func

from app.db.models import User, Team, Channel


@pytest.mark.anyio
async def test_system_status_fresh_db(client: AsyncClient):
    resp = await client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["initialized"] is False


@pytest.mark.anyio
async def test_system_status_initialized(client: AsyncClient, test_session):
    # Mark the system as initialized via the persisted flag
    from app.db.models import SystemState
    state = SystemState(setup_completed=True)
    test_session.add(state)
    await test_session.commit()

    resp = await client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["initialized"] is True


@pytest.mark.anyio
async def test_login_blocked_when_not_initialized(client: AsyncClient):
    # No users/teams exist — login should be blocked with 403
    resp = await client.post(
        "/api/auth/login",
        json={"identifier": "noone", "password": "wrong"}
    )
    assert resp.status_code == 403
    assert resp.json().get("detail") == "System not initialized. Visit /setup"


@pytest.mark.anyio
async def test_setup_initialize_creates_resources(client: AsyncClient, test_session):
    payload = {
        "admin_name": "Admin User",
        "admin_email": "admin@example.com",
        "admin_password": "strongpass123",
        "team_name": "Acme Co",
    }

    resp = await client.post("/api/setup/initialize", json=payload)
    assert resp.status_code == 200 or resp.status_code == 201
    data = resp.json()
    assert "user" in data and "team" in data

    # After initialization, system status should be true and persisted
    resp2 = await client.get("/api/system/status")
    assert resp2.status_code == 200
    assert resp2.json().get("initialized") is True

    # Verify the persisted flag exists in DB
    from app.db.models import SystemState
    result = await test_session.execute(select(SystemState))
    state = result.scalar_one_or_none()
    assert state is not None and state.setup_completed is True

    # Submitting initialize again should return 409
    resp3 = await client.post("/api/setup/initialize", json=payload)
    assert resp3.status_code == 409

    # Login should now succeed for the created admin
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": payload["admin_email"], "password": payload["admin_password"]}
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()
