---
name: mcp-prune
version: 1.0.0
description: |
  MCP 剪枝分析工具 (Phase 1 · T1.4)。基于 mcp-usage-tracker 的使用率数据，
  识别最近 N 天零调用且非 critical 的 MCP 候选，生成剪枝 plan 文件。
  绝不自动修改 ~/.claude.json，用户需人工 apply。
  触发词: "mcp-prune", "剪枝 MCP", "MCP 剪枝", "清理 MCP", "精简 MCP",
  "disable unused MCP", "prune MCP servers"。
maturity: stable
allowed-tools:
  - Bash
  - Read
---

# /mcp-prune — MCP 剪枝分析

基于 `scripts/mcp-usage-tracker.js` 产出的使用率数据，识别并报告低频 MCP
候选。**绝不自动修改** `~/.claude.json` — 用户必须人工 apply。

## 安全边界

| 能力 | 默认 | --plan | --confirm |
|------|------|--------|-----------|
| 只读分析 | ✅ | ✅ | ✅ |
| 生成 plan 文件 | — | ✅ | ✅ |
| 修改 .claude.json | ❌ | ❌ | ❌ (永远不自动改) |
| 打印 apply 指令 | — | — | ✅ |

## 执行

```bash
# 报告模式 (默认 30 天窗口)
node ~/.claude/scripts/mcp-prune.js

# 7 天窗口 (更激进)
node ~/.claude/scripts/mcp-prune.js --days 7

# 写入 plan 文件
node ~/.claude/scripts/mcp-prune.js --plan

# 打印用户 apply 步骤
node ~/.claude/scripts/mcp-prune.js --confirm
```

## 剪枝逻辑

- 候选条件: 窗口内 0 调用 **AND** 不在 `~/.claude/mcp-critical-allowlist.json` 中
- 豁免: critical 清单永远保留
- 数据源:
  - 使用率: `~/.claude/debug/activity-*.jsonl` (event=='mcp')
  - 白名单: `~/.claude/mcp-critical-allowlist.json`
  - 配置: `~/.claude.json` (只读)

## 输出

- 报告到 stdout
- --plan 时写入 `~/.claude/mcp-prune-plan-<date>.json`
- --confirm 追加 apply 指令 (PowerShell + 编辑 .claude.json 指引)

## 关联

- 依赖: `scripts/mcp-usage-tracker.js` (Phase 1 · T1.1)
- 依赖: `mcp-critical-allowlist.json` (Phase 1 · T1.5)
- 消费方: 用户手动 apply plan

## sentinel

PHASE1_T1_4_MCP_PRUNE_2026_04_24
