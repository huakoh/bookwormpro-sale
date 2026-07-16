# BookwormPRO SMR 智能模型路由接入主流程 — 升级总结（审查用）

> 生成时间：2026-07-09
> 目的：供独立对话框审查本次会话对 BookwormPRO 的全部改动
> 项目路径：`C:\Users\leesu\BookwormPRO\`
> 环境：Windows + Git Bash，Python 3.12
> 会话 BWR traceId：299b7aud / v82bz980

---

## 0. 审查者速读（TL;DR）

本次会话将**已建成但未接入**的 SMR（Smart Model Routing，智能模型路由）子系统，
非侵入式接入 BookwormPRO 主对话流程。核心诉求：**每次 CLI 对话根据任务类型自动切换最优模型，
失败静默降级，绝不影响主对话**。

- 改动性质：**新增 3 个文件 + 修改 2 个核心文件 + 修改 1 个配置文件 + 新增 1 skill/1 文档**
- 影响面：**仅 CLI 平台**（gateway / 子代理 / 单查询模式不受影响）
- 风险等级：**LOW**（全部包 try/except 降级，可三级开关，18/18 模型映射一一对应）
- 验证：**17/17 隔离集成测试通过**，3 个 Python 文件 py_compile 全过，doubleCR 全 0

**请重点审查**：
1. 主流程注入是否真正非侵入（异常是否可能逃逸影响主对话）
2. 运行时 `switch_model` 中途切换模型是否破坏 prompt 缓存 / 上下文一致性
3. 三级开关逻辑的优先级与边界
4. 反馈闭环 reward 推导是否合理
5. 凭证处理是否安全（api_key 是否可能泄漏）

---

## 1. 背景：SMR 子系统（本次会话之前已存在）

SMR 位于用户态目录 `~/.bookwormpro/smr/`，与代码库解耦，本次会话**未修改**这 4 个模块：

| 模块 | 作用 | 关键接口 |
|------|------|---------|
| `smr_classifier.py` | 6 类任务分类（coding/reasoning/creative/vision/fast/general），关键词+长度启发式 | `classify_task(text) -> TaskType` |
| `smr_router.py` | 打分路由核心，18 个模型 `MODEL_PROFILES` | `route(text) -> RoutingDecision(.model/.task_type/.score/.reason/.session_id)` |
| `smr_feedback.py` | 反馈收集 + EMA 权重更新（w_new = w_old*0.9 + reward*0.1） | `record_feedback(...)`, `update_weights()`, `RewardType` 枚举 |
| `smr_stats.py` | 统计报告 | — |

打分公式：`score = quality*0.6 + (1-cost_norm)*0.3 + (1-latency_norm)*0.1 + history_bonus + task_affinity`

**关键前提**：SMR 的 18 个 `MODEL_PROFILES` key 与 `config.yaml` 的 18 个 `custom_providers` 的
`model` 名**完全一一对应**（均走 `中转站` provider，同 base_url / api_key）。这使切换时可直接查
config 取凭证，零转换。

---

## 2. 改动清单

### 2.1 新增文件

| 文件 | 行数 | 作用 |
|------|------|------|
| `routing/smr_hook.py` | 340 | **SMR 主流程桥接类**（核心） |
| `scripts/test-smr-integration.py` | 218 | 隔离集成测试（临时 HOME，17 项） |
| `docs/smr-smart-model-routing.md` | 121 | 集成文档 |

### 2.2 修改文件

| 文件 | 注入位置 | 内容 |
|------|---------|------|
| `run_agent.py` | 第 9690-9708 行（`run_conversation` 入口，BWR 注入块后） | SMR 路由 + 切换 |
| `run_agent.py` | 第 13122-13131 行（`run_conversation` 尾部 `return result` 前） | 反馈闭环 |
| `cli.py` | 第 8913-8930 行（`response` 提取后） | 切换/开关提示展示 |
| `config.yaml`（`~/.bookwormpro/`） | `model:` 块后 | 新增 `smr:` 配置块 |

### 2.3 新增 skill

- `noninvasive-mainloop-integration`（software-development 类）：固化本次非侵入集成模式 + CRLF 陷阱规避

---

## 3. 核心桥接模块 `routing/smr_hook.py` 设计

### 3.1 类结构 `SMRHook`

```
SMRHook
├─ get(agent)                    # 类方法，复用绑定到 agent 的实例（agent._smr_hook）
├─ _resolve_process_enabled()    # 进程级开关（env + config，缓存）
├─ _read_config_margin()         # 读 config smr.switch_margin（默认 0.03）
├─ _is_enabled()                 # 会话覆盖优先于进程默认
├─ maybe_toggle(msg)             # 会话内语言指令热切换
├─ _load_model_map()             # config custom_providers -> {base_url,api_key,provider}
├─ route_and_switch(agent, msg)  # 核心：分类→路由→惰性判断→switch_model
├─ _exceeds_margin(decision,cur) # 分数优势阈值判断
└─ record_turn_feedback(result)  # 反馈闭环：从 result 推导 reward
```

### 3.2 惰性状态（实例属性）
- `_session_override`：None=跟随进程默认；True/False=本会话显式覆盖
- `_last_task_type` / `_last_routed_model`：避免同类重复切换
- `last_decision`：最近路由决策，供反馈回填

### 3.3 惰性导入
SMR 4 模块通过 `sys.path.insert` 惰性注入 `~/.bookwormpro/smr/` 导入，失败返回 None（降级）。

---

## 4. 注入点详解（审查重点）

### 4.1 路由注入（run_agent.py `run_conversation` 入口）

```python
# === SMR 智能模型自动路由 ===
# 非侵入式: 仅 CLI 平台; 依据任务类型评估并（可能）切换 self.model。
# 会话内可用 "关闭模型切换"/"恢复模型切换" 语言指令热切换（仅当前会话）。
# 任何异常均静默降级，绝不影响主对话流程。
if isinstance(user_message, str) and getattr(self, "platform", None) == "cli":
    try:
        from routing.smr_hook import SMRHook
        _smr = SMRHook.get(agent=self)
        # 1) 优先处理会话内开关指令（命中则记录提示，不再路由本轮）
        _smr_toggle_msg = _smr.maybe_toggle(user_message)
        if _smr_toggle_msg:
            self._smr_toggle_notice = _smr_toggle_msg
        else:
            # 2) 评估并可能切换模型（切换信息暂存供 CLI 展示）
            _smr_switch = _smr.route_and_switch(self, user_message)
            if _smr_switch:
                self._smr_switch_notice = _smr_switch
    except Exception:
        pass  # SMR 不可用时降级，不影响主流程
```

**位置依据**：紧邻既有 `BWR 路由注入` 块（同类非侵入先例），在 sanitize_context 之后、
tool dispatch 之前。`platform == "cli"` 硬门控。

### 4.2 反馈闭环（run_agent.py `run_conversation` 尾部）

```python
# === SMR 反馈闭环 ===
# 仅 CLI 平台且本轮发生过 SMR 路由时记录反馈（EMA 权重学习）。
# 静默降级，绝不影响返回结果。
if getattr(self, "platform", None) == "cli":
    try:
        _smr_hook = getattr(self, "_smr_hook", None)
        if _smr_hook is not None:
            _smr_hook.record_turn_feedback(result)
    except Exception:
        pass

return result
```

reward 推导逻辑（`record_turn_feedback` 内）：

| turn 结果 | reward 类型 | 值 |
|-----------|------------|-----|
| interrupted=True | API_ERROR_TIMEOUT | -0.5 |
| completed=False | SELF_AUDIT_ERROR | -0.3 |
| completed 且 api_calls > 6 | TASK_COMPLETED_WITH_RETRY | +0.5 |
| completed 且 api_calls ≤ 6 | TASK_COMPLETED_CLEAN | +0.7 |

### 4.3 提示展示（cli.py 第 8913 行）

```python
# === SMR CLI notice ===
try:
    _smr_toggle = getattr(self.agent, "_smr_toggle_notice", None)
    if _smr_toggle:
        _cprint(f"\n{_DIM}⚙ {_smr_toggle}{_RST}")
        self.agent._smr_toggle_notice = None
    _smr_switch = getattr(self.agent, "_smr_switch_notice", None)
    if _smr_switch:
        _smr_line = (
            "⚡ SMR 已切换模型: "
            f"{_smr_switch.get('from')} → {_smr_switch.get('to')} "
            f"({_smr_switch.get('task_type')}, score={_smr_switch.get('score')})"
        )
        _cprint(f"\n{_DIM}{_smr_line}{_RST}")
        self.agent._smr_switch_notice = None
except Exception:
    pass
```

---

## 5. 三级开关设计（审查重点）

优先级从高到低，**会话内指令优先于进程默认**：

| 级别 | 方式 | 作用域 | 实现 |
|------|------|--------|------|
| 1 | env `SMR_DISABLE=1` | 进程级 | `_resolve_process_enabled()` 读 env（1/true/yes/on） |
| 2 | config.yaml `smr.enabled: false` | 配置级持久 | 同上，读 yaml |
| 3 | 会话内 `关闭模型切换`/`恢复模型切换` | **仅当前 CLI 会话** | `maybe_toggle()` 设 `_session_override` |

会话内开关关键逻辑：
```python
def _is_enabled(self):
    if self._session_override is not None:
        return self._session_override   # 会话覆盖优先
    return self._resolve_process_enabled()
```

`maybe_toggle` 只匹配 ≤20 字符的短消息（避免长对话误判），命中短语：
- 关闭：关闭模型切换 / 停止模型切换 / 禁用模型切换 / disable model switch
- 恢复：恢复模型切换 / 开启模型切换 / 启用模型切换 / enable model switch

**设计意图**：临时会话干预不污染全局；新开 CLI 回到 env/config 默认，保持路由机制一致性。

---

## 6. 惰性阈值（防抖动，保护 prompt 缓存）

三重惰性避免频繁切换击穿 prompt 缓存：
1. 目标模型 == 当前模型 → 跳过
2. 同 task_type 且上次已路由过同模型 → 跳过
3. 候选得分未超当前模型 `switch_margin`（默认 0.03，config 可调）→ 跳过

`_exceeds_margin` 用与 router 同源公式近似估算当前模型分数（省略 latency 项做保守估计），
当前模型不在 profile 时允许切到已知更优模型。

---

## 7. config.yaml 新增块

```yaml
# === SMR 智能模型路由 (Smart Model Routing) ===
smr:
  enabled: true          # 总开关（默认 true）
  switch_margin: 0.03    # 候选模型得分需超当前模型此值才切换（防抖动，0-1）
```

---

## 8. 验证结果

### 8.1 语法验证
```
run_agent.py       py_compile OK   doubleCR: 0
cli.py             py_compile OK   doubleCR: 0
routing/smr_hook.py py_compile OK  doubleCR: 0
```

### 8.2 隔离集成测试（scripts/test-smr-integration.py）
17/17 通过，覆盖：
- coding 任务触发路由决策 + 分类正确
- 发生模型切换 + 切换携带 base_url/api_key
- 惰性阈值（同 task_type 不重复切换）
- 会话内关闭/恢复指令识别与生效
- SMR_DISABLE=1 进程级禁用
- 反馈闭环无异常
- feedback_log 写入临时目录（隔离）
- EMA 权重更新
- config 模型映射含 18 模型 + 凭证字段

**测试隔离**：临时 HOME + reload + 显式覆盖模块常量，finally rmtree 清理。
验证真实 `~/.bookwormpro/smr/feedback_log.jsonl` 保持 6 行未被污染。

---

## 9. 已知风险与待审查项

| # | 项目 | 说明 | 建议审查角度 |
|---|------|------|------------|
| R1 | 运行时切换模型 | `switch_model` 在 turn 开始时切换，会 rebuild client + 重置 prompt 缓存 | 确认是否影响多轮上下文连续性；惰性阈值是否足够 |
| R2 | 反馈 reward 推导 | `api_calls > 6` 判定为"有重试"，阈值 6 是经验值 | 是否合理？是否应区分正常多工具调用 vs 真实重试 |
| R3 | 凭证处理 | api_key 从 config 读入内存传给 switch_model | 确认不落日志/不进 result dict/不进异常信息 |
| R4 | 进程级开关缓存 | `_process_enabled` 类变量缓存，env 变更需重启 | 是否需要支持热更新 |
| R5 | maybe_toggle 误判 | ≤20 字符 + 关键词匹配 | 是否存在正常短消息误触发开关 |
| R6 | 首轮切换时机 | 每轮都评估，可能首轮就切换 | 是否应保留用户 /model 显式选择的优先级 |

---

## 10. 回滚方案

改动完全可逆，无数据库 schema 变更、无 API 契约变更：

```bash
# 1. 删除新增文件
rm routing/smr_hook.py scripts/test-smr-integration.py docs/smr-smart-model-routing.md

# 2. run_agent.py 移除两处注入块（第 9690-9708、13122-13131 行的 === SMR === 块）
# 3. cli.py 移除第 8913-8930 行 === SMR CLI notice === 块
# 4. config.yaml 移除 smr: 块

# 或最简单：config.yaml 设 smr.enabled: false，或 export SMR_DISABLE=1（无需改代码）
```

**注意**：Windows Git Bash 编辑这些文件时，`patch` 工具会产生 double-CR (\r\r\n) 破坏 AST。
必须用 Python bytes.replace 编辑，编辑后 `python -m py_compile <file>` 并验证
`open(f,'rb').read().count(b'\r\r\n')==0`。

---

## 11. 交付自审（本次会话已做）

```
🟢 规范   3 文件 py_compile 过, doubleCR 全 0, 类型注解齐全
🟢 安全   凭证仅内存传递不落盘, 测试用假 key 隔离, 无 eval/注入
🟢 质量   17/17 隔离测试, 真实数据零污染
🟢 架构   桥接零耦合, 三级开关, 全链路 try/except 可降级
```

CHANGE IMPACT:
- 影响范围：仅 CLI 平台的模型选择
- API 契约变更：无
- 数据库 schema 变更：无
- 安全影响：新增 config 凭证读取路径（已有 custom_providers，非新增暴露面）
- 需重新部署：否（config/env 开关即时生效，代码改动下次启动 CLI 生效）
- 回归风险：LOW

---

## 附录：审查命令速查

```bash
cd C:/Users/leesu/BookwormPRO

# 语法 + doubleCR 检查
python -m py_compile run_agent.py cli.py routing/smr_hook.py
for f in run_agent.py cli.py routing/smr_hook.py; do
  python -c "d=open('$f','rb').read(); print('$f doubleCR:', d.count(b'\r\r\n'))"
done

# 跑隔离集成测试
python scripts/test-smr-integration.py

# 查看注入点
grep -n "SMR" run_agent.py
grep -n "SMR CLI notice\|_smr_switch_notice\|_smr_toggle_notice" cli.py

# 查看桥接模块
cat routing/smr_hook.py

# 查看完整文档
cat docs/smr-smart-model-routing.md
```
