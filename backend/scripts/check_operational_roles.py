"""Check for NULL operational_role values in the users table.

Usage:
    PYTHONPATH=.. python scripts/check_operational_roles.py

This script connects to the DB configured by DATABASE_URL environment variable (falls back to env var ASYNC_DATABASE_URL or sqlite) and prints the number of users missing operational_role.
Returns non-zero exit code if any NULLs are found.
"""
import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('ASYNC_DATABASE_URL') or 'sqlite:///./dev.db'

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    res = conn.execute(text("SELECT COUNT(1) FROM users WHERE operational_role IS NULL"))
    cnt = res.scalar()
    if cnt is None:
        cnt = 0

    if cnt > 0:
        print(f"Found {cnt} user(s) with NULL operational_role. Fix required before marking migration complete.")
        sys.exit(2)
    else:
        print("All users have operational_role set (0 NULLs).")
        sys.exit(0)
