# SMR 智能模型路由系统 — 主流程集成文档

> Smart Model Routing (SMR) v1.0
> 状态：已接入 BookwormPRO 主对话流程（仅 CLI 平台）
> 最后更新：2026-07-09

## 1. 概述

SMR 在每次 CLI 对话时，根据用户输入的任务类型自动选择最优模型并切换，
无需手动 `/model`。它是**非侵入式**的：任何异常都静默降级，绝不影响主对话。

核心链路：

```
用户输入
  → smr_classifier 分类 6 类任务 (coding/reasoning/creative/vision/fast/general)
  → smr_router 打分选最优模型 (质量0.6 + 成本0.3 + 速度0.1 + 历史奖励 + 任务亲和)
  → 惰性阈值判断是否值得切换 (防抖动，保护 prompt 缓存)
  → agent.switch_model() 运行时切换
  → turn 结束后 smr_feedback 记录反馈 (EMA 权重学习)
```

## 2. 文件结构

| 文件 | 作用 |
|------|------|
| `~/.bookwormpro/smr/smr_classifier.py` | 6 类任务分类器（关键词 + 长度启发式） |
| `~/.bookwormpro/smr/smr_router.py` | 打分路由核心，18 个模型 MODEL_PROFILES |
| `~/.bookwormpro/smr/smr_feedback.py` | 反馈收集 + EMA 权重更新 |
| `~/.bookwormpro/smr/smr_stats.py` | 统计报告 |
| `routing/smr_hook.py` | **主流程桥接**（本次新增） |
| `run_agent.py` (run_conversation) | 路由注入点 + 反馈闭环注入点 |
| `cli.py` | 切换/开关提示展示 |

## 3. 集成注入点

### 3.1 路由注入（run_agent.py `run_conversation`）
紧邻既有 BWR 路由注入块之后，仅 `platform == "cli"` 时触发：
- 先检测会话内开关指令（`maybe_toggle`）
- 未命中则评估并可能切换模型（`route_and_switch`）
- 切换信息暂存 `self._smr_switch_notice`，开关提示暂存 `self._smr_toggle_notice`

### 3.2 反馈闭环（run_agent.py `run_conversation` 尾部）
`return result` 前，根据 turn 结果推导 reward 并记录：

| turn 结果 | reward 类型 | 值 |
|-----------|------------|-----|
| interrupted | API_ERROR_TIMEOUT | -0.5 |
| not completed | SELF_AUDIT_ERROR | -0.3 |
| completed 且 api_calls > 6 | TASK_COMPLETED_WITH_RETRY | +0.5 |
| completed 且 api_calls ≤ 6 | TASK_COMPLETED_CLEAN | +0.7 |

### 3.3 提示展示（cli.py）
`response = result.get("final_response")` 后展示：
- `⚡ SMR 已切换模型: gpt-4o → gpt-5.3-codex-spark (coding, score=1.02)`
- `⚙ 已在当前会话关闭 SMR 模型自动切换（新开 CLI 不受影响）。`

## 4. 三级开关

优先级从高到低：

### 级别 1：环境变量（进程级，紧急关闭）
```bash
export SMR_DISABLE=1      # 关闭
unset SMR_DISABLE          # 恢复（需重启 CLI）
```
接受值：`1` / `true` / `yes` / `on`。

### 级别 2：config.yaml（配置级，持久）
```yaml
smr:
  enabled: true          # 总开关（默认 true）
  switch_margin: 0.03    # 候选模型得分需超当前模型此值才切换（防抖动，0-1）
```

### 级别 3：会话内语言指令（仅当前 CLI 会话）
在对话中直接输入：
- 关闭：`关闭模型切换` / `停止模型切换` / `禁用模型切换` / `disable model switch`
- 恢复：`恢复模型切换` / `开启模型切换` / `启用模型切换` / `enable model switch`

会话内指令**优先于**进程级默认。**新开 CLI 不受影响**，回到 config/env 决定的默认状态——
这保证了路由机制的设计一致性：临时干预不污染全局。

## 5. 惰性阈值（防抖动）

为避免频繁切换模型击穿 prompt 缓存，设计了三重惰性：
1. 目标模型 == 当前模型 → 跳过
2. 同 task_type 且上次已路由过同模型 → 跳过
3. 候选得分未超当前模型 `switch_margin`（默认 0.03）→ 跳过

## 6. 模型映射

SMR 的 18 个 `MODEL_PROFILES` key 与 config.yaml `custom_providers` 的 18 个
`model` 名**完全一一对应**（均走 `中转站` provider）。切换时直接查 config 取
`base_url` / `api_key` / `provider`，无需转换。

若 SMR 选出的模型不在 config（无凭证），自动跳过切换。

## 7. 反馈与学习

- 反馈写入 `~/.bookwormpro/smr/feedback_log.jsonl`
- EMA 公式：`w_new = w_old * 0.9 + reward * 0.1`
- 权重持久化到 `~/.bookwormpro/smr/weights.json`（原子写入）
- 路由时 `weights.json` 覆盖 `MODEL_PROFILES` 内置权重

## 8. 测试

```bash
python C:/Users/leesu/BookwormPRO/scripts/test-smr-integration.py
```
17 项集成测试，全隔离运行（临时 HOME，自动清理，不污染真实 SMR 数据）。

## 9. 故障排查

| 现象 | 排查 |
|------|------|
| 模型没自动切换 | 检查 `platform=="cli"`；`SMR_DISABLE`；`smr.enabled`；会话内是否关过 |
| 频繁切换 | 调大 `switch_margin`（如 0.05） |
| 切换到无凭证模型 | 该模型不在 config custom_providers，SMR 已自动跳过 |
| 反馈没记录 | 检查 `~/.bookwormpro/smr/` 可写；查 `bookworm logs` 中 SMR debug 日志 |
| 完全无效 | 导入降级：确认 `~/.bookwormpro/smr/` 下 4 模块存在且可 py_compile |
