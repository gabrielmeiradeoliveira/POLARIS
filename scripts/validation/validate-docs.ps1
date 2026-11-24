<#
.SYNOPSIS
    Validador documental do repositório POLARIS 2.0.
.DESCRIPTION
    Verifica arquivos Markdown vazios, validade básica de frontmatter YAML no vault/,
    unicidade de IDs no frontmatter do vault/ e integridade de links internos Markdown.
    Não depende de caminhos absolutos específicos de máquina.
#>
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"
Push-Location $RepoRoot

try {
    $mdFiles = Get-ChildItem -Recurse -File -Filter *.md | Where-Object {
        $_.FullName -notmatch '[\\/](node_modules|\.venv|\.git|bin|obj|target)[\\/]'
    }
    $emptyFiles = @($mdFiles | Where-Object { $_.Length -eq 0 -or [string]::IsNullOrWhiteSpace((Get-Content $_.FullName -Raw)) })

    $vaultPath = Join-Path $RepoRoot "vault"
    $vaultMd = if (Test-Path $vaultPath) { Get-ChildItem -Path $vaultPath -Recurse -File -Filter *.md } else { @() }

    $missingYaml = @()
    $idMap = @{}
    $duplicateIds = @()

    foreach ($f in $vaultMd) {
        $raw = Get-Content $f.FullName -Raw
        if ($raw -notmatch '(?s)^---\r?\n.*?id:\s*([^\r\n]+).*?\r?\n.*?title:.*?\r?\n.*?status:.*?\r?\n.*?---') {
            $missingYaml += $f.FullName.Replace($RepoRoot + [System.IO.Path]::DirectorySeparatorChar, "")
        } else {
            $docId = $Matches[1].Trim()
            if ($docId -notmatch 'XXX') {
                if ($idMap.ContainsKey($docId)) {
                    $duplicateIds += "$docId ($($idMap[$docId]) e $($f.FullName.Replace($RepoRoot + [System.IO.Path]::DirectorySeparatorChar, '')))"
                } else {
                    $idMap[$docId] = $f.FullName.Replace($RepoRoot + [System.IO.Path]::DirectorySeparatorChar, "")
                }
            }
        }
    }

    $brokenLinks = @()
    foreach ($f in $mdFiles) {
        $raw = Get-Content $f.FullName -Raw
        $linkMatches = [regex]::Matches($raw, '\[[^\]]+\]\(([^)#\s]+\.md)(?:#[^)]+)?\)')
        foreach ($m in $linkMatches) {
            $target = $m.Groups[1].Value
            if ($target -match '^https?://') { continue }
            $resolved = Join-Path $f.DirectoryName $target
            if (-not (Test-Path $resolved)) {
                $brokenLinks += ($f.FullName.Replace($RepoRoot + [System.IO.Path]::DirectorySeparatorChar, "") + " -> " + $target)
            }
        }
    }

    Write-Output ("TOTAL_MD_FILES=" + $mdFiles.Count)
    Write-Output ("EMPTY_FILES=" + $emptyFiles.Count)
    Write-Output ("MISSING_YAML_COUNT=" + $missingYaml.Count)
    if ($missingYaml.Count -gt 0) { $missingYaml | ForEach-Object { Write-Output ("MISSING_YAML: " + $_) } }
    Write-Output ("DUPLICATE_IDS_COUNT=" + $duplicateIds.Count)
    if ($duplicateIds.Count -gt 0) { $duplicateIds | ForEach-Object { Write-Output ("DUPLICATE_ID: " + $_) } }
    Write-Output ("BROKEN_LINKS_COUNT=" + $brokenLinks.Count)
    if ($brokenLinks.Count -gt 0) { $brokenLinks | ForEach-Object { Write-Output ("BROKEN_LINK: " + $_) } }

    if ($emptyFiles.Count -gt 0 -or $missingYaml.Count -gt 0 -or $duplicateIds.Count -gt 0 -or $brokenLinks.Count -gt 0) {
        exit 1
    }
    exit 0
}
finally {
    Pop-Location
}
