# fear-Allah Deployment Guide

## Prerequisites
- Docker Desktop
- Kind (Kubernetes in Docker)
- kubectl
- Helm (optional)

## Quick Start with Kind

### 1. Create Kind Cluster
```bash
kind create cluster --config kind-config.yaml
```

### 2. Build Docker Images
```bash
# Backend
# Build and push to GHCR (recommended)
docker build -t ghcr.io/<OWNER>/fearallah-backend:latest ./backend
docker push ghcr.io/<OWNER>/fearallah-backend:latest

# Local development (kind): keep the local image name as-is and use kind to load
docker build -t fear-allah-backend:latest ./backend

# Frontend
docker build -t fear-allah-frontend:latest ./frontend
```

### 3. Load Images into Kind
```bash
	# For local kind clusters, load the local image into the cluster
	kind load docker-image fear-allah-backend:latest --name fear-allah
kind load docker-image fear-allah-frontend:latest --name fear-allah
```

### 4. Install NGINX Ingress Controller
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s
```

### 5. Deploy Application
```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/postgres.yaml
kubectl apply -f deploy/k8s/redis.yaml
kubectl apply -f deploy/k8s/minio.yaml
kubectl apply -f deploy/k8s/backend.yaml
kubectl apply -f deploy/k8s/frontend.yaml
kubectl apply -f deploy/k8s/ingress.yaml
```

### 6. Verify Deployment
```bash
kubectl get pods -n fear-allah
kubectl get svc -n fear-allah
```

### 7. Access Application
- Frontend: http://localhost
- Backend API: http://localhost/api
- MinIO Console: http://localhost:9001

## Using the Bootstrap Script
```powershell
.\bootstrap.ps1           # Normal deployment
.\bootstrap.ps1 -Clean    # Clean rebuild
.\bootstrap.ps1 -SkipBuild # Skip Docker build
```

## Database Migrations
```bash
kubectl exec -it deployment/backend -n fear-allah -- alembic upgrade head
```

## Troubleshooting

### View logs
```bash
kubectl logs -f deployment/backend -n fear-allah
kubectl logs -f deployment/frontend -n fear-allah
```

### Restart deployment
```bash
kubectl rollout restart deployment/backend -n fear-allah
```
