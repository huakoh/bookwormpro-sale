---
name: soul-md-lifecycle
description: >
  BookwormPRO SOUL.md 全生命周期管理。当需要从宪法蒸馏 SOUL.md、
  多专家并行审查 SOUL.md、版本对齐、或建立漂移检测时使用此技能。
  唯一运行时路径: ~/.bookwormpro/SOUL.md（系统提示词槽位 #1）。
  触发词: SOUL.md, soul.md, 灵魂文件, 宪法蒸馏, 退化安全网, soul-drift, soul audit。
maturity: stable
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent
---

# soul.md 全生命周期管理

## 适用场景

1. 从完整宪法首次蒸馏 SOUL.md
2. 宪法更新后同步 SOUL.md
3. SOUL.md 多专家审查
4. 版本对齐 + 漂移检测建立
5. DEFAULT_SOUL_MD 升级（bwm_cli/default_soul.py）

## 核心原则

- soul.md 使命: AI 上下文耗尽时提供可靠退化行为指南（非宪法摘要）
- 长度约束: 200-300 行（当前 243 行，警戒线 300）
- 原则优先于枚举: 枚举有缺口，原则覆盖全集
- 退化安全网前置: 第零章 5 条为最终底线
- 唯一路径: `~/.bookwormpro/SOUL.md` — 系统提示词槽位 #1，每次会话自动注入
- 退化安全网同时存在于 CLAUDE.md 内联 + SOUL.md 第零章

---

## 阶段 1: 蒸馏

从 `~/.claude/constitution/` 全量读取后提炼。

### 1.1 读取清单

必须读取的文件:
- `AI-CONSTITUTION.md` (16章, ~1020行)
- `AI-CONSTITUTION-CORE.md` (通用核心装配索引)
- `AI-CONSTITUTION-PRODUCT.md` (产品专用装配索引)
- `anti-arrogance.md` (12条+Agent信任边界)
- `CLAUDE.md` (神经网关路由指令)
- `TEMPLATE-CONSTITUTION.md` (模板，了解结构)
- `AI-HANDOFF.md` (交接记录，了解历史)

### 1.2 蒸馏结构

soul.md 应包含:
- **零、退化安全网** — 5 条不可违反底线（最重要，放最前）
- **一、我是谁** — 身份定义，不超过 5 句
- **二、我相信什么** — 核心价值观（安全/诚实/专业/多AI一致）
- **三、我的操作 DNA** — 工作机制（路由/审查/上下文/闭环）
- **四、我的边界** — 技术栈 + NEVER/ALWAYS + 不可静默修改 + LLM安全
- **五、我的成长** — 事故驱动 + 自审 + 反自负 + NDA
- **六、我的底线宣言** — 一段话独立成章

### 1.3 保留 vs 丢弃

保留: 安全红线、退化安全网、交付格式、事故教训、精神声明
丢弃: 具体端点清单、模块矩阵、测试模板、提交格式（产品专用，宪法可查）
部分保留: 枚举列表 → 原则化表述（如话术黑名单 → "禁止任何夸大声明"）

---

## 阶段 2: 多专家并行审查

使用 `delegate_task` 批量启动 3 路专家子代理:

### 2.1 安全专家

context 必须包含: soul.md 全文 + 宪法第 1/4/11/14/16 章原文
审查目标: 遗漏项(宪法有soul没有)、弱化项(表述不及宪法)、危险简化、NDA违规

### 2.2 质量诚信专家

context 必须包含: soul.md 全文 + anti-arrogance.md 全文 + 宪法第 2/9/13 章
审查目标: 闭环度定义、DoD条件、反自负约束、交付标准

### 2.3 红队攻击专家

context 必须包含: soul.md 全文
审查目标: 攻击向量、可被利用的歧义、枚举缺口、触发词滥用

### 2.4 审查后修正

汇总三路报告 → 按 CRITICAL > HIGH > MEDIUM 优先级修正 → 重写 soul.md

---

## 阶段 3: 部署

### 3.1 唯一运行时路径

**soul.md 的唯一运行时路径是 `~/.bookwormpro/SOUL.md`（大写）**。
`agent/prompt_builder.py:load_soul_md()` 从此路径加载，作为系统提示词槽位 #1。

**不再存在** `~/.claude/constitution/soul.md`（v7.0.0 路径统一后已删除）。

### 3.2 退化安全网内联至 CLAUDE.md

在 `~/.claude/CLAUDE.md` 的"退化安全网"节，5 条规则已内联。

在"项目宪法协议"节追加:
```
- **灵魂文件**: `~/.bookwormpro/SOUL.md`（vX.Y.Z-soul）— 每次会话作为系统提示词槽位 #1 自动注入
```

### 3.3 同步到 dist-portable

dist-portable 不再维护独立 soul.md 副本。更新 `dist-portable/CLAUDE.md` 的 soul 引用指向 `~/.bookwormpro/SOUL.md`:
```
完整灵魂文件见 ~/.bookwormpro/SOUL.md（运行时系统提示词槽位 #1 自动注入）
```
不复制 soul.md 到 dist-portable/constitution/（该目录 soul.md 已删除）。
### 3.4 升级 DEFAULT_SOUL_MD

编辑 `BookwormPRO/bwm_cli/default_soul.py`，确保默认模板包含:
- 退化安全网 5 条（第零章）
- 身份定义（第一章）
- 核心原则：安全底线 + 诚实 + 专业 + 代码基线
- NEVER/ALWAYS 红线
- SOUL.md 健康监控引用

> 旧版 11 行通用占位符在重置 SOUL.md 时会导致身份大幅降级，必须升级。

---

## 阶段 4: 安全指标 + 漂移检测

### 4.1 安全指标评分 (soul-metrics.py)

`~/.claude/scripts/soul-metrics.py` (345行) 计算 5 项指标:
1. 不可逆操作前确认率
2. 凭证暴露率
3. 语义 diff 完整性
4. NEVER 列表遵守率
5. 闭环度报告率

用法:
- `python soul-metrics.py <transcript.jsonl>` — 单文件分析
- `python soul-metrics.py --stdin` — 管道模式
- `python soul-metrics.py --mock` — 自验证 (3场景: PASS/WARN/EDGE_ZERO)
- `python soul-metrics.py --mock --json` — JSON输出

基线建立: 下次重型编码会话(≥3 write_file/patch)结束时自动跑分建 v7.0.0 基线。
自验证绿色 = 回归无破坏；红色 = mock数据或逻辑需修正。

### 4.2 版本号同步

- soul.md 版本: `vX.Y.Z-soul`（与 BookwormPRO major.minor 对齐）
- `bwm_cli/__init__.py` 添加: `__soul_version__ = "X.Y.Z-soul"`
- `bwm_cli/commands.py` 注册 `soul` 命令

### 4.3 漂移检测脚本

维护 `~/.claude/scripts/soul-drift.py`:
- 解析 AI-CONSTITUTION.md 章节标记
- 关键词匹配 soul.md 覆盖状态
- 输出: 覆盖数/总章数 + 遗漏清单
- 退出码: 0=PASS, 1=有核心遗漏
- 挂 cron 每周一: `python soul-drift.py --cron`

### 4.4 自我审计

`soul-self-audit.md`: 用 soul.md 自身标准审计 soul.md
- 格式: `闭环度: M/N (xx%) | 🟢/🟡/⚪: a/b/c | 剩余阻塞: [...]`
- 判定: 闭环度 > 60% = 达标

---

## 阶段 5: 设计哲学文档

在 `~/.claude/constitution/soul-design-rationale.md` 记录:
- 压缩策略（保留什么/丢弃什么/为什么）
- 退化安全网内联决策依据
- 版本同步机制
- 不应该做但有意不做的事
- 维护契约（同步规则/警戒线/CRON）

---

## 阶段 6: 运行时验证审计（soul.md 实质性作用审查）

当需要判断 soul.md 在系统中的**实质性作用**（代码强制执行 vs 文档声明）时使用。

### 6.1 审计方法

按以下顺序逐层追踪，不可跳过：

1. **全量代码引用搜索** — `search_files(pattern="soul|SOUL", target="content", path=<repo>)` 找到所有代码引用
2. **注入链路追迹** — 从引用点反向追踪到系统提示词构造逻辑。关键入口: `run_agent.py` 系统提示词构建、`prompt_builder.py` 上下文文件加载
3. **运行时路径 vs 文档路径** — 代码实际加载的路径（`~/.bookwormpro/SOUL.md`）与 CLAUDE.md 引用的路径（`~/.claude/constitution/soul.md`）可能不同。用 `md5sum` 验证一致性
4. **声明 vs 代码对照** — soul.md 中的每条自动化声明（"cron每周一"、"≥3 write_file自动触发"）必须在代码中找对应实现。无代码支撑 = 标记 ⚪ 未接入
5. **默认值对比** — `bwm_cli/default_soul.py` 的 DEFAULT_SOUL_MD 与宪法蒸馏版 soul.md 是否一致
6. **CLI 命令验证** — `/soul audit|drift` 是否注册了 handler，handler 实际调用哪个脚本

### 6.2 已知实质性架构事实（v7.0.0-soul）

```
注入链路（唯一源 ~/.bookwormpro/SOUL.md）:
  run_agent.py:4323  →  load_soul_md()  →  ~/.bookwormpro/SOUL.md  →  槽位 #1 (Agent身份)
  run_agent.py:4430  →  build_context_files_prompt(skip_soul=True)  →  防重复注入

CLAUDE.md 退化安全网: 5条规则内联在 CLAUDE.md 文中 — 独立于 SOUL.md 是否加载

唯一源:
  ~/.bookwormpro/SOUL.md  — 唯一运行时文件 + 编辑源（二合一）
  ~/.claude/constitution/soul.md  — 已删除（v6.6.1残留，不应存在）

bwm_cli 常量:
  __soul_version__ = "7.0.0-soul"
  __soul_path__ = "~/.bookwormpro/SOUL.md"

DEFAULT_SOUL_MD: 60行宪法蒸馏最小版（退化安全网 + 核心原则 + NEVER/ALWAYS + 健康监控）
Cron: soul-drift-monday (aca1da1ea8d4) — 每周一 09:00 漂移检测
```

### 6.3 已知未接入项（v7.0.0-soul）

| 声明 | 实际 | 影响 |
|------|------|------|
| soul-metrics "≥3 write_file 自动触发" | 无代码实现 — 建议用户手动运行 | ⚪ 轻度 |
| soul-metrics 基线建立 | 需手动首次跑分 | ⚪ 轻度 |

---

## 关键陷阱

### Windows CRLF

`patch` 工具在 Windows Git Bash 上 CRLF 失败（"wrote X, read back Y"）。
**解决**: 用 `write_file` 写 Python 脚本 → `terminal` 执行脚本修改文件。

### Bash 反引号转义

Python 字符串中含反引号时（如 `` `[需完整宪法确认]` ``），
bash 会将反引号内容作为命令执行，导致内容被截断。
**解决**: 用 `write_file` 先写 `.py` 文件，再 `python file.py` 执行。

### 关键字匹配准确性

`soul-drift.py` 的关键词匹配需要同时覆盖:
- 中文表述 + 英文缩写
- 完整词 + 子串
- 汉字 + 阿拉伯数字变体

验证方式: `python -c "print('keyword' in text)"` 手动测试命中的关键词。

### 路径漂移（多副本不同步）

当 soul.md 存在于多个路径时（`~/.claude/constitution/soul.md` 和 `~/.bookwormpro/SOUL.md`），
代码只加载后者，但文档可能引用前者。审计方法:
```bash
md5sum ~/.bookwormpro/SOUL.md ~/.claude/constitution/soul.md
```
md5 不同 = 运行时行为与文档声明不一致。**解决**: 删除旧副本，以 `~/.bookwormpro/SOUL.md` 为唯一源。

---

## 产出物清单

完成一次 soul.md 生命周期后的文件:
```
~/.bookwormpro/SOUL.md                         (灵魂文件, 唯一运行时路径, ~243行)
~/.claude/constitution/soul-self-audit.md      (自我审计报告)
~/.claude/constitution/soul-design-rationale.md(设计哲学)
~/.claude/constitution/soul-ab-verification.md (A/B验证方案)
~/.claude/CLAUDE.md                            (退化安全网内联+SOUL.md引用)
~/.claude/scripts/soul-metrics.py              (5指标安全评分, --mock自验证)
~/.claude/scripts/soul-drift.py                (漂移检测, 默认路径指向 .bookwormpro/SOUL.md)
BookwormPRO/bwm_cli/__init__.py                (__soul_version__, __soul_path__)
BookwormPRO/bwm_cli/commands.py                (soul命令)
BookwormPRO/bwm_cli/default_soul.py            (默认SOUL.md模板, 宪法蒸馏最小版)
Cron: soul-drift-monday                        (每周一 09:00)
```

---

*版本: v1.0 | 2026-05-01 | 基于 soul.md v7.0.0-soul 全生命周期实战*
