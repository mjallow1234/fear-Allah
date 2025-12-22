import pytest
import importlib.util
from app.core.config import settings

pytestmark = pytest.mark.unit


def test_seed_refuses_production(monkeypatch):
    monkeypatch.setattr(settings, 'APP_ENV', 'production')
    spec = importlib.util.spec_from_file_location('seed_staging', 'backend/scripts/seed_staging.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError):
        import asyncio
        asyncio.run(module.run())
