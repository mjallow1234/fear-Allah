"""
Phase 8.5.4 - Admin User Creation Tests

Tests for POST /api/system/users endpoint:
- Admin can create user
- Non-admin blocked (403)
- Duplicate username
- Duplicate email
- Role assignment works
- Audit log created
- Password not logged
- No self-action loopholes
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, AuditLog, Role

pytestmark = pytest.mark.integration


# === Helper Functions ===

async def create_admin_user(client: AsyncClient) -> tuple[dict, str]:
    """Create and login as admin user, return user data and token."""
    # Register admin
    reg_response = await client.post(
        "/api/auth/register",
        json={
            "email": "admin_creator@test.com",
            "password": "adminpass123",
            "username": "admin_creator",
        },
    )
    assert reg_response.status_code == 201
    
    # Login
    login_response = await client.post(
        "/api/auth/login",
        json={
            "identifier": "admin_creator@test.com",
            "password": "adminpass123",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    return reg_response.json()["user"], token


async def create_regular_user(client: AsyncClient) -> tuple[dict, str]:
    """Create and login as regular (non-admin) user."""
    reg_response = await client.post(
        "/api/auth/register",
        json={
            "email": "regular@test.com",
            "password": "regularpass123",
            "username": "regular_user",
        },
    )
    assert reg_response.status_code == 201
    
    login_response = await client.post(
        "/api/auth/login",
        json={
            "identifier": "regular@test.com",
            "password": "regularpass123",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    return reg_response.json()["user"], token


async def make_user_admin(test_session: AsyncSession, user_id: int):
    """Directly update user to be system admin in DB."""
    result = await test_session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    user.is_system_admin = True
    await test_session.commit()
    await test_session.refresh(user)


async def get_default_role_id(test_session: AsyncSession) -> int:
    """Get or create a default role for testing."""
    result = await test_session.execute(select(Role).where(Role.name == "default"))
    role = result.scalar_one_or_none()
    if role:
        return role.id
    
    # Create a default role if it doesn't exist
    new_role = Role(
        name="default",
        description="Default test role",
        scope="system",
        is_system=False,
    )
    test_session.add(new_role)
    await test_session.commit()
    await test_session.refresh(new_role)
    return new_role.id


# === Tests ===

@pytest.mark.anyio
async def test_admin_can_create_user(client: AsyncClient, test_session: AsyncSession):
    """Test that a system admin can create a new user."""
    # Setup: create admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    # Get a valid role ID
    role_id = await get_default_role_id(test_session)
    
    # Create new user via API
    response = await client.post(
        "/api/system/users",
        json={
            "username": "newuser",
            "email": "newuser@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 201
    data = response.json()
    
    # Verify response structure
    assert "user" in data
    assert "temporary_password" in data
    assert data["user"]["username"] == "newuser"
    assert data["user"]["email"] == "newuser@test.com"
    assert data["user"]["active"] is True
    assert data["user"]["is_system_admin"] is False
    assert data["user"]["role_id"] == role_id
    
    # Verify password is reasonable
    temp_pass = data["temporary_password"]
    assert len(temp_pass) >= 12
    assert len(temp_pass) <= 16
    # Check it has mixed characters
    assert any(c.isupper() for c in temp_pass)
    assert any(c.islower() for c in temp_pass)
    assert any(c.isdigit() for c in temp_pass)


@pytest.mark.anyio
async def test_non_admin_blocked(client: AsyncClient, test_session: AsyncSession):
    """Test that non-admin users get 403 when trying to create users."""
    # Setup: create regular user (NOT admin)
    user_data, token = await create_regular_user(client)
    
    # Get a valid role ID
    role_id = await get_default_role_id(test_session)
    
    # Attempt to create user
    response = await client.post(
        "/api/system/users",
        json={
            "username": "blocked_user",
            "email": "blocked@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 403


@pytest.mark.anyio
async def test_duplicate_username_rejected(client: AsyncClient, test_session: AsyncSession):
    """Test that duplicate username is rejected with 400."""
    # Setup admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    role_id = await get_default_role_id(test_session)
    
    # Create first user
    response1 = await client.post(
        "/api/system/users",
        json={
            "username": "duplicate_name",
            "email": "unique1@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response1.status_code == 201
    
    # Try to create second user with same username
    response2 = await client.post(
        "/api/system/users",
        json={
            "username": "duplicate_name",
            "email": "unique2@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response2.status_code == 400
    assert "username" in response2.json()["detail"].lower()


@pytest.mark.anyio
async def test_duplicate_email_rejected(client: AsyncClient, test_session: AsyncSession):
    """Test that duplicate email is rejected with 400."""
    # Setup admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    role_id = await get_default_role_id(test_session)
    
    # Create first user
    response1 = await client.post(
        "/api/system/users",
        json={
            "username": "unique_name1",
            "email": "duplicate@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response1.status_code == 201
    
    # Try to create second user with same email
    response2 = await client.post(
        "/api/system/users",
        json={
            "username": "unique_name2",
            "email": "duplicate@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response2.status_code == 400
    assert "email" in response2.json()["detail"].lower()


@pytest.mark.anyio
async def test_invalid_role_id_rejected(client: AsyncClient, test_session: AsyncSession):
    """Test that invalid role_id is rejected with 400."""
    # Setup admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    # Use a role ID that doesn't exist
    response = await client.post(
        "/api/system/users",
        json={
            "username": "invalid_role_user",
            "email": "invalid_role@test.com",
            "role_id": 99999,  # Non-existent role
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 400
    assert "role" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_role_assignment_works(client: AsyncClient, test_session: AsyncSession):
    """Test that role is properly assigned to the new user."""
    # Setup admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    # Create a specific role
    test_role = Role(
        name="test_role",
        description="Test role for assignment",
        scope="system",
        is_system=False,
    )
    test_session.add(test_role)
    await test_session.commit()
    await test_session.refresh(test_role)
    
    # Create user with this role
    response = await client.post(
        "/api/system/users",
        json={
            "username": "role_assigned_user",
            "email": "role_assigned@test.com",
            "role_id": test_role.id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["role_id"] == test_role.id
    assert data["user"]["role_name"] == "test_role"


@pytest.mark.anyio
async def test_audit_log_created(client: AsyncClient, test_session: AsyncSession):
    """Test that audit log is created for user creation."""
    # Setup admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    role_id = await get_default_role_id(test_session)
    
    # Create user
    response = await client.post(
        "/api/system/users",
        json={
            "username": "audit_test_user",
            "email": "audit_test@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    new_user_id = response.json()["user"]["id"]
    
    # Check audit log
    result = await test_session.execute(
        select(AuditLog).where(
            AuditLog.action == "user.create",
            AuditLog.target_id == new_user_id,
        )
    )
    audit = result.scalar_one_or_none()
    
    assert audit is not None
    assert audit.target_type == "user"
    assert audit.user_id == admin_data["id"]


@pytest.mark.anyio
async def test_password_not_in_audit_log(client: AsyncClient, test_session: AsyncSession):
    """Test that the temporary password is NOT logged in audit meta."""
    # Setup admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    role_id = await get_default_role_id(test_session)
    
    # Create user
    response = await client.post(
        "/api/system/users",
        json={
            "username": "password_log_test",
            "email": "password_log@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    temp_password = response.json()["temporary_password"]
    new_user_id = response.json()["user"]["id"]
    
    # Check audit log meta
    result = await test_session.execute(
        select(AuditLog).where(
            AuditLog.action == "user.create",
            AuditLog.target_id == new_user_id,
        )
    )
    audit = result.scalar_one()
    
    # Ensure password is NOT in the meta field
    if audit.meta:
        meta_str = str(audit.meta)
        assert temp_password not in meta_str
        assert "password" not in meta_str.lower() or "password_hash" not in meta_str.lower()


@pytest.mark.anyio
async def test_create_system_admin_user(client: AsyncClient, test_session: AsyncSession):
    """Test that is_system_admin flag works correctly."""
    # Setup admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    role_id = await get_default_role_id(test_session)
    
    # Create a new system admin
    response = await client.post(
        "/api/system/users",
        json={
            "username": "new_admin",
            "email": "new_admin@test.com",
            "role_id": role_id,
            "is_system_admin": True,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["is_system_admin"] is True
    
    # Verify in DB
    result = await test_session.execute(
        select(User).where(User.username == "new_admin")
    )
    new_admin = result.scalar_one()
    assert new_admin.is_system_admin is True


@pytest.mark.anyio
async def test_create_inactive_user(client: AsyncClient, test_session: AsyncSession):
    """Test creating a user with active=False."""
    # Setup admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    role_id = await get_default_role_id(test_session)
    
    # Create inactive user
    response = await client.post(
        "/api/system/users",
        json={
            "username": "inactive_user",
            "email": "inactive@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["active"] is False


@pytest.mark.anyio
async def test_unauthenticated_blocked(client: AsyncClient, test_session: AsyncSession):
    """Test that unauthenticated requests are blocked."""
    role_id = await get_default_role_id(test_session)
    
    # No token
    response = await client.post(
        "/api/system/users",
        json={
            "username": "unauth_user",
            "email": "unauth@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
    )
    
    # The app returns 403 Forbidden for unauthenticated access; assert accordingly
    assert response.status_code == 403


@pytest.mark.anyio
async def test_new_user_can_login_with_temp_password(client: AsyncClient, test_session: AsyncSession):
    """Test that the created user can login with the temporary password."""
    # Setup admin
    admin_data, token = await create_admin_user(client)
    await make_user_admin(test_session, admin_data["id"])
    
    role_id = await get_default_role_id(test_session)
    
    # Create user
    create_response = await client.post(
        "/api/system/users",
        json={
            "username": "login_test_user",
            "email": "login_test@test.com",
            "role_id": role_id,
            "is_system_admin": False,
            "active": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    temp_password = create_response.json()["temporary_password"]
    
    # Try to login with temp password
    login_response = await client.post(
        "/api/auth/login",
        json={
            "identifier": "login_test@test.com",
            "password": temp_password,
        },
    )
    
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()
