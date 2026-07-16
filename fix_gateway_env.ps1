# Fix gateway service environment variables (needs admin)
# Adds missing PATH, USERPROFILE, PYTHONPATH to prevent silent failures

$NSSM = Get-ChildItem -Path "$env:USERPROFILE\AppData\Local\Microsoft\WinGet\Packages\NSSM.NSSM_*" -Recurse -Filter nssm.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName

$pythonDir = "C:\Users\leesu\AppData\Local\Programs\Python\Python312"
$scriptsDir = "$pythonDir\Scripts"
$workDir = "C:\Users\leesu\BookwormPRO"
$hermesHome = "C:\Users\leesu\.bookwormpro"

# Complete environment: BOOKWORMPRO_HOME + USERPROFILE + PATH + PYTHONPATH
$envExtra = "BOOKWORMPRO_HOME=$hermesHome USERPROFILE=C:\Users\leesu PATH=$pythonDir;$scriptsDir;%PATH% PYTHONPATH=$workDir"

Write-Host "=== Stopping service ===" -ForegroundColor Yellow
& $NSSM stop bookworm-gateway
Start-Sleep -Seconds 2

Write-Host "=== Setting AppEnvironmentExtra ===" -ForegroundColor Yellow
& $NSSM set bookworm-gateway AppEnvironmentExtra $envExtra
Write-Host "Set to: $envExtra" -ForegroundColor Green

Write-Host "=== Verifying ===" -ForegroundColor Yellow
& $NSSM get bookworm-gateway AppEnvironmentExtra

Write-Host ""
Write-Host "=== Starting service ===" -ForegroundColor Yellow
& $NSSM start bookworm-gateway
Start-Sleep -Seconds 3
$status = & $NSSM status bookworm-gateway
Write-Host "Status: $status" -ForegroundColor $(if ($status -match "RUNNING") {"Green"} else {"Red"})

Write-Host ""
Write-Host "Done. Check logs at $hermesHome\logs\" -ForegroundColor Cyan
