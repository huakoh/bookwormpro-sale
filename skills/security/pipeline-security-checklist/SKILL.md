---
name: pipeline-security-checklist
description: >
  Agent Pipeline 安全审计清单 (P0→P2 三级)。当设计或审查任何涉及外部 API
  调用、用户输入拼接、图片/文件生成、多阶段流程的 Agent Skill/Pipeline 时使用。
  覆盖 4 个 P0 安全红线 + 7 个 P1 核心增强 + 5 个 P2 架构强化。
  触发词: pipeline 安全, agent 审计, Skill 安全检查, 上线前审查。
safety:
  level: medium
  permissions: [read_file, search_files]
maturity: stable
cost_level: low
tags: [security, audit, checklist, pipeline, agent-safety, review]
---

# Agent Pipeline 安全审计清单

> 来源: BookwormPRO AdCreativePipeline 六专家交叉审查 (2026-05-02)
> 适用: 任何调用外部 API + 处理用户输入的 Agent Pipeline

## P0 — 上线前必修 (4 项)

违反任一条 = 不可上线。

| # | 检查项 | 查什么 | 怎么修 |
|---|--------|--------|--------|
| P0-1 | **API Key 保护** | Key 是否明文在环境变量/代码/日志中? | encrypt() 加密存储 + mask_key() 日志脱敏 |
| P0-2 | **成本追踪** | 有无预算上限? 能否阻止超支? | CostTracker(check_and_charge) + 预算硬上限 |
| P0-3 | **注入过滤** | 用户输入是否直接拼接到 API prompt? | sanitize_prompt() — 17条中英文正则 + 敏感词库 |
| P0-4 | **输出校验** | 外部返回的文件是否不经检查就写磁盘? | 文件头校验 + PIL verify + 可疑文件删除 |

## P1 — 本周修 (7 项)

影响核心体验和可靠性。

| # | 检查项 | 查什么 |
|---|--------|--------|
| P1-1 | **并发** | API 调用是否串行? 能否并发提速? |
| P1-2 | **Prompt 分层** | System/User/Negative 是否分离? |
| P1-3 | **反馈闭环** | 失败/低分结果是否有反馈给上游? |
| P1-4 | **量化评审** | 质量判断是主观还是量化 (ΔE/数值)? |
| P1-5 | **脏数据清理** | 中间文件是否有自动清理策略? |
| P1-6 | **健康检查** | 启动前是否验证所有依赖可用? |
| P1-7 | **工期诚实** | 估算是否包含了边界调试时间? |

## P2 — 本月修 (5 项)

架构长期健康。

| # | 检查项 | 查什么 |
|---|--------|--------|
| P2-1 | **抽象接口** | 外部依赖是否通过接口解耦? 能否换后端? |
| P2-2 | **反模式库** | 质量规则是代码还是数据 (可配置)? |
| P2-3 | **降级策略** | 主后端挂了有 fallback 吗? |
| P2-4 | **运行时指标** | 每阶段耗时/成功率/成本是否可度量? |
| P2-5 | **路径沙箱** | 所有文件写入是否在允许目录内? |

## 使用方式

设计新 Pipeline 时: 逐项过 P0 → 修完再设计 → 过了 P0 再开始写代码

审查已有 Pipeline 时: 跑一遍 P0→P2 → 输出严重性分级 → 排优先级

## 红队 5 问

每个 Pipeline 设计完成后自问:
1. 用户能通过 prompt 绕过安全限制吗?
2. API Key 会出现在任何日志/错误/子进程里吗?
3. 账单会失控吗?
4. 外部返回的数据会污染本地文件系统吗?
5. 管线崩溃后能恢复吗? 从哪恢复?
