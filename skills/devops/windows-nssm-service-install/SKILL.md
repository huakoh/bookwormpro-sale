---
name: windows-nssm-service-install
description: |
  将任意 Python 脚本安装为 Windows 系统服务（开机自启），基于 NSSM (Non-Sucking Service Manager)。
  覆盖：winget 安装 NSSM、nssm install/set/start/stop/restart/status/remove 命令、管理员权限检测、
  AppExit 三参数语法、CRLF 兼容性陷阱、PowerShell RunAs 提权。
  触发词：Windows 服务、开机自启、nssm、Windows service、boot start
---

# Windows NSSM 服务安装

## 1. 安装 NSSM

```bash
# winget (最可靠，nssm.cc 常 503)
winget install --id NSSM.NSSM -e --accept-source-agreements --accept-package-agreements

# 备选: choco (需要管理员)
choco install nssm -y

# 手动下载: nssm.cc → 解压 win64/nssm.exe
```

## 2. 服务管理脚本模板

```python
import ctypes, subprocess, sys
from pathlib import Path

SERVICE_NAME = "my-service"

def _nssm_path() -> str:
    """找到 nssm.exe"""
    bundled = Path(__file__).parent / "nssm.exe"
    if bundled.exists():
        return str(bundled)
    import shutil
    found = shutil.which("nssm")
    if found:
        return found
    # Winget 默认路径
    pkg = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    for exe in pkg.glob("NSSM.NSSM_*/**/win64/nssm.exe"):
        return str(exe)
    raise FileNotFoundError("nssm.exe not found")

def _is_admin() -> bool:
    return ctypes.windll.shell32.IsUserAnAdmin() != 0

def _run_nssm(args: list) -> subprocess.CompletedProcess:
    return subprocess.run([str(_nssm_path())] + args, capture_output=True, text=True)

def install():
    if not _is_admin():
        sys.exit("需要管理员权限。以管理员身份运行 cmd/PowerShell 后重试。")
    
    # 1. 安装服务
    r = _run_nssm(["install", SERVICE_NAME, sys.executable, __file__, "run"])
    if r.returncode != 0:
        sys.exit(f"install 失败: {r.stderr}")
    
    # 2. 配置参数
    config = {
        "AppDirectory": str(Path.cwd()),
        "DisplayName": "My Service Description",
        "Start": "SERVICE_AUTO_START",
        "AppStdout": str(Path.home() / "logs" / "stdout.log"),
        "AppStderr": str(Path.home() / "logs" / "stderr.log"),
        "AppRotateFiles": "1",
        "AppRotateOnline": "1",
        "AppRotateBytes": "10485760",
    }
    for k, v in config.items():
        r = _run_nssm(["set", SERVICE_NAME, k, v])
        if r.returncode != 0:
            _run_nssm(["remove", SERVICE_NAME, "confirm"])  # 清理
            sys.exit(f"set {k} 失败: {r.stderr}")
    
    # 3. AppExit 需要 3 参数形式! (不是 "AppExit Restart")
    r = _run_nssm(["set", SERVICE_NAME, "AppExit", "Default", "Restart"])
    if r.returncode != 0:
        _run_nssm(["remove", SERVICE_NAME, "confirm"])
        sys.exit(f"set AppExit 失败: {r.stderr}")
    
    print("[成功] 服务已安装，开机自启")

def uninstall():
    if not _is_admin():
        sys.exit("需要管理员权限")
    _run_nssm(["stop", SERVICE_NAME])
    r = _run_nssm(["remove", SERVICE_NAME, "confirm"])
    if r.returncode == 0:
        print("[成功] 服务已卸载")

def start():   _run_nssm(["start", SERVICE_NAME])
def stop():    _run_nssm(["stop", SERVICE_NAME])
def restart(): _run_nssm(["restart", SERVICE_NAME])
def status():  print(_run_nssm(["status", SERVICE_NAME]).stdout.strip())
```

## 3. 关键陷阱

### 3.1 AppExit 是三参数命令
```bash
# 错误 (会报 "Parameter requires a subparameter")
nssm set svc AppExit Restart

# 正确
nssm set svc AppExit Default Restart
nssm set svc AppExit 1 Restart        # 退出码 1 时重启
```

### 3.2 nssm install 可能不加管理员也能成功，但 nssm set 必须管理员
总是先检测 `_is_admin()`，否则 `set` 阶段全失败导致半成品服务。

### 3.3 Windows CRLF 与 patch 工具
BookwormPRO 的 `patch` 工具在 Windows Git Bash 上对 CRLF 文件经常失败 ("wrote X, read back Y")。
多行修改用 `write_file` 重写整个文件，不要用 `patch`。

### 3.4 PowerShell RunAs 不捕获 stdout
```bash
# 提权运行，但看不到脚本输出
powershell -Command "Start-Process python -ArgumentList 'script.py','install' -Verb RunAs -Wait"
# 用 nssm status 验证结果，不依赖脚本输出
```

### 3.5 status 命令不需要管理员
```python
def status():
    # nssm status 可以从非管理员用户查询
    result = _run_nssm(["status", SERVICE_NAME])
    print(result.stdout.strip())
```

### 3.6 Windows 服务以 SYSTEM 账户运行 — Path.home() 陷阱
Windows 服务默认以 SYSTEM 身份运行，不是当前用户。导致：
- `Path.home()` → `C:\Windows\System32\config\systemprofile`
- `~/.bookwormpro/.env` 不在那个目录 → 所有凭据/环境变量静默加载失败
- Gateway 日志显示 "No messaging platforms enabled" 尽管 .env 配置正确

**症状：** 交互式运行正常，但作为服务运行时找不到配置。

**修复：** 用 NSSM AppEnvironmentExtra 注入关键环境变量
```bash
# 例: 让 Gateway 找到用户 .env
nssm set bookworm-gateway AppEnvironmentExtra BOOKWORMPRO_HOME=C:\Users\BOOKWORMPRO_USER\.bookwormpro

# 也可以直接注入凭据 (不推荐，会写入注册表)
nssm set bookworm-gateway AppEnvironmentExtra WECOM_BOT_ID=xxx
nssm set bookworm-gateway AppEnvironmentExtra WECOM_SECRET=yyy
```

**验证：**
```bash
nssm get <name> AppEnvironmentExtra
# 应输出: BOOKWORMPRO_HOME=C:\Users\<user>\.bookwormpro
```

### 3.7 nssm install 成功但 nssm set 需要管理员
`nssm install` 在部分 Windows 配置下可能不需要管理员就能创建服务，但 `nssm set` 总是需要管理员。
这会导致：服务已创建但 AppDirectory/Start/AppExit 等全部错误 → 半成品服务。
**必须在 install() 开头检测 `_is_admin()` 并 exit**，不要依赖 nssm 自己报错。

## 4. NSSM 常用命令速查

```bash
nssm install <name> <program> [args...]
nssm set <name> <key> <value>
nssm set <name> AppExit Default Restart
nssm get <name> <key>           # 读取配置
nssm start <name>
nssm stop <name>
nssm restart <name>
nssm status <name>              # SERVICE_RUNNING / SERVICE_STOPPED
nssm remove <name> confirm      # 卸载 (需要 "confirm" 字面量)
nssm dump <name>                # 导出全部配置
```

## 5. 验证清单

安装完成后检查:
```bash
nssm status <name>              # 应为 SERVICE_STOPPED
nssm get <name> AppDirectory    # 应为正确的工作目录
nssm get <name> Start           # 应为 SERVICE_AUTO_START
nssm get <name> AppStdout       # 应为正确的日志路径
```
