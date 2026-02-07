# fear-Allah

A real-time team chat application built with modern technologies.

## 🚧 Current Focus

Orders & Tasks are frozen as of tag `v0.3-orders-stable`.

Active work areas:
1. Chats (real-time messaging, reliability, UX)
2. Users & Roles (management, permissions, auditability)

Sales & finance modules will be addressed AFTER chat stability.

## Project Structure

```
fear-Allah/
├── backend/          # FastAPI backend
├── frontend/         # React + TypeScript frontend
├── deploy/           # Deployment configs (Helm, K8s)
├── docs/             # Documentation
└── tests/            # E2E and integration tests
```

## Tech Stack

- **Frontend**: React, TypeScript, Vite
- **Backend**: FastAPI, Python 3.11
- **Database**: PostgreSQL
- **Cache/Presence**: Redis
- **File Storage**: MinIO
- **Deployment**: Kubernetes, Helm, Kind

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker & Docker Compose
- Kind (for local Kubernetes)

### Development

```bash
# Frontend (local dev)
cd frontend && npm install && npm run dev

# Backend (local dev)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
```

### Local Docker Compose

Bring up a local stack (Postgres, Redis, MinIO, backend, frontend):

```powershell
docker compose up --build -d
# view logs
docker compose logs -f
# stop
docker compose down

### Development (fast feedback)

Option A — Run everything in containers (frontend built/static):

```powershell
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d
```

Option B — Run frontend locally (fast HMR) and use the compose stack for backend/services:

1. Start the compose stack (backend, Postgres, Redis, MinIO, and an API proxy):

```powershell
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d
```

2. Run the frontend dev server locally (PowerShell):

```powershell
cd frontend
$env:VITE_API_URL = 'http://localhost:18002'
npm ci
npm run dev -- --host 0.0.0.0
```

`VITE_API_URL` points the local Vite dev server to the API proxy at `http://localhost:18002`.

This keeps the backend internal to the compose network; the `api-proxy` service exposes the API on `localhost:18002` for local frontend development.

Note: for security the chat WebSocket requires an auth token in production. For local development (`DEBUG=true`) the backend will auto-join users to channels on WebSocket connect to make iterating easier.
```

Notes:
- Frontend is exposed on http://localhost:5173 (nginx in the frontend container)
- Backend is exposed on http://localhost:8000
- MinIO console is available on http://localhost:9001 (user: `minioadmin`, pass: `minioadmin`)
- Healthchecks are included; services may take a few seconds to become ready

## License

MIT
