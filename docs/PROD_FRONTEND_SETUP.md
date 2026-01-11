Production frontend serving (chosen mode: static build served by nginx via `api-proxy`)

Final request flow (PROD mode):

browser -> app.sidrahsalaam.com -> api-proxy (nginx) -> serves static files from /usr/share/nginx/html (mounted from ./frontend/dist)

Notes & deployment steps

1) Build frontend locally or in CI to produce `frontend/dist`:

   cd frontend
   npm ci
   npm run build

2) Ensure `frontend/dist` is present and up-to-date (commit or pipeline artifact) and then deploy the stack.

3) Start services (from repo root):

   docker compose down -v
   docker compose up -d --build api-proxy backend postgres redis minio

   - `api-proxy` will serve static SPA from `./frontend/dist` (mounted read-only).
   - `backend` serves API and WebSockets on the internal Docker network.

4) Verify endpoints:
   - http://app.sidrahsalaam.com/ should return the SPA (index.html) — **nginx must not return default welcome page**.
   - API routes begin with `/api/` and are proxied to backend.
   - WebSocket endpoints (`/socket.io/` and `/ws`) are proxied to backend.

DEV mode note (alternative):
- If you need Vite dev server instead (developer workflows), revert the change to `docker-compose.override.yml` to restore the `frontend` service that runs Vite on port 5173 and proxy `/` to it.

Why PROD mode chosen
- Deterministic, fast, and does not rely on running a dev server in production/staging.
- Simpler to reason about for smoke tests and initial-setup flows.

Safety
- `api-proxy.conf` uses `try_files $uri $uri/ /index.html` to ensure SPA fallback for client-side routes.
- `server_name` is set to `app.sidrahsalaam.com` so nginx will not respond with a generic default page when served under the expected host.
