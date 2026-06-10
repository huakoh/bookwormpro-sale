# ============================================================================
# BookwormPRO — Host Bridge Setup (Windows / PowerShell)
# ============================================================================
# Generates a `.env` file in the repo root that maps your real host paths
# into the Docker container, so the agent can read/write/delete files on
# your actual Desktop and project workspace instead of being confined to
# the in-container sandbox.
#
# Run once after cloning the repo:
#   .\scripts\setup-host-bridge.ps1
#
# Re-run any time to update paths.  Existing .env values are preserved
# unless -Force is passed.
# ============================================================================

param(
    [string]$Desktop = $null,
    [string]$Workspace = $null,
    [switch]$Force,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvFile  = Join-Path $RepoRoot ".env"

function Read-EnvFile {
    param([string]$Path)
    $kv = [ordered]@{}
    if (-not (Test-Path $Path)) { return $kv }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $kv[$line.Substring(0, $idx)] = $line.Substring($idx + 1)
    }
    return $kv
}

function Write-EnvFile {
    param([string]$Path, $Kv)
    $lines = $Kv.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }
    Set-Content -Encoding UTF8 -LiteralPath $Path -Value $lines
}

# --- Auto-detect defaults ---
$DefaultDesktop   = Join-Path $env:USERPROFILE "Desktop"
$DefaultWorkspace = Split-Path -Parent $RepoRoot   # parent of hermes-agent

# --- Resolve final values (param > prompt > default) ---
$existing = Read-EnvFile -Path $EnvFile

if (-not $Desktop) {
    $cur = $existing["HOST_DESKTOP"]
    if ($cur -and -not $Force) { $Desktop = $cur }
    elseif ($NonInteractive)   { $Desktop = $DefaultDesktop }
    else {
        $Desktop = Read-Host "Host Desktop path [$DefaultDesktop]"
        if (-not $Desktop) { $Desktop = $DefaultDesktop }
    }
}

if (-not $Workspace) {
    $cur = $existing["HOST_WORKSPACE"]
    if ($cur -and -not $Force) { $Workspace = $cur }
    elseif ($NonInteractive)   { $Workspace = $DefaultWorkspace }
    else {
        $Workspace = Read-Host "Host workspace path [$DefaultWorkspace]"
        if (-not $Workspace) { $Workspace = $DefaultWorkspace }
    }
}

# --- Validate ---
foreach ($pair in @(@{Name="HOST_DESKTOP"; Value=$Desktop}, @{Name="HOST_WORKSPACE"; Value=$Workspace})) {
    if (-not (Test-Path -LiteralPath $pair.Value)) {
        Write-Warning "$($pair.Name) path does not exist: $($pair.Value)"
        Write-Warning "Docker will create it on first run, but you may want to verify."
    }
}

# --- Merge & write ---
$existing["HOST_DESKTOP"]   = $Desktop
$existing["HOST_WORKSPACE"] = $Workspace
Write-EnvFile -Path $EnvFile -Kv $existing

Write-Host ""
Write-Host "[OK] Wrote host bridge config to $EnvFile" -ForegroundColor Green
Write-Host "  HOST_DESKTOP   = $Desktop"
Write-Host "  HOST_WORKSPACE = $Workspace"
Write-Host ""
Write-Host "Next: docker compose up -d --build"
Write-Host "Verify: docker exec bookworm ls /host/desktop"
