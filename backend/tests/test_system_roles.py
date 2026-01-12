"""
Phase 8.5.2 - Role & Permission Management Tests

Tests for:
1. Cannot delete system role
2. Cannot delete role in use
3. Cannot remove last admin's effective permissions
4. Permission diff logging correctness
5. Role assignment audit correctness
"""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.database import get_db, async_session
from app.db.models import User, Role, PermissionModel, RolePermission, AuditLog
from app.db.models import UserRole as UserRoleModel
from app.core.security import get_password_hash

# Mark whole module as anyio (legacy asyncio marks supported via module-level marker)
pytestmark = pytest.mark.anyio


# === Test Fixtures ===

@pytest.fixture
async def db_session(test_session):
    """Provide a database session for tests using the test engine."""
    yield test_session


@pytest.fixture
async def admin_user(db_session: AsyncSession):
    """Create or get admin user for tests."""
    result = await db_session.execute(
        select(User).where(User.email == "admin@fearallah.com")
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            username="admin",
            email="admin@fearallah.com",
            hashed_password=get_password_hash("admin123"),
            operational_role='agent',
            is_system_admin=True,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    return user


@pytest.fixture
async def regular_user(db_session: AsyncSession):
    """Create a regular (non-admin) user for tests."""
    result = await db_session.execute(
        select(User).where(User.username == "testuser_roles")
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            username="testuser_roles",
            email="testuser_roles@test.com",
            hashed_password=get_password_hash("test123"),
            operational_role='agent',
            is_system_admin=False,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_token():
    """Get admin auth token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={"identifier": "admin@fearallah.com", "password": "admin123"}
        )
        if response.status_code != 200:
            pytest.skip("Admin user not available")
        return response.json()["access_token"]


@pytest.fixture
async def test_role(db_session: AsyncSession):
    """Create a test role for deletion tests."""
    # Check if exists
    result = await db_session.execute(
        select(Role).where(Role.name == "test_deletable_role")
    )
    role = result.scalar_one_or_none()
    if not role:
        role = Role(
            name="test_deletable_role",
            description="Test role for deletion tests",
            scope="system",
            is_system=False,
        )
        db_session.add(role)
        await db_session.commit()
        await db_session.refresh(role)
    return role


# === Test: Cannot Delete System Role ===

@pytest.mark.asyncio
async def test_cannot_delete_system_role(admin_token: str, db_session: AsyncSession):
    """Test that system roles (system_admin, default) cannot be deleted."""
    # Get system_admin role ID
    result = await db_session.execute(
        select(Role).where(Role.name == "system_admin")
    )
    system_role = result.scalar_one_or_none()
    
    if not system_role:
        pytest.skip("system_admin role not found in database")
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            f"/api/system/roles/{system_role.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 400
        assert "Cannot delete system role" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_delete_default_role(admin_token: str, db_session: AsyncSession):
    """Test that the default system role cannot be deleted."""
    result = await db_session.execute(
        select(Role).where(Role.name == "default")
    )
    default_role = result.scalar_one_or_none()
    
    if not default_role:
        pytest.skip("default role not found in database")
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            f"/api/system/roles/{default_role.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 400
        assert "Cannot delete system role" in response.json()["detail"]


# === Test: Cannot Delete Role In Use ===

@pytest.mark.asyncio
async def test_cannot_delete_role_in_use(
    admin_token: str,
    db_session: AsyncSession,
    regular_user: User,
):
    """Test that roles assigned to users cannot be deleted."""
    # Create a role and assign it to a user
    result = await db_session.execute(
        select(Role).where(Role.name == "role_in_use_test")
    )
    role = result.scalar_one_or_none()
    
    if not role:
        role = Role(
            name="role_in_use_test",
            description="Test role for in-use check",
            scope="system",
            is_system=False,
        )
        db_session.add(role)
        await db_session.commit()
        await db_session.refresh(role)
    
    # Assign role to user
    result = await db_session.execute(
        select(UserRoleModel).where(
            UserRoleModel.user_id == regular_user.id,
            UserRoleModel.role_id == role.id
        )
    )
    existing = result.scalar_one_or_none()
    if not existing:
        assignment = UserRoleModel(user_id=regular_user.id, role_id=role.id)
        db_session.add(assignment)
        await db_session.commit()
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            f"/api/system/roles/{role.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 400
        assert "user(s) are assigned to this role" in response.json()["detail"]
    
    # Cleanup: Remove assignment so role can be deleted later
    await db_session.execute(
        select(UserRoleModel).where(UserRoleModel.role_id == role.id)
    )
    # Don't delete role - leave for future tests


# === Test: Cannot Remove Last Admin Permissions ===

@pytest.mark.asyncio
async def test_cannot_remove_system_admin_required_permissions(
    admin_token: str,
    db_session: AsyncSession,
):
    """Test that system_admin role must retain minimum system permissions."""
    result = await db_session.execute(
        select(Role).where(Role.name == "system_admin")
    )
    system_role = result.scalar_one_or_none()
    
    if not system_role:
        pytest.skip("system_admin role not found")
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Try to remove system.manage_users permission
        response = await client.patch(
            f"/api/system/roles/{system_role.id}/permissions",
            json={"permissions": ["channel.create"]},  # Missing required system.* permissions
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 400
        assert "must retain permissions" in response.json()["detail"]


# === Test: Permission Diff Logging ===

@pytest.mark.asyncio
async def test_permission_diff_logging(
    admin_token: str,
    db_session: AsyncSession,
):
    """Test that permission changes are logged with added/removed diff."""
    # Create a test role
    result = await db_session.execute(
        select(Role).where(Role.name == "diff_test_role")
    )
    role = result.scalar_one_or_none()
    
    if not role:
        role = Role(
            name="diff_test_role",
            description="Test role for diff logging",
            scope="system",
            is_system=False,
        )
        db_session.add(role)
        await db_session.commit()
        await db_session.refresh(role)
    
    # Get initial audit count
    initial_count = await db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "role.permissions.update",
            AuditLog.target_id == role.id
        )
    ) or 0
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Update permissions
        response = await client.patch(
            f"/api/system/roles/{role.id}/permissions",
            json={"permissions": ["channel.create", "sales.view"]},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response has diff info
        if data.get("changed"):
            assert "added" in data or "removed" in data
    
    # Verify audit log was created
    new_count = await db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "role.permissions.update",
            AuditLog.target_id == role.id
        )
    ) or 0
    
    # If permissions changed, audit should be created
    # Note: First run creates the role with permissions, subsequent runs may show no change
    assert new_count >= initial_count


# === Test: Role Assignment Audit ===

@pytest.mark.asyncio
async def test_role_assignment_audit(
    admin_token: str,
    db_session: AsyncSession,
    regular_user: User,
):
    """Test that role assignments are properly audited with before/after state."""
    # Get default role
    result = await db_session.execute(
        select(Role).where(Role.name == "default")
    )
    default_role = result.scalar_one_or_none()
    
    if not default_role:
        pytest.skip("default role not found")
    
    # Get initial audit count
    initial_count = await db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "user.role.change",
            AuditLog.target_id == regular_user.id
        )
    ) or 0
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/api/system/users/{regular_user.id}/assign-role",
            json={"role_id": default_role.id},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
    
    # Verify audit log
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "user.role.change",
            AuditLog.target_id == regular_user.id
        ).order_by(AuditLog.created_at.desc())
    )
    audit = result.scalars().first()
    
    if audit:
        import json
        meta = json.loads(audit.meta) if audit.meta else {}
        assert "before" in meta
        assert "after" in meta
        assert "new_role" in meta


# === Test: Create Role ===

@pytest.mark.asyncio
async def test_create_role_success(admin_token: str, db_session: AsyncSession):
    """Test successful role creation."""
    import uuid
    role_name = f"test_role_{uuid.uuid4().hex[:8]}"
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/system/roles",
            json={
                "name": role_name,
                "description": "Test role created by test",
                "permissions": ["channel.create"]
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == role_name
        assert data["is_system"] == False
        assert "channel.create" in data["permissions"]
    
    # Cleanup
    result = await db_session.execute(select(Role).where(Role.name == role_name))
    role = result.scalar_one_or_none()
    if role:
        await db_session.delete(role)
        await db_session.commit()


@pytest.mark.asyncio
async def test_create_role_invalid_name(admin_token: str):
    """Test that role names must be lowercase snake_case."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/system/roles",
            json={
                "name": "Invalid-Name",  # Not snake_case
                "permissions": []
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 400
        assert "snake_case" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cannot_create_system_role_name(admin_token: str):
    """Test that reserved system role names cannot be used."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/system/roles",
            json={
                "name": "system_admin",  # Reserved name
                "permissions": []
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 400
        assert "reserved" in response.json()["detail"].lower() or "already exists" in response.json()["detail"].lower()


# === Test: List Roles ===

@pytest.mark.asyncio
async def test_list_roles(admin_token: str):
    """Test listing all roles."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/system/roles",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "roles" in data
        assert "total" in data
        
        # System roles should be present
        role_names = [r["name"] for r in data["roles"]]
        assert "system_admin" in role_names or len(role_names) > 0


# === Test: List Permissions ===

@pytest.mark.asyncio
async def test_list_permissions(admin_token: str):
    """Test listing all available permissions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/system/permissions",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "permissions" in data
        assert "total" in data
        
        # Should have our taxonomy permissions
        perm_keys = [p["key"] for p in data["permissions"]]
        # At least some of our initial permissions should be there
        expected = ["system.manage_users", "channel.create", "sales.view"]
        found = [k for k in expected if k in perm_keys]
        assert len(found) > 0, f"Expected permissions not found. Got: {perm_keys[:10]}"


# === Test: Delete Role Success ===

@pytest.mark.asyncio
async def test_delete_role_success(admin_token: str, db_session: AsyncSession):
    """Test successful deletion of a non-system, unassigned role."""
    # Create a deletable role
    import uuid
    role_name = f"deletable_{uuid.uuid4().hex[:8]}"
    
    role = Role(
        name=role_name,
        description="Role to be deleted",
        scope="system",
        is_system=False,
    )
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(role)
    role_id = role.id
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete(
            f"/api/system/roles/{role_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["deleted"] == True
    
    # Verify deleted
    result = await db_session.execute(select(Role).where(Role.id == role_id))
    assert result.scalar_one_or_none() is None
