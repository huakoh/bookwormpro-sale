#!/usr/bin/env python3
"""
BookwormPRO 彩色安装向导
引导用户一步步完成配置，无需手动编辑文件
"""

import sys
import os
import re
import shutil
from pathlib import Path

# ── 终端色彩 ──
C = {
    'R': '\033[91m', 'G': '\033[92m', 'Y': '\033[93m',
    'B': '\033[94m', 'M': '\033[95m', 'C': '\033[96m',
    'W': '\033[97m', 'X': '\033[0m', 'D': '\033[2m',
}
# Windows 兼容
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except:
        for k in C: C[k] = ''

HOME = Path.home()
TARGET = HOME / '.bookwormpro'
SRC = Path(__file__).parent.parent

def banner():
    print(f"""
{C['C']}  ╔══════════════════════════════════════════════════════╗
  ║    ____              _                                ║
  ║   | __ )  ___   ___ | | _____      _____  _ __       ║
  ║   |  _ \\ / _ \\ / _ \\| |/ / \\ \\ /\\ / / _ \\| '__|      ║
  ║   | |_) | (_) | (_) |   <  \\ V  V / (_) | |         ║
  ║   |____/ \\___/ \\___/|_|\\_\\  \\_/\\_/ \\___/|_|         ║
  ║                                                      ║
  ║         {C['W']}AI 智能助手技能包 · 安装向导{C['C']}                ║
  ╚══════════════════════════════════════════════════════╝{C['X']}
    """)

def section(title):
    print(f"\n{C['B']}  ▸ {title}{C['X']}")

def ok(msg):
    print(f"  {C['G']}✅{C['X']} {msg}")

def warn(msg):
    print(f"  {C['Y']}⚠️{C['X']}  {msg}")

def fail(msg):
    print(f"  {C['R']}❌{C['X']} {msg}")

def ask(prompt, default=None, secret=False):
    """交互式询问"""
    hint = f" [{default}]" if default else ""
    if secret:
        val = input(f"  {prompt}{hint}: ").strip()
    else:
        val = input(f"  {prompt}{hint}: ").strip()
    return val if val else default

def validate_api_key(key, provider):
    """验证 API Key 格式"""
    patterns = {
        'deepseek': r'^sk-[a-zA-Z0-9]{32,}$',
        'dashscope': r'^sk-[a-zA-Z0-9]{20,}$',
        'google': r'^AIza[0-9A-Za-z\-_]{30,}$',
        'doubao': r'^ark-[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12}$',
    }
    if provider not in patterns:
        return True
    return bool(re.match(patterns[provider], key))

def test_api(key, base_url):
    """测试 API 连通性"""
    try:
        import urllib.request, json
        req = urllib.request.Request(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {key}"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except:
        return False

def install_skills():
    """复制技能文件"""
    src = SRC / 'skills'
    dst = TARGET / 'skills'
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return len(list(dst.rglob('SKILL.md')))

def install_soul():
    """复制灵魂文件"""
    src = SRC / 'soul'
    for f in src.glob('*.md'):
        shutil.copy(f, TARGET / f.name)
    # 也复制到 ~/.claude/
    claude_dir = HOME / '.claude'
    if not claude_dir.exists():
        claude_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(SRC / 'soul' / 'SOUL.md', claude_dir / 'SOUL.md')

def install_config():
    """复制配置文件模板"""
    config_src = SRC / 'config'
    if not (TARGET / 'config.yaml').exists():
        shutil.copy(config_src / 'config.yaml', TARGET / 'config.yaml')
    if not (TARGET / '.env').exists():
        shutil.copy(config_src / '.env.template', TARGET / '.env')

def main():
    banner()

    # ── 步骤 1: 准备 ──
    section("步骤 1/4 — 环境准备")
    TARGET.mkdir(parents=True, exist_ok=True)
    ok(f"目标目录: {TARGET}")
    ok(f"Python {sys.version.split()[0]}")

    # ── 步骤 2: API Key ──
    section("步骤 2/4 — 配置 API Key（至少配一个）")
    print(f"  {C['D']}Key 只存储在本地，不会上传到任何服务器{C['X']}\n")

    env_lines = []

    # DeepSeek
    print(f"  {C['W']}── DeepSeek（推荐 · 性价比最高 · 支持支付宝充值）──{C['X']}")
    key = ask("DeepSeek API Key", secret=True)
    if key:
        if validate_api_key(key, 'deepseek'):
            ok("密钥格式正确")
            env_lines.append(f"DEEPSEEK_API_KEY={key}")
            env_lines.append("DEEPSEEK_BASE_URL=https://api.deepseek.com/v1")
            print(f"  {C['D']}测试连通性...{C['X']}", end=' ')
            if test_api(key, "https://api.deepseek.com/v1"):
                print(f"{C['G']}✅ 连通{C['X']}")
            else:
                print(f"{C['Y']}⚠ 无法验证（可稍后检查）{C['X']}")
        else:
            fail("密钥格式不正确（应以 sk- 开头），跳过")
    else:
        warn("跳过 DeepSeek")

    # DashScope
    print(f"\n  {C['W']}── 通义千问 / DashScope（视觉识别 + 图片生成）──{C['X']}")
    key = ask("DashScope API Key")
    if key:
        if validate_api_key(key, 'dashscope'):
            ok("密钥格式正确")
            env_lines.append(f"DASHSCOPE_API_KEY={key}")
            env_lines.append("DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1")
            env_lines.append("AUXILIARY_VISION_MODEL=qwen-vl-max")
        else:
            fail("密钥格式不正确")
    else:
        print("  ⚪ 跳过")

    # Google Gemini
    print(f"\n  {C['W']}── Google Gemini（可选）──{C['X']}")
    key = ask("Google API Key")
    if key:
        if validate_api_key(key, 'google'):
            ok("密钥格式正确")
            env_lines.append(f"GOOGLE_API_KEY={key}")
        else:
            fail("密钥格式不正确")
    else:
        print("  ⚪ 跳过")

    if not env_lines:
        print(f"\n{C['Y']}  ⚠ 未配置任何 API Key！{C['X']}")
        print(f"  {C['D']}稍后可编辑 {TARGET / '.env'} 手动添加{C['X']}")

    # ── 步骤 3: 安装文件 ──
    section("步骤 3/4 — 安装技能文件")

    print("  📦 复制技能包...", end=' ', flush=True)
    n = install_skills()
    ok(f"{n} 个技能已安装")

    print("  🧠 安装灵魂文件...", end=' ', flush=True)
    install_soul()
    ok("SOUL.md + CLAUDE.md 已就绪")

    print("  ⚙  安装配置文件...", end=' ', flush=True)
    install_config()
    ok("config.yaml + .env 已就绪")

    # 写入 .env
    env_file = TARGET / '.env'
    with open(env_file, 'a', encoding='utf-8') as f:
        if env_lines:
            f.write('\n' + '\n'.join(env_lines) + '\n')

    # ── 步骤 4: 完成 ──
    section("步骤 4/4 — 安装完成")

    not_ready = []
    if not (TARGET / 'skills').exists(): not_ready.append("技能文件")
    if not (TARGET / 'SOUL.md').exists(): not_ready.append("SOUL.md")
    if not env_lines: not_ready.append("API Key 未配置")

    if not_ready:
        print(f"\n  {C['Y']}⚠ 以下项目需要关注：{C['X']}")
        for item in not_ready:
            print(f"    · {item}")
    else:
        print(f"\n  {C['G']}✅ 所有组件已就绪！{C['X']}")

    print(f"""
  {C['W']}📋 下一步：{C['X']}
    1. 打开 {C['C']}docs/快速开始.html{C['X']} 查看图文教程
    2. 重启你的 AI 助手
    3. 输入 {C['C']}bookworm自检{C['X']} 验证安装

  {C['D']}更新: 重新运行本向导即可覆盖安装{C['X']}
  {C['D']}卸载: 删除 {TARGET / 'skills'} 目录{C['X']}
    """)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{C['Y']}  安装已取消{C['X']}\n")
    except Exception as e:
        print(f"\n{C['R']}  ❌ 错误: {e}{C['X']}\n")
        sys.exit(1)
