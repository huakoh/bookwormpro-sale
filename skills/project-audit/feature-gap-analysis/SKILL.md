---
name: feature-gap-analysis
description: Systematically compare a feature checklist/wishlist against a codebase to identify gaps, rate completeness, and produce prioritized action plans. Use when the user has a "必做一览" (must-do checklist), roadmap, or feature wishlist and wants to know what's missing from the current system.
version: 1.0.0
author: BookwormPRO
tags: [audit, gap-analysis, checklist, planning, code-review]
---

# Feature Gap Analysis

Compare a feature checklist (from screenshots, docs, or user input) against a codebase and produce a prioritized gap report with percentage ratings.

## When to Use

- User shares a checklist/wishlist/roadmap and asks "what's missing?"
- User has a feature comparison table and wants current-state assessment
- Pre-release audit: does the codebase deliver what the marketing claims?
- Due diligence: buyer/investor wants to verify feature claims against code

## Steps

### 1. Parse Checklist Items

Extract distinct features from the source. If source is a screenshot that can't be viewed (no multimodal support), use OCR fallback first:
- `screenshot-ocr-fallback` skill for OCR.space API
- Or `browser_vision` if model supports it

### 2. Batch Search for Evidence

For each checklist item, run parallel `search_files` calls (target='content', file_glob='*.py') looking for:
- Keywords from the feature name
- Related implementation terms (e.g., for "memory" search for "memory|mem0|honcho|retain")
- Keep searches broad — false positives are filtered later

Also search for absence signals:
- Check user's actual config files to see if feature is configured
- Check if feature appears in tips/docs but has no implementation

### 3. Deep-Dive Key Files

For any item where search results suggest partial implementation:
- `read_file` the first 80-120 lines of key implementation files
- Look for: class definitions, function signatures, docstrings, imports
- Determine if this is a skeleton vs full implementation

### 4. Rate Completeness

Give each item a percentage (0-100):
- **0-20%**: No code, or only placeholder/todo comments
- **30-50%**: Skeleton exists (e.g., backup is local-only but advertised as "three-layer")
- **55-70%**: Core works but major advertised sub-feature missing
- **75-85%**: Works well but user hasn't configured it
- **90-100%**: Mature, fully implemented

Always describe the SPECIFIC gap — not just "not done" but exactly what's missing.  Use Chinese for report output (用户看中文报告), English for code.

**Scoring nuance**: When code exists but the user hasn't configured it (e.g., Camofox browser code is 100% done but user has no `CAMOFOX_URL` set), score it 75-85% with gap note: "代码存在，缺配置".  When the feature works but is a flat/dumb implementation advertised as "smart/three-layer", score 30-50% — the advertising claim is what the user expects.

### 5. Cross-Check Against User Config

Read the user's actual config files:
- `~/.bookwormpro/config.yaml`
- `~/.bookwormpro/.env` (grep for relevant vars)
- `~/.bookwormpro/SOUL.md`, `~/.bookwormpro/MEMORY.md`

A feature may be 90% implemented in code but 0% configured for this user — rate accordingly and flag as "code exists, needs config".

### 6. Produce Prioritized Report

Output a table:

| # | Feature | Score | Gap | Action |
|---|---------|-------|-----|--------|
| 1 | name | X% | what's missing | concrete fix |

Then priority-order the gaps:
- **Critical (score <40%)**: Data loss / security risk
- **High (40-60%)**: Core advertised feature broken/missing
- **Medium (60-80%)**: Works but incomplete
- **Low (80%+)**: Minor config/docs needed

### 7. Offer Action Plan

After the report, offer to start fixing the top-priority gap immediately.

## Pitfalls

- Don't trust function/class names alone — read the implementation. `backup()` might exist but only do local zip when "three-layer backup" needs git+remote.
- **OCR from screenshots is garbled when source is Chinese+English terminal output** — use context to reconstruct. 中文和英文混排的截图 OCR 准确率很低（<50%），需要结合代码库已知术语进行还原。例如 OCR 输出 "æyermesAgent" → 实际是 "HermesAgent"；"三层记忆" 可正确识别但细节乱码。先提取关键字再搜索代码库确认。
- A feature in `tips.py` (marketing copy) doesn't mean it's fully implemented. Verify with code search.  `tips.py` 中的功能描述是宣传用语，需要用代码搜索验证实际实现程度。
- User might not have configured an available feature — distinguish "missing code" from "missing config". 读 `~/.bookwormpro/config.yaml` 和 `.env` 确认。
- **Batch 所有搜索为一次调用** — 9 个 checklist 项目可以一次性发 9 个 `search_files` 调用并行返回，避免逐项串行搜索浪费时间。
