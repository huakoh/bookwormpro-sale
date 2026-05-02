---
name: multi-expert-audit
description: 多专家会审方法论 — 调用 5-7 个领域专家技能对系统/方案进行交叉审查，发现盲区、生成优先级分级的优化方案。触发词：多专家会审、专家评审、交叉审查、系统审计、专家会诊。
version: 1.1.0
author: BookwormPRO (实战验证于 2026-05-01 + 2026-05-02 AdCreativePipeline 评审)
tags: [audit, review, methodology, governance, optimization]
category: system-tools
safety:
  level: low
  permissions: [read_file, skill_view, search_files]
maturity: stable
cost_level: medium
---

# 多专家会审方法论

**最佳组成**: 必须包含 1 安全视角 + 1 业务视角 + 1 架构视角，三者缺一则出现致命盲区。

## 实战验证案例

### Case 1: BookwormPRO 技能系统 (2026-05-01)
对 BookwormPRO 技能系统（141技能 → 14类）执行六专家会审：

**专家组**: ai-ml-expert + tech-lead-mentor + architect-expert + algorithm-expert + ai-philosophy-expert + security-expert/red-teaming

**发现**: 8 个系统级缺口 → 4 个新技能创建 + 48 文件安全/元数据打标 + 全链路集成

**关键教训**: security-expert 的教学代码（含 `rm -rf` 等反面示例）被 skill-guardian 标记为 CRITICAL — 属于误报。解决方案：在教学性安全技能中加入 `_EDUCATIONAL_WHITELIST` 自动降级。

### Case 2: AdCreativePipeline 设计方案预实施评审 (2026-05-02)
对一个 1,240 行的 AI Pipeline Skill 设计文档执行六专家交叉评审：

**专家组**: architect-expert + security-expert + ai-ml-expert + designer-expert + tech-lead-mentor + devops-expert

**发现**: 28 个问题（2 CRITICAL / 7 HIGH / 9 MEDIUM / 8 LOW / 2 INFO）

**关键教训**:
- **安全 + 运维视角贡献了 2 个 CRITICAL 发现**（API Key 明文保护缺失、零成本追踪）— 纯开发类专家（架构/AI/设计）完全不会注意到这些问题
- **设计师视角发现了品牌色量化门控缺失** — 这是 AI+架构视角的盲区
- **Tech Lead 视角纠正了工期估算**（12 → 18 天）— 纯技术专家普遍低估调试时间
- **DevOps 视角发现零可观测性** — 无 Pre-flight Check、无指标、无脏数据清理
- **评审时机是关键** — 在设计文档完成后、写第一行代码前执行，用 30 分钟评审避免 30 小时返工

**最佳组成**: 必须包含 1 安全视角 + 1 业务视角 + 1 架构视角，三者缺一则出现致命盲区。Case 3 (2026-05-02) 验证了对于纯技术方案审查，安全+架构是**最低必要组合**（2 专家即可发现 5 个 CRITICAL/HIGH 问题）。

## 工作流

### Phase 1: 选择专家组
根据审查目标选择 5-7 个互补视角：

| 审查目标 | 推荐专家组 |
|----------|-----------|
| 代码库质量 | developer + security + architect + debugger + reviewer |
| 系统架构 | architect + cloud + performance + security + tech-lead |
| AI 产品 | ai-ml + ai-philosophy + product-manager + security + designer |
| 安全审计 | security + devsecops + red-teaming + guardian + legal |
| 技能系统 | ai-ml + tech-lead + architect + algorithm + ai-philosophy + security |
| **AI Pipeline / Agent 设计评审** | **architect + security + ai-ml + designer + tech-lead + devops** |
| 商业方案 | business-plan + finance + pricing + industry-research + investor |

### Phase 2: 加载专家视角
```python
# 依次调用 skill_view() 加载每个专家技能
for expert in selected_experts:
    skill_view(expert)
# 每个专家带来独特的检查框架和评估维度
```

### Phase 3: 交叉审查
每个专家从自己的框架出发，审查目标系统：

```\nAI/ML 专家 → 算法覆盖度、模型选择、数据流\nCTO/Tech Lead → 可用性、度量、团队效能、上手路径\n架构师 → 结构合理性、依赖链、技术债、扩展性\n算法专家 → 理论深度、数学严谨性、计算复杂度\nAI 哲学专家 → 伦理对齐、偏见审计、透明度、人机关系\n安全/红队 → 攻击面、权限模型、恶意注入、沙箱隔离\n设计师 → 视觉质量门控、设计系统一致性、品牌约束、可访问性\nDevOps → 成本追踪、可观测性、健康检查、脏数据清理、降级策略\n```

### Phase 4: 发现汇总
合并所有专家发现，去重后按严重性分级：

```
CRITICAL (红): 安全漏洞、系统崩溃风险
HIGH (橙):     功能缺失、架构缺陷
MEDIUM (黄):   体验问题、效率瓶颈
LOW (蓝):      改进建议、优化空间
```

### Phase 5: 方案编排
将发现转化为 P0-P2 优先级方案：

```
P0 (立即): 安全红线 — 必须在任何上线前修复
P1 (本周): 核心能力缺口 — 影响主要使用场景
P2 (本月): 架构增强 — 提升长期可维护性
```

**P0-P2 修复表模板（含工时估算）：**

```markdown
### P0 — 必须修（上线前）

| # | 修复 | 专家源 | 工作量 |
|---|------|--------|--------|
| P0-1 | [具体修复内容] | S1 | [时间] |
| P0-2 | ... | ... | ... |

### P1 — 本周修（影响核心体验）

| # | 修复 | 专家源 | 工作量 |
|---|------|--------|--------|

### P2 — 本月修（长期质量）

| # | 修复 | 专家源 | 工作量 |
|---|------|--------|--------|
```

**P0 数量强制**: P0 必须 ≤ 3 项。超过 3 项说明方案有根本性缺陷，应重新设计而非修补。

### Phase 5b: 最终判断清单（预实施评审专属）

当评审对象为设计文档（非运行系统）时，追加此判断：

```markdown
| 问题 | 回答 |
|------|------|
| 方案方向对吗？ | [✅/⚠️/❌] |
| 能直接开工吗？ | [✅ 能 / ⚠️ 需先修 P0 / ❌ 需重新设计] |
| 最大的风险？ | [单点故障/成本失控/安全漏洞/过度设计...] |
| 最大的设计亮点？ | [值得保留发扬的决策] |
| 建议的修改顺序？ | [修 P0 → 修 P1-1/P1-2 → 开始实施 → 实施中修 P2] |
```

## 输出模板

```markdown
## {N}专家会审报告: {审查目标}

### 参与专家

| 专家 | 视角 | 审查维度 |
|------|------|---------|

### 发现的 {N} 个系统级缺口

| # | 缺口 | 严重 | 专家源 |
|---|------|------|--------|

### 优化方案

#### P0 — 安全红线
#### P1 — 核心能力缺口  
#### P2 — 架构增强

### 执行计划

| 步骤 | 内容 | 预计产出 |
|------|------|---------|
```

## 成功要素

1. **专家多样性**: 必须包含至少一个安全视角 + 一个业务视角
2. **独立审查**: 每个专家独立产出发现，避免跟随性偏差
3. **交叉验证**: 同一缺口被多个专家发现 = 高确信度
4. **可执行输出**: 每个发现附带"怎么修"而不只是"哪里不对"
5. **优先级强制**: P0 必须少于 3 项，确保真正聚焦

## 反模式

- 只用 2-3 个专家（视角不足，发现不全）
- 专家同质化（如只选开发类专家，忽略安全/业务）
- 发现不分组（原始列表无优先级，无法执行）
- 只审计不实施（会审的产出必须转化为行动）
