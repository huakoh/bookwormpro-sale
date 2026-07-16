# BookwormPRO Gateway - 安装为 Windows 服务（开机自启）
# 右键以管理员身份运行此文件，或管理员 PowerShell 中执行:
#   powershell -ExecutionPolicy Bypass -File install_gateway.ps1

$SvcName = "bookworm-gateway"
$Python  = "C:\Users\leesu\AppData\Local\Programs\Python\Python312\python.exe"
$WorkDir = "C:\Users\leesu\BookwormPRO"
$LogDir  = "C:\Users\leesu\.bookwormpro\logs"

# 找到 nssm.exe
$NSSM = Get-ChildItem -Path "$env:USERPROFILE\AppData\Local\Microsoft\WinGet\Packages\NSSM.NSSM_*" -Recurse -Filter nssm.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
if (-not $NSSM) { $NSSM = (Get-Command nssm -ErrorAction SilentlyContinue).Source }
if (-not $NSSM) { Write-Host "[错误] 找不到 nssm.exe" -ForegroundColor Red; exit 1 }

Write-Host "NSSM: $NSSM" -ForegroundColor Cyan
Write-Host "Python: $Python" -ForegroundColor Cyan
Write-Host "WorkDir: $WorkDir" -ForegroundColor Cyan

# 1. 安装
& $NSSM install $SvcName $Python "-u" "-m" "gateway.run"
if ($LASTEXITCODE -ne 0) { Write-Host "[失败] install" -ForegroundColor Red; exit 1 }
Write-Host "[1/6] 服务已注册" -ForegroundColor Green

# 2. 工作目录
& $NSSM set $SvcName AppDirectory $WorkDir
Write-Host "[2/6] 工作目录已设置" -ForegroundColor Green

# 3. 开机自启
& $NSSM set $SvcName Start SERVICE_AUTO_START
Write-Host "[3/6] 开机自启" -ForegroundColor Green

# 4. 日志
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
& $NSSM set $SvcName AppStdout "$LogDir\gateway-stdout.log"
& $NSSM set $SvcName AppStderr "$LogDir\gateway-stderr.log"
& $NSSM set $SvcName AppRotateFiles 1
Write-Host "[4/6] 日志已配置" -ForegroundColor Green

# 5. 环境变量 (SYSTEM 账户找不到用户 ~/.bookwormpro)
$PythonDir = Split-Path $Python -Parent
$ScriptsDir = "$PythonDir\Scripts"
$EnvExtra = "BOOKWORMPRO_HOME=$env:USERPROFILE\.bookwormpro USERPROFILE=$env:USERPROFILE PATH=$PythonDir;$ScriptsDir;%PATH%"
& $NSSM set $SvcName AppEnvironmentExtra $EnvExtra
Write-Host "[5/6] 环境变量已注入 (BOOKWORMPRO_HOME)" -ForegroundColor Green

# 6. 崩溃重启
& $NSSM set $SvcName AppExit Default Restart
& $NSSM set $SvcName DisplayName "BookwormPRO Gateway"
Write-Host "[6/6] 自动重启已配置" -ForegroundColor Green

# 启动
Write-Host ""
Write-Host "启动服务..." -ForegroundColor Yellow
& $NSSM start $SvcName
Start-Sleep -Seconds 3
$status = & $NSSM status $SvcName
Write-Host "状态: $status" -ForegroundColor $(if ($status -match "RUNNING") {"Green"} else {"Red"})

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "✓ BookwormPRO Gateway 已安装为 Windows 服务" -ForegroundColor Green
Write-Host "  开机自启: 已启用" -ForegroundColor Green
Write-Host "  日志: $LogDir\gateway-stdout.log" -ForegroundColor Gray
Write-Host "======================================" -ForegroundColor Cyan
