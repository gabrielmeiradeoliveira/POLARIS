param(
    [string]$ServerUrl = "http://127.0.0.1:8001",
    [string]$ProjectKey = "polaris-self",
    [string]$ProjectName = "POLARIS 2.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $Root "src"

$ReportPath = Join-Path $env:TEMP "polaris-self-report.json"

Write-Host "[POLARIS] Creating/ensuring project '$ProjectKey'..."
try {
    Invoke-RestMethod -Uri "$ServerUrl/api/v1/projects" -Method Post -ContentType "application/json" -Body (@{ projectKey = $ProjectKey; name = $ProjectName } | ConvertTo-Json) | Out-Null
} catch {
    # Project may already exist (409)
}

Write-Host "[POLARIS] Running independent scanner on src/..."
& $VenvPython -m polaris_scanner.cli analyze --target (Join-Path $Root "src") --project $ProjectKey --exclude ".venv,node_modules,bin,obj,target,dist,.git,__pycache__" --output $ReportPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Scanner execution failed."
    exit 1
}

Write-Host "[POLARIS] Uploading analysis report to $ServerUrl/api/v1/analyses..."
$ReportJson = Get-Content -Path $ReportPath -Raw -Encoding UTF8
Invoke-RestMethod -Uri "$ServerUrl/api/v1/analyses" -Method Post -ContentType "application/json" -Body $ReportJson | ConvertTo-Json -Depth 4
