---
name: bookwormpro-evolution
description: BookwormPRO system evolution workflow — 5-pillar audit, fix, capability building, Hermes module porting
version: 1.2.0
maturity: stable
---

# BookwormPRO 系统进化工作流

## Phase 1: 五柱体检
- Cron: cronjob list 检查 last_status
- MCP: node mcp-probe.js (8s超时, windows-mcp需30s重测)
- Agent: delegate_task 烟雾测试 (单+并发)
- Skills: SKILL.md YAML完整性 + 僵尸检测(>30d)
- Routing: cd routing && node accuracy.js

## Phase 2: 修复
- Cron model=null: jobs.json补model + cron/jobs.py auto-resolve (create_job中读config.yaml默认值)
- MCP超时: 30s重测 + 监控cron
- Agent路由: BWR bridge + hook集成到run_agent.py (非侵入式try/except)
- Skills僵尸: >30d未更新 → 移至_archived/
- Vision报错: config.yaml auxiliary.vision.model + fallback_model 可配
- Skills僵尸: 移至_archived/

## Phase 3: 能力建设
- BWR引擎: ~/.claude/scripts/ → BookwormPRO/routing/
- 路径适配: lib/root.js → ~/.bookwormpro/
- 消歧规则: trigger/boost/penalty/weight格式
- Submit机制: 规则匹配但skill不在BM25时注入 (route-analyzer.js L836)
- BM25修复: 用skills-index.json(含keyword)非lite版

## Phase 4: Hermes Agent 模块移植
- 差异分析: diff D:/HermesAgent vs BookwormPRO
- 审查: 逐文件审查功能重叠度
- 复制: COPY文件到BookwormPRO (NEVER修改D:/HermesAgent)
- 适配: ~/.hermes/→~/.bookwormpro/ · hermes_cli→bwm_cli · hermes_constants→bwm_constants
- 集成: COMMAND_REGISTRY注册 · skill_commands钩子 · config.yaml启用
- 验证: import可用 + py_compile语法 + 函数调用测试

## Phase 5: 文档与发布
- 架构对比HTML: 暗色终端美学 · JetBrains Mono+Noto Sans SC
- 汉化: 系统名保留(BWR/MCP/BM25),其他全中文
- 脱敏: 移除个人用户名/路径,保留公开仓库
- 去幻觉: 逐条交叉验证HTML中的每个数据主张
- GitHub: 精准add → git diff --cached → commit → push (NEVER force push main · NEVER git add .)

## Phase 6: 持久化
- Memory: 保存系统终态
- Skill: 更新bookwormpro-evolution
- Cron: 验证cron (明天09:00自动验收)

## 关键路径
~/.claude/ (v6.6.1) COPY→ BookwormPRO/routing/ (v7.0.0)
D:/HermesAgent COPY→ BookwormPRO/ (模块移植)
~/.bookwormpro/ ← 共享运行时 (skills-index.json, debug/, config.yaml)

## Phase 7: v7.0.0→v6.6.1 反向反哺

当 v7.0.0 已验证的改进需要回填到 v6.6.1 (~/.claude/):
- v6.6.1 NEVER MODIFY 原则在此方向不适用 (目标是 v6.6.1 自身)
- 反哺路径: 识别可移植模块 → 安全架构联合审查 → 逐项执行

### 反哺分类
| 类别 | v7.0.0 源 | v6.6.1 落点 | 示例 |
|------|----------|-----------|------|
| 数据文件 | routing/*.json | scripts/*.json (diff合并,非覆盖) | golden-set.json, disambiguation-rules.json |
| Hook 脚本 | agent/*.py 逻辑 | hooks/*.js (翻译为轻量 JS,~50-80行) | circuit-breaker, rate-limit-guard |
| 系统 prompt | prompt_builder.py 策略 | CLAUDE.md 结构调整 | 缓存锚点重组, R1动态切片 |
| 运维脚本 | bwm_cli/*.py | scripts/*.js | backup.js, audit.js |
| Cron 激活 | cron/scheduler.py | cronjob create | soul-metrics-weekly |

### 审查流程 (必须)
1. 架构审查: 耦合分析 (文件冲突/依赖链/Hook管线负载)
2. 安全审查: 攻击面分析 (NEVER/ALWAYS对照, 宪法合规, 红队5问)
3. 联合判定: 每项附带条件 (如 Tirith需SHA-256验签, 健康探测需白名单)
4. 优先级: P0(无条件)→P1(附条件)→P2(按需)

### Hook 创建模板 (v6.6.1)
```javascript
// 标准 hook 结构: require → 配置 → 状态管理 → 主逻辑 → output
'use strict';
const fs = require('fs'); const path = require('path');
const CLAUDE_ROOT = (()=>{try{return require('./lib/root.js')}catch{return path.resolve(__dirname,'..')}})();
function ensureDir(){...} function loadState(){...} function saveState(){...}
function main(){const input=JSON.parse(fs.readFileSync(process.stdin.fd||0,'utf8'));/*...*/}
function output(obj){process.stdout.write(JSON.stringify(obj));}
try{main()}catch(e){process.stderr.write('[hook-name] '+e.message+'\n');process.stdout.write(JSON.stringify({status:'error'}));}
```

### settings.json 注册 (Python 安全修改)
```python
# 必须用 Python 脚本修改 settings.json, 禁止手动编辑
data = json.loads(open('settings.json').read())
data['hooks']['PostToolUse'].insert(0, {'matcher':'...', 'hooks':[{'type':'command','command':'node ...','timeout':2000}]})
open('settings.json','w').write(json.dumps(data,ensure_ascii=False,indent=2))
```

### Windows 特定陷阱
- patch 工具 CRLF 假阴性: 报告"verification failed"但常已写入 → 重读验证
- write_file ~/.claude/路径: 某些情况下抛 WinError 267 → 用 C:/Users/BOOKWORMPRO_USER/.claude/ 绝对路径
- Python 字符串含反引号: terminal() 内 bash 会解释为命令替换 → 先 write_file 临时脚本再 terminal 执行
- CLAUDE.md 修改: 必须 binary 模式 read/write (rb/wb) 保留原始 CRLF

## 陷阱
- skills-index-lite.json无keyword→用完整版(980KB)
- cron新job model=null→已auto-resolve但新job仍需验证
- Windows CRLF→patch报错但常已写入,重读验证
- python3→Win Store stub exit49,用python
- 消歧规则不生效→检查BM25 index是否完整
- 用户可见hermes痕迹→仅dump命令一处
- write_file ~/.claude/ → 某些环境 WinError 267, 用绝对路径 C:/Users/BOOKWORMPRO_USER/.claude/
- terminal() 内 Python 反引号 → bash 命令替换, 改为 write_file 临时脚本
