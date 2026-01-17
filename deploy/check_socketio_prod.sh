#!/usr/bin/env bash
set -euo pipefail

# Usage: ./deploy/check_socketio_prod.sh http://localhost:18002
BASE_URL=${1:-http://localhost:18002}

echo "1) Checking /api/teams (should be 401, 403, or 405, not 404)"
curl -i -s -S "$BASE_URL/api/teams" | sed -n '1,6p'

echo -e "\n2) Socket.IO websocket upgrade (expect HTTP/1.1 101 Switching Protocols)"
# Use a known-valid Sec-WebSocket-Key value
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==" \
  "$BASE_URL/socket.io/?EIO=4&transport=websocket" | sed -n '1,6p'

echo -e "\n3) Short poll check to socket.io polling endpoint (should return handshake JSON)"
curl -s "$BASE_URL/socket.io/?EIO=4&transport=polling" | sed -n '1,4p'

echo -e "\nDone. If the websocket handshake returns 101 and /api endpoints are not 404, config is correct."