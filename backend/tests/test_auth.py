import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_endpoint(client: AsyncClient):
    """Test the health check endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.anyio
async def test_register_user(client: AsyncClient):
    """Test user registration"""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpassword123",
            "username": "testuser",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert "id" in data


@pytest.mark.anyio
async def test_register_duplicate_email(client: AsyncClient):
    """Test registration with duplicate email"""
    # First registration
    await client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "testpassword123",
            "username": "user1",
        },
    )
    # Second registration with same email
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "password": "testpassword123",
            "username": "user2",
        },
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_login(client: AsyncClient):
    """Test user login"""
    # Register user first
    await client.post(
        "/api/auth/register",
        json={
            "email": "login@example.com",
            "password": "testpassword123",
            "username": "loginuser",
        },
    )
    # Login
        response = await client.post(
        "/api/auth/login",
            json={
                "identifier": "login@example.com",
                "password": "testpassword123",
            },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.anyio
async def test_login_invalid_credentials(client: AsyncClient):
    """Test login with invalid credentials"""
        response = await client.post(
        "/api/auth/login",
            json={
                "identifier": "nonexistent@example.com",
                "password": "wrongpassword",
            },
    )
    assert response.status_code == 401
