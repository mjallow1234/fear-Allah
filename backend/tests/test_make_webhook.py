"""
Tests for Make.com Webhook Integration (Phase 6.5)
Validates payload contract, idempotency, and failure handling.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


class TestPayloadBuilder:
    """Test payload builder functions."""
    
    def test_build_make_payload_structure(self):
        """Verify payload matches exact contract structure."""
        from app.automation.payloads import build_make_payload
        
        payload = build_make_payload(
            event="order.created",
            actor_user_id=12,
            actor_username="agent1",
            actor_role="agent",
            entity_type="order",
            entity_id=345,
            data={"order_type": "sales", "status": "created"},
        )
        
        # Verify all required top-level keys
        assert payload["version"] == "1.0"
        assert payload["event"] == "order.created"
        assert payload["event_id"].startswith("evt_")
        assert "occurred_at" in payload
        assert payload["environment"] in ("development", "staging", "production")
        assert payload["source"] == "fear-allah-backend"
        
        # Verify actor block
        assert payload["actor"]["user_id"] == 12
        assert payload["actor"]["username"] == "agent1"
        assert payload["actor"]["role"] == "agent"
        
        # Verify entity block
        assert payload["entity"]["type"] == "order"
        assert payload["entity"]["id"] == 345
        
        # Verify data block
        assert payload["data"]["order_type"] == "sales"
        assert payload["data"]["status"] == "created"
    
    def test_payload_is_json_serializable(self):
        """Verify payload can be serialized to JSON."""
        from app.automation.payloads import build_make_payload
        
        payload = build_make_payload(
            event="task.created",
            actor_user_id=1,
            actor_username="test",
            entity_type="task",
            entity_id=100,
            data={"title": "Test task", "nested": {"key": "value"}},
        )
        
        # Should not raise
        json_str = json.dumps(payload)
        assert json_str is not None
        
        # Should round-trip correctly
        parsed = json.loads(json_str)
        assert parsed == payload
    
    def test_event_id_uniqueness(self):
        """Verify each payload gets a unique event_id."""
        from app.automation.payloads import build_make_payload
        
        ids = set()
        for _ in range(100):
            payload = build_make_payload(
                event="test.event",
                entity_type="test",
                entity_id=1,
                data={},
            )
            ids.add(payload["event_id"])
        
        # All IDs should be unique
        assert len(ids) == 100
    
    def test_event_id_can_be_provided(self):
        """Verify custom event_id is respected (for idempotency)."""
        from app.automation.payloads import build_make_payload
        
        custom_id = "evt_CUSTOM123456"
        payload = build_make_payload(
            event="test.event",
            entity_type="test",
            entity_id=1,
            data={},
            event_id=custom_id,
        )
        
        assert payload["event_id"] == custom_id
    
    def test_occurred_at_is_utc_iso8601(self):
        """Verify timestamp format matches contract."""
        from app.automation.payloads import build_make_payload
        
        payload = build_make_payload(
            event="test.event",
            entity_type="test",
            entity_id=1,
            data={},
        )
        
        occurred_at = payload["occurred_at"]
        # Should end with Z (UTC)
        assert occurred_at.endswith("Z")
        # Should be parseable
        datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    
    def test_system_actor_defaults(self):
        """Verify system events have correct actor defaults."""
        from app.automation.payloads import build_make_payload
        
        payload = build_make_payload(
            event="automation.triggered",
            entity_type="automation_task",
            entity_id=1,
            data={},
        )
        
        assert payload["actor"]["user_id"] is None
        assert payload["actor"]["username"] == "system"
        assert payload["actor"]["role"] == "system"


class TestEventSpecificPayloads:
    """Test event-specific payload builders."""
    
    def test_order_created_payload(self):
        """Test order.created payload structure."""
        from app.automation.payloads import build_order_created_payload
        
        payload = build_order_created_payload(
            order_id=345,
            order_type="sales",
            status="created",
            items=[{"sku": "SKU-001", "quantity": 2}],
            actor_user_id=12,
            actor_username="agent1",
            source="slash_command",
        )
        
        assert payload["event"] == "order.created"
        assert payload["entity"]["type"] == "order"
        assert payload["entity"]["id"] == 345
        assert payload["data"]["order_type"] == "sales"
        assert payload["data"]["items"] == [{"sku": "SKU-001", "quantity": 2}]
        assert payload["data"]["meta"]["source"] == "slash_command"
    
    def test_sale_completed_payload(self):
        """Test sale.completed payload structure."""
        from app.automation.payloads import build_sale_completed_payload
        
        payload = build_sale_completed_payload(
            sale_id=981,
            product_id=55,
            quantity=3,
            unit_price=1500,
            total_amount=4500,
            location="kanifing",
            related_order_id=345,
        )
        
        assert payload["event"] == "sale.completed"
        assert payload["entity"]["type"] == "sale"
        assert payload["entity"]["id"] == 981
        assert payload["data"]["product_id"] == 55
        assert payload["data"]["quantity"] == 3
        assert payload["data"]["total_amount"] == 4500
    
    def test_inventory_low_stock_payload(self):
        """Test inventory.low_stock payload structure."""
        from app.automation.payloads import build_inventory_low_stock_payload
        
        payload = build_inventory_low_stock_payload(
            inventory_id=77,
            product_id=55,
            current_stock=4,
            threshold=5,
            last_change=-3,
        )
        
        assert payload["event"] == "inventory.low_stock"
        assert payload["entity"]["type"] == "inventory"
        assert payload["data"]["current_stock"] == 4
        assert payload["data"]["threshold"] == 5
        assert payload["data"]["last_change"] == -3
    
    def test_task_created_payload(self):
        """Test task.created payload structure."""
        from app.automation.payloads import build_task_created_payload
        
        payload = build_task_created_payload(
            task_id=201,
            title="Verify payment",
            assigned_user_id=22,
            assigned_username="support1",
            related_order_id=345,
            required=True,
        )
        
        assert payload["event"] == "task.created"
        assert payload["entity"]["type"] == "task"
        assert payload["data"]["title"] == "Verify payment"
        assert payload["data"]["assigned_to"]["user_id"] == 22
        assert payload["data"]["related_order_id"] == 345
    
    def test_task_completed_payload(self):
        """Test task.completed payload structure."""
        from app.automation.payloads import build_task_completed_payload
        
        completed_at = datetime(2026, 1, 1, 13, 10, 0, tzinfo=timezone.utc)
        payload = build_task_completed_payload(
            task_id=201,
            completed_by_user_id=22,
            completed_by_username="support1",
            completed_at=completed_at,
        )
        
        assert payload["event"] == "task.completed"
        assert payload["data"]["completed_by"]["user_id"] == 22
        assert payload["data"]["completed_by"]["username"] == "support1"
        assert "2026-01-01" in payload["data"]["completed_at"]
    
    def test_automation_triggered_payload(self):
        """Test automation.triggered payload structure."""
        from app.automation.payloads import build_automation_triggered_payload
        
        payload = build_automation_triggered_payload(
            automation_task_id=9001,
            rule="order_created_sales_flow",
            trigger_event="order.created",
            status="queued",
        )
        
        assert payload["event"] == "automation.triggered"
        assert payload["entity"]["type"] == "automation_task"
        assert payload["data"]["rule"] == "order_created_sales_flow"
        assert payload["data"]["status"] == "queued"
    
    def test_automation_failed_payload(self):
        """Test automation.failed payload structure."""
        from app.automation.payloads import build_automation_failed_payload
        
        payload = build_automation_failed_payload(
            entity_type="order",
            entity_id=345,
            reason="missing_inventory",
            message="Insufficient stock for SKU-001",
            recoverable=False,
        )
        
        assert payload["event"] == "automation.failed"
        assert payload["data"]["reason"] == "missing_inventory"
        assert payload["data"]["recoverable"] is False


class TestWebhookEmitter:
    """Test webhook emitter functionality.
    
    These tests use asyncio.run() to avoid pytest fixture issues with the
    autouse clean_tables fixture from conftest.py.
    """
    
    def test_webhook_disabled_when_url_not_set(self):
        """Verify webhook does nothing when MAKE_WEBHOOK_URL is not configured."""
        import asyncio
        from app.integrations.make_webhook import emit_make_webhook, clear_sent_events_cache
        
        async def _test():
            clear_sent_events_cache()
            
            # With no URL configured, should return False without error
            with patch('app.integrations.make_webhook.settings') as mock_settings:
                mock_settings.MAKE_WEBHOOK_URL = ""
                
                result = await emit_make_webhook({
                    "version": "1.0",
                    "event": "test.event",
                    "event_id": "evt_TEST123",
                    "data": {},
                })
                
                assert result is False
        
        asyncio.run(_test())
    
    def test_webhook_called_with_correct_payload(self):
        """Verify webhook is called with correct headers and payload."""
        import asyncio
        from app.integrations.make_webhook import emit_make_webhook, clear_sent_events_cache
        from app.automation.payloads import build_make_payload
        
        async def _test():
            clear_sent_events_cache()
            
            payload = build_make_payload(
                event="order.created",
                actor_user_id=1,
                actor_username="test",
                entity_type="order",
                entity_id=123,
                data={"status": "created"},
            )
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            
            with patch('app.integrations.make_webhook.httpx.AsyncClient') as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                
                result = await emit_make_webhook(payload, webhook_url="https://hook.make.com/test")
                
                assert result is True
                
                # Verify POST was called
                mock_instance.post.assert_called_once()
                call_args = mock_instance.post.call_args
                
                # Verify URL
                assert call_args[0][0] == "https://hook.make.com/test"
                
                # Verify headers
                assert call_args[1]["headers"]["Content-Type"] == "application/json"
                assert call_args[1]["headers"]["X-Event-ID"] == payload["event_id"]
                
                # Verify payload
                assert call_args[1]["json"] == payload
        
        asyncio.run(_test())
    
    def test_idempotency_prevents_duplicate_sends(self):
        """Verify same event_id is not sent twice."""
        import asyncio
        from app.integrations.make_webhook import emit_make_webhook, clear_sent_events_cache
        
        async def _test():
            clear_sent_events_cache()
            
            event_id = "evt_IDEMPOTENT1"
            payload = {
                "version": "1.0",
                "event": "test.event",
                "event_id": event_id,
                "data": {},
            }
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            call_count = 0
            
            async def mock_post(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return mock_response
            
            with patch('app.integrations.make_webhook.httpx.AsyncClient') as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post = mock_post
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                
                # First call should send
                result1 = await emit_make_webhook(payload, webhook_url="https://hook.make.com/test")
                assert result1 is True
                assert call_count == 1
                
                # Second call with same event_id should skip
                result2 = await emit_make_webhook(payload, webhook_url="https://hook.make.com/test")
                assert result2 is True  # Returns True because event was already sent
                assert call_count == 1  # No additional call
        
        asyncio.run(_test())
    
    def test_failure_does_not_raise_exception(self):
        """Verify webhook failure doesn't crash the caller."""
        import asyncio
        from app.integrations.make_webhook import emit_make_webhook, clear_sent_events_cache
        import httpx
        
        async def _test():
            clear_sent_events_cache()
            
            payload = {
                "version": "1.0",
                "event": "test.event",
                "event_id": "evt_FAIL123",
                "data": {},
            }
            
            with patch('app.integrations.make_webhook.httpx.AsyncClient') as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                
                # Should not raise
                result = await emit_make_webhook(payload, webhook_url="https://hook.make.com/test")
                
                # Should return False on failure
                assert result is False
        
        asyncio.run(_test())
    
    def test_http_error_response_returns_false(self):
        """Verify non-2xx responses return False."""
        import asyncio
        from app.integrations.make_webhook import emit_make_webhook, clear_sent_events_cache
        
        async def _test():
            clear_sent_events_cache()
            
            payload = {
                "version": "1.0",
                "event": "test.event",
                "event_id": "evt_HTTP500",
                "data": {},
            }
            
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            
            with patch('app.integrations.make_webhook.httpx.AsyncClient') as mock_client:
                mock_instance = AsyncMock()
                mock_instance.post = AsyncMock(return_value=mock_response)
                mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
                
                result = await emit_make_webhook(payload, webhook_url="https://hook.make.com/test")
                
                assert result is False
        
        asyncio.run(_test())
    
    def test_missing_event_id_skips_send(self):
        """Verify payloads without event_id are rejected."""
        import asyncio
        from app.integrations.make_webhook import emit_make_webhook
        
        async def _test():
            payload = {
                "version": "1.0",
                "event": "test.event",
                # Missing event_id
                "data": {},
            }
            
            result = await emit_make_webhook(payload, webhook_url="https://hook.make.com/test")
            assert result is False
        
        asyncio.run(_test())


# Integration tests need DB fixtures - mark them
pytestmark_integration = pytest.mark.integration


@pytest.mark.integration
class TestWebhookIntegrationWithAutomation:
    """Integration tests verifying webhook emission from AutomationService."""
    
    @pytest.mark.anyio
    async def test_task_created_emits_webhook(self, test_session):
        """Verify task creation emits task.created webhook."""
        from app.automation.service import AutomationService
        from app.db.enums import AutomationTaskType
        from app.db.models import User
        from app.integrations.make_webhook import clear_sent_events_cache
        
        clear_sent_events_cache()
        
        # Create a test user first
        user = User(
            email="webhook_test@test.com",
            username="webhook_test",
            hashed_password="x",
            operational_role='agent',
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)
        
        captured_payload = None
        
        async def capture_webhook(payload, **kwargs):
            nonlocal captured_payload
            captured_payload = payload
            return True
        
        with patch('app.automation.service.emit_make_webhook', capture_webhook):
            task = await AutomationService.create_task(
                db=test_session,
                task_type=AutomationTaskType.restock,
                title="Test Webhook Task",
                created_by_id=user.id,
                description="Testing webhook emission",
            )
        
        assert captured_payload is not None
        assert captured_payload["event"] == "task.created"
        assert captured_payload["entity"]["type"] == "task"
        assert captured_payload["entity"]["id"] == task.id
        assert captured_payload["data"]["title"] == "Test Webhook Task"
    
    @pytest.mark.anyio
    async def test_assignment_completed_emits_webhook(self, test_session):
        """Verify assignment completion emits task.completed webhook."""
        from app.automation.service import AutomationService
        from app.db.enums import AutomationTaskType
        from app.db.models import User, TaskAssignment
        from app.integrations.make_webhook import clear_sent_events_cache
        
        clear_sent_events_cache()
        
        # Create test user
        user = User(
            email="assignee_test@test.com",
            username="assignee_test",
            hashed_password="x",
            operational_role='agent',
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)
        
        # Create task (capture but ignore this webhook)
        with patch('app.automation.service.emit_make_webhook', AsyncMock(return_value=True)):
            task = await AutomationService.create_task(
                db=test_session,
                task_type=AutomationTaskType.custom,
                title="Assignment Test Task",
                created_by_id=user.id,
            )
        
        # Create assignment
        assignment = TaskAssignment(
            task_id=task.id,
            user_id=user.id,
            status='PENDING',
        )
        test_session.add(assignment)
        await test_session.commit()
        
        captured_payload = None
        
        async def capture_webhook(payload, **kwargs):
            nonlocal captured_payload
            captured_payload = payload
            return True
        
        # Now complete the assignment
        with patch('app.automation.service.emit_make_webhook', capture_webhook):
            await AutomationService.complete_assignment(
                db=test_session,
                task_id=task.id,
                user_id=user.id,
                assignment_id=assignment.id,
            )
        
        assert captured_payload is not None
        assert captured_payload["event"] == "task.completed"
        assert captured_payload["data"]["completed_by"]["user_id"] == user.id
        assert captured_payload["data"]["completed_by"]["username"] == "assignee_test"
    
    @pytest.mark.anyio
    async def test_webhook_failure_does_not_break_automation(self, test_session):
        """Verify automation continues even if webhook fails."""
        from app.automation.service import AutomationService
        from app.db.enums import AutomationTaskType
        from app.db.models import User
        from app.integrations.make_webhook import clear_sent_events_cache
        
        clear_sent_events_cache()
        
        # Create test user
        user = User(
            email="failure_test@test.com",
            username="failure_test",
            hashed_password="x",
            operational_role='agent',
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)
        
        # Make webhook fail
        async def failing_webhook(payload, **kwargs):
            raise Exception("Webhook failed!")
        
        with patch('app.automation.service.emit_make_webhook', failing_webhook):
            # Should not raise exception
            task = await AutomationService.create_task(
                db=test_session,
                task_type=AutomationTaskType.custom,
                title="Failure Test Task",
                created_by_id=user.id,
            )
        
        # Task should still be created
        assert task is not None
        assert task.id is not None
        assert task.title == "Failure Test Task"
