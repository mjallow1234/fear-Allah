#!/usr/bin/env bash
set -e

BASE_URL=${BASE_URL:-http://127.0.0.1:8000}

echo "🔍 Health check"
curl -f "$BASE_URL/health"

echo "🔐 Register"
# deterministic register; will fail if user exists
curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke2@example.com","password":"Pass123!","username":"smoke2"}' \
  | jq -e '.access_token' >/dev/null

echo "✅ Smoke tests passed"
