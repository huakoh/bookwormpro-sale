"""审计仍含 hermes 的文件，按类型分组并统计。"""
import os
import re
from collections import defaultdict

ROOT = "D:/repos/hermes-agent"
SKIP_DIRS = {".venv", "node_modules", ".git", "__pycache__", "hermes_agent.egg-info", "bookwormpro.egg-info", "dist", "build"}
EXTS = {".py", ".md", ".yaml", ".yml", ".json", ".sh", ".toml", ".ts", ".tsx", ".js", ".html", ".txt", ".cfg", ".ini"}

# 分类规则
CATEGORIES = {
    "P0_user_visible_strings": [
        r'print\s*\([^)]*[Hh]ermes',
        r'logger\.\w+\([^)]*[Hh]ermes',
        r'_cprint\s*\([^)]*[Hh]ermes',
        r'console\.print\([^)]*[Hh]ermes',
        r'echo\s+[^|]*[Hh]ermes',
        r'description\s*=\s*["\'][^"\']*[Hh]ermes',
        r'help\s*=\s*["\'][^"\']*[Hh]ermes',
    ],
    "P1_doc_md": [],  # filled by extension
    "P2_test_only": [],  # filled by path
    "P3_function_attribute_names": [
        r'\bdef\s+\w*hermes\w*',
        r'\bclass\s+\w*[Hh]ermes\w*',
        r'\b_hermes_\w+',
    ],
    "PROTECTED_hermes_model_family": [
        r'hermes_swe_env',
        r'hermes_base_env',
        r'hermes_parser',
        r'HermesAgentLoop',
        r'HermesAgentBaseEnv',
        r'HermesAgentEnvConfig',
        r'hermes_pkce',
        r'NousResearch/hermes-agent',
        r'openclaw_to_bookwormpro',
        r'DeepHermes',
    ],
}

stats = defaultdict(lambda: {"files": set(), "count": 0})
file_categories = defaultdict(list)

for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in files:
        ext = os.path.splitext(fname)[1].lower()
        if ext not in EXTS:
            continue
        path = os.path.join(root, fname)
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except (PermissionError, OSError):
            continue
        if not re.search(r"hermes", content, re.IGNORECASE):
            continue

        # 该文件总命中数
        total = len(re.findall(r"hermes", content, re.IGNORECASE))

        # 分类: 优先级判定
        is_test = rel.startswith("tests/") or "/tests/" in rel
        is_doc = ext == ".md"
        is_skill = "/skills/" in rel or "/optional-skills/" in rel
        is_website = rel.startswith("website/")

        # 检查是否仅含模型家族保留词
        non_protected = content
        for prot in CATEGORIES["PROTECTED_hermes_model_family"]:
            non_protected = re.sub(prot, "", non_protected, flags=re.IGNORECASE)
        if not re.search(r"hermes", non_protected, re.IGNORECASE):
            cat = "PROTECTED_only"
        elif is_website:
            cat = "P1_website_docs"
        elif is_skill:
            cat = "P2_skill_content"
        elif is_test:
            cat = "P3_test_internal"
        elif is_doc:
            cat = "P1_doc_md"
        elif ext == ".py":
            # 看是否仅是函数/属性名
            if re.search(r'(def\s+\w*hermes|class\s+\w*[Hh]ermes|_hermes_\w+)', content, re.IGNORECASE):
                # 检查是否还有别的
                stripped = re.sub(r'(def\s+\w*hermes\w*|class\s+\w*[Hh]ermes\w*|_hermes_\w+)', "", content, flags=re.IGNORECASE)
                if re.search(r"hermes", stripped, re.IGNORECASE):
                    cat = "P0_py_user_strings"
                else:
                    cat = "P3_py_internal_names"
            else:
                cat = "P0_py_user_strings"
        else:
            cat = "P1_other_config"

        stats[cat]["files"].add(rel)
        stats[cat]["count"] += total
        file_categories[cat].append((rel, total))

print(f"=== 分类汇总 ===\n")
for cat in sorted(stats.keys()):
    info = stats[cat]
    print(f"{cat}: {len(info['files'])} 文件, {info['count']} 处")

print("\n=== 详细 (Top 10/类) ===\n")
for cat in sorted(stats.keys()):
    print(f"\n[{cat}]")
    items = sorted(file_categories[cat], key=lambda x: -x[1])
    for rel, n in items[:10]:
        print(f"  {n:4d}  {rel}")
    if len(items) > 10:
        print(f"  ... +{len(items)-10} more")
