---
name: ad-creative-pipeline
description: >
  广告图片全流程生成管线。构思→设计→创作→精修→定稿，五阶段闭环。
  当用户需要生成广告创意图片、社交媒体广告图、Google Display 横幅、
  Facebook/Instagram 广告素材时使用此技能。
safety:
  level: medium
  permissions: [read_file, write_file, terminal, vision_analyze]
maturity: alpha
cost_level: medium
dependencies:
  - dashscope (或 gpt-image-2 via 中转站)
  - Pillow
  - PyYAML
composable: true
  composed_of:
    - stage1-concept-ideation
    - stage2-design-direction
    - stage3-image-generation
    - stage4-critique-refine
    - stage5-final-export
---

# AdCreativePipeline — 广告图片全流程生成

## Pipeline 总览

```
User Input → Stage1 构思 → Stage2 设计 → [Gate 1: 人工确认]
    → Stage3 生成 → Stage4 评审精修 → [Gate 2: 人工确认]
    → Stage5 导出 → 定稿交付
```

| Stage | 职责 | 工具 | 耗时 |
|-------|------|------|------|
| 1 构思 | 3-5 个广告概念 (角度+标题+视觉描述) | LLM 推理 | < 5s |
| 2 设计 | 配色/字体/构图/风格方案 | LLM + 设计系统 | < 5s |
| 3 生成 | 调用 DashScope 生成图片 | qwen-image-plus | 15s (并发) |
| 4 评审 | 4维评分 + PIL 基础修复 | vision + PIL | 15s/张 |
| 5 导出 | 多平台多尺寸裁剪 | PIL | < 3s |

## 使用方式

### 基础调用
```
/ad-creative-pipeline "明远生物 AVITS 智能温控系统" --platform wechat_moment,linkedin
```

### 完整参数
```
/ad-creative-pipeline \
  --brand "明远生物" \
  --product "AVITS 医药冷链温控系统，实时监测温度湿度" \
  --audience "药企物流经理、医药经销商" \
  --platforms "wechat_moment,linkedin" \
  --tone "professional" \
  --colors "#0052D9,#E37318" \
  --concepts 3 \
  --budget 5.0 \
  --provider dashscope \
  --output "./ad-output/"
```

### 恢复中断的 Pipeline
```
/ad-creative-pipeline --resume acp_20260502_143000
```

## 工作流

### Step 1: 解析输入 + 初始化

1. 解析参数，填充 `state-schema.json` 的 `input` 字段
2. 生成 `pipeline_id = "acp_{timestamp_hex}"`
3. 创建输出目录 `{output_dir}/{pipeline_id}/`
4. 运行 Pre-flight 检查
   ```python
   from shared.preflight import run_all_checks, print_check_report
   result = run_all_checks()
   print_check_report(result)
   # 不通过 → exit(1)
   ```
5. 初始化 `CostTracker(budget_yuan=budget)`
6. 初始化 `MetricsCollector(pipeline_id, output_dir)`
7. 写入初始 `state.json`
8. 通知用户: "Pipeline 已启动 | ID: acp_xxx | 预计生成 {concepts} 个概念 × {len(platforms)} 个平台"

### Step 2: 调度 Stage 1 — 构思

```
加载: skill_view("stage1-concept-ideation")
输入: brand_name, product_description, target_audience, platforms, tone, language, concept_count
输出: concepts[3-5]
写入: state.stage1.concepts
```

LLM 收到 Stage 1 的 SKILL.md system prompt，自动执行角度选择 → 概念生成 → JSON 输出。

### Step 3: 调度 Stage 2 — 设计

```
加载: skill_view("stage2-design-direction")
输入: concepts + brand_colors + tone + platforms
输出: design_directions[]
写入: state.stage2.design_directions
```

### Step 4: Gate 1 — 人工确认设计方案

```
展示格式:
┌──────────────────────────────────┐
│ 📋 创意概念卡 #1                  │
│ 角度: 痛点 (Pain Point)           │
│ 标题: "每一度温差，都是百万损失"    │
│ 视觉: 冰封药品+温度计+冷链场景      │
│ 设计: 科技冷峻风 | 深蓝+冰晶纹理    │
│                                  │
│ 📋 创意概念卡 #2 ...              │
│ 📋 创意概念卡 #3 ...              │
├──────────────────────────────────┤
│ 💰 预估: ¥{cost_estimate}         │
│ 选项: [Y]全部通过 [N:id]修改 [X]终止│
└──────────────────────────────────┘
```

Y → 进入 Stage 3
N:id → 修改指定概念 (返回 Stage 1 重做该概念)
X → 保存 state.json, 退出

### Step 5: 调度 Stage 3 — 生成

```python
from stages.stage3_image_generation.scripts.generate import generate_images

images, gen_metrics = generate_images(
    concepts=approved_concepts,
    design_directions=approved_designs,
    output_dir=f"{output_dir}/stage3/",
    platform=platforms[0],  # 主平台
    provider_name=provider,
    budget_yuan=budget,
    concurrent=5
)
```

输出: 每张图 `{image_id}.png` + 状态记录到 `state.stage3.images`

### Step 6: 调度 Stage 4 — 评审精修

对每张图运行 Critic：

```python
from stages.stage4_critique_refine.scripts.critic import critique_image
from stages.stage4_critique_refine.scripts.refine import auto_refine

for img in images:
    critic_result = critique_image(img["path"], brand_context, platform)
    if critic_result["needs_fix"]:
        fixed = auto_refine(img["path"], critic_result, f"{output_dir}/stage4/{img['id']}_fixed.png")
    # needs_regeneration → 记录到重生成队列
```

**重生成循环 (最多 2 轮):**
```
if needs_regeneration:
    Stage 3 → 增强 prompt (注入 Critic 反馈) → Stage 4 → 再评审
    if still < 4.0:
        标记为 failed，不进入 Stage 5
```

### Step 7: Gate 2 — 人工确认精修结果

```
展示格式:
┌──────────────────────────────────┐
│ 🖼️ 图片 #1 (c1)                  │
│ [精修前] ←→ [精修后] 对比         │
│ 总分: 7.2/10  ✅ 通过             │
│ 修复: contrast_enhance_1.25x       │
│                                  │
│ 🖼️ 图片 #2 (c2)                  │
│ 总分: 4.5/10  ⚠️ 建议重生成       │
│                                  │
├──────────────────────────────────┤
│ 选项: [Y]全部通过 [R:id]重生成    │
│       [N:id]重精修 [X]终止        │
└──────────────────────────────────┘
```

### Step 8: 调度 Stage 5 — 导出

```bash
python stages/stage5-final-export/scripts/export.py \
  --images approved_images.json \
  --platforms "wechat_moment,linkedin" \
  --output {output_dir}/
```

### Step 9: 交付清单

```
✅ Pipeline 完成
📁 输出: ./ad-output/acp_20260502_143000/
📊 统计:
   概念: 3 | 初稿: 3 | 通过: 3 | 导出: 12 个文件
💰 费用: ¥0.12 (3 × ¥0.04)
⏱️  耗时: 1分42秒

📁 文件:
   exports/img_ds_a1b2c3_wechat_moment_feed.png (342KB)
   exports/img_ds_a1b2c3_linkedin_sponsored.png (285KB)
   ...
```

## 错误处理矩阵

| 场景 | Stage | 处理 |
|------|-------|------|
| Pre-flight 失败 | init | 退出 + 修复指引 |
| LLM 输出格式错误 | 1,2 | 重试 1 次，仍失败则终止 |
| Provider 不可用 | 3 | Fallback 到备选 Provider |
| API 超时 (120s) | 3 | 单张重试 1 次 |
| 所有图 < 4.0 分 | 4 | 提示用户调整，不自动死循环 |
| 用户中途 Ctrl+C | 任意 | 保存 state.json，支持 --resume |
| 预算超支 | 3 | 停止，提示 --budget |
| Prompt 注入命中 | 3 | 跳过该图，记录到 errors[] |
| 磁盘空间不足 | 3,5 | Pre-flight 已拦截 (≥1GB) |

## --resume 恢复机制

```python
# 读取 state.json
state = json.load(open(f"{output_dir}/state.json"))

# 根据 status 字段定位断点
if state["status"] == "generating":
    # Stage 3 中崩溃 → 检查哪些图已完成
    completed = [img for img in state["stage3"]["images"] if img["status"] == "completed"]
    pending = [img for img in state["stage3"]["images"] if img["status"] != "completed"]
    # 只重新生成 pending 的图
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AD_PRIMARY_PROVIDER` | 主 Provider | `dashscope` |
| `DASHSCOPE_API_KEY` | DashScope Key | — |
| `GPT_IMAGE_BASE_URL` | gpt-image-2 中转站地址 | — |
| `GPT_IMAGE_API_KEY` | gpt-image-2 Key | — |
| `AD_BUDGET_YUAN` | 默认预算 | `5.0` |

## 禁止事项

- ❌ 不要跳过 Gate 的人工确认（除非 `--auto` flag）
- ❌ 不要在 Gate 1 未通过时进入 Stage 3
- ❌ 不要对 needs_regeneration 的图进入 Stage 5
- ❌ 不要覆盖已有的 state.json（除非 --force）
- ❌ 不要在无 Pre-flight 检查的情况下启动 Pipeline
