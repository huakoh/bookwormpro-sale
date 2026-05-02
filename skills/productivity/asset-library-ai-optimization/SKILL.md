---
name: asset-library-ai-optimization
description: >
  Optimize structured asset/media libraries for AI-powered retrieval.
  Covers FTS5 search index rebuild, manifest enrichment with ai_guidance,
  cross-library linking, cron maintenance, and CJK search workarounds.
  Trigger: user has a file-based library and wants AI to search it quickly.
---

# Asset Library AI Optimization

Optimize an existing structured asset library (like ~/assets) for AI-powered retrieval.

## When to Use
- User has a file-based asset/media library with some structure already
- User wants AI assistants to quickly find files by semantic search
- Library already has naming conventions and manifests

## Workflow

### Step 1: Understand existing system first
Read README.md, any manifests, check for `.search.db`, `.manifest.json`, `.assets.json`. Don't rebuild from scratch — enhance what's there.

### Step 2: Rebuild/verify search index
```python
# Check FTS5 status
python -c "import sqlite3; db=sqlite3.connect('~/assets/.search.db'); print(db.execute('SELECT COUNT(*) FROM fts_content').fetchone()[0])"
# Rebuild if incomplete
python _scripts/build_search_index.py --skip-ocr  # fast
# Or with OCR (needs rapidocr-onnxruntime installed)
python _scripts/build_search_index.py --force-ocr
```

### Step 3: Inject AI metadata into root manifest
Add three fields to `.manifest.json`:
- `ai_guidance`: Decision tree for AI retrieval flow
- `projects_map`: Project-to-path mapping for project-based queries  
- `recommended_picks`: 10-15 common query→file shortcuts

### Step 4: Create AI-README.md
Concise AI manual: search paths, FTS5 query syntax, directory map, constraints.

### Step 5: Cross-link with other libraries
If user has multiple asset/document libraries, add bidirectional README references.

### Step 6: Set up cron maintenance
```
# Weekly manifest refresh
cron: 0 9 * * 1  cd ~/assets && python _scripts/refresh-manifest.py
```

## FTS5 Chinese Search Limitation
FTS5 unicode61 tokenizer doesn't segment CJK well. Multi-character Chinese queries mostly fail. Solutions:
- English keywords work perfectly (use them in filenames/tags)
- Install jieba + custom tokenizer for full Chinese support
- Single Chinese character search works as fallback

## Pitfalls
- `pip install ghostscript` installs Python bindings, NOT the binary. Actual GS needs winget or installer.
- `pip install rapidocr-onnxruntime` needed before `--force-ocr` works
- Default system `sqlite3` CLI may lack FTS5 module — use Python's `sqlite3` instead
