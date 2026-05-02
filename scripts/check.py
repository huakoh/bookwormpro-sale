#!/usr/bin/env python3
"""
BookwormPRO 安装验证
检测所有组件是否就绪，输出彩色诊断报告
"""

import sys
import os
from pathlib import Path

C = {'R': '\033[91m', 'G': '\033[92m', 'Y': '\033[93m', 'B': '\033[94m', 'X': '\033[0m'}
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except:
        for k in C: C[k] = ''

HOME = Path.home()
TARGET = HOME / '.bookwormpro'
ALL_OK = True

def check(name, condition, detail=""):
    global ALL_OK
    if condition:
        print(f"  {C['G']}✅{C['X']} {name}  {detail}")
    else:
        print(f"  {C['R']}❌{C['X']} {name}  {C['R']}→ {detail}{C['X']}")
        ALL_OK = False

print(f"""
{C['B']}  ╔══════════════════════════════════════════════════════╗
  ║         BookwormPRO 安装诊断                             ║
  ╚══════════════════════════════════════════════════════╝{C['X']}
""")

# ── 文件检查 ──
print(f"{C['B']}  ▸ 文件完整性{C['X']}")
skills_dir = TARGET / 'skills'
if skills_dir.exists():
    count = len(list(skills_dir.rglob('SKILL.md')))
    check("技能文件", count > 0, f"{count} 个技能")
else:
    check("技能文件", False, "skills/ 目录不存在")

check("SOUL.md", (TARGET / 'SOUL.md').exists())
check("CLAUDE.md", (TARGET / 'CLAUDE.md').exists() or (HOME / '.claude' / 'CLAUDE.md').exists())
check("config.yaml", (TARGET / 'config.yaml').exists())

# ── 环境变量检查 ──
print(f"\n{C['B']}  ▸ API 配置{C['X']}")
env_file = TARGET / '.env'
if env_file.exists():
    env_content = env_file.read_text(encoding='utf-8')
    providers = {
        'DeepSeek': 'DEEPSEEK_API_KEY',
        'DashScope': 'DASHSCOPE_API_KEY',
        'Gemini': 'GOOGLE_API_KEY',
        'Doubao': 'DOUBAO_API_KEY',
    }
    configured = 0
    for name, var in providers.items():
        if var + '=' in env_content:
            # 检查是否不是占位符
            line = [l for l in env_content.split('\n') if l.startswith(var + '=')]
            if line and 'your-' not in line[0].lower() and 'xxx' not in line[0].lower() and 'here' not in line[0].lower():
                configured += 1
                check(f"{name}", True, "已配置")
            else:
                check(f"{name}", False, "需填入真实 Key")
        else:
            check(f"{name}", False, "未配置")
    
    if configured == 0:
        print(f"\n  {C['Y']}⚠ 至少需要配置一个 API Key 才能使用{C['X']}")
else:
    check(".env 文件", False, "文件不存在")

# ── API 连通性测试 ──
print(f"\n{C['B']}  ▸ API 连通性测试{C['X']}")
if env_file.exists():
    for key_var, base_var, name in [
        ('DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'DeepSeek'),
        ('DASHSCOPE_API_KEY', 'DASHSCOPE_BASE_URL', 'DashScope'),
    ]:
        lines = env_content.split('\n')
        key_line = [l for l in lines if l.startswith(key_var + '=')]
        base_line = [l for l in lines if l.startswith(base_var + '=')]
        if key_line and base_line:
            key = key_line[0].split('=', 1)[1].strip()
            base = base_line[0].split('=', 1)[1].strip()
            if 'your-' not in key.lower() and 'xxx' not in key.lower():
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        f"{base}/models",
                        headers={"Authorization": f"Bearer {key}"}
                    )
                    resp = urllib.request.urlopen(req, timeout=10)
                    check(f"{name} 连通", resp.status == 200, f"状态 {resp.status}")
                except Exception as e:
                    check(f"{name} 连通", False, str(e)[:50])
            else:
                check(f"{name} 连通", False, "Key 未配置")
        else:
            check(f"{name} 连通", False, "未配置")

# ── 结果 ──
print()
if ALL_OK:
    print(f"  {C['G']}🎉 所有检查通过！BookwormPRO 已就绪。{C['X']}")
    print(f"  {C['D']}试试输入: bookworm自检{C['X']}")
else:
    print(f"  {C['Y']}⚠ 部分检查未通过，请参考上方提示修复。{C['X']}")
    print(f"  {C['D']}运行 install.bat 可重新配置{C['X']}")
print()
