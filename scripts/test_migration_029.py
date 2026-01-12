"""Quick verification for migration 029_normalize_teams_keep_sidrah_salaam
This script creates a temporary SQLite DB, sets up minimal schema, populates scenarios,
and runs the SQL logic identical to the Alembic migration to validate behavior.
"""
import sqlite3
import os

DB = "./test_migration_029.db"

MIGRATION_SQL = [
    # The migration uses Python logic; here we replicate necessary SQL statements
    # We'll perform the sequence programmatically in Python using sqlite3
]


def reset_db():
    try:
        os.remove(DB)
    except OSError:
        pass

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Create tables
    c.executescript('''
    CREATE TABLE teams (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, display_name TEXT);
    CREATE TABLE team_members (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, team_id INTEGER, role TEXT, created_at TEXT);
    CREATE TABLE channels (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, team_id INTEGER, display_name TEXT);
    CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER, content TEXT);
    CREATE TABLE channel_members (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, channel_id INTEGER, last_read_at TEXT, last_viewed_at TEXT, created_at TEXT);
    ''')
    conn.commit()
    conn.close()


def run_migration_logic(conn):
    c = conn.cursor()
    # Resolve team ids
    c.execute("SELECT id FROM teams WHERE name = ? LIMIT 1", ("sidrah-salaam",))
    primary = c.fetchone()
    c.execute("SELECT id FROM teams WHERE name = ? LIMIT 1", ("default",))
    legacy = c.fetchone()
    if not primary or not legacy:
        print('No-op: one or both teams missing')
        return
    primary_id = primary[0]
    legacy_id = legacy[0]

    print('primary_id', primary_id, 'legacy_id', legacy_id)

    # counts before
    c.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?", (legacy_id,))
    members_legacy = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?", (primary_id,))
    members_primary = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM channels WHERE team_id = ?", (legacy_id,))
    channels_legacy = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM channels WHERE team_id = ?", (primary_id,))
    channels_primary = c.fetchone()[0]
    print('before', members_legacy, members_primary, channels_legacy, channels_primary)

    # Insert missing memberships
    c.execute('''
        INSERT INTO team_members (user_id, team_id, role, created_at)
        SELECT tm.user_id, ?, tm.role, tm.created_at FROM team_members tm
        WHERE tm.team_id = ?
        AND NOT EXISTS (SELECT 1 FROM team_members t2 WHERE t2.team_id = ? AND t2.user_id = tm.user_id)
    ''', (primary_id, legacy_id, primary_id))

    # Process legacy channels
    c.execute('SELECT id, name FROM channels WHERE team_id = ?', (legacy_id,))
    legacy_channels = c.fetchall()
    for lc in legacy_channels:
        legacy_ch_id, name = lc
        c.execute('SELECT id FROM channels WHERE team_id = ? AND name = ? LIMIT 1', (primary_id, name))
        pc = c.fetchone()
        if pc:
            primary_ch_id = pc[0]
            # Move messages
            c.execute('UPDATE messages SET channel_id = ? WHERE channel_id = ?', (primary_ch_id, legacy_ch_id))
            # Insert missing channel members
            c.execute('''
                INSERT INTO channel_members (user_id, channel_id, last_read_at, last_viewed_at, created_at)
                SELECT cm.user_id, ?, cm.last_read_at, cm.last_viewed_at, cm.created_at FROM channel_members cm
                WHERE cm.channel_id = ?
                AND NOT EXISTS (SELECT 1 FROM channel_members c2 WHERE c2.channel_id = ? AND c2.user_id = cm.user_id)
            ''', (primary_ch_id, legacy_ch_id, primary_ch_id))
            # Delete legacy channel
            c.execute('DELETE FROM channels WHERE id = ?', (legacy_ch_id,))
        else:
            c.execute('UPDATE channels SET team_id = ? WHERE id = ?', (primary_id, legacy_ch_id))

    # Delete legacy team members
    c.execute('DELETE FROM team_members WHERE team_id = ?', (legacy_id,))
    # Delete legacy team
    c.execute('DELETE FROM teams WHERE id = ?', (legacy_id,))

    # counts after
    c.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?", (primary_id,))
    members_primary_after = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM channels WHERE team_id = ?", (primary_id,))
    channels_primary_after = c.fetchone()[0]
    print('after', members_primary_after, channels_primary_after)

    conn.commit()


def scenario_both():
    reset_db()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Create teams
    c.execute("INSERT INTO teams (name, display_name) VALUES (?, ?)", ("sidrah-salaam", "Sidrah"))
    c.execute("INSERT INTO teams (name, display_name) VALUES (?, ?)", ("default", "Default"))
    sid = c.execute("SELECT id FROM teams WHERE name = 'sidrah-salaam'").fetchone()[0]
    defid = c.execute("SELECT id FROM teams WHERE name = 'default'").fetchone()[0]
    # Add memberships to default (users 1..3)
    for u in range(1, 4):
        c.execute('INSERT INTO team_members (user_id, team_id, role, created_at) VALUES (?, ?, ?, ?)', (u, defid, 'member', 'now'))
    # Add a channel to default and a channel with same name to primary
    c.execute('INSERT INTO channels (name, team_id, display_name) VALUES (?, ?, ?)', ('general', defid, 'General'))
    c.execute('INSERT INTO channels (name, team_id, display_name) VALUES (?, ?, ?)', ('general', sid, 'General'))
    conn.commit()
    print('Before migration (both):')
    run_migration_logic(conn)
    print('Running migration second time (idempotency)')
    run_migration_logic(conn)
    conn.close()


def scenario_only_primary():
    reset_db()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO teams (name, display_name) VALUES (?, ?)", ("sidrah-salaam", "Sidrah"))
    conn.commit()
    print('Before migration (only primary):')
    run_migration_logic(conn)
    conn.close()


def scenario_only_legacy():
    reset_db()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO teams (name, display_name) VALUES (?, ?)", ("default", "Default"))
    # Add members & channels
    defid = c.execute("SELECT id FROM teams WHERE name = 'default'").fetchone()[0]
    c.execute('INSERT INTO team_members (user_id, team_id, role, created_at) VALUES (?, ?, ?, ?)', (1, defid, 'member', 'now'))
    c.execute('INSERT INTO channels (name, team_id, display_name) VALUES (?, ?, ?)', ('general', defid, 'General'))
    conn.commit()
    print('Before migration (only legacy):')
    run_migration_logic(conn)
    conn.close()


if __name__ == '__main__':
    print('=== Scenario: both teams ===')
    scenario_both()
    print('\n=== Scenario: only primary ===')
    scenario_only_primary()
    print('\n=== Scenario: only legacy ===')
    scenario_only_legacy()
    # Clean up
    try:
        os.remove(DB)
    except Exception:
        pass
    print('Done')
