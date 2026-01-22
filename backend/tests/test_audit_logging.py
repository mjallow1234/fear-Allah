import pytest

import app.audit.logger as audit_logger_module
from app.audit.logger import log_audit


class DummyDB:
    def __init__(self, fail_commit=False):
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.fail_commit = fail_commit

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        if self.fail_commit:
            raise Exception("commit failed")
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


@pytest.mark.asyncio
async def test_log_audit_inserts_row():
    db = DummyDB()

    class U:
        id = 42
        operational_role_name = 'agent'

    # Replace AuditLog with a simple fake to avoid SQLAlchemy internals in unit test
    original = audit_logger_module.AuditLog
    class Fake:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    audit_logger_module.AuditLog = Fake
    try:
        await log_audit(db, U(), action="create", resource="orders", resource_id=1001, success=True)

        assert len(db.added) == 1
        entry = db.added[0]
        assert isinstance(entry, Fake)
        assert entry.user_id == 42
        assert entry.role == 'agent'
        assert entry.action == 'create'
        assert entry.resource == 'orders'
        assert entry.resource_id == 1001
        assert entry.success is True
        assert db.committed is True
    finally:
        audit_logger_module.AuditLog = original


@pytest.mark.asyncio
async def test_log_audit_handles_commit_failure_gracefully():
    db = DummyDB(fail_commit=True)

    class U:
        id = 55
        operational_role_name = 'admin'

    # Replace AuditLog with a simple fake
    original = audit_logger_module.AuditLog
    class Fake:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    audit_logger_module.AuditLog = Fake
    try:
        # Should not raise
        await log_audit(db, U(), action="update", resource="inventory", resource_id=2, success=False, reason="denied")

        # Commit should have failed internally and rollback should have been attempted
        assert len(db.added) == 1
        assert db.rolled_back is True
    finally:
        audit_logger_module.AuditLog = original
