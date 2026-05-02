---
name: skill-navigator
description: 技能导航器 — 根据用户意图智能推荐技能组合、生成学习路径、按场景编排多技能协作
version: 1.0.0
author: BookwormPRO (六专家会审产出)
tags: [meta, navigation, discovery, onboarding]
safety:
  level: low
  permissions: [read_file, skills_list]
maturity: alpha
cost_level: low
---

# 技能导航器 (Skill Navigator)

帮助用户在海量技能中找到正确的工具。

## 触发条件

- "我需要做什么..." / "有没有技能可以..."
- "/skill-navigator" / `bookworm skill navigator`

## 场景路由

| 用户意图 | 推荐技能链 |
|----------|-----------|
| 搭建 SaaS 产品 | product-manager → architect → frontend → backend → devops → security |
| 数据分析项目 | data-analyst → ai-ml → data-science → data-engineer |
| 写商业计划书 | business-plan → finance-advisor → pricing-strategist → industry-research-cn |
| 部署上云 | cloud-architect → kubernetes → terraform → setup-deploy → ship |
| 安全审计 | security → devsecops → red-teaming → guardian → skill-guardian |
| SEO 优化 | technical-seo → programmatic-seo → copywriter → growth-hacker |
| 微信小程序 | miniprogram → frontend → api-designer → mobile |
| 团队管理 | tech-lead → project-coordinator → developer-expert → review |
| AI Agent 开发 | ai-ml → mlops → prompt-optimizer → codex → red-teaming |
| 算法竞赛 | algorithm-expert → developer-expert → debugger-expert |

## 分级学习路径

```
Level 1 — 基础 (先装这 5 个)
  developer-expert    日常编程
  frontend-design     界面设计
  project-coordinator 项目管理
  github              版本控制
  security-expert     安全意识

Level 2 — 进阶 (按需)
  architect-expert    系统设计
  ai-ml-expert        AI 开发
  devops              部署运维
  product-manager     产品思维
  algorithm-expert    算法设计

Level 3 — 专家 (深度)
  kubernetes          容器编排
  red-teaming         安全攻防
  mlops               ML 工程化
  ai-philosophy       AI 伦理
```

## 替代方案

```
typescript-pro 不可用 → developer-expert + frontend-expert
kubernetes 不可用     → cloud-native-expert + terraform
ai-philosophy 不可用  → security-expert + guardian
```
