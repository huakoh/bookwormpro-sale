# BookwormPRO 借鉴 hermes-agent 升级方案

版本：v1.0
日期：2026-07-09
来源：NousResearch/hermes-agent（commit 8e73481, 2026-07-07 主干最新）
审查方式：架构专家 + 安全工程师 + DevOps/测试工程师 三路并行论证

---

## 一、背景

BookwormPRO 与 hermes-agent 同源，代码结构高度重叠。本次审查发现部分模块
（checkpoint_manager、budget_config、insights.py）已存在但不完整，另有 6 个
模块（turn_finalizer、verification_stop、verify_hooks、learn_prompt、
background_review、learning_graph、image_routing）完全缺失。

三路专家一致结论：**本次升级的最大风险不是技术可行性，而是安全性**。
所有涉及"自动写入磁盘""自动执行脚本""LLM 驱动决策"的功能，在补齐前
必须先修复已知的 P0-1（API Key 日志未脱敏）和 P0-3（无 sanitize_prompt），
否则新功能会放大现有漏洞的危害半径。

---

## 二、九项候选综合评级

| 编号 | 项目 | 架构评级 | 安全等级 | Windows风险 | 测试难度 | 现状 |
|----|------|:---:|:---:|:---:|:---:|------|
| 1 | checkpoint_manager 补全 | A | 🔴红 | 高 | 难 | 已有653行(hermes 1675行) |
| 2 | verification_stop+verify_hooks | A | 🔴红 | 低 | 易 | 完全缺失 |
| 3 | 自动skill审查触发器 | A | 🔴红 | 高 | 难 | 完全缺失 |
| 4 | /学习命令(learn_prompt) | B | 🔴红 | 低 | 易 | 完全缺失 |
| 5 | budget_config 补全 | A | 🟡黄 | 低 | 易 | 已有52行(hermes 114行) |
| 6 | insights引擎激活 | B | 🟡黄 | 中 | 中 | 已有932行(近乎完整) |
| 7 | per-skill provider绑定 | B | 🔴红 | 低 | 中 | 完全缺失 |
| 8 | 索引化内存 | C | 🟡黄 | 中 | 中 | 已有SQLite三层记忆(更优) |
| 9 | kanban任务调度 | B | 🟡黄 | 中 | 中 | 完全缺失 |

**关键分歧点**：架构师认为 checkpoint_manager/verification_stop 是最高优先级
基础设施；安全工程师认为这两项恰恰是红色风险最集中的地方（git 快照泄漏密钥、
验证脚本任意代码执行）；DevOps 工程师指出 checkpoint_manager 和自动触发器
在 Windows 上技术难度最高（symlink 权限、asyncio ProactorEventLoop、无 fork）。

三方结论收敛为：**这两项价值最高，但必须最后做，且做之前必须先补安全护栏**。

---

## 三、最终实施顺序（四批次）

### 批次 0（前置阻塞项，不完成不得开始批次1）

- 修复 P0-1：API Key 日志脱敏（复用现有 redact.py 逻辑扩展）
- 修复 P0-3：sanitize_prompt 注入过滤器
- 建立统一脱敏管道 secret_redact.py，供后续所有新功能共用
- 建立 SKILL.md schema 校验器（拒绝 execute/shell/script 等危险字段）

### 批次 1（低风险高回报，可立即上线）

| 优先级 | 项目 | 理由 |
|---|---|---|
| P1 | /学习命令汉化移植 | 零平台风险，用户可见收益最高，但需先接入 schema 校验器 |
| P1 | budget_config 补全(52→114行) | 纯配置逻辑，硬上限防 context flooding |
| P2 | verification_stop + verify_hooks | 逻辑清晰易测试，脚本执行需白名单路径+哈希签名 |
| P2 | per-skill provider绑定 | provider URL 白名单+仅允许环境变量引用API Key |

### 批次 2（中等风险，需专项测试）

| 优先级 | 项目 | 理由 |
|---|---|---|
| P3 | insights引擎激活 | 已932行，接通命令路由即可，历史数据需脱敏后再注入 |
| P3 | 索引化内存 → **改为**"增强SQLite三层记忆的关键词索引" | 原方案与现有更优方案冲突，重新定义需求 |
| P3 | kanban任务调度 | 建立在cron/scheduler.py之上而非替代，circuit_breaker状态写SQLite |

### 批次 3（高风险，需充分验证，独立Sprint）

| 优先级 | 项目 | 理由 |
|---|---|---|
| P4 | checkpoint_manager 补全(653→1675行) | 需先做secret扫描+.gitignore白名单，Windows symlink需专项验证 |
| P4 | 自动skill审查触发器(turn_finalizer) | asyncio+Windows进程管理难度最高，触发条件必须走静态规则非LLM决定 |

---

## 四、强制安全控制清单（逐项落地要求）

1. **checkpoint_manager**：白名单模式快照（默认拒绝一切）+ secret pattern扫描
   + 禁止快照 .env/audit.db/*.key/*.pem + dry-run预览确认
2. **verification_stop**：验证脚本仅限白名单路径 + SHA-256哈希校验（复用
   skill_crypto.py）+ 30秒超时 + 执行日志写audit.db
3. **自动skill触发器**：触发条件必须静态规则，不可由LLM动态决定 + 全局开关
   `background_triggers: false` + 异步执行权限不得高于只读
4. **/学习命令**：生成内容仅走结构化schema（拒绝execute/shell字段）+ 写入前
   展示diff需用户确认 + 路径白名单仅限/skills/ + 生成后用skill_crypto签名
5. **budget_config**：硬上限32KB/工具结果，SKILL.md不可覆盖 + 截断处加明确标记
6. **insights引擎**：注入prompt前脱敏 + 仅读最近N条非全量 + session文件HMAC校验
7. **per-skill provider绑定**：provider URL白名单（拒绝IP/localhost/内网段）+
   仅允许https + API Key只能引用环境变量名，不可明文写入SKILL.md
8. **索引化内存**：写入前脱敏 + 检索结果过滤secret pattern + 索引文件加密存储
9. **kanban调度**：队列文件HMAC签名 + circuit_breaker状态只能通过主配置修改 +
   高危任务（文件写入/网络/脚本）逐一用户确认

---

## 五、汉化规范（DevOps工程师制定）

### 编码标准
```python
# 文件头统一声明
# -*- coding: utf-8 -*-

# 所有 open() 显式编码
with open(filepath, 'r', encoding='utf-8') as f:
    ...
```

### Windows/Git Bash 终端兼容
```bash
export LANG=zh_CN.UTF-8
export PYTHONIOENCODING=utf-8
```
```python
# bwm_cli 入口点
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
```

### 汉化覆盖清单
- [ ] argparse/click 的 help/description 文字
- [ ] 所有 print()/logging 用户提示
- [ ] 异常 raise 中的错误消息
- [ ] 配置文件注释（建议但非必须）

### 不应汉化
- 变量名/函数名/类名（保持英文）
- 日志JSON字段名、API请求/响应字段名
- git commit message、环境变量名（如 OPENAI_API_KEY）

---

## 六、架构红线（长期维护约束）

1. turn_finalizer.py 是多项功能的枢纽，批次3启动前必须先建立完整骨架
2. SKILL.md schema 需在批次1开始前统一定义，避免/学习命令与provider绑定各自
   产生不兼容格式
3. 所有异步任务统一走 cron/scheduler.py，不引入第二套异步机制
4. checkpoint_manager 补全后应立即接入 circuit_breaker 状态持久化

---

## 七、实施进度追踪（实时更新）

> 本章记录实际执行情况，与前述规划表可能有出入——以本章为准。

### 批次0 · 安全护栏 ✅ 已完成（2026-07-09）

| 项目 | 状态 | 交付物 | 验证 |
|------|------|--------|------|
| P0-1 敏感信息脱敏 | ✅ | agent/redact.py（811行，28类密钥前缀+JWT/私钥/DB连接串/授权头） | bwm_logging 已预留 RedactingFormatter，补文件即全链路生效；端到端 logger→磁盘无明文残留 |
| P0-3 注入过滤 | ✅ | tools/threat_patterns.py（284行，all/context/strict 三作用域，28条模式含C2检测+NFKC正规化） | memory_tool + prompt_builder 内联旧版（11条/10条）改为委托共享库+fallback |

验收脚本：scripts/test_batch0_security.py — **15/15 通过**

### 批次1 · 低风险高回报 ✅ 部分完成（2026-07-09）

| 项目 | 状态 | 说明 |
|------|------|------|
| budget_config 补全 | ✅ | 52→95行。补 resolve_threshold 的 min() 上限保护 + budget_for_context_window 动态缩放。验证：200K不变/32K缩放/4K下限/None回退 全过 |
| /学习 命令 | ✅ | learn_prompt.py 移植（author 改 BookwormPRO）+ commands.py 注册（别名 /学习）+ cli.py dispatch + _handle_learn_command handler（中文提示）。全链路验证过 |
| verification_stop | ⏸️ 移至批次3 | 依赖 coding_context.py(883)+verification_evidence.py(618) 两个缺失大模块，集成点在主循环，与 turn_finalizer 共享接线，拆开做会重复改主循环 |
| per-skill provider 绑定 | ❌ 剔除 | **核实 hermes 当前主干代码后确认此特性不存在**——是早期 v0.10 博客概念，后来改为 `hermes model` 全局切换。无法移植不存在的东西。如需应重新定义为自研需求 |

### 批次2 · 中风险 ✅ 已完成（2026-07-09）

| 项目 | 状态 | 说明 |
|------|------|------|
| insights 引擎激活 | ✅ | 已完全接线(dispatch+handler+InsightsEngine)，实测85行报告可运行 |
| 索引化内存改造 | ✅ | 新建 agent/memory_search.py(FTS5 trigram 中英文检索) + /记忆搜索命令。不动僵化的三层记忆，纯增量 |
| kanban 调度 | ✅ | 不移植15000行庞大子系统，落地核心价值:cron/jobs.py mark_job_run 加 consecutive_failures 熔断(连续5次失败自动暂停 state=circuit_open) |

### 批次3 · 高风险 ✅ 已完成（2026-07-09）

| 项目 | 状态 | 说明 |
|------|------|------|
| verification_stop 全子系统 | ✅ | 移植5文件(含_subprocess_compat/coding_context/verification_evidence/verify_hooks/verification_stop) + run_agent.py 三处接线(文件变更记录/收尾nudge注入/per-turn重置)。行为验证:代码触发/文档不触发/防死循环 |
| checkpoint_manager 补全 | ✅ | 整体升级为 hermes 单一共享 git 对象库(653→1675行,含 auto-prune/orphan清理/尺寸上限/遗留迁移)。强化 secret exclude 白名单(.env/*.key/*.pem/audit.db/vpn.yaml 等)。Windows 端到端验证:密钥排除+代码跟踪+restore+auto-prune 全过 |
| 自动 skill 审查触发器 | ✅ | 核实后发现 BookwormPRO 已完整实现:静态规则触发(_skill_nudge_interval=10,非LLM决定)+后台线程 review agent(_spawn_background_review)+3个review prompt常量。符合安全要求,无需移植 |

---

## 八、过程中的关键发现

1. **BookwormPRO 与 hermes 同源**：之前的安全审计只是"发现问题未落地"，而 hermes 主干早有成熟实现，直接移植比自研更快更可靠。
2. **诚实核实原则**：per-skill provider 是宣传概念而非实际代码，核实后剔除——不凭空移植不存在的东西。
3. **Windows CRLF 陷阱新变体**：写含 `print("\n...")` 的代码块时，`open(newline='\r\n')` 会把 `\n` 转义误转成真实换行→SyntaxError。解法用 bytes 模式精准替换。

文档路径：C:\Users\leesu\BookwormPRO\docs\hermes-upgrade-plan-2026-07-09.md
