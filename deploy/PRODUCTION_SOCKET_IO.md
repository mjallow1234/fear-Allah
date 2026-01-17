# Production Socket.IO / WebSocket checklist 🔧

This document provides the minimal, authoritative guidance to deploy the nginx configuration changes required to reliably proxy Socket.IO and to strip `/api` for REST calls.

Important goals
- Frontend calls: `/api/*` (must be stripped before forwarding to backend)
- Backend routes: `/...` (no `/api` in definitions)
- Socket.IO: must upgrade over HTTP/1.1 and must not be nested inside `/api` or blocked by HTTP/2

Suggested nginx snippets (apply only if your production nginx is managed from this repo):

1) Authoritative `/api` location (strip `/api` prefix)

```nginx
location ^~ /api/ {
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # IMPORTANT: trailing slash ensures /api prefix is removed when forwarding
    proxy_pass http://backend:8000/;
}
```

2) Authoritative `/socket.io/` location (force HTTP/1.1, preserve upgrade headers)

```nginx
location ^~ /socket.io/ {
    proxy_http_version 1.1;

    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_read_timeout 86400;
    proxy_send_timeout 86400;

    proxy_buffering off;
    proxy_cache off;

    proxy_pass http://backend:8000;
}
```

Do NOT:
- Add `/socket.io/` inside `/api` (should be a sibling block, ordered after `/api` if needed)
- Add a trailing slash to the `/socket.io` `proxy_pass`
- Use variables (e.g., `$upstream_backend`) in the `/socket.io/` block (avoid subtle header rewrite issues)
- Enable `http2` in the `listen` directive (disable or omit `http2` where TLS is terminated)

Production verification checklist
1. Deploy config changes (create a PR, have infra review, then apply on staging). ✅
2. Recreate nginx / proxy container/process (no backend rebuild required). ✅
3. Run the verification script `deploy/check_socketio_prod.sh` against the staging or production domain. ✅
4. Confirm `curl` WebSocket handshake returns `HTTP/1.1 101 Switching Protocols`.
5. Confirm `curl -i http://<host>/api/teams` returns `401` (auth required) or `405` where applicable — not `404`.

Notes for operators / CDNs / Load Balancers
- If you have an external CDN or Load Balancer (e.g., Cloudflare, AWS ALB, GCP LB):
  - Confirm it supports WebSocket upgrades and is configured to preserve `Upgrade` / `Connection` headers.
  - If the CDN terminates TLS and speaks HTTP/2 to nginx, ensure the path that reaches the backend uses `proxy_http_version 1.1` and preserves headers, or change the CDN/LB to use HTTP/1.1 or pass-through behavior for websocket paths.
  - Consider sticky sessions or use the Socket.IO adapter (Redis) if you run multiple backend replicas to ensure polling → upgrade affinity.

Rollback / quick revert
- Revert the nginx change and reload the proxy (or redeploy previous container image):
  - `git revert <commit>` (or restore previous config file) → `docker compose up -d --force-recreate api-proxy`

If you'd like, I can open a PR branch with these changes and include the `check_socketio_prod.sh` script to automate the verification steps.
