#!/usr/bin/env python3
import json
import subprocess
import sys

ns = 'fear-allah'
name = 'backend-fear-allah-backend'
secret_name = 'ghcr-secret'

try:
    dep_json = subprocess.check_output(['kubectl', '-n', ns, 'get', 'deployment', name, '-o', 'json'])
except subprocess.CalledProcessError as e:
    print('Failed to get deployment:', e, file=sys.stderr)
    sys.exit(1)

dep = json.loads(dep_json)

# Replace imagePullSecrets with only the requested secret
dep['spec']['template']['spec']['imagePullSecrets'] = [{'name': secret_name}]

# Apply updated deployment
proc = subprocess.run(['kubectl', '-n', ns, 'apply', '-f', '-'], input=json.dumps(dep), text=True, capture_output=True)
if proc.returncode != 0:
    print('kubectl apply failed:', proc.stderr, file=sys.stderr)
    sys.exit(proc.returncode)

print(proc.stdout)
