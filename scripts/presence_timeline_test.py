#!/usr/bin/env python
"""Presence timeline test

Connects two websocket clients (admin and testuser1) to /ws/presence and to /ws/chat for channel actions.
Continuously polls Redis for user:<id> keys (status + TTL) and logs timeline of events.

Usage: python scripts/presence_timeline_test.py --admin-email admin@fearallah.com --admin-pass SidraPass2025! --user-email testuser1@example.com --user-pass TestPass2025! --channel 5
"""
import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from typing import Dict, Any

import websockets
import requests


def now():
    return datetime.utcnow().isoformat() + 'Z'


class Timeline:
    def __init__(self):
        self.events = []

    def add(self, source: str, event_type: str, payload: Any, redis_info: Dict[str, Any] = None):
        ev = {
            'ts': now(),
            'source': source,
            'event': event_type,
            'payload': payload,
            'redis': redis_info or {}
        }
        self.events.append(ev)
        print(json.dumps(ev, default=str))

    def dump(self):
        print('\nTIMELINE:')
        for e in self.events:
            print(json.dumps(e, default=str))


async def presence_client(token: str, name: str, timeline: Timeline, run_event: asyncio.Event):
    uri = f"ws://127.0.0.1:8000/ws/presence?token={token}"
    async with websockets.connect(uri) as ws:
        timeline.add(name, 'connected', {'uri': uri})
        try:
            while not run_event.is_set():
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                try:
                    payload = json.loads(msg)
                except Exception:
                    payload = msg
                timeline.add(name, 'presence_event', payload)
        except asyncio.TimeoutError:
            # Continue loop until run_event
            pass
        finally:
            timeline.add(name, 'disconnected', {})


async def chat_client(name: str, token: str, user_id: int, channel_id: int, timeline: Timeline, run_event: asyncio.Event, actions: list):
    uri = f"ws://127.0.0.1:8000/ws/chat/{channel_id}?token={token}"
    async with websockets.connect(uri) as ws:
        timeline.add(name, 'chat_connected', {'uri': uri})
        # run actions sequentially
        for action in actions:
            if action['type'] == 'send':
                payload = {'type': 'message', 'content': action['content']}
                await ws.send(json.dumps(payload))
                timeline.add(name, 'message_sent', payload)
            elif action['type'] == 'sleep':
                await asyncio.sleep(action.get('seconds', 1))
            elif action['type'] == 'disconnect':
                timeline.add(name, 'chat_disconnect', {})
                return
        # leave socket open until run_event set
        while not run_event.is_set():
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                payload = json.loads(msg)
                timeline.add(name, 'chat_event', payload)
            except asyncio.TimeoutError:
                continue


def kubectl_get_redis_pod():
    res = subprocess.run(['kubectl', '-n', 'fear-allah', 'get', 'pods', '-l', 'app=redis', '-o', 'name'], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError('Failed to get redis pod: ' + res.stderr)
    lines = res.stdout.strip().splitlines()
    if not lines:
        raise RuntimeError('No redis pod found')
    # returns e.g. pod/redis-xxxxx
    return lines[0].split('/')[-1]


def redis_get_status_ttl(pod: str, user_id: int):
    key = f'user:{user_id}'
    # Use redis-cli hget and ttl for atomic-ish reads
    hget = subprocess.run(['kubectl', '-n', 'fear-allah', 'exec', pod, '--', 'redis-cli', 'hget', key, 'status'], capture_output=True, text=True)
    ttl = subprocess.run(['kubectl', '-n', 'fear-allah', 'exec', pod, '--', 'redis-cli', 'ttl', key], capture_output=True, text=True)
    status = hget.stdout.strip() if hget.returncode == 0 else ''
    ttlv = ttl.stdout.strip() if ttl.returncode == 0 else ''
    return status, int(ttlv) if ttlv.isdigit() else None


async def poll_redis(pod: str, user_ids: list, timeline: Timeline, run_event: asyncio.Event, interval: float = 0.2):
    while not run_event.is_set():
        for uid in user_ids:
            status, ttl = redis_get_status_ttl(pod, uid)
            timeline.add('redis_poll', 'poll', {'user_id': uid, 'status': status, 'ttl': ttl})
        await asyncio.sleep(interval)


async def main_async(args):
    # Login to get tokens if not provided
    def login(email, password):
        resp = requests.post(f"http://127.0.0.1:8000/api/auth/login", json={"identifier": email, "password": password})
        resp.raise_for_status()
        return resp.json()['access_token'], resp.json()['user']

    admin_token, admin_user = login(args.admin_email, args.admin_pass)
    user_token, user = login(args.user_email, args.user_pass)

    # find redis pod
    pod = kubectl_get_redis_pod()
    timeline = Timeline()
    run_event = asyncio.Event()

    # Create tasks
    tasks = []
    tasks.append(asyncio.create_task(presence_client(admin_token, f"admin-{admin_user['id']}", timeline, run_event)))
    tasks.append(asyncio.create_task(presence_client(user_token, f"user-{user['id']}", timeline, run_event)))
    tasks.append(asyncio.create_task(poll_redis(pod, [admin_user['id'], user['id']], timeline, run_event, interval=0.2)))

    # Start chat activity to cause join & message events: connect admin, send message, connect user, message, disconnect admin
    admin_chat_actions = [
        {'type': 'sleep', 'seconds': 1},
        {'type': 'send', 'content': 'Admin hello from presence test'},
        {'type': 'sleep', 'seconds': 1},
        {'type': 'send', 'content': '@testuser1 mention from admin'},
        {'type': 'sleep', 'seconds': 1},
        {'type': 'disconnect'}
    ]
    user_chat_actions = [
        {'type': 'sleep', 'seconds': 2},
        {'type': 'send', 'content': 'testuser1 reply'},
        {'type': 'sleep', 'seconds': 2},
    ]

    tasks.append(asyncio.create_task(chat_client(f"admin-{admin_user['id']}", admin_token, admin_user['id'], args.channel, timeline, run_event, admin_chat_actions)))
    tasks.append(asyncio.create_task(chat_client(f"user-{user['id']}", user_token, user['id'], args.channel, timeline, run_event, user_chat_actions)))

    # Let this run for X seconds
    await asyncio.sleep(args.duration)
    run_event.set()

    # Allow tasks to cancel gracefully
    await asyncio.gather(*tasks, return_exceptions=True)

    # Dump timeline
    timeline.dump()
    # Write timeline to file
    try:
        out_path = 'scripts/presence_timeline_output.json'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(timeline.events, f, ensure_ascii=False, indent=2)
        print(f'Wrote timeline to {out_path}')
    except Exception as e:
        print('Failed to write timeline file:', e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--admin-email', required=True)
    parser.add_argument('--admin-pass', required=True)
    parser.add_argument('--user-email', required=True)
    parser.add_argument('--user-pass', required=True)
    parser.add_argument('--channel', type=int, required=True)
    parser.add_argument('--duration', type=int, default=60)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == '__main__':
    main()
