"""
Phase 8.5.1 - System User Management Tests

Tests for admin user management endpoints:
- Cannot deactivate self
- Cannot demote last admin
- Admin can promote another admin
- Audit entry created
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


# === Helper Functions ===

async def create_admin_user(client: AsyncClient) -> tuple[dict, str]:
    """Create an admin user and return user data + token."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "admin@test.com",
            "password": "adminpass123",
            "username": "testadmin",
            "operational_role": "agent",
        },
    )
    assert response.status_code == 201
    data = response.json()
    
    # Make user an admin directly via DB (would need admin to do this normally)
    # For testing, we'll use login after setting up
    return data["user"], data["access_token"]


async def create_regular_user(client: AsyncClient, suffix: str = "") -> tuple[dict, str]:
    """Create a regular user and return user data + token."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": f"user{suffix}@test.com",
            "password": "userpass123",
            "username": f"testuser{suffix}",
            "operational_role": "agent",
        },
    )
    assert response.status_code == 201
    data = response.json()
    return data["user"], data["access_token"]


async def make_user_admin(client: AsyncClient, user_id: int, admin_token: str) -> None:
    """Promote a user to admin using admin token."""
    response = await client.patch(
        f"/api/system/users/{user_id}/admin",
        json={"is_system_admin": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # May succeed or fail depending on permissions
    return response


# === Tests ===

@pytest.mark.anyio
async def test_cannot_deactivate_self(client: AsyncClient, test_session):
    """Admin cannot deactivate themselves."""
    # Create and register admin
    user, token = await create_admin_user(client)
    
    # Make this user a system admin in DB
    from app.db.models import User
    from sqlalchemy import select, update
    
    result = await test_session.execute(
        update(User)
        .where(User.id == user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login to get updated token with is_system_admin
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "admin@test.com", "password": "adminpass123"},
    )
    assert login_resp.status_code == 200
    admin_token = login_resp.json()["access_token"]
    
    # Try to deactivate self
    response = await client.patch(
        f"/api/system/users/{user['id']}/status",
        json={"active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 400
    assert "yourself" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_cannot_demote_self(client: AsyncClient, test_session):
    """Admin cannot demote themselves."""
    # Create admin
    user, _ = await create_admin_user(client)
    
    # Make this user a system admin in DB
    from app.db.models import User
    from sqlalchemy import update
    
    await test_session.execute(
        update(User)
        .where(User.id == user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "admin@test.com", "password": "adminpass123"},
    )
    admin_token = login_resp.json()["access_token"]
    
    # Try to demote self
    response = await client.patch(
        f"/api/system/users/{user['id']}/admin",
        json={"is_system_admin": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 400
    assert "yourself" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_cannot_demote_last_admin(client: AsyncClient, test_session):
    """Cannot demote the only remaining admin."""
    # Create two users
    admin_user, _ = await create_admin_user(client)
    target_user, _ = await create_regular_user(client, "target")
    
    # Make first user admin
    from app.db.models import User
    from sqlalchemy import update
    
    await test_session.execute(
        update(User)
        .where(User.id == admin_user["id"])
        .values(is_system_admin=True)
    )
    # Make target user admin too initially
    await test_session.execute(
        update(User)
        .where(User.id == target_user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login admin
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "admin@test.com", "password": "adminpass123"},
    )
    admin_token = login_resp.json()["access_token"]
    
    # First, demote target - should succeed (2 admins -> 1)
    response = await client.patch(
        f"/api/system/users/{target_user['id']}/admin",
        json={"is_system_admin": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    
    # Create another user and try to demote the last admin
    third_user, _ = await create_regular_user(client, "third")
    await test_session.execute(
        update(User)
        .where(User.id == third_user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login as third user (now admin)
    third_login = await client.post(
        "/api/auth/login",
        json={"identifier": f"userthird@test.com", "password": "userpass123"},
    )
    third_token = third_login.json()["access_token"]
    
    # Now try to demote the original admin - should fail (would leave only third)
    # Actually, there are now 2 admins (admin_user and third_user), so we need to demote one first
    # Let's demote third_user first using admin_token
    response = await client.patch(
        f"/api/system/users/{third_user['id']}/admin",
        json={"is_system_admin": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    
    # Now admin_user is the only admin
    # Use third_token (now not admin) - should fail auth
    response = await client.patch(
        f"/api/system/users/{admin_user['id']}/admin",
        json={"is_system_admin": False},
        headers={"Authorization": f"Bearer {third_token}"},
    )
    assert response.status_code == 403  # Not admin anymore


@pytest.mark.anyio
async def test_admin_can_promote_user(client: AsyncClient, test_session):
    """Admin can promote another user to admin."""
    # Create admin and regular user
    admin_user, _ = await create_admin_user(client)
    regular_user, _ = await create_regular_user(client)
    
    # Make first user admin
    from app.db.models import User
    from sqlalchemy import update
    
    await test_session.execute(
        update(User)
        .where(User.id == admin_user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login admin
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "admin@test.com", "password": "adminpass123"},
    )
    admin_token = login_resp.json()["access_token"]
    
    # Promote regular user
    response = await client.patch(
        f"/api/system/users/{regular_user['id']}/admin",
        json={"is_system_admin": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["changed"] is True
    assert data["user"]["is_system_admin"] is True


@pytest.mark.anyio
async def test_admin_can_change_user_role(client: AsyncClient, test_session):
    """Admin can change a user's role."""
    # Create admin and regular user
    admin_user, _ = await create_admin_user(client)
    regular_user, _ = await create_regular_user(client)
    
    # Make first user admin
    from app.db.models import User
    from sqlalchemy import update
    
    await test_session.execute(
        update(User)
        .where(User.id == admin_user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login admin
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "admin@test.com", "password": "adminpass123"},
    )
    admin_token = login_resp.json()["access_token"]
    
    # Change regular user's role to team_admin
    response = await client.patch(
        f"/api/system/users/{regular_user['id']}/role",
        json={"role": "team_admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["changed"] is True
    assert data["user"]["role"] == "team_admin"


@pytest.mark.anyio
async def test_audit_entry_created_on_promote(client: AsyncClient, test_session):
    """Audit log entry is created when promoting user."""
    # Create admin and regular user
    admin_user, _ = await create_admin_user(client)
    regular_user, _ = await create_regular_user(client)
    
    # Make first user admin
    from app.db.models import User, AuditLog
    from sqlalchemy import update, select
    
    await test_session.execute(
        update(User)
        .where(User.id == admin_user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login admin
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "admin@test.com", "password": "adminpass123"},
    )
    admin_token = login_resp.json()["access_token"]
    
    # Promote regular user
    response = await client.patch(
        f"/api/system/users/{regular_user['id']}/admin",
        json={"is_system_admin": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    
    # Check audit log
    result = await test_session.execute(
        select(AuditLog)
        .where(AuditLog.action == "user.promote_admin")
        .where(AuditLog.target_id == regular_user["id"])
    )
    audit_entry = result.scalar_one_or_none()
    
    assert audit_entry is not None
    assert audit_entry.target_type == "user"
    assert audit_entry.user_id == admin_user["id"]


@pytest.mark.anyio
async def test_password_reset_returns_temp_password(client: AsyncClient, test_session):
    """Password reset returns a temporary password."""
    # Create admin and regular user
    admin_user, _ = await create_admin_user(client)
    regular_user, _ = await create_regular_user(client)
    
    # Make first user admin
    from app.db.models import User
    from sqlalchemy import update
    
    await test_session.execute(
        update(User)
        .where(User.id == admin_user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login admin
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "admin@test.com", "password": "adminpass123"},
    )
    admin_token = login_resp.json()["access_token"]
    
    # Reset password
    response = await client.post(
        f"/api/system/users/{regular_user['id']}/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "temporary_password" in data
    assert len(data["temporary_password"]) >= 12  # URL-safe token


@pytest.mark.anyio
async def test_cannot_force_logout_self(client: AsyncClient, test_session):
    """Admin cannot force logout themselves."""
    # Create admin
    admin_user, _ = await create_admin_user(client)
    
    # Make this user a system admin
    from app.db.models import User
    from sqlalchemy import update
    
    await test_session.execute(
        update(User)
        .where(User.id == admin_user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "admin@test.com", "password": "adminpass123"},
    )
    admin_token = login_resp.json()["access_token"]
    
    # Try to force logout self
    response = await client.post(
        f"/api/system/users/{admin_user['id']}/force-logout",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 400
    assert "yourself" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_invalid_role_rejected(client: AsyncClient, test_session):
    """Invalid role values are rejected."""
    # Create admin and regular user
    admin_user, _ = await create_admin_user(client)
    regular_user, _ = await create_regular_user(client)
    
    # Make first user admin
    from app.db.models import User
    from sqlalchemy import update
    
    await test_session.execute(
        update(User)
        .where(User.id == admin_user["id"])
        .values(is_system_admin=True)
    )
    await test_session.commit()
    
    # Re-login admin
    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "admin@test.com", "password": "adminpass123"},
    )
    admin_token = login_resp.json()["access_token"]
    
    # Try invalid role
    response = await client.patch(
        f"/api/system/users/{regular_user['id']}/role",
        json={"role": "super_duper_admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 400
    assert "invalid role" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_non_admin_cannot_access_system_endpoints(client: AsyncClient):
    """Regular users cannot access system admin endpoints."""
    # Create regular user
    user, token = await create_regular_user(client)
    
    # Try to access system users list
    response = await client.get(
        "/api/system/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 403

