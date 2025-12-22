import pytest
import asyncio
from app.core.automation import run_if_automations_enabled
from app.core.config import settings

pytestmark = pytest.mark.unit

@pytest.mark.anyio
async def test_automation_decorator_skips_when_disabled(monkeypatch):
    # Ensure automations disabled
    monkeypatch.setattr(settings, 'AUTOMATIONS_ENABLED', False)

    called = False

    @run_if_automations_enabled
    async def _do_something():
        nonlocal called
        called = True
        return 'done'

    res = await _do_something()
    assert res is None
    assert called is False

@pytest.mark.anyio
async def test_automation_decorator_runs_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, 'AUTOMATIONS_ENABLED', True)

    @run_if_automations_enabled
    async def _do_something():
        return 'done'

    res = await _do_something()
    assert res == 'done'