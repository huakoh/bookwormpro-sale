---
name: assets-ai-ready
description: >
  Make asset libraries AI-searchable: rebuild FTS5 search indexes, inject ai_guidance/projects_map/recommended_picks
  into manifest files, and create AI-README.md query guides. Use when the user needs an AI — Claude, Copilot,
  ChatGPT, etc. — to be able to search and retrieve specific visual assets from a structured library by natural-language
  queries. Trigger words: AI检索, 智能搜索, FTS5, asset library search, AI可查询, AI查找资料, manifest enrich.
allowed-tools: Read, Write, Edit, Bash, terminal, sqlite3, python
maturity: draft
last-reviewed: 2026-04-29
---

# Assets AI-Ready — AI 可检索资产库

Turn a structured asset library into one an AI can query via natural language, powered by
SQLite FTS5 full-text search + enriched JSON manifests.

## When to Use

- The user has a folder of images/PDFs/documents organized by category
- They want AI assistants to find the right file from a natural-language query
- There's already a naming convention and some JSON metadata (`.assets.json`, `.manifest.json`)
- They say things like "让 AI 能快速精准找到资料"

## The 5-Step Pipeline

### Step 1: Understand the Existing System

```bash
# Check for existing infra
find <root> -name ".manifest.json" -o -name ".assets.json" -o -name ".search.db" -o -name "README.md"
# Read README for conventions
# If .manifest.json exists, check its schema and coverage
python -c "import json; m=json.load(open('<root>/.manifest.json',encoding='utf-8')); print(f'Files: {len(m[\"files\"])}'); print('Keys:', list(m.keys()))"
```

Look for:
- .manifest.json (root file-level index)
- .assets.json per directory (leaf directory descriptions)
- .search.db (FTS5 SQLite index)
- _scripts/ (maintenance scripts)
- _schemas/ (JSON schema validation)

### Step 2: Rebuild/Verify Search Index

If `.search.db` exists but is incomplete:

```bash
# Check FTS5 coverage
python -c "
import sqlite3; db = sqlite3.connect('<root>/.search.db')
print(f'FTS docs: {db.execute(\"SELECT COUNT(*) FROM fts_content\").fetchone()[0]}')
print(f'Meta rows: {db.execute(\"SELECT COUNT(*) FROM meta\").fetchone()[0]}')
"

# Rebuild from manifest (skip OCR for speed, ~50s for 160 files)
cd <root> && python _scripts/build_search_index.py --skip-ocr
```

If no search index exists, create one:

```sql
-- Schema: meta table + FTS5 virtual table
CREATE TABLE meta (
  path TEXT PRIMARY KEY, sha1 TEXT, size INTEGER, mtime TEXT, ext TEXT,
  category TEXT, subtype TEXT, product_line TEXT, project TEXT,
  language TEXT, version TEXT, page_count INTEGER, year INTEGER,
  tags TEXT, title TEXT, summary TEXT, text_chars INTEGER DEFAULT 0,
  ocr_used INTEGER DEFAULT 0, indexed_at TEXT
);
CREATE VIRTUAL TABLE fts USING fts5(
  path UNINDEXED,
  title, summary, tags, filename, body,
  tokenize = "unicode61 remove_diacritics 2"
);
```

**Important**: The system `sqlite3` CLI may not have FTS5 compiled in. Always test via Python's `sqlite3` module:

```python
import sqlite3
db = sqlite3.connect("path/to/.search.db")
# FTS5 queries always work through Python
rows = db.execute("SELECT path FROM fts WHERE fts MATCH 'vaccine logo'").fetchall()
```

### Step 3: Inject AI Metadata into Root Manifest

The root `.manifest.json` needs three fields AI assistants read:

**`ai_guidance`** — An AI-centric decision tree for query routing:
```json
"ai_guidance": "1. 用户描述模糊 → FTS5 全文搜索 .search.db\n2. 用户指定项目/类别 → 查 projects_map 定位目录\n3. 用户问特定物料 → 查 recommended_picks 快速命中\n4. 需要深看 → 读 .assets.json 的 description 字段"
```

**`projects_map`** — Project-to-path mapping with Chinese/English names:
```json
"projects_map": {
  "project_key": {
    "name": "中文名称",
    "name_en": "English Name",
    "paths": {"logos": "01-brand/logos", "photos": "02-photos"}
  }
}
```

**`recommended_picks`** — Common query → exact path shortcuts (aim for 10-15):
```json
"recommended_picks": [
  {"query": "明远 logo", "path": "01-brand/logos/mingyuan_brand_logo_company.png", "note": "主品牌Logo"},
  {"query": "公司宣传册 中文", "path": "05-prints/brochure/company/..._final_12p.pdf", "note": "12页企业宣传册"}
]
```

Create a reusable injection script (`_scripts/inject_ai_meta.py`):
```python
import json
from pathlib import Path
man = json.loads(Path("~/assets/.manifest.json").read_text(encoding="utf-8"))
man["ai_guidance"] = """..."""
man["projects_map"] = {...}
man["recommended_picks"] = [...]
Path("~/assets/.manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
```

### Step 4: Create AI-README.md

A concise Markdown file at the library root, optimized for AI consumption:

**Must include:**
- Decision tree (recommended_picks → FTS5 → .assets.json → file read)
- FTS5 query code snippet (Python)
- .assets.json field documentation (purpose, search_hints, description, tags, source_file)
- Directory map as a compact tree
- Project attribution table
- Naming convention reference
- Constraints (don't scan all images, _sources need Photoshop, web/ = compressed)

**Template**: See `assets/AI-README.template.md` in this skill.

### Step 5: Validate with 5 Real Queries

Run queries that match how a user would actually ask:

```python
import sqlite3
db = sqlite3.connect("path/to/.search.db")
tests = [
    ("给我疫苗系统的产品图", "vaccine system photo"),
    ("找公司宣传册的英文版", "brochure company en"),
    ("机械手相关的所有资料", "robot arm"),
    ("有没有春节的海报", "spring festival poster"),
    ("明远生物的logo", "logo company mingyuan"),
]
for question, query in tests:
    rows = db.execute(
        "SELECT path, snippet(fts,1,'>>','<<','...',40) FROM fts WHERE fts MATCH ? LIMIT 5",
        (query,)
    ).fetchall()
    print(f"\n用户: {question}")
    for i, (path, snip) in enumerate(rows, 1):
        print(f"  {i}. {path}")
```

**Success criteria**: All 5 queries return relevant results within the top 5.

## FTS5 Query Patterns

| User Chinese | FTS5 Query | Notes |
|-------------|------------|-------|
| 疫苗系统产品图 | `vaccine system photo` | English tokens work because filenames/tags/body are English |
| 公司宣传册英文 | `brochure company en` | Space = AND |
| 机械手资料 | `robot arm` | Product line names are English |
| 春节海报 | `spring festival poster` | Filenames contain these tokens |
| Logo | `logo company` | Simple keyword match |

**Why English queries**: The FTS5 index uses `unicode61` tokenizer which splits on non-letter characters.
Chinese characters would need jieba segmentation (not used). English keywords match because
filenames, tags, and OCR body text use English/ASCII tokens.

## Pitfalls

- **System `sqlite3` CLI lacks FTS5** — always test/search via Python's `sqlite3` module, which bundles FTS5
- **Don't run OCR on first build** — use `--skip-ocr` for speed (~50s vs hours). Run with OCR as a separate pass
- **Manifest vs search DB mismatch** — always rebuild .search.db after running enrich_manifest.py
- **Existing scripts may overwrite manual fields** — check if rebuild scripts preserve `ai_guidance`/`projects_map`/`recommended_picks` before running them; create a separate `inject_ai_meta.py` script that only touches those fields
- **recommended_picks must be exact paths** — verify each path exists before adding to the list
- **`patch` tool fails on Chinese/English mixed files** — post-write verification fails with "on-disk content differs from intended write". Use `sed -i` for simple edits or `write_file` to rewrite the entire file
- **`python3` may be broken on Windows Git Bash** (exit code 49, no stdout) — use `python` not `python3`, and write to temp .py files instead of `-c` inline scripts, or use heredoc `python << 'PYEOF'`
- **PDF compression**: prefer pikepdf+Pillow (pure Python, no Ghostscript dependency) — saves ~42-50%. Output to `web/` subdirectories, keep originals untouched.
- **Ghostscript not required**: winget package name `ArtifexSoftware.GhostScript` may not resolve; pikepdf `compress-pdfs.py` (150dpi JPEG quality=75 re-encode) works without GS and handles PDF image stream compression directly
- **`zip` command unavailable on Windows Git Bash** — use Python's `zipfile` module instead: `python -c "import zipfile; zf=zipfile.ZipFile('out.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9); zf.write('large.psb')"`
- **`7z` may be broken on Windows** (HTML wrapper, not binary) — prefer Python zipfile as fallback
- **RapidOCR needs explicit install**: `pip install rapidocr-onnxruntime` before running `build_search_index.py --force-ocr`
- **OCR improves search but Chinese multi-word is limited** — FTS5 unicode61 tokenizer splits CJK characters individually; for full Chinese phrase search, jieba integration is needed but filenames/tags in English already give good coverage
- **Read existing audit reports** (`_reports/audit-*.md`) before starting work — previous agents may have already fixed naming, deduplication, and manifest issues

## Deliverables

After this pipeline, the library root contains:
```
<root>/
  .manifest.json       ← with ai_guidance + projects_map + recommended_picks
  .search.db           ← full FTS5 index (all files)
  .assets.json *       ← per-directory descriptions + search hints
  AI-README.md         ← AI assistant operation manual
  _scripts/
    inject_ai_meta.py  ← reusable AI metadata injection script
```

## Companion Operations

### Cross-Library Linking
When multiple asset libraries exist (e.g., ~/assets for visuals + ~\Desktop\_Archive for docs), add mutual references in each library's README:

```markdown
## 关联资产库
| 库 | 路径 | 内容 |
|----|------|------|
| Visual Assets | ~/assets | Brand/product/UI |
| Desktop Archive | ~\Desktop\_Archive | Docs/reports/scripts |
```

This tells the AI "if you can't find it here, look there."

### Cron-Based Maintenance
```python
# Weekly manifest refresh (prevents file_count drift)
cronjob(action="create", name="Assets Weekly Refresh",
  schedule="0 9 * * 1",
  prompt="cd <root> && python _scripts/refresh-manifest.py",
  toolsets=["terminal", "file"],
  workdir="<root>")

# Monthly archive reminder
cronjob(action="create", name="Monthly Archive Reminder",
  schedule="0 9 1 * *",
  prompt="Check current month archive folder exists, count files, report empty dirs",
  toolsets=["terminal", "file"])
```

### Sensitive File Handling in Archives
When archives contain VPN configs or credential files, use GPG encryption:
```bash
gpg --batch --passphrase "<password>" -c credentials.yaml  # → credentials.yaml.gpg
rm credentials.yaml  # delete plaintext
```
Mark encrypted files in manifests and document `gpg -d` for decryption.
