# Reset admin password script
# Usage: Run in PowerShell where kubectl and python are available.
# This script:
# - Generates a bcrypt hash for SidraPass2025! using local Python + passlib
# - Escapes $ characters for PowerShell/Postgres
# - Updates the admin user's hashed_password in the Postgres pod
# - Verifies the update and optionally performs a test login

Set-StrictMode -Version Latest

# --- Helper: find python executable ---
$python = $null
$cmd = Get-Command python -ErrorAction SilentlyContinue
if ($cmd) { $python = $cmd.Source }
else {
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source }
}

if (-not $python) {
    Write-Host "ERROR: Python not found in PATH. Install Python before running this script." -ForegroundColor Red
    exit 1
}
Write-Host "Using Python executable: $python"

# --- Create temporary Python script to generate bcrypt hash using passlib ---
$tmpPy = Join-Path $env:TEMP ("gen_pass_{0}.py" -f ([System.Guid]::NewGuid().ToString()))
$pyCode = @'
from passlib.hash import bcrypt
print(bcrypt.hash("SidraPass2025!"))
'@
Set-Content -Path $tmpPy -Value $pyCode -Encoding UTF8
Write-Host "Wrote temporary Python script: $tmpPy"

# --- Try to run the script. If passlib missing, attempt pip install then retry. ---
function Run-GenHash {
    param($pyExe, $script)
    Write-Host "Running: $pyExe $script"
    $out = & $pyExe $script 2>&1
    return ,$out
}

$hashOutput = Run-GenHash -pyExe $python -script $tmpPy
$hashText = ($hashOutput | Where-Object { $_ -and $_ -match '\$2[abxy]\$' } | Select-Object -First 1)

if (-not $hashText) {
    Write-Host "passlib not available or hash not produced. Attempting to install passlib[bcrypt] locally for the current python..." -ForegroundColor Yellow
    Write-Host "Running: $python -m pip install --user 'passlib[bcrypt]'"
    & $python -m pip install --user 'passlib[bcrypt]' 2>&1 | ForEach-Object { Write-Host $_ }

    Write-Host "Retrying hash generation..."
    $hashOutput = Run-GenHash -pyExe $python -script $tmpPy
    $hashText = ($hashOutput | Where-Object { $_ -and $_ -match '\$2[abxy]\$' } | Select-Object -First 1)
}

Write-Host "Python output (raw):"
$hashOutput | ForEach-Object { Write-Host $_ }

if (-not $hashText) {
    Write-Host "ERROR: Could not generate bcrypt hash. Aborting to avoid corrupting DB." -ForegroundColor Red
    Remove-Item -Path $tmpPy -ErrorAction SilentlyContinue
    exit 1
}

$HASH = $hashText.Trim()
Write-Host "Parsed bcrypt hash: $HASH"

# Escape $ for embedding in PowerShell double-quoted strings
$safeHash = $HASH -replace '\$', '`$'
Write-Host "Escaped hash for PowerShell/psql embedding: $safeHash"

# --- Find postgres pod ---
Write-Host "Finding Postgres pod..."
$pg = kubectl -n fear-allah get pod -l app=postgres -o jsonpath="{.items[0].metadata.name}" 2>&1
if (-not $pg) { Write-Host "ERROR: Could not find postgres pod" -ForegroundColor Red; exit 1 }
Write-Host "POSTGRES POD: $pg"

# --- Determine DB name ---
Write-Host "Querying available databases to select DB name..."
$dbs = kubectl -n fear-allah exec -it $pg -- psql -U postgres -tAc "SELECT datname FROM pg_database;" 2>&1
Write-Host "Databases returned:"; $dbs | ForEach-Object { Write-Host $_ }

if ($dbs -match 'fearallah') { $DBNAME = 'fearallah' }
elseif ($dbs -match 'fear_allah_db') { $DBNAME = 'fear_allah_db' }
else { $DBNAME = 'fearallah' }
Write-Host "Selected database name: $DBNAME"

# --- Update the admin password in DB ---
$updateCmd = "UPDATE users SET hashed_password='$safeHash' WHERE email='admin@fearallah.com';"
Write-Host "About to run UPDATE with command:"; Write-Host $updateCmd

Write-Host "Executing kubectl exec to run UPDATE on Postgres pod..."
$updOut = kubectl -n fear-allah exec -it $pg -- psql -U postgres -d $DBNAME -c "$updateCmd" 2>&1
Write-Host "Update output:"; $updOut | ForEach-Object { Write-Host $_ }

# --- Verify the admin row ---
$selectCmd = "SELECT id, username, email, is_active, is_system_admin, hashed_password FROM users WHERE email='admin@fearallah.com';"
Write-Host "Verifying admin row with:"; Write-Host $selectCmd
$verifyOut = kubectl -n fear-allah exec -it $pg -- psql -U postgres -d $DBNAME -c "$selectCmd" 2>&1
Write-Host "Verification output:"; $verifyOut | ForEach-Object { Write-Host $_ }

# --- Optional: Test login via curl ---
Write-Host "Attempting test login (may require local port-forward to be active)"
Write-Host "Command: curl.exe -s -X POST http://127.0.0.1:8000/api/auth/login -H \"Content-Type: application/json\" -d '{\"email\":\"admin@fearallah.com\",\"password\":\"SidraPass2025!\"}'"
$admLogin = curl.exe -s -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"email":"admin@fearallah.com","password":"SidraPass2025!"}' 2>&1
Write-Host "Login response:"; $admLogin | ForEach-Object { Write-Host $_ }

# --- Cleanup ---
Remove-Item -Path $tmpPy -ErrorAction SilentlyContinue
Write-Host "Done."