# Windows counterpart of `make doctor`: checks local prerequisites and the pinned OPA version.
#   pwsh scripts/doctor.ps1      (or: powershell -File scripts\doctor.ps1)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Test-Tool([string[]]$names) {
    foreach ($n in $names) { if (Get-Command $n -ErrorAction SilentlyContinue) { return $n } }
    return $null
}

foreach ($t in @(@('python3', 'python'), 'node', 'npm', 'docker', 'git', 'terraform', 'helm', 'kubectl')) {
    $label = @($t)[0]
    if (Test-Tool @($t)) { Write-Host "  ✓ $label" } else { Write-Host "  ✗ $label (missing)" }
}

$want = (Get-Content (Join-Path $root '.opa-version') -Raw).Trim()
if (-not (Test-Tool @('opa'))) {
    Write-Host "  ✗ opa (missing; want $want — scoop install opa, or choco install opa)"
} else {
    $have = (opa version | Select-String '^Version:\s*(\S+)').Matches[0].Groups[1].Value
    if ($have -eq $want) { Write-Host "  ✓ opa $have" }
    else { Write-Host "  ! opa $have (repo pins $want in .opa-version)" }
}
