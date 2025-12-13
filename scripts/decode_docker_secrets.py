#!/usr/bin/env python3
import json, base64, subprocess

for s in ['ghcr-secret', 'ghcr-pull-secret']:
    try:
        out = subprocess.check_output(['kubectl', '-n', 'fear-allah', 'get', 'secret', s, '-o', 'json'])
    except subprocess.CalledProcessError:
        print('Secret not found:', s)
        continue
    js = json.loads(out)
    dot = js['data'].get('.dockerconfigjson')
    if dot:
        decoded = base64.b64decode(dot).decode('utf-8')
        print('Secret:', s)
        print(decoded)
        print('---')
    else:
        print('Secret', s, 'has no .dockerconfigjson')
