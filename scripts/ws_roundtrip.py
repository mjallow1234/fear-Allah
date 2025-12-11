#!/usr/bin/env python
"""WebSocket roundtrip test: starts a listener (target user) and a sender (admin)
Usage: python scripts/ws_roundtrip.py <channel_id> <admin_token> <admin_username> <target_token> <target_username>
"""
import asyncio
import json
import sys

import websockets


async def listener(channel_id: int, token: str, username: str):
    uri = f"ws://127.0.0.1:8000/ws/chat/{channel_id}?token={token}"
    print(f"LISTENER connecting -> {uri}")
    try:
        async with websockets.connect(uri) as ws:
            print(f"LISTENER connected as {username} ({user_id})")
            while True:
                msg = await ws.recv()
                print("LISTENER RECV:", msg)
    except Exception as e:
        print("LISTENER error:", repr(e))


async def sender(channel_id: int, token: str, username: str, target_username: str):
    uri = f"ws://127.0.0.1:8000/ws/chat/{channel_id}?token={token}"
    print(f"SENDER connecting -> {uri}")
    try:
        async with websockets.connect(uri) as ws:
            print(f"SENDER connected as {username} ({user_id})")
            # Send a normal message
            await asyncio.sleep(1)
            payload = {"type": "message", "content": "Hello from admin (automated test)"}
            await ws.send(json.dumps(payload))
            print("SENDER sent message 1")

            # Send a mention to the target
            await asyncio.sleep(1)
            mention_msg = f"Hi @{target_username}, you have a mention from {username}!"
            payload2 = {"type": "message", "content": mention_msg}
            await ws.send(json.dumps(payload2))
            print("SENDER sent mention message")

            # Give server time to process and deliver
            await asyncio.sleep(3)
    except Exception as e:
        print("SENDER error:", repr(e))


async def main():
    if len(sys.argv) < 6:
        print("Usage: python scripts/ws_roundtrip.py <channel_id> <admin_token> <admin_username> <target_token> <target_username>")
        sys.exit(2)

    channel_id = int(sys.argv[1])
    admin_token = sys.argv[2]
    admin_username = sys.argv[3]
    target_token = sys.argv[4]
    target_username = sys.argv[5]

    # Start listener first (target user), then sender
    listener_task = asyncio.create_task(listener(channel_id, target_token, target_username))

    # Give listener time to connect
    await asyncio.sleep(0.6)

    await sender(channel_id, admin_token, admin_username, target_username)

    # Give listener time to receive messages
    await asyncio.sleep(2)

    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass

    print("Done")


if __name__ == '__main__':
    asyncio.run(main())
