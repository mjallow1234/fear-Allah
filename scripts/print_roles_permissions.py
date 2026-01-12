#!/usr/bin/env python3
import sqlite3, os
DB='test_concurrency.db'
if not os.path.exists(DB):
    print('Local test DB not found:', DB)
else:
    conn=sqlite3.connect(DB)
    cur=conn.cursor()
    tables=['roles','permissions','role_permissions','user_roles','channel_roles']
    for t in tables:
        try:
            cur.execute(f"SELECT * FROM {t} LIMIT 10")
            rows=cur.fetchall()
            print(f"\nTABLE: {t} (up to 10 rows)")
            if not rows:
                print('  (no rows)')
            for r in rows:
                print(' ', r)
        except Exception as e:
            print(f"Table {t} not present or error: {e}")
    # Additionally show permission keys
    try:
        cur.execute("SELECT id, key, name, description FROM permissions LIMIT 10")
        print('\nPermissions (detailed):')
        rows=cur.fetchall()
        if not rows:
            print('  (no rows)')
        for r in rows:
            print(' ', r)
    except Exception:
        pass
    conn.close()
