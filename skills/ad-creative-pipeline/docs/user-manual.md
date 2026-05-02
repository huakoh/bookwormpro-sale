# AdCreativePipeline 使用手册

> 广告图片全流程生成——从一句话到多平台定稿。

## 快速开始

### 安装依赖
```bash
pip install dashscope Pillow pyyaml
```

### 设置 API Key
```bash
# DashScope (默认，¥0.04/张)
export DASHSCOPE_API_KEY=sk-xxxx

# gpt-image-2 (可选，¥0.15/张，高质量)
export GPT_IMAGE_BASE_URL=https://bww.your-domain.com/v1
export GPT_IMAGE_API_KEY=sk-xxxx
```

### 基础使用
```
/ad-creative-pipeline "明远生物 AVITS 医药冷链温控系统"
```

### 完整参数
```
/ad-creative-pipeline \
  --brand "明远生物" \
  --product "AVITS 智能温控系统，实时监测温度湿度，±0.1°C 精度" \
  --audience "药企物流经理、医药经销商" \
  --platforms "wechat_moment,linkedin" \
  --tone "professional" \
  --colors "#0052D9,#E37318" \
  --concepts 3 \
  --budget 5.0 \
  --provider dashscope
```

## 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--brand` | ✅ | — | 品牌名称 |
| `--product` | ✅ | — | 产品/服务描述 |
| `--audience` | ❌ | "通用受众" | 目标用户画像 |
| `--platforms` | ✅ | — | 投放平台，逗号分隔。可选: wechat_moment, linkedin, facebook_feed, instagram_feed, instagram_story, google_display, twitter, douyin |
| `--tone` | ❌ | professional | 品牌调性: professional / playful / luxury / minimal / bold / warm |
| `--colors` | ❌ | 自动推导 | 品牌色，逗号分隔的 HEX |
| `--concepts` | ❌ | 3 | 创意概念数量 (3-5) |
| `--budget` | ❌ | 5.0 | 预算上限 (元) |
| `--provider` | ❌ | dashscope | 图片引擎: dashscope / gpt-image-2 |
| `--output` | ❌ | ./ad-output/ | 输出目录 |
| `--auto` | ❌ | false | 跳过人工 Gate，全自动运行 |
| `--resume` | ❌ | — | 恢复中断的 Pipeline (acp_xxx) |

## Pipeline 流程

```
Step 1: 输入品牌/产品信息
   ↓
Stage 1: 生成 3-5 个创意概念 (角度+标题+视觉描述)
   ↓
Stage 2: 为每个概念生成设计方向 (配色+字体+构图+风格)
   ↓
[Gate 1] ← 你确认设计方案
   ↓
Stage 3: 调用 AI 生成广告图 (DashScope 并发, ¥0.04/张)
   ↓
Stage 4: AI 自动评审 + 基础修复
   ↓
[Gate 2] ← 你确认精修结果
   ↓
Stage 5: 多平台多尺寸导出
   ↓
📁 定稿交付
```

## Gate 操作

### Gate 1 (设计方案确认)
```
📋 创意概念卡 #1
角度: 痛点
标题: "每一度温差，都是百万损失"
设计: 科技冷峻风 | 深蓝渐变 + 冰晶纹理

[Y] 全部通过  [N:1] 修改概念1  [X] 终止
```

### Gate 2 (精修结果确认)
```
🖼️ 图片 #1  总分: 7.2/10  ✅
🖼️ 图片 #2  总分: 4.5/10  ⚠️

[Y] 全部通过  [R:2] 重生成图2  [N:1] 重精修图1  [X] 终止
```

## 费用参考

| Provider | 每张成本 | 3 概念 × 1 平台 | 含重修 |
|----------|---------|----------------|--------|
| DashScope | ¥0.04 | ¥0.12 | ~¥0.20 |
| gpt-image-2 | ~¥0.15 | ~¥0.45 | ~¥0.75 |

## 输出目录结构

```
ad-output/acp_20260502_143000/
├── state.json              ← Pipeline 状态 (可 --resume)
├── metrics.jsonl           ← 运行时指标
├── stage3/                 ← 初稿图片
│   ├── img_ds_a1b2c3.png
│   └── img_ds_d4e5f6.png
├── stage4/                 ← 精修图片
│   └── img_ds_a1b2c3_fixed.png
└── exports/                ← 最终交付
    ├── img_ds_a1b2c3_wechat_moment_moment_feed.png
    ├── img_ds_a1b2c3_linkedin_sponsored_content.png
    └── ...
```

## 常见问题

**Q: DashScope API Key 在哪获取？**
A: https://dashscope.aliyun.com/ → 开通灵积模型服务 → 获取 API Key

**Q: 生成失败怎么办？**
A: 检查 `metrics.jsonl` 定位失败阶段。常见原因: API Key 未设置/欠费/限流。支持 `--resume` 恢复。

**Q: 中文文字模糊？**
A: DashScope 不保证中文文字精确渲染。建议将文字作为 Stage 5 后的 Photoshop 叠加层。gpt-image-2 文字渲染更好。

**Q: 如何降低费用？**
A: 减少 `--concepts` 到 2，减少 `--platforms`，或设置 `--budget 2.0`。

**Q: 如何提升图片质量？**
A: 使用 `--provider gpt-image-2` (需中转站可用)，或在 Stage 4 Gate 多次要求精修。

## 清理

```bash
# 查看待清理
python shared/cleanup.py

# 执行清理 (>7天的已完成Pipeline)
python shared/cleanup.py --execute
```
