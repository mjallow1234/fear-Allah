#!/usr/bin/env python3
"""
Reset the application database by dropping and recreating it.

This script uses the application's DATABASE_URL environment variable when available
and otherwise falls back to sensible defaults.

Safety: when APP_ENV == 'production' this script will refuse to run unless
FORCE_RESET=true is set in the environment.
"""
import os
import sys
from urllib.parse import urlparse

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def parse_database_url(database_url: str):
    parsed = urlparse(database_url)
    user = parsed.username or os.getenv("POSTGRES_USER", "postgres")
    password = parsed.password or os.getenv("POSTGRES_PASSWORD", "postgres")
    host = parsed.hostname or os.getenv("POSTGRES_HOST", "localhost")
    port = parsed.port or int(os.getenv("POSTGRES_PORT", 5432))
    dbname = parsed.path.lstrip("/") if parsed.path else os.getenv("POSTGRES_DB", "fearallah")
    return user, password, host, port, dbname


def main():
    # Respect existing DATABASE_URL if present
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fearallah")
    app_env = os.getenv("APP_ENV", "development")

    if app_env == "production" and os.getenv("FORCE_RESET", "false").lower() != "true":
        print("ERROR: Refusing to run database reset in production without FORCE_RESET=true", file=sys.stderr)
        sys.exit(2)

    admin_user, admin_pass, host, port, db_name = parse_database_url(database_url)

    print(f"Resetting database '{db_name}' on {host}:{port} as user '{admin_user}' (APP_ENV={app_env})")

    try:
        # Connect to the default 'postgres' administrative database
        conn = psycopg2.connect(
            dbname=os.getenv("PG_ADMIN_DB", "postgres"),
            user=admin_user,
            password=admin_pass,
            host=host,
            port=port,
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # Use SQL identifiers to avoid injection.
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {};").format(sql.Identifier(db_name)))
        cur.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(db_name)))

        cur.close()
        conn.close()

        print("Database reset complete")
        sys.exit(0)

    except Exception as exc:  # pragma: no cover - simple script
        print("ERROR: Failed to reset database:", exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
