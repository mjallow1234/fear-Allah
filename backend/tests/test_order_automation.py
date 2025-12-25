"""
Tests for Order-Driven Automation (Phase 6.2)
Tests that orders automatically create and update automation tasks.
"""
import pytest
from httpx import AsyncClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_order_creates_automation_task(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test that creating an order also creates an automation task."""
    client, user_data = async_client_authenticated
    
    # Create an order
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "AGENT_RESTOCK",
            "items": [{"product_id": 1, "quantity": 10}],
            "metadata": {"note": "Test order"},
        },
    )
    assert order_resp.status_code == 201, f"Order creation failed: {order_resp.text}"
    order_data = order_resp.json()
    order_id = order_data["order_id"]
    
    # Check automation status
    auto_resp = await client.get(f"/api/orders/{order_id}/automation")
    assert auto_resp.status_code == 200
    auto_data = auto_resp.json()
    
    assert auto_data["has_automation"] == True
    assert "task_id" in auto_data
    assert auto_data["title"] == f"Restock Order #{order_id}"
    assert auto_data["task_status"] == "IN_PROGRESS"  # Should be in progress since we have assignments


@pytest.mark.anyio
async def test_order_without_automation(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test getting automation status for non-existent order."""
    client, _ = async_client_authenticated
    
    # Check automation for non-existent order
    auto_resp = await client.get("/api/orders/99999/automation")
    assert auto_resp.status_code == 200
    auto_data = auto_resp.json()
    
    assert auto_data["has_automation"] == False


@pytest.mark.anyio
async def test_retail_order_automation(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test retail order creates appropriate automation."""
    client, user_data = async_client_authenticated
    
    # Create a retail order
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "AGENT_RETAIL",
            "items": [{"product_id": 2, "quantity": 5}],
            "metadata": {},
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]
    
    # Check automation status
    auto_resp = await client.get(f"/api/orders/{order_id}/automation")
    auto_data = auto_resp.json()
    
    assert auto_data["has_automation"] == True
    assert "Retail Order" in auto_data["title"]


@pytest.mark.anyio
async def test_automation_task_linked_to_order(
    async_client_authenticated: tuple[AsyncClient, dict],
):
    """Test that automation task is properly linked to order."""
    client, user_data = async_client_authenticated
    
    # Create an order
    order_resp = await client.post(
        "/api/orders/",
        json={
            "order_type": "CUSTOMER_WHOLESALE",
            "items": [],
            "metadata": {},
        },
    )
    assert order_resp.status_code == 201
    order_id = order_resp.json()["order_id"]
    
    # Get automation status
    auto_resp = await client.get(f"/api/orders/{order_id}/automation")
    auto_data = auto_resp.json()
    task_id = auto_data["task_id"]
    
    # Get the automation task directly
    task_resp = await client.get(f"/api/automation/tasks/{task_id}")
    assert task_resp.status_code == 200
    task_data = task_resp.json()
    
    # Verify the task is linked to the order
    assert task_data["related_order_id"] == order_id
    assert "WHOLESALE" in task_data["task_type"]
