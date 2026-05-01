#!/usr/bin/env python3
"""
批量将 hermes 品牌引用替换为 bookworm，保留 Hermes 模型家族功能代码。

保护清单 (绝不修改):
  - environments/hermes_swe_env/* (Hermes 模型 SWE 训练环境)
  - environments/hermes_base_env.py (Hermes 模型基础环境)
  - environments/tool_call_parsers/hermes_parser.py (Hermes 模型工具调用解析器)
  - HermesAgentLoop/HermesAgentBaseEnv/HermesAgentEnvConfig 类名
  - hermes_pkce OAuth 来源标识 (上游协议)
  - 'NousResearch/hermes-agent' 字符串 (上游 git remote)
  - 第三方项目 HermesClaw 链接

替换清单 (按优先级):
  P0: User-Agent / 临时目录 / 文件名前缀 / 内部 ID 前缀
  P1: 内部 Python 属性 (_hermes_*) / 函数名 (添加 alias)
"""

import os
import re
import sys

ROOT = os.path.normpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 跳过的文件/目录 (含 Hermes 模型功能代码)
SKIP_PATHS = {
    "environments/hermes_swe_env",
    "environments/hermes_base_env.py",
    "environments/tool_call_parsers/hermes_parser.py",
    ".venv",
    "node_modules",
    ".git",
    "__pycache__",
    "hermes_agent.egg-info",
    "bookwormpro.egg-info",
    "scripts/rebrand_hermes_to_bookworm.py",  # 不要改自己
}

# 保留的字符串模式 (即便其他地方 hermes → bookworm，这些不改)
PROTECTED_LITERALS = [
    "HermesAgentLoop",
    "HermesAgentBaseEnv",
    "HermesAgentEnvConfig",
    "hermes_pkce",
    "NousResearch/hermes-agent",
    "huakoh/BookwormPRO",  # 已经是新名
    "openclaw_to_bookwormpro",  # migration 脚本名
    "DeepHermes",  # 模型家族 (BookwormPRO/DeepHermes-3-...)
    "hermes_parser",  # 解析器引用
    "hermes_base_env",  # 环境引用
    "hermes_swe_env",  # 环境引用
]

# 替换规则 (顺序敏感: 先替换长字符串)
REPLACEMENTS = [
    # P0: User-Agent header 字符串
    (r'\bHermesAgent/(\d)', r'BookwormPRO/\1'),
    (r'compatible; HermesAgent/', r'compatible; BookwormPRO/'),

    # P0: 临时目录/文件名前缀
    (r'"hermes_voice"', r'"bookworm_voice"'),
    (r"'hermes_voice'", r"'bookworm_voice'"),
    (r'"hermes_conversation_', r'"bookworm_conversation_'),

    # P0: 内部 ID 前缀 (字符串字面量中)
    (r'f"hermes_hook_', r'f"bookworm_hook_'),
    (r'f"hermes_dashboard_plugin_', r'f"bookworm_dashboard_plugin_'),
    (r'f"hermes_\{', r'f"bookworm_{'),
    (r'"hermes_action"', r'"bookworm_action"'),
    (r'"hermes_memory"', r'"bookworm_memory"'),
    (r'"hermes_tool"', r'"bookworm_tool"'),

    # P1: 内部 Python 属性 (_hermes_*)
    (r'\b_hermes_ipv4_patched\b', r'_bwm_ipv4_patched'),
    (r'\b_hermes_session_injector\b', r'_bwm_session_injector'),
    (r'\b_hermes_verbose\b', r'_bwm_verbose'),
    (r'\b_hermes_run_generation\b', r'_bwm_run_generation'),
    (r'\b_hermes_user_memory\b', r'_bwm_user_memory'),
    (r'\b_hermes_upload\.b64', r'_bwm_upload.b64'),

    # P1: config 字段名
    (r'"hermes_bin"', r'"bookworm_bin"'),
    (r'"hermes_version"', r'"bookworm_version"'),
    (r'"hermes_home":', r'"bookworm_home":'),
]


def should_skip(path: str) -> bool:
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    return any(skip in rel for skip in SKIP_PATHS)


def process_file(path: str) -> int:
    """处理单文件，返回替换数。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, PermissionError):
        return 0

    original = content
    total = 0
    for pattern, replacement in REPLACEMENTS:
        new_content, n = re.subn(pattern, replacement, content)
        if n:
            content = new_content
            total += n

    if content != original:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    return total


def main() -> int:
    files_changed = 0
    total_replacements = 0
    for root, dirs, files in os.walk(ROOT):
        # 过滤目录
        dirs[:] = [d for d in dirs if not any(s in os.path.join(root, d).replace("\\", "/") for s in SKIP_PATHS)]
        for fname in files:
            if not fname.endswith((".py", ".md", ".yaml", ".yml", ".json", ".sh")):
                continue
            path = os.path.join(root, fname)
            if should_skip(path):
                continue
            n = process_file(path)
            if n:
                files_changed += 1
                total_replacements += n
                print(f"  {os.path.relpath(path, ROOT)}: {n} 处")
    print()
    print(f"汇总: {files_changed} 个文件, {total_replacements} 处替换")
    return 0


if __name__ == "__main__":
    sys.exit(main())
