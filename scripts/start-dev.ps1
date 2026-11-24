param(
    [string]$HostAddr = "127.0.0.1",
    [int]$Port = 8001,
    [string]$DatabaseMode = "test",
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Uvicorn = Join-Path $Root ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtualenv Python not found at $VenvPython"
    exit 1
}

$portInUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Error "Port $Port is already in use. Stop the existing process or choose another port."
    exit 1
}

if (-not $env:POLARIS_PG_DSN) {
    if ($DatabaseMode -eq "test") {
        $env:POLARIS_PG_DSN = "postgresql://polaris:polaris@127.0.0.1:5433/polaris_test"
    } else {
        $env:POLARIS_PG_DSN = "postgresql://polaris:polaris@127.0.0.1:5433/polaris"
    }
}

$env:PYTHONPATH = Join-Path $Root "src"

Write-Host "[POLARIS] Running controlled database migrations ($DatabaseMode)..."
& $VenvPython -c "from polaris_server.db import run_migrations; run_migrations()"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Database migration failed. Verify PostgreSQL is running on port 5433."
    exit 1
}

Write-Host "[POLARIS] Building frontend..."
npm --prefix (Join-Path $Root "web") run build
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend build failed."
    exit 1
}

Write-Host "[POLARIS] Starting POLARIS Server at http://${HostAddr}:${Port} ..."
$proc = Start-Process -FilePath $Uvicorn -ArgumentList "polaris_server.api:app", "--host", $HostAddr, "--port", "$Port" -PassThru -NoNewWindow

$ready = $false
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) {
        Write-Error "POLARIS Server exited prematurely with code $($proc.ExitCode)."
        exit 1
    }
    Start-Sleep -Milliseconds 500
    try {
        $resp = Invoke-RestMethod -Uri "http://${HostAddr}:${Port}/health/ready" -TimeoutSec 2
        if ($resp.status -eq "READY") {
            $ready = $true
            break
        }
    } catch {
        # waiting for server
    }
}

if (-not $ready) {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
    Write-Error "POLARIS Server did not become READY within ${TimeoutSeconds}s."
    exit 1
}

Write-Host "[POLARIS] Server is READY at http://${HostAddr}:${Port} (PID $($proc.Id))"
exit 0
