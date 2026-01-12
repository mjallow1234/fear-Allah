def test_migration_030_contains_null_guard():
    """Static check that migration 030 performs backfill only on NULLs and verifies there are no NULLs before making column NOT NULL."""
    import pathlib
    p = pathlib.Path(__file__).parents[1] / 'alembic' / 'versions' / '030_add_operational_role.py'
    assert p.exists(), "Migration 030 file not found"
    txt = p.read_text()
    assert 'WHERE operational_role IS NULL' in txt, "Backfill should only update NULLs"
    assert 'SELECT COUNT(1) FROM users WHERE operational_role IS NULL' in txt, "Migration should verify no NULLs remain before altering column"
    assert "batch_op.alter_column('operational_role'" in txt, "Migration should alter column to NOT NULL after verification"
