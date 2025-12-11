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
# Frontend
cd frontend && npm install && npm run dev

# Backend
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
```

## License

MIT
