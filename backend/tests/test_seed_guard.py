import pytest
import importlib.util
from pathlib import Path
from app.core.config import settings

pytestmark = pytest.mark.unit


def test_seed_refuses_production(monkeypatch):
    monkeypatch.setattr(settings, 'APP_ENV', 'production')
    # Resolve script path robustly whether tests run from repo root or backend dir
    backend_dir = Path(__file__).resolve().parents[1]
    candidate = backend_dir / 'scripts' / 'seed_staging.py'
    if not candidate.exists():
        # Fallback to repo-root style path
        candidate = backend_dir.parent / 'backend' / 'scripts' / 'seed_staging.py'

    assert candidate.exists(), f"Seed script not found at {candidate}"

    spec = importlib.util.spec_from_file_location('seed_staging', str(candidate))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(RuntimeError):
        import asyncio
        asyncio.run(module.run())
