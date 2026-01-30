from app.db.database import sync_engine
import traceback

try:
    conn = sync_engine.connect()
    res = conn.execute('SELECT id, meta FROM orders ORDER BY id DESC LIMIT 1;')
    print(res.fetchone())
    conn.close()
except Exception:
    traceback.print_exc()