#!/usr/bin/env python3
"""
BookwormPRO EXE 打包指南 + 自动检测脚本
帮助用户将安装向导打包成 Windows .exe

用法:
  python scripts/build_exe.py          # 检测环境，给出打包指引
  python scripts/build_exe.py --run    # 如果有 PyInstaller，直接打包
"""

import sys, subprocess, shutil
from pathlib import Path

SRC = Path(__file__).parent.parent

def detect_pyinstaller():
    """检测 PyInstaller 是否可用"""
    try:
        result = subprocess.run(['pyinstaller', '--version'], capture_output=True, text=True)
        return result.stdout.strip()
    except FileNotFoundError:
        return None

def detect_nsis():
    """检测 NSIS 是否安装"""
    nsis_paths = [
        r'C:\Program Files (x86)\NSIS\makensis.exe',
        r'C:\Program Files\NSIS\makensis.exe',
    ]
    for p in nsis_paths:
        if Path(p).exists():
            return p
    return None

def build_exe():
    """用 PyInstaller 打包 setup_wizard.py"""
    print("🔨 打包 BookwormPRO 安装向导...\n")
    
    wizard = SRC / 'scripts' / 'setup_wizard.py'
    dist = SRC / 'dist'
    
    cmd = [
        'pyinstaller',
        '--onefile',
        '--console',
        '--name', 'BookwormPRO-Setup',
        '--add-data', f'skills{";"}skills' if sys.platform == 'win32' else f'skills:skills',
        '--add-data', f'soul{";"}soul' if sys.platform == 'win32' else f'soul:soul',
        '--add-data', f'config{";"}config' if sys.platform == 'win32' else f'config:config',
        str(wizard),
    ]
    
    subprocess.run(cmd, cwd=SRC)
    
    exe = dist / 'BookwormPRO-Setup.exe'
    if exe.exists():
        size = exe.stat().st_size / (1024 * 1024)
        print(f"\n✅ 打包成功: {exe} ({size:.1f} MB)")
    else:
        print("\n❌ 打包失败，检查上方错误日志")

def main():
    print("""
  ╔══════════════════════════════════════════════════════╗
  ║         BookwormPRO EXE 打包工具                      ║
  ╚══════════════════════════════════════════════════════╝
    """)
    
    pyinstaller = detect_pyinstaller()
    nsis = detect_nsis()
    
    print(f"  PyInstaller: {'✅ ' + pyinstaller if pyinstaller else '❌ 未安装'}")
    print(f"  NSIS:        {'✅ ' + nsis if nsis else '⚪ 未安装（可选）'}")
    print()
    
    if '--run' in sys.argv:
        if pyinstaller:
            build_exe()
        else:
            print("❌ PyInstaller 未安装，无法打包")
            print("   安装: pip install pyinstaller")
        return
    
    # 给出打包指引
    print("  📋 打包方案：\n")
    print("  方案 A: PyInstaller 单文件 EXE（推荐）")
    print("  ─────────────────────────────────────")
    print("  1. pip install pyinstaller")
    print("  2. python scripts/build_exe.py --run")
    print("  3. dist/BookwormPRO-Setup.exe 即发布包\n")
    
    print("  方案 B: NSIS 专业安装向导")
    print("  ─────────────────────────────────────")
    print("  1. 安装 NSIS: https://nsis.sourceforge.io")
    print("  2. 先跑方案 A 生成 EXE")
    print("  3. 用 NSIS 包装成安装向导（许可协议+选择目录+桌面快捷方式）")
    print("  4. 参考: scripts/installer.nsi\n")
    
    print("  方案 C: 纯 ZIP 分发（零依赖）")
    print("  ─────────────────────────────────────")
    print("  python scripts/make_release.py")
    print("  用户解压后双击 install.bat\n")
    
    if not pyinstaller:
        print(f"  ⚠ 当前推荐方案 C（ZIP），方案 A 需先安装 PyInstaller")

if __name__ == '__main__':
    main()
