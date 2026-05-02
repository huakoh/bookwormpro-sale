---
name: evolution-tracker
version: 2.0.0
description: |
  系统进化追踪器。可视化 Bookworm 系统的进化时间线，分析版本历史、
  变更趋势、触发器分布和修复统计。v2.0 新增技能使用度量。
  触发词: "进化追踪", "evolution", "系统历史", "变更时间线", "版本历史"。
  支持子命令: timeline, stats, version, search, health-trend, usage-stats, combo-analysis。
maturity: stable
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
safety:
  level: low
  permissions: [read_file, search_files]
cost_level: low
---

# /evolution-tracker — 系统进化追踪器

分析 `evolution-log.jsonl` 生成系统进化可视化报告。v2.0 新增技能使用度量。

## 子命令

根据用户输入匹配子命令。无参数时默认执行 `timeline`。

### timeline (默认) — 进化时间线
读取全部 JSONL 记录，按日期分组，生成 ASCII 时间线。按版本分组，版本内按日期倒序。

### stats — 统计分析
生成多维度统计报告: 版本分布、触发源排名、标签热力图、修复统计、周活跃度。

### version [ver] — 版本详情
显示指定版本的所有变更记录 + 汇总统计。

### search [keyword] — 关键词搜索
在 summary、tags、fix_note 中搜索关键词。

### health-trend — 健康趋势
关联 `debug/health-snapshots/` 中的历史快照数据。

---

## 技能使用度量 (v2.0 新增 - 六专家会审)

追踪技能调用频率，识别冷门/热门技能。数据源: `~/.bookwormpro/skill-usage.jsonl`

### usage-stats — 使用统计
热门 Top 10 / 冷门技能 (30天未用) / 弃用候选 / 合并候选 / 晋升候选

### combo-analysis — 技能组合分析
高频组合识别 / 推荐合并: qa+tester-expert, devops+devops-expert / 依赖图生成

### 阈值
冷门淘汰: 90天0调用 | Alpha→Beta: 10次成功 | Beta→Stable: 50次+0错误

---

### skill-usage — 技能使用报告

读取 skill-usage.jsonl 生成 30天热门 Top10 / 冷门列表 / 合并候选 / 晋升建议

---

## 输出约定
- 所有输出使用 markdown 格式
- ASCII 图表使用全角块字符
- 超过 20 条记录显示 Top 20 + 省略
- 本 Skill 为只读，不写入任何文件
