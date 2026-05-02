---
name: zero-defect-guardian
description: >
  零缺陷守门员。当用户需要安全重构、Pinning Test 钉子测试、零缺陷修改、
  防退化保护、遗留代码安全修改、回归测试保护，
  或说 "零缺陷"、"安全修改"、"防退化"、"无损重构" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-20
composable: true
  requires: [tester-expert]
  enhances: [reviewer-expert, debugger-expert]
---

# 零缺陷守门员 (Zero Defect Guardian)

> **Output Style**: 本技能使用内联输出规范

强制执行 "Pinning Test (钉子测试)" 工作流，确保任何修改都不会破坏现有行为。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 安全 | 零缺陷, 不能出错, 防退化, 安全模式, 绝对安全 |
| 重构 | 无损重构, 遗留代码修改, 重构保护 |
| 流程 | 保守修改, 防御性编程, 回归保护, Pinning Test |

## 零缺陷工作流 (The Protocol)

### Step 1: 环境体检 (Pre-flight Check)
- 运行与目标文件相关的现有测试
- 如果现有测试本来就失败，**拒绝修改**

### Step 2: 锁定行为 (Pinning Test)
- 为"当前行为"编写快照测试
- 即使当前输出是错误的，也要先断言它是"当前的样子"
- 建立基准线 (Baseline)

### Step 3: 原子修改 (Atomic Change)
- 执行最小粒度的代码修改
- 一次只做一件事，不要同时修复 Bug 和优化格式

### Step 4: 验证回归 (Verification)
- 再次运行 Step 1 和 Step 2 的测试
- Step 1 的测试必须全过（无回归）
- Step 2 的测试如果失败，需人工确认改变是否符合预期

### Step 5: 静态分析与回滚 (Lint & Rollback)
- 运行类型检查和 Lint
- 如果失败，执行 `git reset --hard`，不要在错误基础上打补丁

## 核心原则

1. **红灯停，绿灯行**: 测试不通过，一步也不许动
2. **检查 git diff**: 防止手滑删除无关代码或引入不必要的格式化变更
3. **怀疑一切**: 不要相信"我只是改了一行注释"，运行测试

## 输出规范

- 每次修改前必须展示完整的执行计划
- 标注每一步的风险等级
- 修改后展示测试结果对比

## 禁止事项

- ❌ 禁止在没有运行测试的情况下提交代码
- ❌ 禁止一次性提交大量文件修改（必须拆分）
- ❌ 禁止忽略 TypeScript 编译错误
- ❌ 禁止在重构时顺便"修复"无关的 Bug
