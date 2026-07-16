# BookwormPRO 三窗口并行优化 · 0bug 终审提示词（2026-07-09）

> **用途**：重启 BookwormPRO 后，在新对话框粘贴本文件路径或内容，触发对本轮三个窗口全部优化的 0bug 终审。
> **本文件自包含**——不依赖任何窗口的会话上下文。
> **项目**：`C:\Users\leesu\BookwormPRO\`（hermes-agent fork，Windows + Git Bash，Python 3.12）
> **审核基调**：三个窗口并行改了同一套代码，**最大风险是交叉覆盖 / 行号漂移 / 隐性回归**，不是单点 bug。

---

## 0. 审核指令（贴给审核 AI）

```
请对 BookwormPRO 本轮三个并行窗口的全部优化做 0bug 终审。这是"多窗口改同一代码库"的
集成审查，不是单功能审查。请按以下顺序执行，每步给结论（🟢通过/🟡警告/🔴阻断）：

第一优先：交叉冲突审查（最高风险）
  run_agent.py（12k行核心，三个窗口都改了它的 run_conversation）被三方注入：
    - 工作线A(verify): 9146/9738/12852 三处
    - 工作线B(SMR): 9690/13122 两处 + bwr_hook 9684
  逐一确认：① 三方注入块是否都完整存在、无一方覆盖另一方
            ② 注入顺序是否合理（BWR→SMR→tool dispatch→verify收尾→SMR反馈）
            ③ role alternation 是否被破坏（verify 注 user nudge，SMR 不注消息）
            ④ 异常隔离：任一注入块抛异常是否会逃逸影响主对话

第二优先：语法与污染基线
  python -m py_compile 全部改动的 .py；每个文件 open('rb').count(b'\r\r\n') 必须==0

第三优先：各线功能回归（跑三条线的测试脚本）
  python scripts/test_batch0_security.py       # 工作线A安全 期望15/15
  python scripts/test_redact_p0_1.py           # 工作线A脱敏
  python scripts/test-smr-integration.py       # 工作线B SMR 期望17/17

第四优先：重点风险深挖（见第4节 R1-R10）

输出：交叉冲突结论 + 三线各自结论 + R1-R10 逐项 + 总 verdict。
发现🔴阻断项必须给出精确行号和修复建议。
```

---

## 1. 三条工作线总览

| 线 | 主题 | 窗口 | 状态 |
|----|------|------|------|
| **A** | hermes-agent 借鉴升级（安全/检索/验证/检查点） | 本总结主线 | 4批完成 |
| **B** | SMR 智能模型路由 + BWR drift 纠错 | 另一窗口 | 已接入 |
| **C** | skills_tool 重写 + skill_usage 修复 | 另一窗口 | 已改 |

---

## 2. 完整改动清单（git status 实测）

### 2.1 修改文件（11 个）

| 文件 | 变动规模 | 归属线 | 说明 |
|------|---------|--------|------|
| `run_agent.py` | +64 | **A+B 共改** | ⚠️三方注入同一 run_conversation，最高风险 |
| `cli.py` | +98 | A+B | A:/学习+/记忆搜索命令；B:SMR notice展示 |
| `agent/redact.py` | 大改(1151) | A | 脱敏整体移植 hermes 811行版 |
| `agent/prompt_builder.py` | +35 | A | 上下文注入过滤委托 threat_patterns |
| `tools/checkpoint_manager.py` | 大改(1390) | A | 升级单一共享git库 |
| `tools/memory_tool.py` | +20 | A | 内存写入委托 threat_patterns |
| `tools/budget_config.py` | +45 | A | 动态缩放 |
| `cron/jobs.py` | +21 | A | 连续失败熔断 |
| `bwm_cli/commands.py` | +4 | A | /学习 /记忆搜索 注册 |
| `tools/skills_tool.py` | **大改(3064!)** | **C** | ⚠️几乎全文重写，重点审查 |
| `tools/skill_usage.py` | +4 | C | 移除 bundled 过滤 |

### 2.2 新增文件

| 文件 | 行数 | 归属 | 作用 |
|------|------|------|------|
| `agent/redact.py`(改) / `tools/threat_patterns.py` | 811/284 | A | 脱敏+注入过滤 |
| `agent/memory_search.py` | ~200 | A | FTS5 trigram 记忆检索 |
| `agent/learn_prompt.py` | 150 | A | /学习 提示词 |
| `agent/verification_stop.py` `verification_evidence.py` `coding_context.py` `verify_hooks.py` | 313/618/883/69 | A | 验证止损子系统 |
| `bwm_cli/_subprocess_compat.py` | 234 | A | Windows subprocess 兼容 |
| `routing/smr_hook.py` | 340 | B | SMR 主流程桥接 |
| `agent/bwr_drift.py` | 432 | B | BWR 路由漂移纠错 |
| `scripts/bwr_drift_decay.py` | 20 | B | drift 衰减 cron |
| `scripts/test-smr-integration.py` | 218 | B | SMR 隔离测试 |
| `scripts/test_batch0_security.py` `test_redact_p0_1.py` | - | A | A线测试 |

### 2.3 配置

- `~/.bookwormpro/config.yaml` 新增 `smr:` 块（B线，enabled/switch_margin）

---

## 3. run_agent.py 三方注入点地图（交叉冲突审查用）

按行号从上到下的注入顺序（实测行号，重启后可能漂移，以 grep 为准）：

```
9146  [A verify]  文件变更工具路径记录（write_file/patch → _turn_file_mutation_paths）
9684  [B bwr]     BWRHook 路由注入
9690  [B smr]     SMRHook 路由+切换注入（run_conversation 入口）
9738  [A verify]  per-turn 状态重置（_turn_file_mutation_paths / _verification_stop_nudges）
12852 [A verify]  收尾 nudge 注入（编辑代码无验证证据 → 追 user nudge continue）
13122 [B smr]     SMR 反馈闭环（return result 前）
```

**审查关键**：
- A 的 9738 重置 vs B 的 9690 路由：谁先执行？重置应在路由前还是后？
- A 的 12852 收尾 nudge(注 user 消息 continue) vs B 的 13122 反馈(不注消息)：
  若 A 触发 continue，是否会导致 B 的 13122 反馈闭环被跳过或重复执行？
- 三方都是 try/except 降级，确认异常不逃逸。

---

## 4. 重点风险清单（深挖项）

### 工作线 A（hermes 升级）
- **RA1** verify 收尾 nudge 注 user 消息后 continue，与 SMR 反馈闭环的执行次序——
  会不会因 continue 导致同一 turn 反馈被记录多次 / 漏记？
- **RA2** checkpoint_manager 从 per-project 独立库改为单一共享 git 库，
  旧的 per-project checkpoint 数据是否有迁移路径？首次运行是否会丢历史快照？
- **RA3** redact.py 整体替换，确认 bwm_logging 的 RedactingFormatter 挂载点未变、日志脱敏仍生效。
- **RA4** cron/jobs.py 熔断：circuit_open 状态的 job 如何恢复？是否只能手动？

### 工作线 B（SMR，文档 smr-upgrade-review 的 R1-R6）
- **RB1** 运行时 switch_model 中途切换 → rebuild client + 重置 prompt 缓存，多轮上下文连续性？
- **RB2** reward 阈值 api_calls>6 判定"重试"，是否误伤正常多工具调用？
- **RB3** api_key 从 config 读入内存传 switch_model，确认不落日志/不进 result/不进异常。
  ⚠️与 A 线 redact.py 交叉：SMR 切换日志是否被 redact 覆盖？
- **RB4** maybe_toggle ≤20字符短消息匹配，正常短消息误触发开关的概率？
- **RB5** 每轮都评估切换，是否覆盖了用户 /model 显式选择的优先级？

### 工作线 C（skills_tool 重写，我掌握最少，重点审）
- **RC1** tools/skills_tool.py 3064行几乎全文重写——这是本轮改动最大的单文件，
  必须确认：所有原有 skill 加载/注册/查询接口签名未变（调用方 model_tools.py/run_agent.py 不报错）。
- **RC2** skill_usage.py 移除 bundled 过滤后，技能使用统计是否会把内置技能也计入导致数据失真？

---

## 5. 验证基线（审核必跑）

```bash
cd C:/Users/leesu/BookwormPRO

# ① 语法 + 双CR（三方改动后）
for f in run_agent.py cli.py agent/redact.py tools/checkpoint_manager.py \
         tools/skills_tool.py routing/smr_hook.py agent/verification_stop.py; do
  python -c "import ast; ast.parse(open('$f',encoding='utf-8').read()); print('$f OK')"
  python -c "print('$f 双CR:', open('$f','rb').read().count(b'\r\r\n'))"
done

# ② 三线测试
python scripts/test_batch0_security.py       # A 期望 15/15
python scripts/test_redact_p0_1.py           # A
python scripts/test-smr-integration.py       # B 期望 17/17

# ③ 全模块导入回归（确认三方无 import 冲突）
python -c "
import sys; sys.path.insert(0,'.')
import run_agent, cli
import agent.redact, agent.memory_search, agent.verification_stop, agent.learn_prompt
import tools.threat_patterns, tools.budget_config, tools.checkpoint_manager
import tools.skills_tool, tools.skill_usage
import routing.smr_hook, agent.bwr_drift
import cron.jobs, bwm_cli.commands, bwm_cli._subprocess_compat
print('[成功] 全部模块导入无冲突')
"

# ④ 三方注入点地图
grep -n 'verify-on-stop\|=== SMR\|BWRHook\|bwr_drift' run_agent.py
```

---

## 6. 环境陷阱（编辑修复时必守）

- 全部 CRLF。修复用 **bytes 模式** `open(wb)`，禁 `open(newline='\r\n')`
  （会把 `print("\n")` 的 `\n` 转义误转真实换行 → SyntaxError）。
- bytes 写 CRLF 若原文已 `\r\n` 再写 `\r\n` → `\r\r\n` 双CR污染破坏 AST。写完必查 `count(b'\r\r\n')==0`。
- bytes literal 禁含中文（用 `\uXXXX`）。`patch` 工具在此项目会产生双CR，改用 Python bytes 编辑。

---

## 6.5 本轮增补：SMR 会话开关污染 Bug（2026-07-09 午后）

### 现象
用户发"关闭模型切换"，SMR 仍持续自动切换模型（agent.log 同一 session_id 在关闭指令后连续 3 次切换 fable-5→sonnet-4-6，11:03/11:04/11:09）。

### 根因（v1 认知：BWR 注入污染下游）
`run_agent.py` ~9686 `_bwr.inject_directive(user_message)` 把用户原文前面拼接 `[BWR:...] 置信度... [MUST_INVOKE_SKILL...]` 前缀，消息从几字符暴增到几百字符。下游 SMR `maybe_toggle` 有 `if len(msg)>20: return None` 短消息判定 → 脏消息超长被判"非开关指令"返回 None → 走 else 分支 `route_and_switch` 照常切换。

### 🔴 根因修正（v2 · 2026-07-09 晚，v1 修复经 live E2E 证伪后深挖）
**v1 修复不完整**：污染不止 BWR 一层。真正的主污染源在**上游 cli.py**——`run_agent()` 闭包在调 `run_conversation` 前，会把 `_pending_model_switch_note`（cli.py:5249，手动/SMR 切模型后留的 `[Note: model was just switched...]` ~100 字符英文提示）和 `_voice_prefix` 前置拼进 `agent_message`（cli.py:8742）。所以到达 run_agent:9687 时 `user_message` **已被上游拼接污染**，v1 在 9688(BWR) 之前存的"原文"根本不净。
- **证据链**：用户手动 /model 切 opus → 设 pending note → 下一轮打"关闭模型切换"被前置成 135 字符 → 9687 存的 `_smr_raw_message` 是脏的 → `len>20` 漏判 → route 切 sonnet（agent.log session `20260709_143355` 14:34:44 坐实）。用户看到的"模型切换已关闭…"是**模型幻觉的确认语**（在助手回复框里），非代码提示（代码提示带 `⚙` 前缀，cli.py:8918）。

### 修复 v1（run_agent.py 2 处，**不完整，已被 v2 取代**）
1. ~9687 BWR 注入前存 `self._smr_raw_message = user_message`（只剥了 BWR 一层，未剥上游 note/voice）
2. ~9701 `maybe_toggle(getattr(self,"_smr_raw_message",None) or user_message)` 用该消息判开关

### 修复 v2（显式传参 · 治本 · 3 处，2026-07-09 晚）
把 cli.py 手里的**净原文**（未经任何前置拼接的用户输入 `message`）显式传进来，不再依赖"在某一层之前存原文"的脆弱假设：
1. `run_agent.py` run_conversation 签名新增 `raw_user_message: Optional[str] = None`
2. `run_agent.py` ~9687 `self._smr_raw_message = raw_user_message if raw_user_message is not None else user_message`（CLI 传净原文；非 CLI 调用方缺省回退旧行为）
3. `cli.py` ~8757 调用点新增 `raw_user_message=message`（8738 前的净入参，先于 voice_prefix/note/BWR 任何拼接）
   （`route_and_switch` 仍用注入后消息做意图路由，不动）

### 附带修复（routing/smr_hook.py）
- 第18行后补文档警告：短语须精确子串匹配，勿加夹字（"暂停模型自动切换"含"自动"隔断"模型切换"不命中）
- 关闭确认提示语注入真实 model 名：`f"...固定使用 {self.agent.model}"`，带兜底不崩溃

### 排查结论（同类隐患）
- record_turn_feedback(13131)：只吃 result dict，无隐患 🟢
- BWR 反馈闭环(13084)：用 original_user_message(净)，无隐患 🟢
- codex ack 判断(2807/2922)：user_message 非关键因子，影响可忽略，记为次要项 🟡
- 全项目仅 9699-9706 一处 SMR 调用，无第二路径

### 关键教训（已固化为 skill: bwr-injection-downstream-contamination）
1. **改 .py 后必须重启 CLI**：Python 长驻进程不热重载。本 bug 因 CLI 是今早 02:08 旧进程、修复 11:12 写入，被误判"还是不行"3 次。诊断必查"进程启动时间 vs 代码修改时间"。
2. **模拟测试须复现真实数据流**：传纯净字符串会命中开关误判"逻辑无 bug"，必须传 BWR 注入后的脏消息。查真实 agent.log 坐实，别用简化测试自证清白。
3. **【v2 新增】污染是多层的，复现必须复现"最上游"那层**：v1 只模拟 BWR 单层污染就自证 PASS，但真实链路上 cli.py 的 `_pending_model_switch_note`/`_voice_prefix` 在 BWR 之前就拼了。教训：定位"净原文"必须回溯到调用栈**最顶端的用户输入**（cli.py 的 `message`），而非在中途某层"之前"存。修复用**显式传参**从源头传净值，比"猜哪层之前存"鲁棒。诊断"进程是新的、代码是新的、行为却是旧的"时，第一嫌疑=测的路径≠实时真正走的路径（本例确认语文本对不上=铁证）。

### 验收状态
- [作废] ~~v1 [已验·代码级]~~：v1 的数据流复现只模拟了 BWR 单层污染，**未覆盖上游 note/voice 污染**，被 live E2E（14:34 用户实测：关闭后"你好"仍切 opus→sonnet）证伪。教训见下方第 3 条。
- [已验·代码级 v2 2026-07-09 晚] 显式传参 3 处已落；语法 AST_OK、双CR=0；签名含 raw_user_message；**污染场景数据流复现**：135 字符（switch-note 前置）污染消息 + 新接线 → `_smr_raw_message`=净"关闭模型切换" → maybe_toggle 命中关闭 → 关闭后 route_and_switch 返回 None；非CLI 缺省回退正常；test-smr-integration 17/17 无回归；run_agent+cli import 无冲突
- [✅ 已验·live E2E PASS 2026-07-09 晚] 用户重启后按污染场景复测：手动 /model 切 opus(制造 pending note)→ 发"关闭模型切换"→ **`⚙ 已在当前会话关闭 SMR 模型自动切换…固定使用 claude-opus-4-8`（⚙ 前缀=代码真命中，非幻觉）**→ 发"你好"无 `⚡ SMR 已切换` → 再手动 /mo 切 gpt-5.3-codex-spark 后"你好"仍停留(SMR 确已停用)。三重证据：①⚙命中 ②无⚡切换 ③agent.log 最后一条"SMR 已切换"停在 14:34:44(v1 失败旧 session)，disable 后全程无新切换。**fix 组1 闭环。**

---

## 6.6 本轮增补：影子模型工具调用文本化逃逸（2026-07-09 午后，核心链路改动·终审重点）

### 现象
claude-fable-5（影子模型，opus 偶发也会）下，工具调用以纯文本 `<invoke name="..."><parameter ...>` XML 泄漏到终端正文，且工具**未执行**。三次稳定复现。

### 根因（两层）
- **执行层**：`agent/transports/chat_completions.py` normalize ~368 行 `if msg.tool_calls:` 只认结构化 tool_calls 字段。影子模型偶发把工具调用写进 content 正文（Anthropic XML 风格）而非 tool_calls → 捕获不到 → 不执行。
- **显示层**：`agent/response_handler.py` `_TOOL_CALL_TAG_NAMES` 剥离列表缺 invoke/parameter → 泄漏文本没被清除 → 满屏 XML。
- 诱因：影子模型 function-calling 协议遵守不稳定；中转站走 chat_completions transport(OpenAI 兼容)。

### 修复（两层合璧）
**第2层·执行层（治本，⚠️核心链路，agent/transports/chat_completions.py）**
1. 模块末尾加 `_parse_invoke_xml_tool_calls(content)`：纯字符串扫描(不用 re，零回溯)，逐个提取 invoke→工具名、parameter→参数，合成 ToolCall，返回 (calls, cleaned)。异常静默返回 ([], content)，未闭合截断放弃。
2. normalize 返回逻辑 ~461 行接线，**触发条件严格**：`if not tool_calls and isinstance(content_str,str) and "<invoke name=" in content_str:` 才解析；成功则合成 tool_calls + 清 content + finish_reason stop→tool_calls。**tool_calls 非空时零影响，正常路径完全不动**（参照同文件 439 行 tool_use_blocks 同款兜底模式）。

**第1层·显示层（保底，agent/response_handler.py）**
`_TOOL_CALL_TAG_NAMES` 补 invoke/antml:invoke/parameter/antml:parameter；orphan 闭合正则补相应变体。

### ⚠️ 终审重点（本改动风险等级最高）
- **改的是核心 transport 链路**，任何 bug 影响所有走 chat_completions 的模型（中转站全系）。终审必须重点扫：
  · RT1：触发条件 `not tool_calls` 是否真能保证正常结构化调用零回归（正常 tool_calls 非空时绝不进兜底分支）
  · RT2：`_parse_invoke_xml_tool_calls` 对畸形/嵌套/超长 content 是否安全（已测：未闭合截断→[]，异常→静默降级）
  · RT3：finish_reason stop→tool_calls 改写是否与下游 agent 循环的 tool 执行逻辑一致
  · RT4：cleaned content 为空时返回 None 是否被下游正确处理

### 验证状态
- [成功] 子进程测试：真实逃逸格式(vision转录三参数read_file)正确还原+剥离；正常content零影响；未闭合安全降级；多工具调用解析2个；AST OK；双CR=0；import回归OK
- [✅ 已验·真实链路端到端 2026-07-09 晚] 用 mock 复刻 fable-5 逃逸响应跑**真实 `ChatCompletionsTransport.normalize_response()`**(非仅 _parse 辅助)4 场景全过：①逃逸→合成 tool_calls(read_file 三参数正确)+剥XML+finish stop→tool_calls ②正常结构化 tool_calls 非空→零回归不进兜底 ③纯文本无 invoke→零影响 ④纯逃逸 cleaned 空→content=None；**显示层** response_handler `_TOOL_CALL_TAG_NAMES` 实测含 invoke/antml:invoke/parameter/antml:parameter + orphan 正则。两层防御真实代码路径均坐实。
- [已验·代码级 2026-07-09 终审] RT1(触发条件 `not tool_calls`：此处 tool_calls 只可能 None 或非空 list，无空 list 边界，正常路径零回归)/RT2(纯 find 扫描零回溯，cursor 严格前进不死循环，未闭合→[]+原文保留，畸形→[]，异常→静默降级)/RT3(下游 run_agent.py:12260 按 `assistant_message.tool_calls` 存在性派发，非 finish_reason；修复置 tool_calls 即触发派发，finish_reason stop→tool_calls 仅保持一致)/RT4(cleaned 空→`cleaned or None`=None) 全部数据流复现 PASS
- [观察性·live 自然复现] 剩"fable-5 在真实使用中自发吐逃逸"这一步为非确定观察项（影子模型偶发，只能实际用时遇到）；两层防御代码正确性已由上条真实链路端到端坐实，真遇到时应：工具正常执行 + 终端无原始 `<invoke>` XML。无需专门制造，日常用到 fable-5 时留意即可。

### 已固化 skill
shadow-model-tool-call-text-leak（含两层修复方案、真实格式、陷阱、规避方案）

---

## 7. 验收判定

- 交叉冲突审查全🟢 + 三线测试全通过 + R1-R10 无🔴 → **可提交 / 可考虑更新分享包**
- 任一🔴 → 阻断，给精确行号+修复建议，修复后重跑本清单
- 分享包（dist-portable，~/.claude 体系，独立系统）在**本终审全绿后**才动，不在本轮范围
