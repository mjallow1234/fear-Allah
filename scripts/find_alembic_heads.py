import re
from pathlib import Path

folder = Path('backend/alembic/versions')
re_rev = re.compile(r"^revision\s*=\s*'([^']+)'", re.M)
re_down = re.compile(r"^down_revision\s*=\s*(?:'([^']+)'|\(([^)]+)\))", re.M)

revisions = set()
downs = set()

for p in folder.glob('*.py'):
    txt = p.read_text()
    m = re_rev.search(txt)
    if m:
        revisions.add(m.group(1))
    m2 = re_down.search(txt)
    if m2:
        if m2.group(1):
            downs.add(m2.group(1))
        elif m2.group(2):
            # tuple of down revisions
            items = [x.strip().strip("'\"") for x in m2.group(2).split(',')]
            for it in items:
                downs.add(it)

heads = revisions - downs
print('All revisions:', sorted(revisions))
print('All down revisions:', sorted(downs))
print('Heads:', sorted(heads))
