$ErrorActionPreference = "Stop"
$InstallDir = "$env:LOCALAPPDATA\bookworm\bookwormpro"
$SkillsDest = "$env:LOCALAPPDATA\bookworm\skills"

Write-Host ""
Write-Host "  BookwormPRO Update" -ForegroundColor Cyan
Write-Host "  ==================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $InstallDir)) {
    Write-Host "  [FAIL] BookwormPRO not installed at $InstallDir" -ForegroundColor Red
    if ([Environment]::UserInteractive) { Read-Host "  Press Enter to exit" }
    exit 1
}

Write-Host "  [1/3] Fetching latest code..." -ForegroundColor Yellow
Push-Location $InstallDir
try {
    git fetch origin 2>&1 | ForEach-Object { Write-Host "    $_" }
    git reset --hard origin/master 2>&1 | ForEach-Object { Write-Host "    $_" }
    Write-Host "  [OK] Code updated" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
    Pop-Location
    if ([Environment]::UserInteractive) { Read-Host "  Press Enter to exit" }
    exit 1
}
Pop-Location

Write-Host "  [2/4] Updating dependencies..." -ForegroundColor Yellow
Push-Location $InstallDir
try {
    & python -m pip install -r requirements.txt --quiet 2>&1 | ForEach-Object { Write-Host "    $_" }
    Write-Host "  [OK] Dependencies up to date" -ForegroundColor Green
} catch {
    Write-Host "  [WARN] Dependency update failed: $_" -ForegroundColor Yellow
    Write-Host "         Run manually: pip install -r requirements.txt" -ForegroundColor Yellow
}
Pop-Location

Write-Host "  [3/4] Syncing skills..." -ForegroundColor Yellow
if (-not (Test-Path $SkillsDest)) { New-Item -ItemType Directory -Path $SkillsDest -Force | Out-Null }
Copy-Item -Recurse -Force "$InstallDir\skills\*" $SkillsDest -ErrorAction SilentlyContinue
if (Test-Path "$InstallDir\optional-skills") {
    Copy-Item -Recurse -Force "$InstallDir\optional-skills\*" $SkillsDest -ErrorAction SilentlyContinue
}
$encCount = (Get-ChildItem $SkillsDest -Recurse -Filter "*.enc" -ErrorAction SilentlyContinue).Count
Write-Host "  [OK] $encCount encrypted skills synced" -ForegroundColor Green

Write-Host "  [4/4] Done!" -ForegroundColor Green
Write-Host ""
Write-Host "  Restart bookworm to apply changes." -ForegroundColor Cyan
Write-Host ""
if ([Environment]::UserInteractive) { Read-Host "  Press Enter to exit" }
