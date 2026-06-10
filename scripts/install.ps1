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
    
    # Let uv find or install Python
    try {
        $pythonPath = & $UvCmd python find $PythonVersion 2>$null
        if ($pythonPath) {
            $ver = & $pythonPath --version 2>$null
            Write-Success "Python found: $ver"
            return $true
        }
    } catch { }
    
    # Python not found — use uv to install it (no admin needed!)
    Write-Info "Python $PythonVersion not found, installing via uv..."
    try {
        $uvOutput = & $UvCmd python install $PythonVersion 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pythonPath = & $UvCmd python find $PythonVersion 2>$null
            if ($pythonPath) {
                $ver = & $pythonPath --version 2>$null
                Write-Success "Python installed: $ver"
                return $true
            }
        } else {
            Write-Warn "uv python install output:"
            Write-Host $uvOutput -ForegroundColor DarkGray
        }
    } catch {
        Write-Warn "uv python install error: $_"
    }

    # uv downloads from GitHub which is often blocked in China — enable mirrors
    $script:UseChinaMirrors = $true

    # Fallback: try winget install (uses Microsoft CDN, works in China)
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "uv download failed (likely network issue), trying winget..."
        try {
            & winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
                # Refresh PATH for current session
                $machPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
                $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
                $env:Path = "$machPath;$userPath"
                $pythonPath = & $UvCmd python find $PythonVersion 2>$null
                if (-not $pythonPath) { $pythonPath = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source }
                if ($pythonPath) {
                    $ver = & $pythonPath --version 2>$null
                    Write-Success "Python installed via winget: $ver"
                    return $true
                }
            }
        } catch {
            Write-Warn "winget install also failed: $_"
        }
    }

    # Fallback: check if ANY Python 3.10+ is already available on the system
    Write-Info "Trying to find any existing Python 3.10+..."
    foreach ($fallbackVer in @("3.12", "3.13", "3.11", "3.10")) {
        try {
            $pythonPath = & $UvCmd python find $fallbackVer 2>$null
            if ($pythonPath) {
                $ver = & $pythonPath --version 2>$null
                Write-Success "Found fallback: $ver"
                $script:PythonVersion = $fallbackVer
                return $true
            }
        } catch { }
    }

    # Fallback: try system python
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $sysVer = python --version 2>$null
        if ($sysVer -match "3\.(1[0-9]|[1-9][0-9])") {
            Write-Success "Using system Python: $sysVer"
            return $true
        }
    }
    
    Write-Err "Failed to install Python $PythonVersion"
    Write-Info "Install Python 3.11 manually, then re-run this script:"
    Write-Info "  https://www.python.org/downloads/"
    Write-Info "  Or: winget install Python.Python.3.11"
    return $false
}

function Test-Git {
    Write-Info "Checking Git..."
    
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $version = git --version
        Write-Success "Git found ($version)"
        return $true
    }
    
    Write-Err "Git not found"
    Write-Info "Please install Git from:"
    Write-Info "  https://git-scm.com/download/win"
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
                    Move-Item $extractedDir.FullName $InstallDir -Force
                    Write-Success "Downloaded and extracted"
                    
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

        if (-not $cloneSuccess) {
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
    
    Write-Info "Creating virtual environment with Python $PythonVersion..."
    
    Push-Location $InstallDir
    
    if (Test-Path "venv") {
        Write-Info "Virtual environment already exists, recreating..."
        Remove-Item -Recurse -Force "venv"
    }
    
    # uv creates the venv; --seed includes pip/setuptools for fallback installs
    & $UvCmd venv venv --python $PythonVersion --seed
    
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
        Write-Info "Installing Node.js dependencies (browser tools)..."
        try {
            npm install --silent @npmRegArgs 2>&1 | Out-Null
            Write-Success "Node.js dependencies installed"
        } catch {
            Write-Warn "npm install failed (browser tools may not work)"
        }
    }

    # Install TUI dependencies
    $tuiDir = "$InstallDir\ui-tui"
    if (Test-Path "$tuiDir\package.json") {
        Write-Info "Installing TUI dependencies..."
        Push-Location $tuiDir
        try {
            npm install --silent @npmRegArgs 2>&1 | Out-Null
            Write-Success "TUI dependencies installed"
        } catch {
            Write-Warn "TUI npm install failed (bookworm --tui may not work)"
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
    Invoke-SetupWizard
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
