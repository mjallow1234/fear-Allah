import httpx
r = httpx.post('http://localhost:8000/api/auth/login', json={'identifier':'admin', 'password':'Admin123!'})
print('status', r.status_code)
print('body', r.text)
print('token', r.json().get('access_token',''))
