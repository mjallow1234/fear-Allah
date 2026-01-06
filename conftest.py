from pathlib import Path


def pytest_ignore_collect(path, config):
    # Prevent pytest from trying to treat non-python test artifacts at repo root as tests
    try:
        p = Path(str(path))
        if p.name == "test_upload.txt":
            return True
    except Exception:
        return False
    return False
