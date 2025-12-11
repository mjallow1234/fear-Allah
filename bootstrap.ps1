# fear-Allah Bootstrap Script
# Run this to set up a local Kubernetes deployment

param(
    [switch]$Clean,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$ClusterName = "fear-allah"

Write-Host "=== fear-Allah Bootstrap ===" -ForegroundColor Cyan

# Clean up if requested
if ($Clean) {
    Write-Host "Cleaning up existing cluster..." -ForegroundColor Yellow
    kind delete cluster --name $ClusterName 2>$null
}

# Check if cluster exists
$existingCluster = kind get clusters 2>$null | Where-Object { $_ -eq $ClusterName }
if (-not $existingCluster) {
    Write-Host "Creating Kind cluster..." -ForegroundColor Green
    kind create cluster --config kind-config.yaml
} else {
    Write-Host "Cluster '$ClusterName' already exists" -ForegroundColor Yellow
}

# Set kubectl context
kubectl cluster-info --context kind-$ClusterName

# Build Docker images
if (-not $SkipBuild) {
    Write-Host "Building Docker images..." -ForegroundColor Green
    
    Write-Host "  Building backend..." -ForegroundColor Gray
    docker build -t fear-allah-backend:latest ./backend
    
    Write-Host "  Building frontend..." -ForegroundColor Gray
    docker build -t fear-allah-frontend:latest ./frontend
    
    Write-Host "Loading images into Kind..." -ForegroundColor Green
    kind load docker-image fear-allah-backend:latest --name $ClusterName
    kind load docker-image fear-allah-frontend:latest --name $ClusterName
}

# Install NGINX Ingress
Write-Host "Installing NGINX Ingress Controller..." -ForegroundColor Green
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
Write-Host "Waiting for Ingress controller..." -ForegroundColor Gray
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=120s

# Deploy application
Write-Host "Deploying application..." -ForegroundColor Green
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/postgres.yaml
kubectl apply -f deploy/k8s/redis.yaml
kubectl apply -f deploy/k8s/minio.yaml

Write-Host "Waiting for infrastructure..." -ForegroundColor Gray
Start-Sleep -Seconds 10

kubectl apply -f deploy/k8s/backend.yaml
kubectl apply -f deploy/k8s/frontend.yaml
kubectl apply -f deploy/k8s/ingress.yaml

# Wait for deployments
Write-Host "Waiting for deployments to be ready..." -ForegroundColor Gray
kubectl wait --namespace fear-allah --for=condition=available deployment/postgres --timeout=120s
kubectl wait --namespace fear-allah --for=condition=available deployment/redis --timeout=60s
kubectl wait --namespace fear-allah --for=condition=available deployment/backend --timeout=120s
kubectl wait --namespace fear-allah --for=condition=available deployment/frontend --timeout=120s

# Run migrations
Write-Host "Running database migrations..." -ForegroundColor Green
$backendPod = kubectl get pods -n fear-allah -l app=backend -o jsonpath="{.items[0].metadata.name}"
kubectl exec -n fear-allah $backendPod -- alembic upgrade head

# Display status
Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Cyan
Write-Host ""
kubectl get pods -n fear-allah

Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Green
Write-Host "  Frontend:    http://localhost" -ForegroundColor White
Write-Host "  Backend API: http://localhost/api" -ForegroundColor White
Write-Host "  Health:      http://localhost/health" -ForegroundColor White
Write-Host ""
