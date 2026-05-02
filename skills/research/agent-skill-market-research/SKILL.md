---
name: agent-skill-market-research
description: >
  Agent Skill/项目市场调研。当用户需要在 GitHub 或主流 Agent 社区
  寻找某个领域的现有 Skill、Agent 或开源项目时使用此技能。
  覆盖：多源搜索、屏蔽规避、交叉验证、结构化对比报告。
  触发词：寻找 skill、搜索 agent、有没有现成的、社区调研、
  GitHub 调研、skills 市场调研。
safety:
  level: low
  permissions: [web_search, web_extract, browser_navigate]
allowed-tools: web_search, web_extract, browser_navigate, Read
maturity: stable
cost_level: medium
last-reviewed: 2026-05-02
---

# Agent Skill 市场调研

## 触发场景

当用户想在动手构建前，了解社区是否已有现成的 Agent Skill 或开源项目时触发。

## 核心方法论

### 1. 多源并行搜索（第一轮）

同时从以下维度发起搜索：

| 维度 | 搜索策略 | 示例 Query |
|------|---------|-----------|
| GitHub 直接 | `github {domain} agent skill workflow stars` | `github ad creative agent skill image generation workflow stars` |
| GitHub Topics | `site:github.com/topics {keyword}` | `site:github.com/topics ad-generation` |
| Agent 市场 | `agentskills.io OR awesomeskill.ai OR mcp.directory {keyword} skill` | `agentskills.io "ad creative" skill` |
| Awesome 列表 | `github awesome agent skills {keyword}` | `github awesome agent skills ad creative` |
| 社区讨论 | `reddit OR medium claude code skill {keyword} workflow` | `reddit claude code agent skill ad creative image` |

### 2. 屏蔽规避策略

当 `web_extract` 或 `browser_navigate` 被 GitHub/Medium 等站点屏蔽时：

- **不重复尝试被屏蔽的 URL**——立即切换策略
- **间接获取 star 数**：搜索 `"{repo-name}" github stars` 或查找 Medium/Reddit/LinkedIn/X 帖子中的提及
- **间接获取 SKILL.md 内容**：搜索 `"{repo-path}" SKILL.md content "{关键词}"` 或查找技能市场的摘要描述
- **交叉验证**：从至少 2 个独立来源确认 star 数和功能描述

### 3. 深入挖掘（第二轮+）

对第一轮发现的有前途项目，逐项深挖：

```
对每个候选项目：
  ├─ 搜索 "{owner}/{repo}" github stars forks README → 获取规模
  ├─ 搜索 "{repo} workflow pipeline steps" → 获取工作流细节
  ├─ 搜索 "{repo} {keyword}" → 获取社区评价
  └─ 搜索 "{repo} CVE OR vulnerability OR issue" → 安全检查
```

### 4. 中文社区补充

针对中文用户场景：
```
github claude code agent {中文关键词} skill
```
关键词示例：广告图片、生成、skill、构思、设计、创作

### 5. 结果结构化

产出报告必须包含：

```markdown
## 一、头部项目（⭐万星级别）
## 二、精准管线项目（⭐百-千级别）
## 三、Skill 目录/聚合器（值得翻找）
## 四、综合评估与推荐
  - 匹配度矩阵（构思/设计/创作/精修/定稿 × 各项目）
  - 即装即用 / 最接近管线 / 从零定制 三条建议路径
```

匹配度矩阵格式：
```
              构思  设计  创作  精修  定稿  Stars  开箱
project-a      ✅    ❌    ✅    ✅    ⚠️    24K   中
project-b      ✅    ✅    ✅    ✅    ⚠️    23K   低
```

## 输出规范

- 每个项目标注 GitHub URL、star 数（注明是精确值还是估值）、许可证
- 匹配度使用 ✅/⚠️/❌ 三态 + 文字说明
- 给出 2-3 条可操作的建议路径（即装即用 / 最接近需求 / 从零定制）
- 对 star 数 < 100 的项目注明「社区验证度低」
- 对有 CVE 安全漏洞的项目显式标注风险

## 注意事项

- web_extract 对 github.com、medium.com、leadgenjay.com 等站点大概率被屏蔽，不要在单个 URL 上重试超过 2 次
- star 数优先从 GitHub 直接获取；如果被屏蔽，从社区帖子间接获取并注明来源
- 优先推荐 star 数 > 1K 的项目，除非精准匹配度极高
- 如果搜索结果为空，扩大搜索词范围（从具体到泛化），不要轻易下「社区没有」的结论
