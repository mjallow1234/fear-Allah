#!/usr/bin/env python3
import http.client, json, sys, time

HOST = '127.0.0.1'
PORT = 8000

def req(method, path, body=None, headers=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
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
    try:
        parsed = json.loads(data) if data else None
    except Exception:
        parsed = data
    return r.status, parsed


def main():
    ts = int(time.time())
    username = f"e2e_ext_{ts}"
    email = f"{username}@example.com"
    password = "TestPass123!"

    print('Registering user...')
    status, body = req('POST', '/api/auth/register', {'username': username, 'email': email, 'password': password})
    print('REGISTER', status, body)
    token = None
    if status == 201:
        token = body.get('access_token')
    else:
        print('Register failed, trying login...')
        status, body = req('POST', '/api/auth/login', {'identifier': email, 'password': password})
        print('LOGIN', status, body)
        if status == 200:
            token = body.get('access_token')

    if not token:
        print('ERROR: could not get token', file=sys.stderr)
        sys.exit(2)

    headers = {'Authorization': 'Bearer ' + token}

    # Find default team
    print('Listing teams...')
    # Some endpoints may redirect to include a trailing slash; request the slash form
    status, body = req('GET', '/api/teams/', headers=headers)
    if status != 200:
        print('Failed to list teams', status, body)
        sys.exit(3)
    team_id = None
    for t in body:
        if t.get('name') == 'default':
            team_id = t.get('id')
            break
    print('Found default team:', team_id)

    # Create a channel in default team
    ch_name = f'e2e-channel-{ts}'
    print('Creating channel', ch_name)
    # Use trailing slash to avoid 307 redirects
    status, body = req('POST', '/api/channels/', {'name': ch_name, 'display_name': ch_name, 'team_id': team_id}, headers=headers)
    print('CREATE CHANNEL', status, body)
    if status != 201:
        print('Failed to create channel', file=sys.stderr)
        sys.exit(4)
    channel_id = body.get('id')

    # Post a message
    msg_content = 'Hello from e2e extended'
    print('Posting message to channel', channel_id)
    # Use trailing slash to avoid 307 redirect for root router
    status, body = req('POST', '/api/messages/', {'content': msg_content, 'channel_id': channel_id}, headers=headers)
    print('CREATE MESSAGE', status, body)
    if status != 201:
        print('Failed to post message', file=sys.stderr)
        sys.exit(5)
    message_id = body.get('id')

    # Get channel messages
    print('Fetching channel messages')
    status, body = req('GET', f'/api/messages/channel/{channel_id}', headers=headers)
    print('CHANNEL MESSAGES', status)
    # Ensure our message is present
    found = False
    if status == 200 and isinstance(body, list):
        for m in body:
            if m.get('id') == message_id:
                found = True
                break
    print('Message present in channel:', found)

    # Add a reaction
    emoji = 'thumbsup'
    print('Adding reaction', emoji, 'to message', message_id)
    status, body = req('POST', f'/api/messages/{message_id}/reactions', {'emoji': emoji}, headers=headers)
    print('ADD REACTION', status, body)

    # Get reactions
    status, body = req('GET', f'/api/messages/{message_id}/reactions', headers=headers)
    print('GET REACTIONS', status, body)

    # Reply to message
    reply_content = 'Reply from e2e'
    print('Replying to message', message_id)
    status, body = req('POST', f'/api/messages/{message_id}/reply', {'content': reply_content}, headers=headers)
    print('CREATE REPLY', status, body)

    # Get replies
    status, body = req('GET', f'/api/messages/{message_id}/replies', headers=headers)
    print('GET REPLIES', status, body)

    print('\nE2E extended test completed successfully')

if __name__ == '__main__':
    main()
