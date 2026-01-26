import httpx, json, sys

base = 'http://localhost:8000'

client = httpx.Client()
# Login
r = client.post(f'{base}/api/auth/login', json={'identifier': 'admin', 'password': 'Admin123!'})
print('login status', r.status_code)
try:
    token = r.json().get('access_token')
except Exception as e:
    print('login body', r.text)
    sys.exit(1)
headers = {'Authorization': f'Bearer {token}'}

# Submit form
r = client.post(f'{base}/api/forms/orders/submit', json={'data': {'order_type': 'agent_restock', 'product_id': 1, 'quantity': 1}}, headers=headers)
print('/api/forms/orders/submit', r.status_code, r.text[:500])

# Create order (not used - use form submission result)
# r = client.post(f'{base}/api/orders/', json={'order_type': 'AGENT_RETAIL', 'items': []}, headers=headers)
# print('/api/orders/ create', r.status_code, r.text[:200])
# order_id = None
# try:
#    order_id = r.json().get('id')
# except Exception:
#    order_id = None

# GET /api/orders/{id}/automation using the submission's result_id
try:
    sub = client.post(f'{base}/api/forms/orders/submit', json={'data': {'order_type': 'agent_restock', 'product_id': 1, 'quantity': 1}}, headers=headers)
    rid = sub.json().get('result_id') if sub.status_code == 200 else None
except Exception:
    rid = None

if rid:
    r = client.get(f'{base}/api/orders/{rid}/automation', headers=headers)
    print(f'/api/orders/{rid}/automation', r.status_code, r.text[:500])
else:
    print('no order id from submission')

# GET /api/automation/tasks
r = client.get(f'{base}/api/automation/tasks', headers=headers)
print('/api/automation/tasks', r.status_code, r.text[:200])
