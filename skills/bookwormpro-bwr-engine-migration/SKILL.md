---
name: bookwormpro-bwr-engine-migration
description: >
  Migrate BWR routing engine from Bookworm v6.6.1 (~/.claude/) to BookwormPRO
  v7.0.0 (C:/Users/BOOKWORMPRO_USER/BookwormPRO/routing/). Covers: file copy, path
  adaptation, CRLF workarounds, BM25 index fix, submit mechanism, bridge.js +
  Python hook integration. Trigger: "migrate BWR", "copy routing engine".
version: 1.1.0
maturity: stable
category: devops
---

# BWR 路由引擎迁移: v6.6.1 → v7.0.0

将 BWR 路由引擎从 Bookworm v6.6.1 迁移到 BookwormPRO v7.0.0。

## 前置条件

- 源: `~/.claude/` (v6.6.1, **只读**)
- 目标: `C:\Users\BOOKWORMPRO_USER\BookwormPRO\routing/`
- Node.js 可用
- `~/.bookwormpro/` 可写

## Phase 1: 复制 + 路径适配

```bash
DST="C:/Users/BOOKWORMPRO_USER/BookwormPRO/routing/"
mkdir -p "$DST/lib"

# 核心引擎 (12 files)
cp ~/.claude/scripts/{bwr-builder,route-engine,route-state,route-telemetry,route-analyzer,route-feedback,route-ab-test,intent-classifier,tfidf-engine,bm25-tuner,semantic-scorer,embedding-router}.js "$DST/"

# 消歧 + 辅助 (20 files)
cp ~/.claude/scripts/{disambiguation-rules.json,disambiguation-tree,adaptive-disambiguator,synonym-expander,synonym-miner,synonyms,skill-domain-map,skill-alias-resolver,skill-chain-recommender,skill-retirement-advisor,domain-classifier,domain-capacity-manager,fusion-weight-learner,weight-store,compile-rules,implicit-feedback,feature-flags,golden-set,paths.config,sanitize}.{js,json} "$DST/"

# Lib (3 files, 需要路径适配)
cp ~/.claude/hooks/lib/{root,safe-append,read-stdin}.js "$DST/lib/"

# 数据文件 — 用完整版 (980KB), 非 lite 版
cp ~/.claude/skills-index.json ~/.bookwormpro/skills-index.json
```

### lib/root.js — 重写
返回 `~/.bookwormpro/` (运行时数据目录)，不是项目根。
```javascript
const path = require('path');
module.exports = path.join(process.env.USERPROFILE || process.env.HOME || '', '.bookwormpro');
```

### route-engine.js line 16/60
```javascript
// SCRIPTS_DIR 指向自身目录
const SCRIPTS_DIR = __dirname;

// 用完整版 skills-index
const indexFile = path.join(CLAUDE_ROOT, 'skills-index.json');
```

### route-state.js
```javascript
// 所有 ../hooks/lib/ → ./lib/
// Windows renameSync 容错
try { fs.renameSync(_tmpState, target); }
catch { fs.writeFileSync(target, data); }
```

## Phase 2: Create bridge.js + bwr_hook.py

**bridge.js**: stdin JSON `{query}` → stdout JSON `{intent, routing, directive}`

**bwr_hook.py**: `BWRHook.inject_directive(msg)` → prepend `[BWR:xxx]`

**Agent 集成** (`run_agent.py`, 非侵入式):
```python
try:
    from routing.bwr_hook import BWRHook
    user_message = BWRHook().inject_directive(user_message)
except Exception: pass
```

## Critical Pitfalls

1. **skills-index-lite.json → BM25 全为零**: lite 版无 keywords 字段。必须用完整版 `skills-index.json` (980KB)。

2. **SCRIPTS_DIR = __dirname**: 指向 routing/ 目录，所有 safeRequire 依赖此路径。

3. **Submit 机制**: 消歧规则匹配但目标 skill 不在 BM25 结果中时，注入虚拟条目 (maxScore × 0.5)。否则规则静默失效。

4. **消歧规则格式**: `{id, trigger(RegExp), boost, penalty, weight}`，不是 `{pattern, target, priority}`。

5. **Windows patch 工具**: CRLF 导致验证失败，改用 Python `write_file`。

6. **cron model=null**: `cron/jobs.py:create_job()` 默认 model=None，需从 config.yaml 自动读取。

## Accuracy Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 全部路由 → developer-expert, conf=0 | skills-index-lite 无 keywords | 用 skills-index.json |
| 规则匹配但结果不变 | 目标 skill 不在 BM25 结果 | 加 submit 机制 |
| 规则从不触发 | 字段名错误 | 用 trigger/boost/penalty/weight |
| accuracy.js 报错 | 缓存未刷新 | `delete require.cache[...]` |

## 验证

```bash
cd routing/
node -e "require('./route-engine.js'); console.log('OK')"
echo '{"query":"帮我写Python脚本"}' | node bridge.js
node accuracy.js   # 应显示 88%+
```

## 准确率演进
```
75.4% → skills-index 修复
84.1% → +16 消歧规则
88.9% → Submit 机制
91.7% → +7 规则 (v1.9, 125 rules total)
```
