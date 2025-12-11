import os
import sys
import inspect

# Ensure `backend` is on PYTHONPATH so `import app` works when running tests from repo root
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BACKEND_PATH = os.path.join(ROOT, 'backend')
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)


def test_userrole_enum_values():
    from app.db.models import UserRole
    assert UserRole.system_admin.value == "system_admin"
    assert UserRole.team_admin.value == "team_admin"
    assert UserRole.member.value == "member"
    assert UserRole.guest.value == "guest"


def test_admin_seed_uses_correct_role():
    # Avoid importing app.main (imports trigger MinIO client which requires network).
    # Instead read the source file directly to assert the seeding uses the lowercase enum.
    main_path = os.path.join(BACKEND_PATH, 'app', 'main.py')
    with open(main_path, 'r', encoding='utf-8') as f:
        src = f.read()
    assert 'UserRole.system_admin' in src


def test_role_comparisons_are_lowercase():
    from app.db.models import UserRole
    # Direct value comparisons should be lowercase
    assert UserRole.system_admin.value == "system_admin"
    # Simulate a consumer comparing string values
    assert (UserRole.system_admin.value == "system_admin") is True
