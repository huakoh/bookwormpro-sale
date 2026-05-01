"""
P0 + P1 全面 Hermes → BookwormPRO 替换。

策略:
- 跳过 Hermes 模型功能代码 (绝对路径白名单)
- 字面量替换: Hermes → BookwormPRO, hermes-agent → bookwormpro
- 保护词不动: HermesAgent 类名、hermes_pkce、DeepHermes、NousResearch、HermesClaw、openclaw_to_bookwormpro
- 受信任的字面量替换: User-Agent / 文档字串 / 标题
"""
import os
import re
import sys

ROOT = os.path.normpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 完全跳过的路径 (Hermes 模型功能)
SKIP_PATHS = [
    "environments/hermes_swe_env",
    "environments/hermes_base_env.py",
    "environments/tool_call_parsers/hermes_parser.py",
    "optional-skills/mlops/hermes-atropos-environments",
    "optional-skills/migration/openclaw-migration",
    "skills/autonomous-ai-agents/hermes-agent",
    ".venv",
    "node_modules",
    ".git",
    "__pycache__",
    "hermes_agent.egg-info",
    "bookwormpro.egg-info",
    "dist",
    "build",
    "scripts/rebrand_hermes_to_bookworm.py",
    "scripts/rebrand_p0_p1.py",
    "scripts/hermes_audit.py",
    "tests/run_agent",  # 包含 HermesAgentLoop 类测试
    "tests/environments",  # benchmark 环境测试
    # P3 测试和内部命名跳过
    "skills/productivity/google-workspace/scripts/_hermes_home.py",
    # README 中的 HermesClaw 链接
    "RELEASE_v",
]

# 保护字符串 (即便整段被替换也保留这些原样)
# 用占位符策略: 先把保护词换成占位符，做完替换再换回
PROTECTED_TOKENS = [
    "HermesAgentLoop",
    "HermesAgentBaseEnv",
    "HermesAgentEnvConfig",
    "HermesClaw",
    "hermes_pkce",
    "NousResearch/hermes-agent",
    "NousResearch",
    "huakoh/BookwormPRO",
    "openclaw_to_bookwormpro",
    "DeepHermes",
    "hermes_parser",
    "hermes_base_env",
    "hermes_swe_env",
    "hermes-atropos",
    "hermes-agent",  # SKILL 目录名
    # 这些是 Hermes 模型本身的提示词解析格式
    "<hermes_im_start>",
    "<hermes_im_end>",
    "<|hermes",
    # Internal 函数名 (只换字符串，不换符号)
    "get_hermes_home",
    "display_hermes_home",
    "get_default_hermes_root",
    "get_hermes_dir",
    "_hermes_now",
    "_hermes_profiles",
    "__hermes_profiles",
    "test_hermes_logging",
    "test_hermes_constants",
    "_hermes_run_generation",
    "_hermes_session_injector",
    "_hermes_verbose",
    "_hermes_ipv4_patched",
    "_hermes_user_memory",
    "_hermes_upload",
    "hermes_pkce",
    "hermes_voice",  # 已被前一脚本替换为 bookworm_voice
    "hermes_conversation_",  # 已替换
    "hermes_hook_",  # 已替换
    "hermes_action",  # 已替换
    "hermes_memory",  # 已替换
    "hermes_tool",  # 已替换
    "hermes_dashboard_plugin_",  # 已替换
    "hermes_bin",  # 已替换
    "hermes_version",  # 已替换
    "hermes_home",  # config 字段
]

EXTS = {".py", ".md", ".yaml", ".yml", ".json", ".sh", ".toml", ".ts", ".tsx", ".js", ".html", ".txt", ".cfg"}


def should_skip(rel_path: str) -> bool:
    return any(s in rel_path for s in SKIP_PATHS)


def protect(content: str) -> tuple[str, dict]:
    """把保护词替换成稳定的占位符。"""
    placeholders = {}
    for i, token in enumerate(PROTECTED_TOKENS):
        placeholder = f"\x00BWMPROTECT{i:03d}\x00"
        if token in content:
            placeholders[placeholder] = token
            content = content.replace(token, placeholder)
    return content, placeholders


def restore(content: str, placeholders: dict) -> str:
    for placeholder, token in placeholders.items():
        content = content.replace(placeholder, token)
    return content


def transform(content: str) -> str:
    """主替换规则。"""
    # 1. 大写品牌词 (短语开头/独立)
    content = re.sub(r'\bHermes Agent\b', 'BookwormPRO', content)
    content = re.sub(r'\bHermes-Agent\b', 'BookwormPRO', content)
    content = re.sub(r'\bHermes\b(?! \d)', 'BookwormPRO', content)  # 不替换 "Hermes 3" 模型版本号
    content = re.sub(r'\bHERMES\b', 'BOOKWORMPRO', content)
    # 2. 复合词
    content = re.sub(r'\bhermes-agent\b', 'bookwormpro', content)
    content = re.sub(r'\bhermes_agent\b', 'bookwormpro', content)
    # 3. 单独 hermes (尾部为符号或空格)
    content = re.sub(r'\bhermes\b', 'bookwormpro', content)
    return content


def process_file(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            original = f.read()
    except (UnicodeDecodeError, PermissionError):
        return 0

    if not re.search(r"hermes", original, re.IGNORECASE):
        return 0

    protected, placeholders = protect(original)
    transformed = transform(protected)
    final = restore(transformed, placeholders)

    if final == original:
        return 0

    # 计数: 替换前后 hermes 出现差
    before_count = len(re.findall(r"hermes", original, re.IGNORECASE))
    after_count = len(re.findall(r"hermes", final, re.IGNORECASE))
    n_replaced = before_count - after_count

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(final)
    return n_replaced


def main():
    files_changed = 0
    total_replaced = 0
    by_dir = {}
    for root, dirs, files in os.walk(ROOT):
        rel_root = os.path.relpath(root, ROOT).replace("\\", "/")
        dirs[:] = [d for d in dirs if not should_skip(os.path.join(rel_root, d).replace("\\", "/"))]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in EXTS:
                continue
            path = os.path.join(root, fname)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            if should_skip(rel):
                continue
            n = process_file(path)
            if n > 0:
                files_changed += 1
                total_replaced += n
                top_dir = rel.split("/")[0]
                by_dir[top_dir] = by_dir.get(top_dir, 0) + n
    print()
    print(f"汇总: {files_changed} 个文件, {total_replaced} 处替换")
    print("\n按目录分布:")
    for d, n in sorted(by_dir.items(), key=lambda x: -x[1]):
        print(f"  {n:5d}  {d}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
