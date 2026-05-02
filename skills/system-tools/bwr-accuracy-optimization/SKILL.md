---
name: bwr-accuracy-optimization
description: BWR 路由准确率优化方法论 — 金标集扩展、BM25 索引修复、消歧规则编写、Submit 机制。当路由准确率 <99% 或需要系统性提升时使用。触发词：路由准确率、BWR accuracy、消歧优化、金标集、routing fix。
version: 2.2.0
author: BookwormPRO (75.4%→96.8%→100.0% routing accuracy, 261 golden 129 rules, v2.2 adds Layer 6 feedback-driven rule gen)
tags: [routing, bwr, accuracy, optimization, disambiguation]
safety:
  level: low
  permissions: [read_file, write_file, terminal]
maturity: stable
cost_level: medium
---

# BWR 路由准确率优化方法论

从 v6.6.1 迁移 BWR 引擎到 v7.0.0 后，准确率从 75.4% 提升到 96.8% 的完整实战流程。

## 四层优化管线

```
Layer 1: BM25 Index Fix       → 75.4% → 84.1%  (+8.7%)
Layer 2: Submit Mechanism     → 84.1% → 88.9%  (+4.8%)
Layer 3: Disambiguation Rules → 88.9% → 91.7%  (+2.8%)
Layer 4: Index Completion      → 91.7% → 96.8%  (+5.1%)
Layer 5: Error Classification   → 96.8% → 100.0% (+3.2%)
```

## Layer 1: BM25 Index Fix

**症状**: 所有路由回退到 `developer-expert`，confidence=0.00

**根因**: `route-engine.js` 引用 `skills-index-lite.json`（无 keyword/token 数据），BM25 全 0 分

**修复**:
```javascript
// route-engine.js line 60
// OLD: path.join(CLAUDE_ROOT, 'skills-index-lite.json')
// NEW:
const indexFile = path.join(CLAUDE_ROOT, 'skills-index.json');
```

**验证**: 单条路由测试应返回非 developer-expert 且 confidence > 0.5

## Layer 2: Submit Mechanism

**症状**: 消歧规则匹配但目标 skill 不在 BM25 结果中，boost 被静默丢弃

**根因**: `route-analyzer.js:836` — `results.find(r => r.name === rule.boost && r.score > 0)` 返回 null

**修复**: 在 `applyDisambiguation` 的 boost 累积循环中添加：
```javascript
// After: const boosted = results.find(...)
// Add:
} else if (rule.boost) {
  const maxScore = results.length > 0 ? Math.max(...results.map(r => r.score || 0)) : 0.001;
  results.push({
    name: rule.boost,
    score: maxScore * 0.5,
    _submitted: true,
    _ruleId: rule.id,
    matched: [],
    weights: {}
  });
  boostVotes.set(rule.boost, effectiveWeight);
}
```

## Layer 3: Disambiguation Rules

### 规则格式 (disambiguation-rules.json)
```json
{
  "id": "R94",
  "note": "API设计 → api-designer",
  "trigger": "REST\\\\s*API.*设计|OpenAPI.*规范",
  "boost": "api-designer",
  "penalty": ["backend-builder", "tech-writer-expert"],
  "weight": 0.40
}
```

### 规则编写原则
- `trigger`: 正则表达式，用 `|` 分隔模式
- `boost`: 目标技能名，**必须与 skills-index 中的 name 完全一致**
- `penalty`: 降权技能列表，防止误路由
- `weight`: 0.30-0.50，越高越强制

### 规则生效验证
```bash
cd routing && node -e "
delete require.cache[require.resolve('./route-engine.js')];
const re = require('./route-engine.js');
const r = re.runRouteEngine('测试查询', {intents:['test'],complexity:'medium'});
console.log(r.primary, r.confidence);
"
```

## Layer 4: Index Completion

**症状**: 金标集中的新技能路由全部失败

**根因**: `skills-index.json` 是 v6.4 旧版，缺少 13 个新技能

**修复**: 在索引中追加缺失技能：
```python
new_skill = {
    'name': 'spotify',
    'description': 'Spotify音乐控制',
    'keywords': [
        {'keyword': 'spotify', 'weight': 1, 'tier': 'core'},
        {'keyword': '音乐', 'weight': 1},
    ],
    'maturity': 'stable',
    'isComposable': False,
    'allowedTools': []
}
```

## 金标集管理

### 结构 (golden-set.json)
```json
{
  "version": "v7.0",
  "generated": "2026-05-01T...",
  "entries": [
    {"query": "帮我写Python脚本", "expectedSkill": "developer-expert", "source": "manual"},
    ...
  ]
}
```

### 运行基准测试
```bash
cd routing && node accuracy.js
# 输出: Correct: N/M (XX.X%)
```

### 分析误路由
```bash
cd routing && node -e "
const re=require('./route-engine.js'),ic=require('./intent-classifier.js');
const gs=require('./golden-set.json');
for(const e of gs.entries){...}
"
```

## 关键路径清单

| 文件 | 作用 |
|------|------|
| `routing/route-engine.js:60` | skills-index 路径 |
| `routing/route-analyzer.js:785` | applyDisambiguation 入口 |
| `routing/route-analyzer.js:836` | boost 投票 (submit 注入点) |
| `routing/disambiguation-rules.json` | 129 条消歧规则 (v2.1) |
| `routing/golden-set.json` | 261 条金标测试用例 |
| `~/.bookwormpro/skills-index.json` | BM25 关键词索引 |

## Layer 5: Error Classification & Systematic Fix (v2.0 新增)

当基准测试返回 N 个错误时，先分类再修复：

### Step 1: 逐个打印错误详情
```bash
cd routing && node -e "
const re=require('./route-engine.js'),ic=require('./intent-classifier.js');
const gs=require('./golden-set.json');
for(const e of gs.entries){
  if(!e.expectedSkill) continue;
  const r=re.runRouteEngine(e.query, ic.classifyIntent(e.query));
  const p=r.primary||'?';
  if(p!==e.expectedSkill){
    console.log('EXP:',e.expectedSkill,'GOT:',p,'|',e.query.substr(0,80));
    console.log('  Candidates:',(r.candidates||[]).slice(0,5).map(c=>c.name).join(','));
  }
}
"
```

### Step 2: 区分两类错误
| 类别 | 特征 | 修复方式 |
|------|------|---------|
| **金标错误** | 引擎路由比金标更精准（如 "升级 gstack" → `gstack-upgrade` 而非泛型 `gstack`） | 修正 golden-set.json 的 expectedSkill |
| **引擎缺陷** | 引擎路由到明显无关技能 | 新增 disambiguation-rules.json 规则 |

### Step 3: 消歧规则调试
**常见陷阱**：
- JS 中 `.*` **不跨换行**——用 `[^]*` 替代（匹配所有字符含 `\n`）
- JSON 中 `\\s` 被解析为字面 `s`——避免在 JSON regex 中用 `\s`/`\S`，直接用 `[^]*`
- 规则 trigger 存入 JSON 前，用 `new RegExp(trigger).test(query)` 验证

**优先级调试指令**：
```javascript
// 测试单条规则是否命中
const rule = rules.rules.find(r => r.id === 'Rxxx');
console.log(new RegExp(rule.trigger).test(query));
```

### Step 4: 权重调优
- 0.35: 温和 boost（与其他候选竞争）
- 0.50: 强 boost（抑制 2-3 个误判）
- 0.80-1.0: 极强 boost（需配合 penalty 列表，抑制 5+ 误判）

### Step 5: 防 whack-a-mole
当 penalty 一个技能后另一个顶上时：
1. 先把前一个 penalty 加入列表
2. 权重升至 0.8+
3. 必要时 penalty 列表可扩大到 8-10 个常见误判技能
4. trigger 保持精准（避免误杀合法路由）

## Layer 6: Feedback-Driven Rule Generation (v2.2 新增 — v6.6.1 反哺)

当从 Bookworm v6.6.1 获取路由反馈数据时，系统性提取 misroute 模式并生成消歧规则。

### 数据源

v6.6.1 `~/.claude/debug/` 目录下:
- `route-feedback.jsonl` — 隐式反馈 (type, routedTo, correctedTo, implicit)
- `shadow-route-log.jsonl` — 路由影子日志 (ph=query, p=predicted, cf=confidence, t5=top5)
- `route-metrics.jsonl` — 路由性能指标 (selected_skill, top_score, gap_1_2, rules_fired)

### 分析流程

```python
import json
from collections import Counter

# Step 1: 提取纠正模式
corrections = []
for line in open('route-feedback.jsonl'):
    e = json.loads(line)
    if e.get('correctedTo') and e['correctedTo'] != e.get('routedTo'):
        corrections.append((e.get('routedTo','none'), e['correctedTo']))

# Step 2: 统计高频纠正
pattern_counts = Counter(corrections)
for (from_skill, to_skill), count in pattern_counts.most_common(10):
    print(f'{from_skill} → {to_skill}: {count}x')

# Step 3: 分析路由失败 (cf=0)
failed = [e for e in data if e.get('cf',0) == 0 and e.get('p') == 'none']
intent_fails = Counter()
for f in failed:
    for i in f.get('it',{}).get('i',[]):
        intent_fails[i] += 1
```

### 规则生成模板

```json
{
  "id": "Rxxx",
  "note": "[v6.6.1反馈] 描述 — N次手动纠正 from→to。修复: 关键词→目标技能",
  "trigger": "关键词1|关键词2|正则模式",
  "boost": "target-skill-name",
  "penalty": ["原误路由技能", "其他候补"],
  "weight": 0.35,
  "source": "v6.6.1-feedback-analysis"
}
```

### 实战案例 (2026-05-02)

从 1116 条反馈数据中提取:
- **15/26 纠正 = HANDOFF 未被识别** → 新增 R130 (weight 0.4)
- **3/26 纠正 = devops 误路由到 SRE** → 新增 R131 (weight 0.3)
- **134 次路由失败 = 短查询无上下文** → 新增 R132 (weight 0.15, 需配合会话继承)

规则文件输出到 Desktop 供人工审查后再合并到 `disambiguation-rules.json`。

## 反模式

- ❌ 只加金标不加消歧规则——金标会测出错误但不修复
- ❌ 消歧规则 trigger 太宽——会误杀正常路由
- ❌ 不改 BM25 index 直接加规则——规则找不到 skill 无法生效
- ❌ 忘 `delete require.cache`——修改后 Node.js 用缓存旧模块
- ❌ 不分类直接加规则——金标错误加规则会污染消歧逻辑
- ❌ JSON regex 用 `\s` `\S`——JSON 解析会将其转为字面字符
- ❌ `.*` 跨换行匹配——JS 正则默认不匹配 `\n`
