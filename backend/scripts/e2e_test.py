#!/usr/bin/env python3
import http.client, json, sys, time

def req(method, path, body=None, headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', 8000, timeout=10)
    h = {}
    if headers:
        h.update(headers)
    b = None
    if body is not None:
        b = json.dumps(body)
        h['Content-Type'] = 'application/json'
    conn.request(method, path, body=b, headers=h)
    r = conn.getresponse()
    data = r.read().decode()
    return r.status, data


def main():
    username = f"e2e_{int(time.time())}"
    email = f"{username}@example.com"
    password = "TestPass123!"

    # Try to register
    status, body = req('POST', '/api/auth/register', {'username': username, 'email': email, 'password': password})
    print('REGISTER', status)
    print(body)

    token = None
    if status == 201:
        token = json.loads(body).get('access_token')
    else:
        # Try login (maybe user exists)
        status, body = req('POST', '/api/auth/login', {'identifier': email, 'password': password})
        print('LOGIN', status)
        print(body)
        if status == 200:
            token = json.loads(body).get('access_token')

    if not token:
        print('ERROR: unable to obtain token', file=sys.stderr)
        sys.exit(2)

    # Fetch current user
    status, body = req('GET', '/api/users/me', headers={'Authorization': 'Bearer ' + token})
    print('ME', status)
    print(body)


if __name__ == '__main__':
    main()
