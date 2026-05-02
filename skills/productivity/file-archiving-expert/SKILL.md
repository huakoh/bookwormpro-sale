---
name: file-archiving-expert
description: >
  文件归档整理专家。诊断文件夹结构问题、去重、重组并生成索引清单。
  当用户需要整理、归档、清理、重组文件/文件夹时使用。
  触发词：整理文件夹、归档、清理文件、重组、档案管理、organize files、archive。
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
maturity: stable
last-reviewed: 2026-04-29
---

# File Archiving Expert (文件归档整理专家)

Professional archive organization — diagnose, restructure, deduplicate, and index any folder.

## Workflow (6 Phases)

### Phase 1: Exploration
```
find <path> -type d | sort          # full directory tree
find <path> -type f | wc -l         # file count
du -sh <path>/*/                    # size per subdirectory
find <path> -type f -exec du -h {} \; | sort -rh | head -30  # largest files
```

### Phase 2: Diagnosis
Present findings as a structured table: # | Problem | Explanation

Common issues to check:
- Missing index/manifest (no README/MANIFEST)
- Mixed project vs type-based categorization
- Redundant/duplicate files or directories
- Empty directories (verify with `ls -la` not just `du`)
- Non-standard file naming (spaces, special chars, excessive length)
- Excessive nesting depth (5+ levels)

### Phase 3: Decision Framework
Present 4 key questions:
1. Classification: by-type / by-project / hybrid
2. Duplicate handling: keep-versioned / keep-all-marked / merge-dedup
3. Index: generate MANIFEST.md? (strongly recommend yes)
4. Empty dirs: delete or keep?

Give professional recommendation before asking.

### Phase 4: Execution
- Create granular todo list (5-9 steps)
- `mkdir -p` target structure upfront
- `mv` for migrations (preserves timestamps, no copy overhead)
- `rmdir` for emptied parent dirs, `rm -rf` only for confirmed-empty subtrees
- Flatten nesting: `mv <deep>/* <shallow>/ && rmdir <deep>`

### Phase 5: Index Generation
Generate `MANIFEST.md` in the archive root with:
- Header: archive date, last organized, total files, total size
- Overview table: directory | file count | size | description
- Per-directory detailed listings
- Change log of operations performed

### Phase 6: Verification
```bash
find <path> -type d -empty | wc -l   # must be 0
find <path> -type f | wc -l           # total file count
du -sh <path>                         # total size
ls -d <path>/*/                       # top-level dirs
```

### Phase 7 (Optional): Post-Archiving Refinements
After verification, offer the user these improvements in priority order. See "Post-Archiving Recommendations" section for details.

## Pitfalls

- **`du -sh */` may show 0 for directories with small files** — always cross-check with `ls -la` before declaring empty
- **`rmdir` fails silently on non-empty dirs** — follow up with `find -type d -empty` to audit, then `find -type d -empty -delete` to clean up
- **`mv "$SRC/named-dir"/* "$DST/"` leaves the source directory behind** — after moving contents, always run `rmdir "$SRC/named-dir"` to clean up
- **`patch` tool fails on mixed Chinese/English files** — post-write verification fails with "on-disk content differs from intended write". Workarounds: (A) `sed -i 's/old/new/' file.md` for simple changes, (B) `write_file` to rewrite entire file after `read_file` (no offset/limit), (C) use `sed -i` with multiline delete/replace patterns for section-level edits
- **`python3` is broken on Windows Git Bash** (exit code 49, empty stdout even for `print('hello')`) — always use `python` not `python3`. Also avoid `-c` inline scripts (same exit 49), write to temp .py files and `python file.py` instead, or use heredoc `python << 'PYEOF'...PYEOF`. Delete temp files after execution
- **Windows paths use `/c/Users/...` format in Git Bash** — use `~/Desktop/...` for cross-platform compatibility
- **File names with spaces/special chars** — always quote variables in shell commands; search trailing spaces with `find -type f -name "* .*"` (space before dot extension)

## Image Compression (PNG → WebP)

When large PNGs (>1MB) are found in the archive, convert to WebP using Pillow:

```python
# Save as _compress.py in archive root, run with: python _compress.py
from PIL import Image
import os, glob

img_dir = os.path.expanduser("~/Desktop/_Archive/YYYY-MM/Images")
for p in glob.glob(os.path.join(img_dir, "*.png")):
    orig = os.path.getsize(p)
    dst = p.replace(".png", ".webp")
    img = Image.open(p)
    img.save(dst, "webp", quality=85)
    new = os.path.getsize(dst)
    print(f"{os.path.basename(p)}: {orig/1024:.0f}KB -> {new/1024:.0f}KB ({100*(1-new/orig):.0f}%)")
```

Keep both PNG originals and WebP copies. Let the user decide whether to delete originals.

## Sensitive File Audit

After organizing, scan archive directories (especially Misc/) for sensitive files:
- **VPN/Proxy configs** (`.yaml` with `password:`, `proxies:`, `server:`) — flag as HIGH risk
- **JSON snapshots** with API keys or tokens — flag as MEDIUM risk

Read these files, identify credential types, and recommend:
1. Delete duplicates (same credentials, older version)
2. Encrypt in-place with GPG (see below)
3. At minimum mark in MANIFEST.md as sensitive

### Sensitive File Encryption (GPG)

When the user wants to encrypt in place (keep file in archive but password-protected):

```bash
# 1. Check GPG availability
which gpg

# 2. Encrypt with symmetric cipher (password-based, no key management)
gpg --batch --passphrase "<password>" -c <file>.yaml
# Produces: <file>.yaml.gpg

# 3. Verify decryption works
gpg --batch --passphrase "<password>" -d <file>.yaml.gpg | head -5

# 4. Delete plaintext original
rm <file>.yaml

# 5. Update MANIFEST: replace plaintext entry with .gpg entry
#    Mark as encrypted, document decrypt command
```

Decrypt: `gpg -d <file>.yaml.gpg > <file>.yaml` (prompts for password in terminal)

### MANIFEST Updates When `patch` Fails

The `patch` tool frequently fails on mixed Chinese/English MANIFEST.md files with "on-disk content differs from intended write". Two fallbacks:

**Fallback A — `sed` for small changes:**
```bash
# Replace a specific line
sed -i 's/old line/new line/' MANIFEST.md

# Replace a multiline section (delete old, insert new)
sed -i '/^## 敏感文件提醒/,/^## 整理变更记录/{/^## 整理变更记录/!d}' MANIFEST.md
sed -i '/^## 整理变更记录/i \
\
## 新的章节标题\
\
| col1 | col2 |' MANIFEST.md

# Append after a matched line
sed -i '/^| 2026-04-29 | 上次操作 |/a\
| 2026-04-29 | 新操作 | 说明' MANIFEST.md
```

**Fallback B — `write_file` for full rewrites:**
- Read the entire file with `read_file` (no offset/limit)
- Compose the full updated content
- Write with `write_file`

## MANIFEST.md Template Structure

```markdown
# <ArchivePath> — 归档清单 (MANIFEST)

> 归档日期：YYYY-MM-DD
> 最后一次整理：YYYY-MM-DD
> 总文件数：N | 总大小：X MB

## 目录速览
| 目录 | 文件数 | 大小 | 说明 |

## 详细内容
### <Dir>/ — <描述> (size · N files)
| 文件 | 大小/类型 | 日期/说明 |

## 整理变更记录
| 操作 | 说明 |
```

## Phase 8 (Optional): AI Asset Library Optimization

If the archive is a visual asset library (images, PDFs, design files with naming conventions
and JSON manifests), offer to make it AI-searchable with FTS5. Load the `assets-ai-ready` skill
for the full workflow. Quick decision heuristic:

- Has `.manifest.json` + `.assets.json` + `.search.db`? → Run `assets-ai-ready` pipeline
- Has structured naming convention + categorized directories? → Offer to build FTS5 index
- Just random files? → Skip, file-archiving-expert's MANIFEST.md is sufficient

## Post-Archiving Recommendations (offer after completion)

After finishing the core reorganization, offer these optional improvements in priority order:

1. **Parent README with SOP rules** — create `_Archive/README.md` with: archive principles, classification system, monthly SOP (5 steps), naming conventions, dedup rules, security reminders. This ensures future archives follow the same standard.

2. **Sub-categorization** — any directory with >10 files should be split into subdirectories by theme/topic/project. Example: `HTMLs/` → `HTMLs/bookworm/` + `HTMLs/reports/` + `HTMLs/mingyuan/` + `HTMLs/guides/`.

3. **File renaming hygiene** — fix: trailing spaces before extensions, excessively long Chinese names (>60 chars). Use naming conventions: `YYYY-MM-DD_主题.扩展名`, `主题_版本.扩展名`, `项目名-模块-版本.扩展名`.

4. **Large file compression** — identify files >1MB (especially PNG >3MB) and offer WebP conversion or lossless compression.

5. **Sensitive file audit** — flag VPN configs, proxy configs, JSON snapshots with keys for encryption or removal from desktop.
