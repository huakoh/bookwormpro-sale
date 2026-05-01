"""文档批量替换：仅处理 .md 文件中的 Hermes 品牌字串。

策略：保护 Hermes 模型相关词，其他用户可见的 Hermes 文本替换为 BookwormPRO。
"""
import os
import re
import sys

ROOT = os.path.normpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SKIP_DIRS = {".venv", "node_modules", ".git", "__pycache__", "hermes_agent.egg-info", "dist", "build"}
SKIP_PATHS = [
    "environments/hermes_swe_env",
    "environments/hermes_base_env.py",
    "environments/tool_call_parsers/hermes_parser.py",
    "optional-skills/mlops/hermes-atropos-environments",
    "optional-skills/migration/openclaw-migration",
    "skills/autonomous-ai-agents/hermes-agent",
    "website/docs/user-guide/skills/optional/migration/migration-openclaw-migration",
    "website/docs/user-guide/skills/optional/mlops/mlops-hermes-atropos-environments",
    "website/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-hermes-agent",
    "RELEASE_v",
]

# 保护词 (这些字眼指 Hermes 模型功能本身，不替换)
PROTECTED = [
    "HermesAgentLoop", "HermesAgentBaseEnv", "HermesAgentEnvConfig",
    "HermesClaw",
    "hermes_pkce", "hermes_swe_env", "hermes_base_env", "hermes_parser",
    "hermes-atropos-environments",
    "hermes-agent skill", "hermes-agent SKILL",
    "DeepHermes", "Nous Hermes", "NousResearch",
    "openclaw_to_bookwormpro", "openclaw-migration",
    "<hermes_im_start>", "<hermes_im_end>",
]


def should_skip(rel: str) -> bool:
    return any(s in rel for s in SKIP_PATHS)


def protect(text: str):
    placeholders = {}
    for i, tok in enumerate(PROTECTED):
        if tok in text:
            ph = f"\x00P{i:03d}\x00"
            placeholders[ph] = tok
            text = text.replace(tok, ph)
    return text, placeholders


def restore(text: str, placeholders: dict) -> str:
    for ph, tok in placeholders.items():
        text = text.replace(ph, tok)
    return text


def transform(t: str) -> str:
    # 大写
    t = re.sub(r'\bHermes\b', 'BookwormPRO', t)
    t = re.sub(r'\bHERMES\b', 'BOOKWORMPRO', t)
    # 小写复合
    t = re.sub(r'\bhermes-agent\b', 'bookwormpro', t)
    t = re.sub(r'\bhermes_agent\b', 'bookwormpro', t)
    t = re.sub(r'\bhermes\b', 'bookwormpro', t)
    return t


def process(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            orig = f.read()
    except (UnicodeDecodeError, PermissionError):
        return 0
    if "hermes" not in orig.lower():
        return 0

    protected, ph = protect(orig)
    new = transform(protected)
    final = restore(new, ph)

    if final == orig:
        return 0

    before = len(re.findall(r"hermes", orig, re.IGNORECASE))
    after = len(re.findall(r"hermes", final, re.IGNORECASE))
    n = before - after

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(final)
    return n


def main():
    files = 0
    total = 0
    for root, dirs, fnames in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in fnames:
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            if should_skip(rel):
                continue
            n = process(path)
            if n > 0:
                files += 1
                total += n
                print(f"  {rel}: {n}")
    print(f"\n汇总: {files} 文件, {total} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
