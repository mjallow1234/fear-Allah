import requests, json

BASE = 'http://localhost:18002/api'

def login(identifier, password):
    r = requests.post(f'{BASE}/auth/login', json={'identifier': identifier, 'password': password}, timeout=20)
    if r.status_code != 200:
        print(f'  LOGIN FAILED for {identifier}: {r.status_code} {r.text}')
        return None
    data = r.json()
    print(f"  Logged in as {data['user']['username']}  role={data['user']['role']}  is_system_admin={data['user']['is_system_admin']}")
    return data['access_token']

def test_endpoint(label, method, url, token, json_body=None):
    headers = {'Authorization': f'Bearer {token}'}
    if method == 'DELETE':
        r = requests.delete(url, headers=headers, timeout=20)
    elif method == 'POST':
        r = requests.post(url, headers=headers, json=json_body or {}, timeout=20)
    elif method == 'PATCH':
        r = requests.patch(url, headers=headers, json=json_body or {}, timeout=20)
    else:
        r = requests.get(url, headers=headers, timeout=20)
    print(f'  {label:40s} => {r.status_code}  {r.text[:120]}')
    return r.status_code

# Use user id=20 (testdelete) as target for tests
# It's already soft-deleted and banned so it can be restored, etc.
TARGET_USER_ID = 20

# --- Login as admin (system_admin) ---
print('\n=== system_admin (admin, id=1) ===')
admin_token = login('admin@fearallah.com', 'SidraPass2025!')

# --- Login as team_admin ---
print('\n=== team_admin (teamadmin_test, id=23) ===')
team_token = login('teamadmin_test', 'TeamAdmin123!')

# --- Login as member ---
print('\n=== member (member_test, id=24) ===')
member_token = login('member_test', 'Member123!')

# Try known credentials if above failed
if not admin_token:
    print('\nTrying admin@sidrachat.com...')
    admin_token = login('admin@sidrachat.com', 'admin123')
if not admin_token:
    print('\nTrying admin/admin123...')
    admin_token = login('admin', 'admin123')

tokens = {
    'system_admin': admin_token,
    'team_admin': team_token,
    'member': member_token,
}

# Filter out failed logins
tokens = {k: v for k, v in tokens.items() if v is not None}

if not tokens:
    print('\nNo tokens obtained. Cannot proceed.')
    raise SystemExit(1)

# Endpoints to test
endpoints = [
    ('GET /system/users',           'GET',    f'{BASE}/system/users?limit=5',                  None),
    ('DELETE /system/users/:id',    'DELETE', f'{BASE}/system/users/{TARGET_USER_ID}',          None),
    ('POST /system/users/:id/restore', 'POST', f'{BASE}/system/users/{TARGET_USER_ID}/restore', None),
    ('PATCH /system/users/:id/activate', 'PATCH', f'{BASE}/system/users/{TARGET_USER_ID}/activate', None),
    ('PATCH /system/users/:id/deactivate', 'PATCH', f'{BASE}/system/users/{TARGET_USER_ID}/deactivate', None),
    ('POST /system/users/:id/ban',  'POST',  f'{BASE}/system/users/{TARGET_USER_ID}/ban',      {'ban_reason': 'test'}),
    ('POST /system/users/:id/unban','POST',  f'{BASE}/system/users/{TARGET_USER_ID}/unban',     None),
]

for role, token in tokens.items():
    print(f'\n=== Testing as {role} ===')
    for label, method, url, body in endpoints:
        test_endpoint(label, method, url, token, body)
