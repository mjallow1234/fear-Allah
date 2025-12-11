# One-shot Copilot script to verify backend GHCR deployment
param(
    [string]$namespace = "fear-allah",
    [string]$deployment = "backend",
    [string]$owner = "mjallow1234",
    [string]$imageName = "fearallah-backend",
    [string]$tag = "latest"
)

$imageRef = "ghcr.io/${owner}/${imageName}:${tag}"

Write-Host "=== 1. Check GHCR pull secret ==="
kubectl -n $namespace get secret | Select-String "ghcr-pull-secret"
if ($?) { Write-Host "GHCR pull secret exists" } else { Write-Warning "GHCR pull secret not found!" }

Write-Host "`n=== 2. Delete failed backend pods (if any) ==="
$failedPods = kubectl -n $namespace get pods -l app=$deployment -o jsonpath='{.items[?(@.status.phase=="Failed")].metadata.name}' -split ' '
foreach ($pod in $failedPods) {
    Write-Host "Deleting failed pod: $pod"
    kubectl -n $namespace delete pod $pod
}

Write-Host "`n=== 3. Wait for backend pods to be Running ==="
while ($true) {
    $statuses = kubectl -n $namespace get pods -l app=$deployment -o jsonpath='{.items[*].status.phase}' -split ' '
    if ($statuses -contains "Pending" -or $statuses -contains "ContainerCreating" -or $statuses -contains "Unknown") {
        Write-Host "Waiting for pods to be Ready..."
        Start-Sleep -Seconds 5
    } elseif ($statuses -contains "Running") {
        $allRunning = $true
        foreach ($status in $statuses) { if ($status -ne "Running") { $allRunning = $false } }
        if ($allRunning) { break }
        Start-Sleep -Seconds 3
    } else {
        break
    }
}
Write-Host "All backend pods are Running"

Write-Host "`n=== 4. Check deployment image ==="
$deploymentImage = kubectl -n $namespace get deployment $deployment -o jsonpath='{.spec.template.spec.containers[0].image}'
Write-Host "Deployment image: $deploymentImage"
if ($deploymentImage -ne $imageRef) { Write-Warning "Deployment image does NOT match expected GHCR image ($imageRef)" } else { Write-Host "Deployment image OK" }

Write-Host "`n=== 5. Test pull GHCR image (dry run) ==="
try {
    kubectl -n $namespace run testpull --image=$imageRef --restart=Never --rm -it
    Write-Host "GHCR pull succeeded"
} catch {
    Write-Warning "GHCR pull failed"
}

Write-Host "`n=== 6. Show backend pod logs ==="
$pods = kubectl -n $namespace get pods -l app=$deployment -o jsonpath='{.items[*].metadata.name}' -split ' '
foreach ($pod in $pods) {
    Write-Host "`n--- Logs for pod $pod ---"
    kubectl -n $namespace logs $pod --tail=50
}

Write-Host "`n✅ Backend GHCR validation complete"

# How to execute
# Save as verify_backend_ghcr.ps1 and run
# .\verify_backend_ghcr.ps1

# Or override defaults
# .\verify_backend_ghcr.ps1 -namespace fear-allah -deployment backend -owner mjallow1234 -imageName fearallah-backend -tag latest
