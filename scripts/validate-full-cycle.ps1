param(
    [string]$PgDsn = $env:POLARIS_PG_DSN,
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

if (-not $PgDsn) {
    Write-Error "POLARIS_PG_DSN must be provided (e.g. postgresql://user:pass@127.0.0.1:5433/polaris_test)."
    exit 1
}
$env:POLARIS_PG_DSN = $PgDsn
$env:PYTHONPATH = Join-Path $Root "src"

$portInUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Error "Port $Port is already in use. Stop the existing process before running validation."
    exit 1
}

Write-Host "[1/6] Building C# analyzer..."
dotnet build (Join-Path $Root "analyzers\csharp\PolarisCSharpAnalyzer.csproj") -c Release
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "[2/6] Building Java analyzer via Maven container..."
docker run --rm -v "${Root}\analyzers\java:/workspace" -w /workspace maven:3.9-eclipse-temurin-21 mvn -q package -DskipTests
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "[3/6] Running unit & analyzer tests..."
& (Join-Path $Root ".venv\Scripts\python.exe") -m unittest tests/test_rules_catalog_api.py tests/test_effective_profiles_analyzers.py tests/test_gates_evaluation.py tests/test_scanner_effective_profile.py
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "[4/6] Running PostgreSQL migrations on test database..."
& (Join-Path $Root ".venv\Scripts\python.exe") -c "from polaris_server.db import run_migrations; run_migrations()"
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "[5/6] Starting test server on port $Port..."
& (Join-Path $Root "scripts\start-dev.ps1") -Port $Port -DatabaseMode "test"
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "[6/6] Running E2E PostgreSQL & Scanner delivery test..."
$env:POLARIS_TEST_PG = "1"
& (Join-Path $Root ".venv\Scripts\python.exe") -m unittest tests/test_e2e_delivery.py
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "[POLARIS] Full validation cycle completed successfully."
