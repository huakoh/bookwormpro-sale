#!/usr/bin/env python3
"""BookwormPRO 一键安装脚本

用法:
    python setup.py          # 交互式安装
    python setup.py --quick  # 快速安装（用默认配置）
"""

import sys
import os
from pathlib import Path

BOOKWORMPRO_HOME = Path.home() / '.bookwormpro'

def print_banner():
    print(r"""
  ╔══════════════════════════════════════════════════════════╗
  ║    ____              _                                   ║
  ║   | __ )  ___   ___ | | _____      _____  _ __ ___       ║
  ║   |  _ \ / _ \ / _ \| |/ / \ \ /\ / / _ \| '__| \ \      ║
  ║   | |_) | (_) | (_) |   <   \ V  V / (_) | |  | | |     ║
  ║   |____/ \___/ \___/|_|\_\   \_/\_/ \___/|_|  |_| |_|   ║
  ║                                                          ║
  ║         AI 智能助手技能包 · 安装向导                      ║
  ╚══════════════════════════════════════════════════════════╝
    """)

def ask(prompt, default=None):
    """交互式询问"""
    if default:
        answer = input(f"  {prompt} [{default}]: ").strip()
        return answer if answer else default
    return input(f"  {prompt}: ").strip()

def setup_env():
    """配置 .env"""
    print("\n📝 配置 API Key（至少配一个 provider）\n")
    
    env_lines = []
    
    # DeepSeek（推荐）
    print("── DeepSeek（推荐，性价比最高）──")
    key = ask("DEEPSEEK_API_KEY（sk-xxx）")
    if key:
        env_lines.append(f"DEEPSEEK_API_KEY={key}")
        env_lines.append("DEEPSEEK_BASE_URL=https://api.deepseek.com/v1")
        print("  ✅ DeepSeek 已配置")
    else:
        print("  ⚪ 跳过")
    
    # DashScope
    print("\n── 通义千问 / DashScope（视觉 + 图片生成）──")
    key = ask("DASHSCOPE_API_KEY（sk-xxx）")
    if key:
        env_lines.append(f"DASHSCOPE_API_KEY={key}")
        env_lines.append("DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1")
        env_lines.append("AUXILIARY_VISION_MODEL=qwen-vl-max")
        print("  ✅ DashScope 已配置")
    else:
        print("  ⚪ 跳过")
    
    # Google
    print("\n── Google Gemini（可选）──")
    key = ask("GOOGLE_API_KEY")
    if key:
        env_lines.append(f"GOOGLE_API_KEY={key}")
        print("  ✅ Gemini 已配置")
    else:
        print("  ⚪ 跳过")
    
    # 写入
    env_file = BOOKWORMPRO_HOME / '.env'
    existing = ""
    if env_file.exists():
        existing = env_file.read_text()
        print(f"\n⚠ {env_file} 已存在，将追加新配置")
    
    with open(env_file, 'a') as f:
        if env_lines:
            f.write('\n'.join(env_lines) + '\n')
    
    if not env_lines:
        print("\n⚠ 未配置任何 API Key！至少需要一个 provider 才能使用。")
        print("  稍后编辑 ~/.bookwormpro/.env 手动添加。")

def setup_quick():
    """快速安装——只复制文件，不交互"""
    print("\n⚡ 快速模式：复制模板文件，请稍后编辑 ~/.bookwormpro/.env")
    src_dir = Path(__file__).parent.parent
    
    # 复制 .env.template
    template = src_dir / 'config' / '.env.template'
    if template.exists():
        dest = BOOKWORMPRO_HOME / '.env'
        if not dest.exists():
            import shutil
            shutil.copy(template, dest)
            print("  ✅ .env 模板已复制")
    
    # 复制 config.yaml
    config_template = src_dir / 'config' / 'config.yaml'
    if config_template.exists():
        dest = BOOKWORMPRO_HOME / 'config.yaml'
        if not dest.exists():
            import shutil
            shutil.copy(config_template, dest)
            print("  ✅ config.yaml 已复制")

def install_skills():
    """安装技能文件"""
    src_skills = Path(__file__).parent.parent / 'skills'
    dst_skills = BOOKWORMPRO_HOME / 'skills'
    
    if not src_skills.exists():
        print("❌ skills/ 目录未找到，请确认书虫PRO完整克隆")
        return False
    
    print(f"\n📦 安装技能文件...")
    
    import shutil
    if dst_skills.exists():
        print(f"  ⚠ {dst_skills} 已存在，将覆盖")
        shutil.rmtree(dst_skills)
    
    shutil.copytree(src_skills, dst_skills)
    
    # 统计
    count = len(list(dst_skills.rglob('SKILL.md')))
    print(f"  ✅ {count} 个技能已安装")
    return True

def install_soul():
    """安装灵魂文件"""
    src_soul = Path(__file__).parent.parent / 'soul'
    dst = BOOKWORMPRO_HOME
    
    import shutil
    for f in src_soul.glob('*.md'):
        dest = dst / f.name
        shutil.copy(f, dest)
        print(f"  ✅ {f.name} 已安装")
    
    # 也安装到 ~/.claude/（如果存在）
    claude_dir = Path.home() / '.claude'
    if claude_dir.exists():
        shutil.copy(src_soul / 'SOUL.md', claude_dir / 'SOUL.md')
        print("  ✅ SOUL.md → ~/.claude/")

def main():
    print_banner()
    
    # 确保目录存在
    BOOKWORMPRO_HOME.mkdir(parents=True, exist_ok=True)
    
    # 安装技能
    if not install_skills():
        return
    
    # 安装灵魂文件
    print("\n🧠 安装灵魂文件...")
    install_soul()
    
    # 配置
    if '--quick' in sys.argv:
        setup_quick()
    else:
        setup_env()
    
    print(f"""
══════════════════════════════════════════════════════
  🎉 安装完成！

  下一步:
    1. 确认 ~/.bookwormpro/.env 中 API Key 正确
    2. 重启你的 AI 助手
    3. 试试输入: bookworm自检

  更新:   cd ~/.bookwormpro && git pull
  卸载:   rm -rf ~/.bookwormpro/skills ~/.bookwormpro/soul
══════════════════════════════════════════════════════
    """)

if __name__ == '__main__':
    main()
