# fear-Allah

A real-time team chat application built with modern technologies.

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

Use the override file to run the frontend in dev mode (Vite) and the backend in dev mode (uvicorn with reload):

```powershell
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build
```

This mounts your local `frontend/` and `backend/` directories into the containers so changes apply immediately.
```

Notes:
- Frontend is exposed on http://localhost:5173 (nginx in the frontend container)
- Backend is exposed on http://localhost:8000
- MinIO console is available on http://localhost:9001 (user: `minioadmin`, pass: `minioadmin`)
- Healthchecks are included; services may take a few seconds to become ready

## License

MIT
