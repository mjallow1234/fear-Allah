import os
from app.core.config import settings
from app.db.database import sync_engine
from sqlalchemy import text
from sqlalchemy.orm import Session

print('DB URL', settings.DATABASE_URL)
with Session(sync_engine) as sess:
    rows = sess.execute(text('select id, username, role, is_system_admin from users order by id desc limit 50'))
    for row in rows:
        print(row)
