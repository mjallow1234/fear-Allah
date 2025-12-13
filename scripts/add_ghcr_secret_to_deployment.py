#!/usr/bin/env python3
import json
import subprocess
import sys

ns = 'fear-allah'
name = 'backend-fear-allah-backend'

try:
    dep_json = subprocess.check_output(['kubectl', '-n', ns, 'get', 'deployment', name, '-o', 'json'])
except subprocess.CalledProcessError as e:
    print('Failed to get deployment:', e, file=sys.stderr)
    sys.exit(1)

dep = json.loads(dep_json)

secrets = dep['spec']['template']['spec'].get('imagePullSecrets', [])

if not any(s.get('name') == 'ghcr-secret' for s in secrets):
    secrets.append({'name': 'ghcr-secret'})
else:
    print('ghcr-secret already present')

dep['spec']['template']['spec']['imagePullSecrets'] = secrets

sys.stdout.write(json.dumps(dep))
