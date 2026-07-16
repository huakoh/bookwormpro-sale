"""
BookwormPRO Gateway — Windows Service Wrapper (NSSM)

Launched by NSSM as SYSTEM. Sets up user environment before importing
the gateway so that ~/.bookwormpro/.env and ~/.bookwormpro/config.yaml
are found correctly.

Install:
    python gateway_service.py install
Uninstall:
    python gateway_service.py uninstall
Start/Stop/Restart:
    python gateway_service.py start|stop|restart
Status:
    python gateway_service.py status
"""
import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path


SERVICE_NAME = "bookworm-gateway"

# ── Paths ────────────────────────────────────────────────────────
USER_HOME         = r"C:\Users\leesu"
HERMES_HOME       = USER_HOME + r"\.bookwormpro"
PROJECT_ROOT      = r"C:\Users\leesu\BookwormPRO"
PYTHON_EXE        = r"C:\Users\leesu\AppData\Local\Programs\Python\Python312\python.exe"
BOOKWORM_SCRIPT   = r"C:\Users\leesu\AppData\Local\Programs\Python\Python312\Scripts\bookworm"

LOG_DIR = os.path.join(HERMES_HOME, "logs")

# ── nssm.exe location ────────────────────────────────────────────
def _find_nssm() -> str:
    # Winget install path (already confirmed)
    winget_base = os.path.join(USER_HOME, "AppData", "Local", "Microsoft", "WinGet", "Packages")
    nssm_pkg = r"NSSM.NSSM_Microsoft.Winget.Source_8wekyb3d8bbwe"
    pkg_dir = os.path.join(winget_base, nssm_pkg)
    if os.path.isdir(pkg_dir):
        candidates = sorted(
            (d for d in os.listdir(pkg_dir) if os.path.isdir(os.path.join(pkg_dir, d))),
            reverse=True
        )
        for c in candidates:
            exe = os.path.join(pkg_dir, c, "win64", "nssm.exe")
            if os.path.isfile(exe):
                return exe
    # Fallback: PATH
    found = shutil.which("nssm")
    if found:
        return found
    raise FileNotFoundError("nssm.exe not found")

NSSM = _find_nssm()

# ── Helpers ──────────────────────────────────────────────────────
def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def _run_nssm(args: list) -> subprocess.CompletedProcess:
    return subprocess.run([NSSM] + args, capture_output=True, text=True)

def _nssm_status() -> str:
    r = _run_nssm(["status", SERVICE_NAME])
    return r.stdout.strip()

# ── Install ──────────────────────────────────────────────────────
def install():
    if not _is_admin():
        print("[错误] 需要管理员权限。请以管理员身份运行 PowerShell 或 cmd 后重试。")
        sys.exit(1)

    print(f"服务名: {SERVICE_NAME}")
    print(f"执行文件: {PYTHON_EXE}")
    print()

    # 1. Install the service
    r = _run_nssm([
        "install", SERVICE_NAME,
        PYTHON_EXE,
        "-u", "-m", "gateway.run"
    ])
    if r.returncode != 0:
        sys.exit(f"NSSM install 失败: {r.stderr}")
    print("[1/5] 服务已注册")

    # 2. AppDirectory — gateway.run needs to find its modules
    r = _run_nssm(["set", SERVICE_NAME, "AppDirectory", PROJECT_ROOT])
    if r.returncode != 0:
        _run_nssm(["remove", SERVICE_NAME, "confirm"])
        sys.exit(f"set AppDirectory 失败: {r.stderr}")
    print("[2/5] 工作目录已设置")

    # 3. Auto-start
    r = _run_nssm(["set", SERVICE_NAME, "Start", "SERVICE_AUTO_START"])
    if r.returncode != 0:
        _run_nssm(["remove", SERVICE_NAME, "confirm"])
        sys.exit(f"set Start 失败: {r.stderr}")
    print("[3/5] 开机自启已启用")

    # 4. Logging
    log_stdout = os.path.join(LOG_DIR, "gateway-stdout.log")
    log_stderr = os.path.join(LOG_DIR, "gateway-stderr.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    r = _run_nssm(["set", SERVICE_NAME, "AppStdout", log_stdout])
    if r.returncode != 0:
        _run_nssm(["remove", SERVICE_NAME, "confirm"])
        sys.exit(f"set AppStdout 失败: {r.stderr}")
    r = _run_nssm(["set", SERVICE_NAME, "AppStderr", log_stderr])
    if r.returncode != 0:
        _run_nssm(["remove", SERVICE_NAME, "confirm"])
        sys.exit(f"set AppStderr 失败: {r.stderr}")
    r = _run_nssm(["set", SERVICE_NAME, "AppRotateFiles", "1"])
    if r.returncode != 0:
        _run_nssm(["remove", SERVICE_NAME, "confirm"])
        sys.exit(f"set AppRotateFiles 失败: {r.stderr}")
    print("[4/5] 日志已配置")

    # 5. Environment: service runs as SYSTEM → needs BOOKWORMPRO_HOME
    #    Also set PATH so Python and scripts are found
    python_dir = os.path.dirname(PYTHON_EXE)
    scripts_dir = os.path.dirname(BOOKWORM_SCRIPT)
    env_extra = (
        f"BOOKWORMPRO_HOME={HERMES_HOME} "
        f"USERPROFILE={USER_HOME} "
        f"PATH={python_dir};{scripts_dir};%PATH%"
    )
    r = _run_nssm(["set", SERVICE_NAME, "AppEnvironmentExtra", env_extra])
    if r.returncode != 0:
        _run_nssm(["remove", SERVICE_NAME, "confirm"])
        sys.exit(f"set AppEnvironmentExtra 失败: {r.stderr}")
    print("[5/5] 环境变量已注入")

    # 6. Restart policy
    r = _run_nssm(["set", SERVICE_NAME, "AppExit", "Default", "Restart"])
    if r.returncode != 0:
        _run_nssm(["remove", SERVICE_NAME, "confirm"])
        sys.exit(f"set AppExit 失败: {r.stderr}")
    print("[6/6] 崩溃自动重启已配置")

    # 7. Display name
    r = _run_nssm(["set", SERVICE_NAME, "DisplayName", "BookwormPRO Gateway"])
    if r.returncode != 0:
        print(f"[警告] set DisplayName 失败: {r.stderr}")

    print()
    print(f"[成功] {SERVICE_NAME} 服务已安装并配置为开机自启")
    print(f"        运行:   nssm start {SERVICE_NAME}")
    print(f"        状态:   nssm status {SERVICE_NAME}")
    print(f"        日志:   {log_stdout}")


# ── Uninstall ────────────────────────────────────────────────────
def uninstall():
    if not _is_admin():
        print("[错误] 需要管理员权限")
        sys.exit(1)
    _run_nssm(["stop", SERVICE_NAME])
    r = _run_nssm(["remove", SERVICE_NAME, "confirm"])
    if r.returncode == 0:
        print(f"[成功] {SERVICE_NAME} 服务已卸载")

# ── Start / Stop / Restart / Status ──────────────────────────────
def start():
    r = _run_nssm(["start", SERVICE_NAME])
    if r.returncode == 0:
        print(f"[成功] {SERVICE_NAME} 已启动")
    else:
        print(f"[失败] {r.stderr.strip()}")

def stop():
    r = _run_nssm(["stop", SERVICE_NAME])
    if r.returncode == 0:
        print(f"[成功] {SERVICE_NAME} 已停止")
    else:
        print(f"[失败] {r.stderr.strip()}")

def restart():
    _run_nssm(["stop", SERVICE_NAME])
    import time
    time.sleep(2)
    start()

def status():
    print(_nssm_status())

# ── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python gateway_service.py [install|uninstall|start|stop|restart|status]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    actions = {
        "install": install, "uninstall": uninstall,
        "start": start, "stop": stop,
        "restart": restart, "status": status,
    }
    if cmd not in actions:
        print(f"未知命令: {cmd}")
        sys.exit(1)
    actions[cmd]()
