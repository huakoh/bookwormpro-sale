---
name: ad-creative-pipeline-design
description: >
  广告图片全流程 Agent 管线设计参考。五阶段闭环: 构思→设计→创作→评审精修→定稿导出。
  当需要设计类似的创意生产管线 (广告图/缩略图/社媒图/Banner) 时使用此技能获取架构参考。
  包含: Pipeline 架构图、状态 Schema、AI Critic 四维评分、反模式库、ImageProvider 模式。
  触发词: 广告图管线, 创意Pipeline, 图片生成Agent, ad creative workflow。
safety:
  level: medium
  permissions: [read_file, write_file, terminal]
maturity: design
cost_level: medium
tags: [ad-creative, pipeline, image-generation, design-pattern, agent-skill, architecture]
---

# 广告创意管线设计参考

## 五阶段架构

```
User Input → Stage1: 构思 → Stage2: 设计 → [Gate1] → Stage3: 生成 → Stage4: 评审精修 → [Gate2] → Stage5: 导出
```

| 阶段 | 输入 | 输出 | 工具 |
|------|------|------|------|
| 1. 构思 | 品牌/产品/受众/平台 | 3-5个概念 (角度+标题+视觉描述) | LLM + 8角度创意库 |
| 2. 设计 | 概念+品牌色+调性 | 配色/字体/构图/风格方案 | LLM + 设计系统 |
| 3. 生成 | 概念+设计+平台尺寸 | 初稿图片 | gpt-image-2 / DashScope |
| 4. 评审 | 图片+品牌色+平台规范 | 4维评分+修复/重生成建议 | vision AI + ΔE量化 |
| 5. 导出 | 通过图片+目标平台 | 多尺寸 PNG | PIL 智能裁剪 |

## 关键设计决策

1. **双人工 Gate**: Stage 2→3 (确认设计) + Stage 4→5 (确认精修)。广告图是品牌资产，不能全自动
2. **AI Critic 四维**: contrast(25%) + readability(25%) + brand(25%) + aesthetic(25%) → ≥6.0 通过
3. **品牌色 ΔE 量化**: CIE76 色差公式，ΔE ≤ 15 合规，与 vision AI 各占 50%
4. **Critic→Prompt 闭环**: 低分反馈转为加固 prompt，重生成而非盲目重试
5. **ImageProvider 解耦**: 同一接口支持 gpt-image-2 / DashScope / 未来 Flux

## 反模式库 (18条)

量化设计规则驱动 Critic 检查，覆盖文字(4)/色彩(4)/构图(3)/品牌(3)/AI通病(3)/平台(3)

详见: `shared/anti_patterns.yaml`

## 安全基线 (P0)

- API Key 加密存储 + 日志脱敏
- Prompt 注入过滤 (17条规则)
- 输出文件头校验 + PIL 合法性
- 成本预算硬上限

## 完整文档

设计文档 + v1.1 附录 + 全部源码:
`~/.bookwormpro/docs/plans/2026-05-02-ad-creative-pipeline*.md`
`~/.bookwormpro/docs/plans/ad-creative-pipeline-src/`
