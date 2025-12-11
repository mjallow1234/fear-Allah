# fear-Allah API Documentation

## Base URL
- Local: \http://localhost:8000\
- Production: \http://localhost/api\

## Authentication

### Register
\\\http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword",
  "username": "username"
}
\\\

**Response:**
\\\json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "username",
  "created_at": "2024-01-01T00:00:00Z"
}
\\\

### Login
\\\http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword"
}
\\\

**Response:**
\\\json
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
\\\

## Teams

### Create Team
\\\http
POST /api/teams
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "My Team",
  "description": "Team description"
}
\\\

### List Teams
\\\http
GET /api/teams
Authorization: Bearer <token>
\\\

### Get Team
\\\http
GET /api/teams/{team_id}
Authorization: Bearer <token>
\\\

## Channels

### Create Channel
\\\http
POST /api/channels
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "general",
  "team_id": "team_uuid",
  "is_private": false
}
\\\

### List Channels
\\\http
GET /api/channels?team_id={team_id}
Authorization: Bearer <token>
\\\

## Messages

### Send Message
\\\http
POST /api/messages
Authorization: Bearer <token>
Content-Type: application/json

{
  "content": "Hello, World!",
  "channel_id": "channel_uuid"
}
\\\

### Get Channel Messages
\\\http
GET /api/messages?channel_id={channel_id}&limit=50
Authorization: Bearer <token>
\\\

## WebSocket

### Connect
\\\javascript
const ws = new WebSocket('ws://localhost:8000/ws?token=<jwt_token>');
\\\

### Message Types

**Incoming:**
\\\json
{
  "type": "message",
  "data": {
    "id": "uuid",
    "content": "Hello!",
    "user_id": "uuid",
    "channel_id": "uuid",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
\\\

**Outgoing:**
\\\json
{
  "type": "message",
  "channel_id": "uuid",
  "content": "Hello!"
}
\\\
"@ | Set-Content "C:\Users\Razerr\fear-Allah\docs\API.md"
@"
# fear-Allah Deployment Guide

## Prerequisites
- Docker Desktop
- Kind (Kubernetes in Docker)
- kubectl
- Helm (optional)

## Quick Start with Kind

### 1. Create Kind Cluster
\\\ash
kind create cluster --config kind-config.yaml
\\\

### 2. Build Docker Images
\\\ash
# Backend
docker build -t fear-allah-backend:latest ./backend

# Frontend
docker build -t fear-allah-frontend:latest ./frontend
\\\

### 3. Load Images into Kind
\\\ash
kind load docker-image fear-allah-backend:latest --name fear-allah
kind load docker-image fear-allah-frontend:latest --name fear-allah
\\\

### 4. Install NGINX Ingress Controller
\\\ash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s
\\\

### 5. Deploy Application
\\\ash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/postgres.yaml
kubectl apply -f deploy/k8s/redis.yaml
kubectl apply -f deploy/k8s/minio.yaml
kubectl apply -f deploy/k8s/backend.yaml
kubectl apply -f deploy/k8s/frontend.yaml
kubectl apply -f deploy/k8s/ingress.yaml
\\\

### 6. Verify Deployment
\\\ash
kubectl get pods -n fear-allah
kubectl get svc -n fear-allah
\\\

### 7. Access Application
- Frontend: http://localhost
- Backend API: http://localhost/api
- MinIO Console: http://localhost:9001

## Using Helm (Alternative)

### Deploy Infrastructure
\\\ash
helm install infra ./deploy/helm/infrastructure -n fear-allah --create-namespace
\\\

### Deploy Backend
\\\ash
helm install backend ./deploy/helm/backend -n fear-allah
\\\

### Deploy Frontend
\\\ash
helm install frontend ./deploy/helm/frontend -n fear-allah
\\\

## Database Migrations

### Run migrations inside the cluster
\\\ash
kubectl exec -it deployment/backend -n fear-allah -- alembic upgrade head
\\\

## Troubleshooting

### View logs
\\\ash
kubectl logs -f deployment/backend -n fear-allah
kubectl logs -f deployment/frontend -n fear-allah
\\\

### Check pod status
\\\ash
kubectl describe pod <pod-name> -n fear-allah
\\\

### Restart deployment
\\\ash
kubectl rollout restart deployment/backend -n fear-allah
\\\
"@ | Set-Content "C:\Users\Razerr\fear-Allah\docs\DEPLOYMENT.md"
@"
# fear-Allah Architecture

## Overview

fear-Allah is a real-time team chat application built with a modern microservices architecture.

## Tech Stack

### Frontend
- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **React Router 6** - Routing
- **Zustand** - State management
- **React Query** - Server state
- **Axios** - HTTP client

### Backend
- **FastAPI** - Python web framework
- **SQLAlchemy 2.0** - ORM with async support
- **Alembic** - Database migrations
- **Pydantic** - Data validation
- **python-jose** - JWT handling
- **passlib** - Password hashing
- **WebSockets** - Real-time communication

### Database & Storage
- **PostgreSQL 15** - Primary database
- **Redis 7** - Caching & pub/sub
- **MinIO** - Object storage (S3-compatible)

### Infrastructure
- **Docker** - Containerization
- **Kubernetes** - Orchestration
- **Kind** - Local K8s cluster
- **Helm** - K8s package manager
- **NGINX Ingress** - Load balancing

## Project Structure

\\\
fear-Allah/
 backend/
    app/
       api/          # API routes
       core/         # Config, security, redis
       db/           # Database models & connection
       storage/      # MinIO file storage
    alembic/          # Database migrations
    tests/            # Backend tests
 frontend/
    src/
        components/   # Reusable UI components
        pages/        # Page components
        layouts/      # Layout components
        stores/       # Zustand stores
        services/     # API services
 deploy/
    k8s/             # Kubernetes manifests
    helm/            # Helm charts
 tests/
    e2e/             # Playwright E2E tests
    unit/            # Additional unit tests
 docs/                 # Documentation
\\\

## Data Flow

\\\
          
    Frontend        NGINX Ingress      Backend     
    (React)                           (FastAPI)    
          
                                                         
                        
                                                                                        
                                                                                        
                                           
                  PostgreSQL                        Redis                          MinIO      
                  (Database)                      (Cache/PS)                     (Storage)    
                                           
\\\

## Authentication Flow

1. User submits credentials to \/api/auth/login\
2. Backend validates credentials against PostgreSQL
3. JWT token generated and returned
4. Frontend stores token in memory/localStorage
5. Token included in Authorization header for subsequent requests
6. WebSocket connections authenticated via query parameter

## Real-time Messaging

1. Client connects to WebSocket at \/ws?token=<jwt>\
2. Backend authenticates and adds to connection manager
3. Messages sent via WebSocket are:
   - Persisted to PostgreSQL
   - Published to Redis pub/sub
   - Broadcast to connected clients in same channel
