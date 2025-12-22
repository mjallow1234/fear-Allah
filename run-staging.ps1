Write-Host "Starting staging environment..." -ForegroundColor Cyan

# Environment flags
$env:APP_ENV="staging"
$env:AUTOMATIONS_ENABLED="false"
$env:WS_ENABLED="false"
$env:PYTHONPATH="backend"

# Seed database (idempotent)
Write-Host "Seeding staging database..." -ForegroundColor Yellow
python backend/scripts/seed_staging.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Seeding failed. Fix errors above." -ForegroundColor Red
    exit 1
}

# Start backend
Write-Host "Starting backend at http://0.0.0.0:8000" -ForegroundColor Green
uvicorn app.main:app --host 0.0.0.0 --port 8000
