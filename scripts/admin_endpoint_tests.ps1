param(
    [string]$AdminToken = $Env:ADMIN_TOKEN,
    [string]$BaseUrl = 'http://127.0.0.1:8000'
)

function Write-Heading($text) {
    Write-Host "`n===== $text =====" -ForegroundColor Cyan
}

if (-not $AdminToken) {
    $AdminToken = Read-Host -Prompt 'Enter admin token (or set $Env:ADMIN_TOKEN)'
}

if (-not $AdminToken) {
    Write-Host 'Admin token required. Exiting.' -ForegroundColor Red
    exit 2
}

$headers = @{ Authorization = "Bearer $AdminToken" }

function Safe-InvokeRestMethod($Method, $Uri, $Body = $null) {
    Write-Host "\n--> $Method $Uri" -ForegroundColor Yellow
    if ($Body) {
        $jsonPayload = $Body | ConvertTo-Json -Depth 10
        Write-Host "Payload:`n$jsonPayload" -ForegroundColor DarkYellow
    }
    try {
        if ($Body) {
            $resp = Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -Body $jsonPayload -ContentType 'application/json'
        }
        else {
            $resp = Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -ContentType 'application/json'
        }
        $converted = $null
        try {
            $converted = $resp | ConvertTo-Json -Depth 10
        } catch {
            $converted = $resp.ToString()
        }
        Write-Host "<-- Status: Success" -ForegroundColor Green
        Write-Host "Response:`n$converted"
        return @{ ok = $true; resp = $resp }
    }
    catch {
        $err = $_.Exception.Response
        Write-Host "<-- Request failed: $($_.Exception.Message)" -ForegroundColor Red
        try {
            $stream = $err.GetResponseStream()
            $sr = New-Object System.IO.StreamReader($stream)
            $body = $sr.ReadToEnd()
            Write-Host "Response Body:`n$body" -ForegroundColor Red
        } catch {
            # no body
        }
        return @{ ok = $false; error = $_ }
    }
}

Write-Heading 'Admin Endpoint Tests Starting'

## 1) GET /api/admin/users
Write-Heading 'List users (GET /api/admin/users)'
$listUsersUrl = "$BaseUrl/api/admin/users"
$result = Safe-InvokeRestMethod -Method 'GET' -Uri $listUsersUrl
if ($result.ok) {
    # Print required fields
    $users = $result.resp.users
    if ($users) {
        $users | ForEach-Object {
            Write-Host "id:$($_.id) username:$($_.username) email:$($_.email) is_active:$($_.is_active) is_system_admin:$($_.is_system_admin)"
        }
    } else {
        Write-Host 'No users returned' -ForegroundColor Yellow
    }
}

## 2) GET /api/admin/stats
Write-Heading 'Admin stats (GET /api/admin/stats)'
$statsUrl = "$BaseUrl/api/admin/stats"
$result = Safe-InvokeRestMethod -Method 'GET' -Uri $statsUrl
if ($result.ok) {
    $obj = $result.resp | ConvertTo-Json -Depth 10
    Write-Host "Stats JSON:`n$obj"
}

## 3) Create a test user (POST /api/admin/users)
Write-Heading 'Create test user (POST /api/admin/users)'
$createUrl = "$BaseUrl/api/admin/users"
$createBody = @{ username = 'testuser2'; email = 'testuser2@example.com'; password = 'TestPass2025!'; display_name = 'Test User 2'; role = 'member' }
$result = Safe-InvokeRestMethod -Method 'POST' -Uri $createUrl -Body $createBody
$testUserId = $null
if ($result.ok) {
    $testUserId = $result.resp.id
    Write-Host "Created user id: $testUserId username: $($result.resp.username)" -ForegroundColor Green
}

## Continue testing even if some steps fail

## 4) Update the new user display_name (PUT)
if ($testUserId) {
    Write-Heading 'Update test user display_name (PUT /api/admin/users/{id})'
    $updateUrl = "$BaseUrl/api/admin/users/$testUserId"
    $updateBody = @{ display_name = 'Updated Test User 2' }
    $result = Safe-InvokeRestMethod -Method 'PUT' -Uri $updateUrl -Body $updateBody
    if ($result.ok) {
        # GET the user's details to confirm
        Write-Heading 'Fetch updated user (GET /api/admin/users/{id})'
        $getUserUrl = "$BaseUrl/api/admin/users/$testUserId"
        $g = Safe-InvokeRestMethod -Method 'GET' -Uri $getUserUrl
        if ($g.ok) {
            $ujson = $g.resp | ConvertTo-Json -Depth 10
            Write-Host "User details:`n$ujson"
        }
    }
} else {
    Write-Host "Skipping update as user creation failed" -ForegroundColor Yellow
}

## 5) Ban the user (POST /api/admin/users/{id}/ban) and verify
if ($testUserId) {
    Write-Heading 'Ban the test user (POST /api/admin/users/{id}/ban)'
    $banUrl = "$BaseUrl/api/admin/users/$testUserId/ban"
    $banBody = @{ reason = 'Testing ban via script' }
    $result = Safe-InvokeRestMethod -Method 'POST' -Uri $banUrl -Body $banBody
    if ($result.ok) {
        # Fetch user and verify is_banned/is_active status
        $getUserUrl = "$BaseUrl/api/admin/users/$testUserId"
        $g = Safe-InvokeRestMethod -Method 'GET' -Uri $getUserUrl
        if ($g.ok) {
            $u = $g.resp
            Write-Host "User banned? is_banned:$($u.is_banned) is_active:$($u.is_active)"
        }
    }
}

## 6) Unban the user (POST /api/admin/users/{id}/unban) and verify
if ($testUserId) {
    Write-Heading 'Unban the test user (POST /api/admin/users/{id}/unban)'
    $unbanUrl = "$BaseUrl/api/admin/users/$testUserId/unban"
    $result = Safe-InvokeRestMethod -Method 'POST' -Uri $unbanUrl
    if ($result.ok) {
        $getUserUrl = "$BaseUrl/api/admin/users/$testUserId"
        $g = Safe-InvokeRestMethod -Method 'GET' -Uri $getUserUrl
        if ($g.ok) {
            $u = $g.resp
            Write-Host "User banned? is_banned:$($u.is_banned) is_active:$($u.is_active)"
        }
    }
}

Write-Heading 'Admin Endpoint Tests Completed'
