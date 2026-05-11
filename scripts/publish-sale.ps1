<#
.SYNOPSIS
    BookwormPRO Sale 仓一键发布脚本
.DESCRIPTION
    脱敏 + Cython 编译 + 推送到 huakoh/bookwormpro-sale
    需要: MSVC Build Tools + Cython + Python 3.12
.EXAMPLE
    .\scripts\publish-sale.ps1           # 构建并推送
    .\scripts\publish-sale.ps1 -DryRun   # 仅预览
#>
param(
    [switch]$DryRun,
    [string]$LicenseKey
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path "$ScriptDir\..").Path

# MSVC vcvars64.bat 查找: BuildTools → Community → Enterprise
$VcVarsCandidates = @(
    "$env:ProgramFiles(x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
    "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
)
$VcVars = $null
foreach ($candidate in $VcVarsCandidates) {
    if (Test-Path $candidate) {
        $VcVars = $candidate
        break
    }
}
if (-not $VcVars) {
    Write-Host "[FAIL] MSVC Build Tools not found. Install 'Desktop development with C++' from Visual Studio Installer" -ForegroundColor Red
    Write-Host "  Searched:" -ForegroundColor DarkGray
    foreach ($c in $VcVarsCandidates) { Write-Host "    $c" -ForegroundColor DarkGray }
    exit 1
}

if (-not $LicenseKey) {
    $LicenseKey = $env:BOOKWORMPRO_LICENSE_KEY
}
if (-not $LicenseKey) {
    Write-Host "[FAIL] License key required: -LicenseKey <key> or set BOOKWORMPRO_LICENSE_KEY" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  BookwormPRO Sale Publish Pipeline" -ForegroundColor Magenta
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

if (-not (Test-Path "$ProjectRoot\scripts\build_sale.py")) {
    Write-Host "[FAIL] build_sale.py not found" -ForegroundColor Red
    exit 1
}

$flag = if ($DryRun) { "--dry-run" } else { "--push" }
$flag = "$flag --license-key `"$LicenseKey`""

Write-Host "[1/2] Loading MSVC x64 environment..." -ForegroundColor Cyan
Write-Host "[2/2] Running build_sale.py $flag" -ForegroundColor Cyan
Write-Host ""

cmd /c "`"$VcVars`" >nul 2>&1 && cd /d `"$ProjectRoot`" && python scripts\build_sale.py $flag"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  DONE" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  FAILED (exit $LASTEXITCODE)" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    exit $LASTEXITCODE
}
