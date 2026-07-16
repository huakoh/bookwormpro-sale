# ============================================================================
# BookwormPRO Installer for Windows
# ============================================================================
# Installation script for Windows (PowerShell).
# Uses uv for fast Python provisioning and package management.
#
# Usage:
#   irm https://raw.githubusercontent.com/huakoh/bookwormpro-sale/master/scripts/install.ps1 | iex
#
# Or download and run with options:
#   .\install.ps1 -NoVenv -SkipSetup
#
# ============================================================================

param(
    [switch]$NoVenv,
    [switch]$SkipSetup,
    [string]$Branch = "master",
    [string]$HermesHome = "$env:LOCALAPPDATA\bookworm",
    [string]$InstallDir = "$env:LOCALAPPDATA\bookworm\bookwormpro"
)

$ErrorActionPreference = "Stop"

# ============================================================================
# Configuration
# ============================================================================

$RepoUrlSsh = "git@github.com:huakoh/bookwormpro-sale.git"
$RepoUrlHttps = "https://github.com/huakoh/bookwormpro-sale.git"
$PythonVersion = "3.12"
$NodeVersion = "22"
$script:UseChinaMirrors = $false
$PypiMirror = "https://pypi.tuna.tsinghua.edu.cn/simple"
$NpmMirror = "https://registry.npmmirror.com"

# Fix UTF-8 encoding for Chinese usernames (PS 5.1 reads external output as system codepage)
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
} catch {}

# ============================================================================
# Helper functions
# ============================================================================

function Write-Banner {
    Write-Host ""
    Write-Host "┌─────────────────────────────────────────────────────────┐" -ForegroundColor Magenta
    Write-Host "│             [BWM] BookwormPRO Installer                    │" -ForegroundColor Magenta
    Write-Host "├─────────────────────────────────────────────────────────┤" -ForegroundColor Magenta
    Write-Host "│  An open source AI agent by BookwormPRO Project.              │" -ForegroundColor Magenta
    Write-Host "└─────────────────────────────────────────────────────────┘" -ForegroundColor Magenta
    Write-Host ""
}

function Write-Info {
    param([string]$Message)
    Write-Host "→ $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[成功] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[警告] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[失败] $Message" -ForegroundColor Red
}

# ============================================================================
# Dependency checks
# ============================================================================

function Install-Uv {
    Write-Info "Checking for uv package manager..."
    
    # Check if uv is already available
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $version = uv --version
        $script:UvCmd = "uv"
        Write-Success "uv found ($version)"
        return $true
    }
    
    # Check common install locations
    $uvPaths = @(
        "$env:USERPROFILE\.local\bin\uv.exe",
        "$env:USERPROFILE\.cargo\bin\uv.exe"
    )
    foreach ($uvPath in $uvPaths) {
        if (Test-Path $uvPath) {
            $script:UvCmd = $uvPath
            $version = & $uvPath --version
            Write-Success "uv found at $uvPath ($version)"
            return $true
        }
    }
    
    # Install uv
    Write-Info "Installing uv (fast Python package manager)..."
    try {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 2>&1 | Out-Null
        
        # Find the installed binary
        $uvExe = "$env:USERPROFILE\.local\bin\uv.exe"
        if (-not (Test-Path $uvExe)) {
            $uvExe = "$env:USERPROFILE\.cargo\bin\uv.exe"
        }
        if (-not (Test-Path $uvExe)) {
            # Refresh PATH and try again
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
            if (Get-Command uv -ErrorAction SilentlyContinue) {
                $uvExe = (Get-Command uv).Source
            }
        }
        
        if (Test-Path $uvExe) {
            $script:UvCmd = $uvExe
            $version = & $uvExe --version
            Write-Success "uv installed ($version)"
            return $true
        }
        
        Write-Err "uv installed but not found on PATH"
        Write-Info "Try restarting your terminal and re-running"
        return $false
    } catch {
        Write-Err "Failed to install uv"
        Write-Info "Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        return $false
    }
}

function Test-Python {
    Write-Info "Checking Python $PythonVersion..."
    
    # ═══════════════════════════════════════════════════════════════
    # 阶段 1: 检测现有 Python
    # ═══════════════════════════════════════════════════════════════
    
    # 1.1 让 uv 查找
    try {
        $pythonPath = & $UvCmd python find $PythonVersion 2>$null
        if ($pythonPath) {
            $ver = & $pythonPath --version 2>$null
            Write-Success "Python found: $ver"
            return $true
        }
    } catch { }
    
    # 1.2 检查系统 PATH 中的任意 Python 3.10+
    # ⚠ 必须过滤 WindowsApps 伪装别名(Microsoft Store stub),否则 python --version 会触发商店并中断脚本
    Write-Info "Checking system Python..."
    try {
        $pyCmds = @(Get-Command python -ErrorAction SilentlyContinue -All)
        foreach ($pyCmd in $pyCmds) {
            # 跳过 Microsoft Store 伪装别名(WindowsApps 下的 0 字节 stub)
            if ($pyCmd.Source -like "*WindowsApps*") { continue }
            try {
                $sysVer = & $pyCmd.Source --version 2>$null
                if ($sysVer -match "3\.(1[0-9]|[1-9][0-9])") {
                    Write-Success "Found system Python: $sysVer"
                    $actualVer = ($sysVer -replace 'Python ', '').Split('.')[0..1] -join '.'
                    $script:PythonVersion = $actualVer
                    return $true
                }
            } catch { }
        }
    } catch { }
    
    # 1.3 uv 查找任意 3.10+ fallback
    foreach ($fallbackVer in @("3.13", "3.12", "3.11", "3.10")) {
        try {
            $pythonPath = & $UvCmd python find $fallbackVer 2>$null
            if ($pythonPath) {
                $ver = & $pythonPath --version 2>$null
                Write-Success "Found Python ${fallbackVer}: $ver"
                $script:PythonVersion = $fallbackVer
                return $true
            }
        } catch { }
    }
    
    # ═══════════════════════════════════════════════════════════════
    # 阶段 2: 自动安装 Python（多路径降级 + 国内镜像智能切换）
    # ═══════════════════════════════════════════════════════════════
    
    Write-Info "Python not found. Starting automatic installation..."
    Write-Info "This will install Python $PythonVersion (no admin needed for uv method)."
    
    # 2.1 路径 A: uv python install（优先，无需管理员）
    Write-Info "[1/4] Trying uv python install (GitHub download)..."
    try {
        $uvOutput = & $UvCmd python install $PythonVersion 2>&1
        if ($LASTEXITCODE -eq 0) {
            Start-Sleep -Seconds 2  # 等待文件系统刷新
            $pythonPath = & $UvCmd python find $PythonVersion 2>$null
            if ($pythonPath) {
                $ver = & $pythonPath --version 2>$null
                Write-Success "✓ Python installed via uv: $ver"
                return $true
            }
        }
        Write-Warn "uv install failed (network or GitHub blocked)"
    } catch {
        Write-Warn "uv install error: $_"
    }
    
    # 启用国内镜像（uv 失败说明国际网络不通）
    $script:UseChinaMirrors = $true
    
    # 2.2 路径 B: winget install（Microsoft CDN，中国可达）
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "[2/4] Trying winget (Microsoft CDN, works in China)..."
        try {
            Write-Host "  → Installing Python.Python.3.12 via winget..." -ForegroundColor Cyan
            $wingetOut = winget install Python.Python.3.12 `
                --accept-source-agreements `
                --accept-package-agreements `
                --silent 2>&1
            
            if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
                # 刷新 PATH（winget 装完需手动刷新）
                $machPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
                $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
                $env:Path = "$machPath;$userPath"
                
                Start-Sleep -Seconds 3
                
                # 验证
                $pythonPath = & $UvCmd python find $PythonVersion 2>$null
                if (-not $pythonPath) {
                    $pythonPath = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
                }
                if ($pythonPath) {
                    $ver = & $pythonPath --version 2>$null
                    Write-Success "✓ Python installed via winget: $ver"
                    Write-Host "  Note: Please close and reopen your terminal after installation." -ForegroundColor Yellow
                    return $true
                }
            }
            
            # winget 非零退出但可能部分成功 - 再次验证
            if (Get-Command python -ErrorAction SilentlyContinue) {
                $ver = python --version 2>$null
                if ($ver -match "3\.(1[0-9]|[1-9][0-9])") {
                    Write-Success "✓ Python available: $ver"
                    return $true
                }
            }
            
            Write-Warn "winget install completed but Python not found in PATH"
            Write-Host $wingetOut -ForegroundColor DarkGray
        } catch {
            Write-Warn "winget failed: $_"
        }
    } else {
        Write-Warn "[2/4] winget not available (需要 Windows 10 1809+ 或 Windows Server 2019+)"
    }
    
    # 2.3 路径 C: 官方安装器下载 + 自动提权运行（弹窗确认）
    Write-Info "[3/4] Trying official Python installer download..."
    
    $installerUrl = if ($script:UseChinaMirrors) {
        # 中国镜像（华为云/阿里云/淘宝/清华 TUNA）
        "https://mirrors.huaweicloud.com/python/3.12.7/python-3.12.7-amd64.exe"
    } else {
        "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
    }
    
    $installerPath = "$env:TEMP\python-3.12-installer.exe"
    
    try {
        Write-Host "  → Downloading from: $installerUrl" -ForegroundColor Cyan
        
        # 使用 .NET WebClient（比 Invoke-WebRequest 快）
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($installerUrl, $installerPath)
        
        if (Test-Path $installerPath) {
            $sizeMB = [math]::Round((Get-Item $installerPath).Length / 1MB, 1)
            Write-Success "✓ Downloaded installer ($sizeMB MB)"
            
            # 弹窗确认（GUI）
            Add-Type -AssemblyName System.Windows.Forms
            $result = [System.Windows.Forms.MessageBox]::Show(
                "Python 3.12 installer downloaded successfully.`n`n" +
                "Click OK to install (requires admin elevation).`n" +
                "This will:`n" +
                "  • Install Python 3.12 for all users`n" +
                "  • Add Python to system PATH`n" +
                "  • Include pip and standard library",
                "BookwormPRO Setup - Python Installation",
                [System.Windows.Forms.MessageBoxButtons]::OKCancel,
                [System.Windows.Forms.MessageBoxIcon]::Question
            )
            
            if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
                Write-Info "Starting Python installer with admin elevation..."
                
                # 静默安装参数
                $installArgs = @(
                    "/quiet",                    # 静默模式
                    "InstallAllUsers=1",        # 所有用户
                    "PrependPath=1",            # 添加到 PATH
                    "Include_pip=1",            # 包含 pip
                    "Include_test=0"            # 不装测试套件
                )
                
                # 提权运行
                $proc = Start-Process -FilePath $installerPath `
                    -ArgumentList $installArgs `
                    -Verb RunAs `
                    -Wait `
                    -PassThru
                
                if ($proc.ExitCode -eq 0) {
                    Write-Success "✓ Python installed successfully"
                    
                    # 刷新 PATH
                    $machPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
                    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
                    $env:Path = "$machPath;$userPath"
                    
                    Start-Sleep -Seconds 2
                    
                    # 验证
                    if (Get-Command python -ErrorAction SilentlyContinue) {
                        $ver = python --version 2>$null
                        Write-Success "Python ready: $ver"
                        Write-Host "`n  ⚠ Please close and reopen your terminal to use Python." -ForegroundColor Yellow
                        return $true
                    }
                } else {
                    Write-Warn "Installer exited with code $($proc.ExitCode)"
                }
            } else {
                Write-Warn "Installation cancelled by user"
            }
            
            # 清理安装器
            Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Warn "Download/install failed: $_"
    }
    
    # 2.4 路径 D: 引导用户手动安装（最后兜底）
    Write-Err "[4/4] All automatic methods failed. Manual installation required."
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║  请手动安装 Python 3.12 后重新运行此脚本                        ║" -ForegroundColor Yellow
    Write-Host "╠═══════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
    Write-Host "║                                                               ║" -ForegroundColor Yellow
    Write-Host "║  方法 1 (推荐): winget 命令安装                                  ║" -ForegroundColor Yellow
    Write-Host "║    winget install Python.Python.3.12                         ║" -ForegroundColor Cyan
    Write-Host "║                                                               ║" -ForegroundColor Yellow
    Write-Host "║  方法 2: 官网下载                                               ║" -ForegroundColor Yellow
    Write-Host "║    https://www.python.org/downloads/                         ║" -ForegroundColor Cyan
    Write-Host "║    安装时勾选 'Add Python to PATH'                             ║" -ForegroundColor Gray
    Write-Host "║                                                               ║" -ForegroundColor Yellow
    Write-Host "║  方法 3: 国内镜像（如果官网下载慢）                                ║" -ForegroundColor Yellow
    Write-Host "║    https://mirrors.huaweicloud.com/python/                   ║" -ForegroundColor Cyan
    Write-Host "║    https://mirrors.aliyun.com/python-release/windows/        ║" -ForegroundColor Cyan
    Write-Host "║                                                               ║" -ForegroundColor Yellow
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    Write-Host ""
    
    # 交互式等待（如果在交互环境）
    if ([Environment]::UserInteractive) {
        Write-Host "Press Enter after installing Python, or Ctrl+C to exit..." -ForegroundColor Gray
        Read-Host
        
        # 用户说装好了，再次检测
        if (Get-Command python -ErrorAction SilentlyContinue) {
            $ver = python --version 2>$null
            if ($ver -match "3\.(1[0-9]|[1-9][0-9])") {
                Write-Success "✓ Python detected: $ver"
                return $true
            }
        }
        
        Write-Err "Python still not found. Please check installation and PATH."
    }
    
    return $false
}


function Test-Git {
    Write-Info "Checking Git..."
    
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $version = git --version
        Write-Success "Git found ($version)"
        return $true
    }
    
    # ═══════════════════════════════════════════════════════════════
    # Git 未找到 — 自动安装（多路径降级）
    # ═══════════════════════════════════════════════════════════════
    Write-Info "Git not found. Starting automatic installation..."
    
    # 路径 A: winget（Microsoft CDN，中国可达，无需手动提权）
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "[1/3] Trying winget (Microsoft CDN)..."
        try {
            Write-Host "  → Installing Git.Git via winget..." -ForegroundColor Cyan
            winget install Git.Git `
                --accept-source-agreements `
                --accept-package-agreements `
                --silent 2>&1 | Out-Null
            
            # 刷新 PATH（Git 装到 Program Files，需刷新）
            $machPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
            $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
            $env:Path = "$machPath;$userPath"
            
            # 常见 Git 安装路径兜底加入 PATH
            $gitCandidates = @(
                "$env:ProgramFiles\Git\cmd",
                "${env:ProgramFiles(x86)}\Git\cmd",
                "$env:LOCALAPPDATA\Programs\Git\cmd"
            )
            foreach ($gc in $gitCandidates) {
                if (Test-Path "$gc\git.exe") { $env:Path = "$gc;$env:Path" }
            }
            
            Start-Sleep -Seconds 2
            if (Get-Command git -ErrorAction SilentlyContinue) {
                $version = git --version
                Write-Success "✓ Git installed via winget ($version)"
                Write-Host "  Note: Please close and reopen your terminal after installation." -ForegroundColor Yellow
                return $true
            }
            Write-Warn "winget completed but git not found in PATH"
        } catch {
            Write-Warn "winget failed: $_"
        }
    } else {
        Write-Warn "[1/3] winget not available"
    }
    
    # 路径 B: 官方安装器下载 + GUI 弹窗确认 + 自动提权
    Write-Info "[2/3] Trying Git official installer download..."
    
    $gitVer = "2.47.1"
    $installerUrl = if ($script:UseChinaMirrors) {
        # 淘宝 npm 镜像（Git for Windows 国内加速）
        "https://npmmirror.com/mirrors/git-for-windows/v$gitVer.windows.1/Git-$gitVer-64-bit.exe"
    } else {
        "https://github.com/git-for-windows/git/releases/download/v$gitVer.windows.1/Git-$gitVer-64-bit.exe"
    }
    
    $installerPath = "$env:TEMP\git-installer.exe"
    
    try {
        Write-Host "  → Downloading from: $installerUrl" -ForegroundColor Cyan
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($installerUrl, $installerPath)
        
        if (Test-Path $installerPath) {
            $sizeMB = [math]::Round((Get-Item $installerPath).Length / 1MB, 1)
            Write-Success "✓ Downloaded installer ($sizeMB MB)"
            
            Add-Type -AssemblyName System.Windows.Forms
            $result = [System.Windows.Forms.MessageBox]::Show(
                "Git installer downloaded successfully.`n`n" +
                "Click OK to install (requires admin elevation).`n" +
                "This will install Git for Windows with default options`n" +
                "and add it to system PATH.",
                "BookwormPRO Setup - Git Installation",
                [System.Windows.Forms.MessageBoxButtons]::OKCancel,
                [System.Windows.Forms.MessageBoxIcon]::Question
            )
            
            if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
                Write-Info "Starting Git installer with admin elevation..."
                # /VERYSILENT 静默 + NORESTART 不重启 + 默认组件含 PATH
                $installArgs = @(
                    "/VERYSILENT",
                    "/NORESTART",
                    "/NOCANCEL",
                    "/SP-",
                    '/COMPONENTS="icons,ext\reg\shellhere,assoc,assoc_sh"'
                )
                $proc = Start-Process -FilePath $installerPath `
                    -ArgumentList $installArgs `
                    -Verb RunAs `
                    -Wait `
                    -PassThru
                
                if ($proc.ExitCode -eq 0) {
                    # 刷新 PATH
                    $machPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
                    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
                    $env:Path = "$machPath;$userPath"
                    foreach ($gc in @("$env:ProgramFiles\Git\cmd", "$env:LOCALAPPDATA\Programs\Git\cmd")) {
                        if (Test-Path "$gc\git.exe") { $env:Path = "$gc;$env:Path" }
                    }
                    Start-Sleep -Seconds 2
                    
                    if (Get-Command git -ErrorAction SilentlyContinue) {
                        $version = git --version
                        Write-Success "✓ Git installed ($version)"
                        Write-Host "`n  ⚠ Please close and reopen your terminal to use Git." -ForegroundColor Yellow
                        return $true
                    }
                } else {
                    Write-Warn "Installer exited with code $($proc.ExitCode)"
                }
            } else {
                Write-Warn "Installation cancelled by user"
            }
            Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Warn "Download/install failed: $_"
    }
    
    # 路径 C: 引导手动安装
    Write-Err "[3/3] Automatic Git installation failed. Manual installation required."
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║  请手动安装 Git 后重新运行此脚本                                ║" -ForegroundColor Yellow
    Write-Host "╠═══════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
    Write-Host "║  方法 1: winget install Git.Git                              ║" -ForegroundColor Cyan
    Write-Host "║  方法 2: https://git-scm.com/download/win                    ║" -ForegroundColor Cyan
    Write-Host "║  方法 3 (国内): https://npmmirror.com/mirrors/git-for-windows/║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    Write-Host ""
    
    if ([Environment]::UserInteractive) {
        Write-Host "Press Enter after installing Git, or Ctrl+C to exit..." -ForegroundColor Gray
        Read-Host
        if (Get-Command git -ErrorAction SilentlyContinue) {
            $version = git --version
            Write-Success "✓ Git detected ($version)"
            return $true
        }
        Write-Err "Git still not found. Please check installation and PATH."
    }
    
    return $false
}

function Test-Node {
    Write-Info "Checking Node.js (for browser tools)..."

    if (Get-Command node -ErrorAction SilentlyContinue) {
        $version = node --version
        Write-Success "Node.js $version found"
        $script:HasNode = $true
        return $true
    }

    # Check our own managed install from a previous run
    $managedNode = "$HermesHome\node\node.exe"
    if (Test-Path $managedNode) {
        $version = & $managedNode --version
        $env:Path = "$HermesHome\node;$env:Path"
        Write-Success "Node.js $version found (BookwormPRO-managed)"
        $script:HasNode = $true
        return $true
    }

    Write-Info "Node.js not found — installing Node.js $NodeVersion LTS..."

    # Try winget first (cleanest on modern Windows)
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "Installing via winget..."
        try {
            winget install OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
            # Refresh PATH
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
            if (Get-Command node -ErrorAction SilentlyContinue) {
                $version = node --version
                Write-Success "Node.js $version installed via winget"
                $script:HasNode = $true
                return $true
            }
        } catch { }
    }

    # Fallback: download binary zip to ~/.bookwormpro/node/
    Write-Info "Downloading Node.js $NodeVersion binary..."
    try {
        $arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }
        $indexUrl = "https://nodejs.org/dist/latest-v${NodeVersion}.x/"
        $indexPage = Invoke-WebRequest -Uri $indexUrl -UseBasicParsing
        $zipName = ($indexPage.Content | Select-String -Pattern "node-v${NodeVersion}\.\d+\.\d+-win-${arch}\.zip" -AllMatches).Matches[0].Value

        if ($zipName) {
            $downloadUrl = "${indexUrl}${zipName}"
            $tmpZip = "$env:TEMP\$zipName"
            $tmpDir = "$env:TEMP\bookworm-node-extract"

            Invoke-WebRequest -Uri $downloadUrl -OutFile $tmpZip -UseBasicParsing
            if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
            Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

            $extractedDir = Get-ChildItem $tmpDir -Directory | Select-Object -First 1
            if ($extractedDir) {
                if (Test-Path "$HermesHome\node") { Remove-Item -Recurse -Force "$HermesHome\node" }
                Move-Item $extractedDir.FullName "$HermesHome\node"
                $env:Path = "$HermesHome\node;$env:Path"

                $version = & "$HermesHome\node\node.exe" --version
                Write-Success "Node.js $version installed to ~/.bookwormpro/node/"
                $script:HasNode = $true

                Remove-Item -Force $tmpZip -ErrorAction SilentlyContinue
                Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
                return $true
            }
        }
    } catch {
        Write-Warn "Download failed: $_"
    }

    Write-Warn "Could not auto-install Node.js"
    Write-Info "Install manually: https://nodejs.org/en/download/"
    $script:HasNode = $false
    return $true
}

function Install-SystemPackages {
    $script:HasRipgrep = $false
    $script:HasFfmpeg = $false
    $needRipgrep = $false
    $needFfmpeg = $false

    Write-Info "Checking ripgrep (fast file search)..."
    if (Get-Command rg -ErrorAction SilentlyContinue) {
        $version = rg --version | Select-Object -First 1
        Write-Success "$version found"
        $script:HasRipgrep = $true
    } else {
        $needRipgrep = $true
    }

    Write-Info "Checking ffmpeg (TTS voice messages)..."
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Success "ffmpeg found"
        $script:HasFfmpeg = $true
    } else {
        $needFfmpeg = $true
    }

    if (-not $needRipgrep -and -not $needFfmpeg) { return }

    # Build description and package lists for each package manager
    $descParts = @()
    $wingetPkgs = @()
    $chocoPkgs = @()
    $scoopPkgs = @()

    if ($needRipgrep) {
        $descParts += "ripgrep for faster file search"
        $wingetPkgs += "BurntSushi.ripgrep.MSVC"
        $chocoPkgs += "ripgrep"
        $scoopPkgs += "ripgrep"
    }
    if ($needFfmpeg) {
        $descParts += "ffmpeg for TTS voice messages"
        $wingetPkgs += "Gyan.FFmpeg"
        $chocoPkgs += "ffmpeg"
        $scoopPkgs += "ffmpeg"
    }

    $description = $descParts -join " and "
    $hasWinget = Get-Command winget -ErrorAction SilentlyContinue
    $hasChoco = Get-Command choco -ErrorAction SilentlyContinue
    $hasScoop = Get-Command scoop -ErrorAction SilentlyContinue

    # Try winget first (most common on modern Windows)
    if ($hasWinget) {
        Write-Info "Installing $description via winget..."
        foreach ($pkg in $wingetPkgs) {
            try {
                winget install $pkg --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
            } catch { }
        }
        # Refresh PATH and recheck
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
        if ($needRipgrep -and (Get-Command rg -ErrorAction SilentlyContinue)) {
            Write-Success "ripgrep installed"
            $script:HasRipgrep = $true
            $needRipgrep = $false
        }
        if ($needFfmpeg -and (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            Write-Success "ffmpeg installed"
            $script:HasFfmpeg = $true
            $needFfmpeg = $false
        }
        if (-not $needRipgrep -and -not $needFfmpeg) { return }
    }

    # Fallback: choco
    if ($hasChoco -and ($needRipgrep -or $needFfmpeg)) {
        Write-Info "Trying Chocolatey..."
        foreach ($pkg in $chocoPkgs) {
            try { choco install $pkg -y 2>&1 | Out-Null } catch { }
        }
        if ($needRipgrep -and (Get-Command rg -ErrorAction SilentlyContinue)) {
            Write-Success "ripgrep installed via chocolatey"
            $script:HasRipgrep = $true
            $needRipgrep = $false
        }
        if ($needFfmpeg -and (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            Write-Success "ffmpeg installed via chocolatey"
            $script:HasFfmpeg = $true
            $needFfmpeg = $false
        }
    }

    # Fallback: scoop
    if ($hasScoop -and ($needRipgrep -or $needFfmpeg)) {
        Write-Info "Trying Scoop..."
        foreach ($pkg in $scoopPkgs) {
            try { scoop install $pkg 2>&1 | Out-Null } catch { }
        }
        if ($needRipgrep -and (Get-Command rg -ErrorAction SilentlyContinue)) {
            Write-Success "ripgrep installed via scoop"
            $script:HasRipgrep = $true
            $needRipgrep = $false
        }
        if ($needFfmpeg -and (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            Write-Success "ffmpeg installed via scoop"
            $script:HasFfmpeg = $true
            $needFfmpeg = $false
        }
    }

    # Show manual instructions for anything still missing
    if ($needRipgrep) {
        Write-Warn "ripgrep not installed (file search will use findstr fallback)"
        Write-Info "  winget install BurntSushi.ripgrep.MSVC"
    }
    if ($needFfmpeg) {
        Write-Warn "ffmpeg not installed (TTS voice messages will be limited)"
        Write-Info "  winget install Gyan.FFmpeg"
    }
}

function Test-ChinaNetwork {
    # Proactively detect Chinese locale → enable Tuna PyPI + npmmirror
    $locale = (Get-Culture).Name
    if ($locale -like "zh-*") {
        $script:UseChinaMirrors = $true
        Write-Info "Chinese locale detected ($locale), using China mirrors"
        return
    }
    # Non-Chinese locale: quick connectivity test (catches VPN-in-China, etc.)
    try {
        Invoke-WebRequest -Uri "https://pypi.org/simple/" -Method Head -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop | Out-Null
    } catch {
        $script:UseChinaMirrors = $true
        Write-Info "PyPI unreachable, enabling China mirrors"
    }
}

# ============================================================================
# Installation
# ============================================================================

function Install-Repository {
    Write-Info "Installing to $InstallDir..."
    
    if (Test-Path $InstallDir) {
        if (Test-Path "$InstallDir\.git") {
            Write-Info "Existing installation found, updating..."
            Push-Location $InstallDir
            git -c windows.appendAtomically=false fetch origin
            git -c windows.appendAtomically=false checkout $Branch
            git -c windows.appendAtomically=false pull origin $Branch
            Pop-Location
        } else {
            Write-Err "Directory exists but is not a git repository: $InstallDir"
            Write-Info "Remove it or choose a different directory with -InstallDir"
            throw "Directory exists but is not a git repository: $InstallDir"
        }
    } else {
        $cloneSuccess = $false

        # Fix Windows git "copy-fd: write returned: Invalid argument" error.
        # Git for Windows can fail on atomic file operations (hook templates,
        # config lock files) due to antivirus, OneDrive, or NTFS filter drivers.
        # The -c flag injects config before any file I/O occurs.
        Write-Info "Configuring git for Windows compatibility..."
        $env:GIT_CONFIG_COUNT = "1"
        $env:GIT_CONFIG_KEY_0 = "windows.appendAtomically"
        $env:GIT_CONFIG_VALUE_0 = "false"
        git config --global windows.appendAtomically false 2>$null

        # Try SSH first, then HTTPS, with -c flag for atomic write fix
        Write-Info "Trying SSH clone..."
        $env:GIT_SSH_COMMAND = "ssh -o BatchMode=yes -o ConnectTimeout=5"
        try {
            git -c windows.appendAtomically=false clone --branch $Branch --no-recurse-submodules $RepoUrlSsh $InstallDir
            if ($LASTEXITCODE -eq 0) { $cloneSuccess = $true }
        } catch { }
        $env:GIT_SSH_COMMAND = $null
        
        if (-not $cloneSuccess) {
            if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue }
            Write-Info "SSH failed, trying HTTPS..."
            try {
                git -c windows.appendAtomically=false clone --branch $Branch --no-recurse-submodules $RepoUrlHttps $InstallDir
                if ($LASTEXITCODE -eq 0) { $cloneSuccess = $true }
            } catch { }
        }

        # Fallback: download ZIP archive (bypasses git file I/O issues entirely)
        if (-not $cloneSuccess) {
            if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue }
            Write-Warn "Git clone failed — downloading ZIP archive instead..."
            $zipPath = "$env:TEMP\bookwormpro-$Branch.zip"
            $extractPath = "$env:TEMP\bookwormpro-extract"
            $zipUrls = @(
                "https://github.com/huakoh/bookwormpro-sale/archive/refs/heads/$Branch.zip",
                "https://portable.bookwormweb.com/bookwormpro-sale.zip"
            )
            $zipDownloaded = $false
            foreach ($zipUrl in $zipUrls) {
                try {
                    Write-Info "Trying: $zipUrl"
                    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing -TimeoutSec 30
                    if ((Test-Path $zipPath) -and (Get-Item $zipPath).Length -gt 1MB) {
                        $zipDownloaded = $true
                        break
                    }
                } catch {
                    Write-Warn "Failed: $_"
                }
            }
            try {
                if (-not $zipDownloaded) { throw "All ZIP download sources failed" }
                if (Test-Path $extractPath) { Remove-Item -Recurse -Force $extractPath }
                Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
                
                # GitHub ZIPs extract to repo-branch/ subdirectory
                $extractedDir = Get-ChildItem $extractPath -Directory | Select-Object -First 1
                if ($extractedDir) {
                    New-Item -ItemType Directory -Force -Path (Split-Path $InstallDir) -ErrorAction SilentlyContinue | Out-Null
                    
                    # Use Copy-Item instead of Move-Item (handles hidden files/.dockerignore/long paths better)
                    if (Test-Path $InstallDir) {
                        Write-Info "Removing existing installation..."
                        Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
                    }
                    
                    Write-Info "Copying files to $InstallDir..."
                    Copy-Item -Path "$($extractedDir.FullName)\*" -Destination $InstallDir -Recurse -Force -ErrorAction Stop
                    Write-Success "Downloaded and extracted"
                    
                    # Verify critical files
                    if (-not (Test-Path "$InstallDir\agent\prompt_builder.py")) {
                        throw "Critical files missing after extraction (agent/prompt_builder.py not found)"
                    }
                    
                    # Initialize git repo so updates work later
                    Push-Location $InstallDir
                    git -c windows.appendAtomically=false init 2>$null
                    git -c windows.appendAtomically=false config windows.appendAtomically false 2>$null
                    git remote add origin $RepoUrlHttps 2>$null
                    Pop-Location
                    Write-Success "Git repo initialized for future updates"
                    
                    $cloneSuccess = $true
                }
                
                # Cleanup temp files
                Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
                Remove-Item -Recurse -Force $extractPath -ErrorAction SilentlyContinue
            } catch {
                Write-Err "ZIP download also failed: $_"
            }
        }

        # Last resort: check if user manually placed the code
        if (-not $cloneSuccess) {
            if ((Test-Path $InstallDir) -and (Test-Path "$InstallDir\agent\run_agent.py")) {
                Write-Warn "Git clone/ZIP failed, but found existing code at $InstallDir"
                Write-Success "Using manually placed code (detected run_agent.py)"
                $cloneSuccess = $true
            }
        }

        if (-not $cloneSuccess) {
            Write-Err ""
            Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
            Write-Host "║  网络问题 — GitHub 无法访问，请选择以下方案:                    ║" -ForegroundColor Yellow
            Write-Host "╠══════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
            Write-Host "║  方案 1: 配置 HTTP 代理后重试                                 ║" -ForegroundColor Cyan
            Write-Host "║    `$env:HTTP_PROXY='http://proxy:port'                ║" -ForegroundColor Cyan
            Write-Host "║    `$env:HTTPS_PROXY='http://proxy:port'               ║" -ForegroundColor Cyan
            Write-Host "║    irm ... | iex                                       ║" -ForegroundColor Cyan
            Write-Host "║                                                        ║" -ForegroundColor Yellow
            Write-Host "║  方案 2: 手动下载 ZIP 后解压到此目录               ║" -ForegroundColor Cyan
            Write-Host "║    $InstallDir" -ForegroundColor Cyan
            Write-Host "║    然后重新运行此脚本即可继续                        ║" -ForegroundColor Cyan
            Write-Host "║                                                        ║" -ForegroundColor Yellow
            Write-Host "║  下载链接:                                          ║" -ForegroundColor Cyan
            Write-Host "║    https://github.com/huakoh/bookwormpro-sale/archive/refs/heads/master.zip" -ForegroundColor Cyan
            Write-Host "║    https://portable.bookwormweb.com/bookwormpro-sale.zip  ║" -ForegroundColor Cyan
            Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
            Write-Host ""
            throw "Failed to download repository (tried git clone SSH, HTTPS, and ZIP)"
        }
    }
    
    # Set per-repo config (harmless if it fails)
    Push-Location $InstallDir
    git -c windows.appendAtomically=false config windows.appendAtomically false 2>$null

    # Submodules (tinker-atropos etc.) are optional — skip for faster install
    Write-Success "Repository ready"
    Pop-Location
    
    Write-Success "Repository ready"
}

function Install-Venv {
    if ($NoVenv) {
        Write-Info "Skipping virtual environment (-NoVenv)"
        return
    }

    Push-Location $InstallDir

    # Health check: venv exists AND python.exe actually runs
    if (Test-Path "venv\Scripts\python.exe") {
        try {
            $ver = & ".\venv\Scripts\python.exe" --version 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver) {
                Write-Success "Virtual environment healthy ($ver)"
                Pop-Location
                return
            }
        } catch {}
    }

    # Remove broken/incomplete venv before recreating
    if (Test-Path "venv") {
        Write-Info "Virtual environment missing or broken, recreating..."
        Remove-Item -Recurse -Force "venv"
    } else {
        Write-Info "Creating virtual environment with Python $PythonVersion..."
    }

    # uv creates the venv; --seed includes pip/setuptools for fallback installs
    & $UvCmd venv venv --python $PythonVersion --seed

    if (-not (Test-Path "venv\Scripts\python.exe")) {
        Pop-Location
        throw "Failed to create virtual environment (venv\Scripts\python.exe not found)"
    }

    Pop-Location

    Write-Success "Virtual environment ready (Python $PythonVersion)"
}

function Install-Dependencies {
    Write-Info "Installing dependencies..."
    
    Push-Location $InstallDir
    
    if (-not $NoVenv) {
        # Tell uv to install into our venv (no activation needed)
        $env:VIRTUAL_ENV = "$InstallDir\venv"
    }
    
    # Build mirror args: uv uses -i only; pip also needs --trusted-host
    $uvMirrorArgs = @()
    $pipMirrorArgs = @()
    if ($script:UseChinaMirrors) {
        $uvMirrorArgs = @("-i", $PypiMirror)
        $pipMirrorArgs = @("-i", $PypiMirror, "--trusted-host", "pypi.tuna.tsinghua.edu.cn")
        Write-Info "Using China PyPI mirror: $PypiMirror"
    }

    # Install main package — retry with verbose output on failure
    $installOk = $false
    foreach ($spec in @(".[all]", ".")) {
        try {
            $output = & $UvCmd pip install -e $spec @uvMirrorArgs 2>&1
            if ($LASTEXITCODE -eq 0) { $installOk = $true; break }
        } catch {}
    }
    if (-not $installOk) {
        Write-Warn "uv editable install failed, trying pip..."
        try {
            & ".\venv\Scripts\python.exe" -m pip install -e "." @pipMirrorArgs 2>&1 | Out-Null
            $installOk = $true
        } catch {}
    }
    # Fallback: if all editable installs failed, add project root to Python path
    if (-not $installOk) {
        Write-Warn "All editable installs failed, adding project to Python path directly..."
    }
    $sitePackages = & ".\venv\Scripts\python.exe" -c "import site; print(site.getsitepackages()[0])" 2>$null
    if ($sitePackages -and (Test-Path $sitePackages)) {
        $pthFile = Join-Path $sitePackages "bookwormpro.pth"
        $pwd.Path | Set-Content -Path $pthFile -Encoding UTF8
    }
    # Safety net: ensure critical third-party deps are present
    $criticalDeps = @("python-dotenv", "pyyaml", "rich", "httpx", "fire", "openai", "anthropic", "cryptography", "prompt_toolkit", "requests", "jinja2", "pydantic", "tenacity", "edge-tts")
    $depsInstalled = $false
    try {
        & $UvCmd pip install @criticalDeps @uvMirrorArgs 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $depsInstalled = $true }
    } catch {}
    if (-not $depsInstalled) {
        Write-Warn "uv pip failed for deps, trying pip directly..."
        try {
            & ".\venv\Scripts\python.exe" -m pip install @criticalDeps @pipMirrorArgs 2>&1 | Out-Null
            $depsInstalled = $true
        } catch {
            Write-Warn "pip also failed: $_"
        }
    }
    # Last resort: try uv pip without mirror (in case mirror was the problem)
    if (-not $depsInstalled -and $script:UseChinaMirrors) {
        Write-Warn "Retrying without mirror..."
        try {
            & $UvCmd pip install @criticalDeps 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { $depsInstalled = $true }
        } catch {}
    }
    if (-not $depsInstalled) {
        Write-Warn "Some dependencies may not have installed. Run manually:"
        Write-Info "  cd $InstallDir"
        Write-Info "  .\venv\Scripts\pip install -i $PypiMirror pyyaml requests rich httpx"
    }

    Write-Success "Main package installed"
    
    # Skip tinker-atropos for sale distribution (RL training backend, not needed)
    if ($env:BOOKWORM_INSTALL_ATROPOS -eq "1" -and (Test-Path "tinker-atropos\pyproject.toml")) {
        Write-Info "Installing tinker-atropos (RL training backend)..."
        try {
            & $UvCmd pip install -e ".\tinker-atropos" 2>&1 | Out-Null
            Write-Success "tinker-atropos installed"
        } catch {
            Write-Warn "tinker-atropos install failed (RL tools may not work)"
        }
    }
    
    Pop-Location
    
    Write-Success "All dependencies installed"
}

function Set-PathVariable {
    Write-Info "Setting up bookworm command..."
    
    if ($NoVenv) {
        $hermesBin = "$InstallDir"
    } else {
        $hermesBin = "$InstallDir\venv\Scripts"
    }
    
    # Add the venv Scripts dir to user PATH so bookworm is globally available
    # On Windows, the bookworm.exe in venv\Scripts\ has the venv Python baked in
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    
    if ($currentPath -notlike "*$hermesBin*") {
        [Environment]::SetEnvironmentVariable(
            "Path",
            "$hermesBin;$currentPath",
            "User"
        )
        Write-Success "Added to user PATH: $hermesBin"
    } else {
        Write-Info "PATH already configured"
    }
    
    # Set BOOKWORMPRO_HOME so the Python code finds config/data in the right place.
    # Only needed on Windows where we install to %LOCALAPPDATA%\bookworm instead
    # of the Unix default ~/.bookwormpro
    $currentHermesHome = [Environment]::GetEnvironmentVariable("BOOKWORMPRO_HOME", "User")
    if (-not $currentHermesHome -or $currentHermesHome -ne $HermesHome) {
        [Environment]::SetEnvironmentVariable("BOOKWORMPRO_HOME", $HermesHome, "User")
        Write-Success "Set BOOKWORMPRO_HOME=$HermesHome"
    }
    $env:BOOKWORMPRO_HOME = $HermesHome
    
    # Fix GBK encoding issues on Chinese Windows
    $currentUtf8 = [Environment]::GetEnvironmentVariable("PYTHONUTF8", "User")
    if (-not $currentUtf8) {
        [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
    }
    $env:PYTHONUTF8 = "1"

    # Update current session
    $env:Path = "$hermesBin;$env:Path"

    Write-Success "bookworm command ready"
}

function Copy-ConfigTemplates {
    Write-Info "Setting up configuration files..."
    
    # Create ~/.bookwormpro directory structure
    New-Item -ItemType Directory -Force -Path "$HermesHome\cron" | Out-Null
    New-Item -ItemType Directory -Force -Path "$HermesHome\sessions" | Out-Null
    New-Item -ItemType Directory -Force -Path "$HermesHome\logs" | Out-Null
    New-Item -ItemType Directory -Force -Path "$HermesHome\pairing" | Out-Null
    New-Item -ItemType Directory -Force -Path "$HermesHome\hooks" | Out-Null
    New-Item -ItemType Directory -Force -Path "$HermesHome\image_cache" | Out-Null
    New-Item -ItemType Directory -Force -Path "$HermesHome\audio_cache" | Out-Null
    New-Item -ItemType Directory -Force -Path "$HermesHome\memories" | Out-Null
    New-Item -ItemType Directory -Force -Path "$HermesHome\skills" | Out-Null

    
    # Create .env
    $envPath = "$HermesHome\.env"
    if (-not (Test-Path $envPath)) {
        $examplePath = "$InstallDir\.env.example"
        if (Test-Path $examplePath) {
            Copy-Item $examplePath $envPath
            Write-Success "Created ~/.bookwormpro/.env from template"
        } else {
            New-Item -ItemType File -Force -Path $envPath | Out-Null
            Write-Success "Created ~/.bookwormpro/.env"
        }
    } else {
        Write-Info "~/.bookwormpro/.env already exists, keeping it"
    }

    # Seed .gitignore — protects against accidental secret commit if user
    # later runs `git init` here (e.g. for backup to private repo).
    # See docker/seed/.gitignore for rationale.
    $gitignorePath = "$HermesHome\.gitignore"
    if (-not (Test-Path $gitignorePath)) {
        $seedPath = "$InstallDir\docker\seed\.gitignore"
        if (Test-Path $seedPath) {
            Copy-Item $seedPath $gitignorePath
            Write-Success "Seeded ~/.bookwormpro/.gitignore (secret-bearing paths excluded)"
        }
    } else {
        Write-Info "~/.bookwormpro/.gitignore already exists, keeping it"
    }
    
    # Create config.yaml
    $configPath = "$HermesHome\config.yaml"
    if (-not (Test-Path $configPath)) {
        $examplePath = "$InstallDir\cli-config.yaml.example"
        if (Test-Path $examplePath) {
            Copy-Item $examplePath $configPath
            Write-Success "Created ~/.bookwormpro/config.yaml from template"
        }
    } else {
        Write-Info "~/.bookwormpro/config.yaml already exists, keeping it"
    }
    
    # Create SOUL.md if it doesn't exist (global persona file)
    $soulPath = "$HermesHome\SOUL.md"
    if (-not (Test-Path $soulPath)) {
        @"
# BookwormPRO Persona

<!-- 
This file defines the agent's personality and tone.
The agent will embody whatever you write here.
Edit this to customize how BookwormPRO communicates with you.

Examples:
  - "You are a warm, playful assistant who uses kaomoji occasionally."
  - "You are a concise technical expert. No fluff, just facts."
  - "You speak like a friendly coworker who happens to know everything."

This file is loaded fresh each message -- no restart needed.
Delete the contents (or this file) to use the default personality.
-->
"@ | Set-Content -Path $soulPath -Encoding UTF8
        Write-Success "Created ~/.bookwormpro/SOUL.md (edit to customize personality)"
    }
    
    Write-Success "Configuration directory ready: ~/.bookwormpro/"
    
    # Seed bundled skills into ~/.bookwormpro/skills/ (manifest-based, one-time per skill)
    Write-Info "Syncing bundled skills to ~/.bookwormpro/skills/ ..."
    $pythonExe = "$InstallDir\venv\Scripts\python.exe"
    $syncOk = $false
    if (Test-Path $pythonExe) {
        try {
            & $pythonExe "$InstallDir\tools\skills_sync.py" 2>$null
            if ($LASTEXITCODE -eq 0) { $syncOk = $true }
        } catch {}
    }
    if ($syncOk) {
        Write-Success "Skills synced to ~/.bookwormpro/skills/"
    } else {
        $bundledSkills = "$InstallDir\skills"
        $userSkills = "$HermesHome\skills"
        if (Test-Path $bundledSkills) {
            Copy-Item -Path "$bundledSkills\*" -Destination $userSkills -Recurse -Force -ErrorAction SilentlyContinue
            if (Test-Path "$InstallDir\optional-skills") {
                Copy-Item -Path "$InstallDir\optional-skills\*" -Destination $userSkills -Recurse -Force -ErrorAction SilentlyContinue
            }
            Write-Success "Skills copied to ~/.bookwormpro/skills/"
        }
    }
}

function Install-NodeDeps {
    if (-not $HasNode) {
        Write-Info "Skipping Node.js dependencies (Node not installed)"
        return
    }

    # Set npm China mirror when needed
    $npmRegArgs = @()
    if ($script:UseChinaMirrors) {
        $npmRegArgs = @("--registry", $NpmMirror)
        Write-Info "Using China npm mirror: $NpmMirror"
    }

    Push-Location $InstallDir

    if (Test-Path "package.json") {
        Write-Info "Installing Node.js dependencies (browser tools, may take a minute)..."
        try {
            npm install --no-fund --no-audit @npmRegArgs
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Node.js dependencies installed"
            } else {
                Write-Warn "npm install exited with code $LASTEXITCODE (browser tools may not work)"
            }
        } catch {
            Write-Warn "npm install failed: $_ (browser tools may not work)"
        }
    }

    # Install TUI dependencies
    $tuiDir = "$InstallDir\ui-tui"
    if (Test-Path "$tuiDir\package.json") {
        Write-Info "Installing TUI dependencies..."
        Push-Location $tuiDir
        try {
            npm install --no-fund --no-audit @npmRegArgs
            if ($LASTEXITCODE -eq 0) {
                Write-Success "TUI dependencies installed"
            } else {
                Write-Warn "TUI npm exited with code $LASTEXITCODE (bookworm --tui may not work)"
            }
        } catch {
            Write-Warn "TUI npm install failed: $_ (bookworm --tui may not work)"
        }
        Pop-Location
    }


    
    Pop-Location
}

function Invoke-SetupWizard {
    if ($SkipSetup) {
        Write-Info "Skipping setup wizard (-SkipSetup)"
        return
    }
    
    Write-Host ""
    Write-Info "Starting setup wizard..."
    Write-Host ""
    
    Push-Location $InstallDir
    
    # Run bookworm setup using the venv Python directly (no activation needed)
    if (-not $NoVenv) {
        & ".\venv\Scripts\python.exe" -m bwm_cli.main setup
    } else {
        python -m bwm_cli.main setup
    }
    
    Pop-Location
}

function Start-GatewayIfConfigured {
    $envPath = "$HermesHome\.env"
    if (-not (Test-Path $envPath)) { return }

    $hasMessaging = $false
    $content = Get-Content $envPath -ErrorAction SilentlyContinue
    foreach ($var in @("TELEGRAM_BOT_TOKEN", "DISCORD_BOT_TOKEN", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "WHATSAPP_ENABLED")) {
        $match = $content | Where-Object { $_ -match "^${var}=.+" -and $_ -notmatch "your-token-here" }
        if ($match) { $hasMessaging = $true; break }
    }

    if (-not $hasMessaging) { return }

    $hermesCmd = "$InstallDir\venv\Scripts\bookworm.exe"
    if (-not (Test-Path $hermesCmd)) {
        $hermesCmd = "bookworm"
    }

    # If WhatsApp is enabled but not yet paired, run foreground for QR scan
    $whatsappEnabled = $content | Where-Object { $_ -match "^WHATSAPP_ENABLED=true" }
    $whatsappSession = "$HermesHome\whatsapp\session\creds.json"
    if ($whatsappEnabled -and -not (Test-Path $whatsappSession)) {
        Write-Host ""
        Write-Info "WhatsApp is enabled but not yet paired."
        Write-Info "Running 'bookworm whatsapp' to pair via QR code..."
        Write-Host ""
        $response = Read-Host "Pair WhatsApp now? [Y/n]"
        if ($response -eq "" -or $response -match "^[Yy]") {
            try {
                & $hermesCmd whatsapp
            } catch {
                # Expected after pairing completes
            }
        }
    }

    Write-Host ""
    Write-Info "Messaging platform token detected!"
    Write-Info "The gateway handles messaging platforms and cron job execution."
    Write-Host ""
    $response = Read-Host "Would you like to start the gateway now? [Y/n]"

    if ($response -eq "" -or $response -match "^[Yy]") {
        Write-Info "Starting gateway in background..."
        try {
            $logFile = "$HermesHome\logs\gateway.log"
            Start-Process -FilePath $hermesCmd -ArgumentList "gateway" `
                -RedirectStandardOutput $logFile `
                -RedirectStandardError "$HermesHome\logs\gateway-error.log" `
                -WindowStyle Hidden
            Write-Success "Gateway started! Your bot is now online."
            Write-Info "Logs: $logFile"
            Write-Info "To stop: close the gateway process from Task Manager"
        } catch {
            Write-Warn "Failed to start gateway. Run manually: bookworm gateway"
        }
    } else {
        Write-Info "Skipped. Start the gateway later with: bookworm gateway"
    }
}

function Write-Completion {
    Write-Host ""
    Write-Host "┌─────────────────────────────────────────────────────────┐" -ForegroundColor Green
    Write-Host "│              [成功] Installation Complete!                   │" -ForegroundColor Green
    Write-Host "└─────────────────────────────────────────────────────────┘" -ForegroundColor Green
    Write-Host ""
    
    # Show file locations
    Write-Host "📁 Your files:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   Config:    " -NoNewline -ForegroundColor Yellow
    Write-Host "$HermesHome\config.yaml"
    Write-Host "   API Keys:  " -NoNewline -ForegroundColor Yellow
    Write-Host "$HermesHome\.env"
    Write-Host "   Data:      " -NoNewline -ForegroundColor Yellow
    Write-Host "$HermesHome\cron\, sessions\, logs\"
    Write-Host "   Code:      " -NoNewline -ForegroundColor Yellow
    Write-Host "$HermesHome\bookwormpro\"
    Write-Host ""
    
    Write-Host "─────────────────────────────────────────────────────────" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[启动] Commands:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   bookworm              " -NoNewline -ForegroundColor Green
    Write-Host "Start chatting"
    Write-Host "   bookworm setup        " -NoNewline -ForegroundColor Green
    Write-Host "Configure API keys & settings"
    Write-Host "   bookworm config       " -NoNewline -ForegroundColor Green
    Write-Host "View/edit configuration"
    Write-Host "   bookworm config edit  " -NoNewline -ForegroundColor Green
    Write-Host "Open config in editor"
    Write-Host "   bookworm gateway      " -NoNewline -ForegroundColor Green
    Write-Host "Start messaging gateway (Telegram, Discord, etc.)"
    Write-Host "   bookworm update       " -NoNewline -ForegroundColor Green
    Write-Host "Update to latest version"
    Write-Host ""
    
    Write-Host "─────────────────────────────────────────────────────────" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "* Restart your terminal for PATH changes to take effect" -ForegroundColor Yellow
    Write-Host ""
    
    if (-not $HasNode) {
        Write-Host "Note: Node.js could not be installed automatically." -ForegroundColor Yellow
        Write-Host "Browser tools need Node.js. Install manually:" -ForegroundColor Yellow
        Write-Host "  https://nodejs.org/en/download/" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if (-not $HasRipgrep) {
        Write-Host "Note: ripgrep (rg) was not installed. For faster file search:" -ForegroundColor Yellow
        Write-Host "  winget install BurntSushi.ripgrep.MSVC" -ForegroundColor Yellow
        Write-Host ""
    }
}

# ============================================================================
# Main
# ============================================================================

function Main {
    Write-Banner
    Test-ChinaNetwork

    if (-not (Install-Uv)) { throw "uv installation failed — cannot continue" }
    if (-not (Test-Python)) { throw "Python $PythonVersion not available — cannot continue" }
    if (-not (Test-Git)) { throw "Git not found — install from https://git-scm.com/download/win" }
    Test-Node              # Auto-installs if missing
    Install-SystemPackages  # ripgrep + ffmpeg in one step
    
    Install-Repository
    Install-Venv
    # Environment vars and config FIRST — must succeed even if deps fail
    Set-PathVariable
    Copy-ConfigTemplates
    # Dependencies are non-fatal — partial install is usable
    try {
        Install-Dependencies
    } catch {
        Write-Warn "Dependency install had errors: $_"
        Write-Warn "You can fix later with: uv pip install --python .\venv\Scripts\python.exe -r requirements.txt"
    }
    Install-NodeDeps
    # Create start.py fallback entry point (works even without editable install)
    $startPy = "$InstallDir\start.py"
    if (-not (Test-Path $startPy)) {
        "import sys;sys.path.insert(0,r'$InstallDir');from bwm_cli.main import main;main()" | Set-Content -Path $startPy -Encoding UTF8
    }
    # Create bookworm.bat fallback (works even without console_scripts)
    $batPath = "$InstallDir\bookworm.bat"
    if (-not (Test-Path $batPath)) {
        "@echo off`r`n`"%~dp0venv\Scripts\python.exe`" `"%~dp0start.py`" %*" | Set-Content -Path $batPath -Encoding ASCII
    }
    Write-Info "Downloading 7-day trial license..."
    try {
        & ".\venv\Scripts\python.exe" -c "
import sys; sys.path.insert(0, r".");
from bwm_cli.license import do_trial; do_trial()
" 2>&1 | Out-String -Stream | ForEach-Object { Write-Host "  $_" }
    } catch {
        Write-Warn "Trial license activation skipped (network issue)"
    }
    Start-GatewayIfConfigured
    
    Write-Completion
}

# Wrap in try/catch so errors don't kill the terminal when run via:
#   irm https://...install.ps1 | iex
# (exit/throw inside iex kills the entire PowerShell session)
try {
    Main
} catch {
    try { [Console]::WriteLine("") } catch {}
    Write-Err "Installation failed: $_"
    try { [Console]::WriteLine("") } catch {}
    Write-Info "If the error is unclear, try downloading and running the script directly:"
    Write-Info "  Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/huakoh/bookwormpro-sale/master/scripts/install.ps1' -OutFile install.ps1"
    Write-Info "  .\install.ps1"
    try { [Console]::WriteLine("") } catch {}
}
