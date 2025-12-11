# WebSocket Security Improvements — Token-Based Authentication

Summary of changes:
- WebSocket chat and presence endpoints now rely solely on the JWT token to identify and authenticate users.
- Client-provided parameters `user_id` and `username` in query strings are no longer accepted for identity assertion.
- The server rejects websocket connections if token is invalid or missing.
- Temporary debug prints used during testing were removed from the codebase.
  - Historical debug traces were archived from `scripts/` to `scripts/archive/` to keep the repo tidy.

Why this matters:
- Uses server-verified token to prevent client impersonation.
- Enforces server-side identity assertions to ensure message author IDs always match the authenticated user and prevent foreign-key violations due to user-controlled params.

Implementation details:
- `backend/app/api/ws.py`:
  - `websocket_chat` now decodes JWT token from `token` query param and extracts `sub` (user_id) + `username` from it server-side.
  - `websocket_presence` now decodes JWT token only; `user_id` and `username` are not accepted from client-provided query params.
  - If the token is invalid or missing, the server rejects the connection (`await websocket.close(code=4403)`).
  - All message insertions now use `author_id` derived from the token.

- `scripts/` updates: example test scripts were modified to use token-only WS URIs. See `scripts/` for example code.

Deployment:
- Rebuild backend and redeploy with secure image tag: `ghcr.io/<OWNER>/fearallah-backend:secure-ws`.

Validation:
- Run the updated presence & chat timeline tests (scripts/presence_timeline_test.py) to verify:
  - No FK errors on message insertions.
  - No ability for client to impersonate another user via query params.
  - Presence TTLs and `user:<id>` keys behave as previously measured.

Notes:
- For additional security, consider: refresh token validation, rotation, and checking token expiration in the WS handshake path.
 - Archived files: historical debug logs (e.g., `backend_presence_debug_tail.log`) were moved to `scripts/archive/` and are no longer present in `scripts/` to avoid accidental re-introduction.
