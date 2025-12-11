Write-Host "=== SidraChat Smoke Test ===" -ForegroundColor Cyan

# 1. Backend health
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1/api/health" -UseBasicParsing
    $json = $health.Content | ConvertFrom-Json
    Write-Host "✅ Backend health: $($json.status)"
    Write-Host "   Database: $($json.services.database.status)"
    Write-Host "   Redis: $($json.services.redis.status)"
    Write-Host "   Storage: $($json.services.storage.status)"
} catch {
    Write-Host "❌ Backend health check failed" -ForegroundColor Red
}

# 2. Login as seeded admin
$body = @{identifier='admin@sidrachat.com'; password='admin123'} | ConvertTo-Json
try {
    $login = Invoke-WebRequest -Uri "http://127.0.0.1/api/auth/login" -Method POST -Body $body -ContentType "application/json"
    $token = ($login.Content | ConvertFrom-Json).access_token
    Write-Host "✅ Login successful, token acquired"
} catch {
    Write-Host "❌ Login failed" -ForegroundColor Red
}

# 3. List teams
$headers = @{Authorization = "Bearer $token"}
try {
    $teams = Invoke-WebRequest -Uri "http://127.0.0.1/api/teams" -Headers $headers -UseBasicParsing
    Write-Host "✅ Teams: $($teams.Content)"
} catch {
    Write-Host "❌ Failed to list teams" -ForegroundColor Red
}

# 4. Send a message to 'general' channel (id=1 assumed from seed)
$body = @{content="Hello from smoke test!"} | ConvertTo-Json
try {
    $msg = Invoke-WebRequest -Uri "http://127.0.0.1/api/channels/1/messages" -Method POST -Headers $headers -Body $body -ContentType "application/json"
    Write-Host "✅ Message sent: $($msg.Content)"
} catch {
    Write-Host "❌ Failed to send message" -ForegroundColor Red
}

Write-Host "=== Smoke Test Complete ===" -ForegroundColor Cyan