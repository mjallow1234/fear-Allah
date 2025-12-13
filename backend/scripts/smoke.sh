#!/usr/bin/env bash
set -e

BASE_URL=${BASE_URL:-http://127.0.0.1:8000}

echo "🔍 Health check"
curl -f "$BASE_URL/health"

echo "🔐 Register"
# deterministic register; will fail if user exists
RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke2@example.com","password":"Pass123!","username":"smoke2"}')

if command -v jq >/dev/null 2>&1; then
  echo "$RESPONSE" | jq -e '.access_token' >/dev/null
else
  # Fallback using python to parse JSON and ensure access_token exists
  python - <<PYTHON_SCRIPT
import json,sys
r=json.loads(sys.stdin.read())
if 'access_token' not in r:
    sys.exit(1)
print('ok')
PYTHON_SCRIPT <<EOF
$RESPONSE
EOF
fi

echo "✅ Smoke tests passed"
