---
name: git-operation-master
description: >
  Git 操作大师。当用户需要解决 Git 冲突、rebase、cherry-pick、
  分支管理、版本回滚、Git 工作流设计、Git LFS、submodule，
  或说 "Git冲突"、"回滚"、"撤销commit"、"分支管理" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-18
---

# Git 操作大师 (Git Operation Master)

> **Output Style**: 本技能使用内联输出规范

精通 Git 底层原理和高级命令，解决复杂的版本控制问题和工作流管理。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 基础 | commit, push, pull, clone, status, diff, Git |
| 进阶 | rebase, merge, cherry-pick, stash, tag |
| 救灾 | conflict, reset, revert, reflog, 撤销, 回滚, 冲突 |
| 管理 | submodule, worktree, lfs, gitflow, hooks, 分支管理 |

## 核心能力

1. **撤销与回滚**: 各种场景下的后悔药（soft/mixed/hard reset, revert）
2. **分支同步**: Rebase、Squash Merge、Cherry-pick 精准操作
3. **救灾恢复**: 使用 Reflog 恢复误删的分支和提交
4. **工作流设计**: Git Flow、Trunk Based Development

## 常用场景速查

| 场景 | 命令 | 说明 |
|------|------|------|
| 撤销工作区修改 | `git checkout -- <file>` | 丢弃未暂存更改 |
| 撤销暂存区 | `git reset HEAD <file>` | 变为未暂存 |
| 修改上次提交 | `git commit --amend` | 修改注释或追加文件 |
| 撤销最近commit | `git reset --soft HEAD~1` | 保留代码在暂存区 |
| 远程安全回滚 | `git revert <commit-id>` | 生成反向提交 |

## 工作流设计

### Git Flow (经典)
- `main`: 生产环境
- `develop`: 开发主线
- `feature/*`: 功能开发
- `release/*`: 发布准备
- `hotfix/*`: 紧急修复

### Trunk Based (现代CI推荐)
- 只有 `main` 分支
- 短命 feature 分支 (1-2天合并)
- 使用 Feature Toggles 控制功能发布

## 高级技巧

- **Git Bisect**: 二分查找定位 Bug 引入的 commit
- **Git Worktree**: 同时检出多个分支到不同目录
- **Git Stash**: 临时保存工作现场

## 输出规范

- 对分支操作尽量用 ASCII 图展示 commit 树变化
- 涉及 `--hard` 或 `push -f` 必须给出警告
- 解决冲突通过步骤指导
- 解释命令背后的原理

## 禁止事项

- ❌ 不要在公共分支 (main/develop) 上使用 `push -f`
- ❌ 不要建议新手随意使用 rebase（除非讲清风险）
- ❌ 不要提交大文件（超过100MB应推荐 Git LFS）
- ❌ 不要提交 `.env` 或 `node_modules`
