#!/usr/bin/env python
"""Presence + Typing test: connect to presence WS, then send typing_start/stop events on chat WS and verify Redis keys via kubectl.
Usage: set ADMIN_TOKEN in environment or pass as first arg.
"""
import asyncio
import json
import os
import sys
import subprocess
import time
from typing import Optional

import websockets


async def connect_presence(token: str):
    uri = f"ws://127.0.0.1:8000/ws/presence?token={token}"
    print("Connecting presence ->", uri)
    async with websockets.connect(uri) as ws:
        print("Connected to presence")
        # read initial presence list
        msg = await ws.recv()
        print("PRESENCE RECV:", msg)
        # Keep connection open for a short time
        await asyncio.sleep(1)


async def send_typing(channel_id: int, token: str, username: str, action: str = 'typing_start'):
    uri = f"ws://127.0.0.1:8000/ws/chat/{channel_id}?token={token}"
    print("Connecting chat ->", uri)
    async with websockets.connect(uri) as ws:
        print("Connected to chat as", username)
        payload = {"type": action}
        await ws.send(json.dumps(payload))
        print("Sent typing action:", action)
        await asyncio.sleep(1)
        # send typing_stop if needed
        if action == 'typing_start':
            await ws.send(json.dumps({"type": "typing_stop"}))
            print("Sent typing_stop")
            await asyncio.sleep(1)


def check_redis_key(pod: str, cmd: str):
    full = ['kubectl', '-n', 'fear-allah', 'exec', pod, '--'] + cmd
    print('Running:',' '.join(full))
    proc = subprocess.run(full, capture_output=True, text=True)
    if proc.returncode != 0:
        print('ERROR:', proc.stderr)
    else:
        print(proc.stdout)
    return proc


def main():
    token = os.getenv('ADMIN_TOKEN')
    if len(sys.argv) > 1:
        token = sys.argv[1]
    if not token:
        print('Missing ADMIN_TOKEN (env or arg)')
        sys.exit(2)

    # Find Redis pod
    pod_res = subprocess.run(['kubectl', '-n', 'fear-allah', 'get', 'pods', '-l', 'app=redis', '-o', 'name'], capture_output=True, text=True)
    pod_name = pod_res.stdout.strip().splitlines()[0].split('/')[-1]
    print('Redis pod:', pod_name)

    # Connect presence
    asyncio.run(connect_presence(token))

    # Check that user:<id> exists after presence connection
    print('\nChecking user:1 hash (admin):')
    check_redis_key(pod_name, ['redis-cli', 'hgetall', 'user:1'])
    check_redis_key(pod_name, ['redis-cli', 'ttl', 'user:1'])

    # Check messages cache for channel 5
    print('\nCached messages for channel 5:')
    check_redis_key(pod_name, ['redis-cli', 'lrange', 'messages:5', '0', '-1'])

    # Send typing_start on channel 5 as admin
    asyncio.run(send_typing(5, token, 'admin', 'typing_start'))

    # Check typing:5 set
    print('\nTyping users for channel 5:')
    check_redis_key(pod_name, ['redis-cli', 'smembers', 'typing:5'])
    check_redis_key(pod_name, ['redis-cli', 'ttl', 'typing:5'])

    print('\nDone')


if __name__ == '__main__':
    main()
