# Staging Deployment Playbook

This document describes a simple, safe, provider-agnostic playbook to deploy a staging environment for fear-Allah.

## Goals
- Staging is safe by default (no WebSockets, no automations enabled)
- Repeatable and testable
- Health and readiness checks available for load balancers

## Environment variables (.env.staging)

Example `.env.staging` (place in repo root on the server):

```
APP_ENV=staging
DEBUG=false

API_BASE_URL=https://staging.yourdomain.com
FRONTEND_URL=https://staging.yourdomain.com

JWT_SECRET=change-this-long-secret
JWT_EXPIRES_MINUTES=60

DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/fear_allah
REDIS_URL=redis://redis:6379/0

WS_ENABLED=false
AUTOMATIONS_ENABLED=false

LOG_LEVEL=info
```

## docker-compose.staging.yml (example)

Use `docker compose -f docker-compose.staging.yml up -d --build` to start services.

```yaml
version: "3.9"
services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    env_file: .env.staging
    depends_on:
      - postgres
      - redis
    restart: always

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: fear_allah
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7
    restart: always

volumes:
  pgdata:
```

## Sequence (exact order)
1. Clone repository and checkout `main`
2. Start services: `docker compose -f docker-compose.staging.yml up -d --build`
3. Run migrations: `docker compose exec backend alembic upgrade head`
4. Seed staging (safe only in staging): `docker compose exec backend python backend/scripts/seed_staging.py`
5. Verify health:
   - `curl https://staging.yourdomain.com/healthz` → `{"status":"ok"}`
   - `curl https://staging.yourdomain.com/readyz` → `{"status":"ready"}`

## Nginx (reverse proxy)
Route traffic to the backend (example):

```
server {
  server_name staging.yourdomain.com;
  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
  }
}
```

## SSL
Use Certbot: `sudo certbot --nginx -d staging.yourdomain.com`

## Rollback
If something is wrong:
```
docker compose down
git checkout <last-known-good-commit>
docker compose up -d --build
```

## Notes
- The staging playbook is intentionally conservative: WebSockets and Automations must be explicitly enabled (they are disabled by default in staging). Use the seed script to populate demo data so teams can test U3.3/U3.4 features safely.
