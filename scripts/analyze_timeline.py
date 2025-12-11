#!/usr/bin/env python
import json
from datetime import datetime

def ts_to_dt(ts):
    # Expect 'YYYY-MM-DDTHH:MM:SS.sssZ'
    return datetime.fromisoformat(ts.replace('Z',''))

def main():
    with open('scripts/presence_timeline_output.json','r',encoding='utf-8') as f:
        events = json.load(f)

    # Build lists
    presence_updates = []
    redis_polls = []
    disconnects = []
    for e in events:
        if e['event']=='presence_event' and isinstance(e['payload'],dict) and e['payload'].get('type')=='presence_update':
            presence_updates.append(e)
        if e['event']=='poll' and e['source']=='redis_poll':
            redis_polls.append(e)
        if e['event']=='disconnected':
            disconnects.append(e)

    def find_next_poll(user_id, after_ts):
        for p in redis_polls:
            if p['payload']['user_id']==user_id and ts_to_dt(p['ts'])>=ts_to_dt(after_ts):
                return p
        return None

    print('Presence -> Redis Poll latencies (ms):')
    latencies = []
    for pu in presence_updates:
        uid = pu['payload']['user_id']
        poll = find_next_poll(uid, pu['ts'])
        if poll:
            delta = (ts_to_dt(poll['ts']) - ts_to_dt(pu['ts'])).total_seconds()*1000
            latencies.append(delta)
            print(f"user {uid} presence->poll delta {delta:.1f} ms (presence ts={pu['ts']} poll ts={poll['ts']} poll_status={poll['payload']['status']})")
        else:
            print(f"user {uid} presence->poll: no poll found after {pu['ts']}")

    if latencies:
        print('\nStats:')
        print(f"min: {min(latencies):.1f} ms, max: {max(latencies):.1f} ms, avg: {sum(latencies)/len(latencies):.1f} ms, count: {len(latencies)}")
    else:
        print('No latencies calculated')

    # For disconnects, find next poll that shows 'offline'
    print('\nDisconnect -> Redis poll latencies (ms):')
    disc_latencies = []
    for d in disconnects:
        # find poll for each user
        # We don't have user_id in payload for disconnected event; attempt to infer from source name
        # source name is admin-1 or user-6
        uid = None
        try:
            uid = int(d['source'].split('-')[-1])
        except Exception:
            continue
        # find next poll that shows 'offline'
        found = None
        for p in redis_polls:
            if p['payload']['user_id']==uid and p['payload']['status']=='offline' and ts_to_dt(p['ts'])>=ts_to_dt(d['ts']):
                found = p
                break
        if found:
            delta = (ts_to_dt(found['ts']) - ts_to_dt(d['ts'])).total_seconds()*1000
            disc_latencies.append(delta)
            print(f"user {uid} disconnect->offline delta {delta:.1f} ms (disconnect ts={d['ts']} offline poll ts={found['ts']})")
        else:
            print(f"user {uid} disconnect->offline: no offline poll found after {d['ts']}")

    if disc_latencies:
        print('\nDisconnect stats:')
        print(f"min: {min(disc_latencies):.1f} ms, max: {max(disc_latencies):.1f} ms, avg: {sum(disc_latencies)/len(disc_latencies):.1f} ms, count: {len(disc_latencies)}")
    else:
        print('No disconnect latencies found')

if __name__=='__main__':
    main()
