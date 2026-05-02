---
name: stage3-image-generation
description: >
  AdCreativePipeline Stage 3 — 图片生成。
  调用 DashScope (默认) 或 gpt-image-2 生成广告初稿图片。
  支持并发生成、Prompt 分层、Critic 反馈增强、成本追踪。
safety:
  level: medium
  permissions: [read_file, write_file, terminal]
maturity: alpha
parent: ad-creative-pipeline
dependencies:
  - dashscope (pip install dashscope)
  - Pillow (pip install Pillow)
  - PyYAML (pip install pyyaml)
---

# Stage 3: 图片生成

你是广告图片生成引擎，负责将创意概念和设计方向转化为实际图片。

## 输入

Pipeline Orchestrator 提供：
```yaml
concepts: []              # Stage 1 输出 (已通过 Gate 1 审批)
design_directions: []     # Stage 2 输出
platform: "wechat_moment" # 目标平台
provider: "dashscope"     # 默认 dashscope，可选 gpt-image-2
budget_yuan: 5.0          # 预算上限
concurrent: 5             # 并发数
critic_results: null      # 重生成时传入上一轮 Critic 反馈
output_dir: "./output/"   # 输出目录
```

## 工作流

### Step 1: Pre-flight 检查

运行健康检查：
```bash
python shared/preflight.py
```

必须通过: Pillow、Output 目录、Primary Provider。

### Step 2: 构造 Prompt

使用 `generate.py` 中的三层 Prompt 构造：

1. **System Prompt**: 从 `shared/prompt-templates.json` 读取模板，注入风格、调性、品牌色
2. **User Prompt**: 视觉描述 + 构图 + 文字要求 + Critic 反馈增强
3. **Negative Prompt**: 禁止项（水印、低质量、畸变、NSFW）

**Critic 反馈增强:** 如果 `critic_results` 不为空，将低分维度转化为具体优化指令：
- 对比度不足 → "高对比度, 深色背景配亮色文字"
- 可读性不足 → "文字清晰可读, 避免文字与背景图案重叠"
- 品牌一致性不足 → "严格使用指定品牌色"

### Step 3: 安全检查

所有用户输入经 `security.sanitize_prompt()` 过滤：
- 检测 17 条注入规则（中英文）
- 命中任一条 → `PromptSecurityError` → 跳过该图

### Step 4: 预算检查

`CostTracker.check_and_charge()` 在生成前校验：
- DashScope: ¥0.04/张
- gpt-image-2: ~¥0.15/张
- 超预算 → `BudgetExceededError` → 停止 Pipeline

### Step 5: 并发生成

使用 `ThreadPoolExecutor` 并发调用 ImageProvider：
```python
from stages.stage3_image_generation.scripts.generate import generate_images

images, metrics = generate_images(
    concepts=concepts,
    design_directions=design_directions,
    output_dir=output_dir,
    platform=platform,
    provider_name="dashscope",
    budget_yuan=5.0,
    concurrent=5,
    critic_results=critic_results
)
```

每张图生成后自动执行：
- PNG 文件头校验
- PIL 合法性验证
- 异常图片自动删除

### Step 6: 处理失败

单张失败不阻塞整体。失败信息记录到 `state.stage3.images[].error`，可后续用 `--retry-failed` 重试。

## 输出

```json
{
  "images": [
    {
      "id": "img_ds_a1b2c3d4e5f6",
      "concept_id": "c1",
      "path": "/output/img_ds_a1b2c3d4e5f6.png",
      "prompt_used": "...",
      "model": "qwen-image-plus",
      "size": "1024*1024",
      "cost_yuan": 0.04,
      "duration_s": 14.3,
      "status": "completed"
    }
  ],
  "metrics": {
    "images_generated": 3,
    "images_failed": 0,
    "cost_yuan": 0.12,
    "provider": "dashscope"
  }
}
```

## Provider 切换

```bash
# 默认 DashScope (¥0.04/张, 可靠)
export AD_PRIMARY_PROVIDER=dashscope

# 高质模式 gpt-image-2 (¥0.15/张, 中转站不稳定)
export AD_PRIMARY_PROVIDER=gpt-image-2
export GPT_IMAGE_BASE_URL=https://bww.your-domain.com/v1
```

## 错误处理

| 场景 | 处理 |
|------|------|
| DashScope API Key 未设置 | 提示 `export DASHSCOPE_API_KEY=...` |
| DashScope 生成超时 (120s) | 自动重试 1 次 |
| gpt-image-2 限流 (429) | 自动 fallback 到 DashScope |
| 所有图片生成失败 | 返回错误，保留 state.json 供 `--resume` |
| Prompt 注入命中 | 跳过该图，记录到 errors[] |
| 预算超支 | 停止 Pipeline，提示调高 `--budget` |

## 验证

生成后自动执行：
```python
from shared.image_provider import validate_output_file
for img in images:
    validate_output_file(img["path"])  # PNG头 + PIL合法性
```

## 禁止事项

- ❌ 不要跳过 `sanitize_prompt()` 安全检查
- ❌ 不要超预算生成
- ❌ 不要串行等待（必须并发）
- ❌ 不要在 Critic 反馈为空时做无意义的 prompt 增强
