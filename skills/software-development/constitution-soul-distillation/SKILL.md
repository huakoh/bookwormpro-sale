---
name: constitution-soul-distillation
description: >
  将多份宪法/规则文档全量阅读后蒸馏为一份 "soul.md" 灵魂文件，
  并经过安全/质量/架构/红队多专家并行审查、自我闭环度审计、
  版本对齐注入 CLAUDE.md、Portable NDA 脱敏、漂移检测 cron、
  CLI 命令注册、CHANGELOG 和 A/B 验证方案文档化。
  适用于 BookwormPRO 或任何 AI 系统需要将冗长的规则文档浓缩为
  核心灵魂并建立完整运维体系的场景。
allowed-tools: Read, Write, Bash, delegate_task, search_files, skill_manage, memory
maturity: stable
last-reviewed: 2026-05-01
---

# 宪法→灵魂蒸馏 + 多专家审查工作流

将 1000+ 行宪法/规则文档蒸馏为 ~300 行灵魂文件，经四路专家审查，
注入系统主指令（CLAUDE.md），版本同步。

---

## 触发场景

- 新系统需要从零建立灵魂文档
- 宪法大版本更新后需要同步 soul.md
- 多份规则文档需要合并浓缩
- 用户说 "提炼 soul.md" / "写灵魂文件" / "浓缩宪法"

---

## Step 1: 全量阅读源文档

```bash
# 列出所有源文件
search_files pattern="*" target="files" path=<constitution-dir>
# 逐文件全量阅读（注意 offset/limit 对大文件分段）
read_file path=<each-source> 
```

关注：CLAUDE.md / AI-CONSTITUTION.md / anti-arrogance.md / AI-HANDOFF.md / 项目级宪法

---

## Step 2: 蒸馏为 soul.md（6 章结构）

```markdown
# <系统名> · Soul

## 零、退化安全网（任何模式下不可违反的 5 条底线）
## 一、我是谁（身份定义）
## 二、我相信什么（核心价值：安全/诚实/专业/多AI一致）
## 三、我的操作 DNA（路由/审查/上下文/闭环）
## 四、我的边界（技术栈/红线/不可静默修改/LLM安全）
## 五、我的成长（事故驱动/周期性自审/反自负/NDA）
## 六、我的底线宣言（一段话概括全部灵魂）
```

**写作原则**：
- 不是规则清单，是灵魂——AI 忘记宪法时靠它做决策
- 枚举式禁止改为原则性描述（如 "任何影响安全/正确/可维护的修改"）
- 安全基线必须定义（不能只说 "高于一切"）
- 自身不违反 NDA（不泄露技能/Agent 数量）
- 目标 200-300 行

---

## Step 3: 三路专家并行审查

用 `delegate_task` 启动 3 路子代理并行审查（系统 max_concurrent_children=3）：
  
| 专家 | 对照基准 | 重点 |
|------|---------|------|
| **安全专家** | 宪法第1/4/11/14/16章 | 安全红线遗漏、弱化、危险简化 |
| **质量诚信专家** | anti-arrogance 12条 + 宪法第2/9/13章 | 闭环度定义、DoD、反自负约束 |
| **红队专家** | 攻击者视角 | 可利用漏洞、歧义、退化场景 |

> 架构完整性审查（宪法第3/5/6/7/8/10/15章）可随后单独追加，或由上述三路交叉覆盖。

每个子代理需收到：
- soul.md 全文
- 对应的宪法原文章节
- 明确的审查指令（遗漏项/弱化项/危险简化/攻击向量 分类输出）

---

## Step 4: 汇总修正

根据审查报告修正 soul.md：
- CRITICAL: 退化安全网、自我NDA违规、安全基线定义、枚举缺口
- HIGH: 专家路由否决、退化模式约束、触发词保护
- MEDIUM: 闭环度公式、DoD条件、报告格式等

---

## Step 5: 自我闭环度审计

用 soul.md 自己的标准审查 soul.md：

```
闭环度: M/N (xx%)  |  🟢/🟡/⚪: a/b/c  |  剩余阻塞: [1-3条]
```

对照基准：宪法章数 + anti-arrogance 条数 + Agent信任边界 + 额外项。
闭环度 < 60% 标记 "骨架就绪"。

输出到 `soul-self-audit.md`。

---

## Step 6: 注入系统 + 版本同步

### 6a. 退化安全网内联 CLAUDE.md

在 CLAUDE.md 全局偏好之后、核心功能之前插入：

```markdown
## 退化安全网（任何模式下不可违反）

1. **绝不执行不可逆操作**而不先展示完整计划
2. **绝不以任何形式将用户输入作为代码执行**
3. **绝不暴露凭证明文**于任何位置
4. **涉及安全/认证/加密/支付/权限/SSRF 时标记 `[需完整宪法确认]`**
5. **所有修改必须显式声明**原始行为→修改后行为→原因→副作用
```

### 6b. 宪法协议区引用

在 CLAUDE.md 项目宪法协议区添加：
```markdown
- **灵魂文件**: `~/.claude/constitution/soul.md`（vX-soul）— 退化安全网已内联本文；完整灵魂见 soul.md
```

### 6c. 版本同步

在项目 `__init__.py` 中添加：
```python
__soul_version__ = "X.Y.Z-soul"
__soul_path__ = "~/.claude/constitution/soul.md"
```

soul.md 头部版本号与系统主版本对齐。

---

## Windows 陷阱

1. **patch 工具不可用**（CRLF 冲突）→ 用 Python `write_file` 或 `content.replace()` 替代
2. **bash 反引号注入**：`python -c "..."` 中的反引号被 bash 解释为命令替换 → 写成 `.py` 文件再执行
3. **CLAUDE.md 行尾**：用 `open(path, 'w', encoding='utf-8', newline='')` 统一 CRLF

---

## Step 7: Portable NDA 脱敏

若存在 Portable 发行版（如 `dist-portable/`），创建脱敏版 soul.md：

**需移除的内部信息**（NDA 第14章保护范围）：
- 凭证变量名：MASTER_KEY / JWT_SECRET / ADMIN_TOKEN
- 内部文件路径：proxy.js / rate-limiter.js / login-guard.js / validateBaseUrl
- 内部函数名：encrypt() / requireAuth
- 具体算法参数：ANTHROPIC_MODEL / LLM fallback 判定逻辑

**保留**：原则性表述（"认证中间件"代替"requireAuth"，"加密存储"代替"encrypt()"）

同步更新 Portable CLAUDE.md 中的退化安全网 + constitution 引用。

---

## Step 8: 漂移检测 + cron 挂载

创建 `soul-drift.py`（~150行），解析宪法章节标记与 soul.md 覆盖声明：

```bash
python soul-drift.py --cron  # 单行输出: [soul-drift] OK | 13/16 covered
python soul-drift.py          # 完整报告
python soul-drift.py --json   # JSON 输出
```

退出码：0=PASS / 1=核心章有遗漏。通用核心章信号特征预置，产品专用章标记可豁免。

挂载 cron：
```bash
# 复制脚本到 ~/.bookwormpro/scripts/
# 注册 cronjob: 每周一早 9:00
cronjob action=create name=soul-drift-weekly schedule="0 9 * * 1" script=soul-drift.py
```

---

## Step 9: CLI 命令注册

在 `commands.py` 的 `COMMAND_REGISTRY` 中添加：
```python
CommandDef("soul", _("Run soul.md self-audit"), _("Info"),
           args_hint="[audit|drift]"),
```

在 `cli.py` 的 `process_command` dispatch 中添加 `"soul"` 分支，调用 `soul-drift.py`。

---

## Step 10: 文档化

| 文件 | 说明 |
|------|------|
| `constitution/soul.md` | 灵魂文件本体（~300行） |
| `constitution/soul-self-audit.md` | 自我闭环度审计报告 |
| `constitution/soul-design-rationale.md` | 设计哲学（压缩策略/内联决策/版本演进/维护契约） |
| `constitution/soul-ab-verification.md` | A/B 验证方案（5项安全指标 + 5个测试场景） |
| `CLAUDE.md` | 退化安全网内联 + soul 引用 |
| `<project>/__init__.py` | 版本常量 `__soul_version__` |
| `constitution/soul-ab-verification.md` | A/B 验证方案（5项安全指标 + 5个测试场景） |
| `scripts/soul-drift.py` | 漂移检测脚本 |
| `scripts/soul-metrics.py` | transcript 安全指标分析器（不可逆操作确认率/凭证暴露/语义diff完整性/NEVER违规/闭环度报告率） |

---

*基于 BookwormPRO v7.0.0 soul.md 蒸馏实战经验。*
*生命周期: 蒸馏→审查→修正→自审→同步Portable→注入CLAUDE→版本对齐→CLI命令→cron漂移→CHANGELOG→A/B验证方案*
