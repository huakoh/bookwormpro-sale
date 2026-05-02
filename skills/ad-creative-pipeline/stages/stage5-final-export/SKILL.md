---
name: stage5-final-export
description: >
  AdCreativePipeline Stage 5 — 定稿导出。
  将审批通过的图片按目标平台导出多尺寸版本，
  智能裁剪避开安全区域，文件大小合规检查。
safety:
  level: low
  permissions: [read_file, write_file, terminal]
maturity: alpha
parent: ad-creative-pipeline
dependencies:
  - Pillow
---

# Stage 5: 定稿导出

你是图片导出引擎，将审批通过的广告图按目标平台导出为多尺寸最终文件。

## 输入

```yaml
images: []              # Stage 4 审批通过的图片
platforms: ["wechat_moment", "linkedin"]  # 目标平台
output_dir: "./output/"  # 输出目录
```

## 工作流

### Step 1: 加载平台规范

从 `stages/stage2-design-direction/references/platform-specs.json` 读取目标平台的尺寸、安全区域、文件大小限制。

### Step 2: 逐图导出

```bash
python stages/stage5-final-export/scripts/export.py \
  --images state.json \
  --platforms "wechat_moment,linkedin" \
  --output ./output/
```

每张图 × 每个平台 × 每个尺寸 = N 个导出文件。

### Step 3: 智能裁剪

`smart_crop_resize()` 优先中心裁剪，避开安全区域：
- Instagram Story: 顶部/底部各留 250px
- 其他平台: 居中裁剪

### Step 4: 文件大小检查

导出后检查文件大小是否超过平台限制：
- Google Display: 150KB
- Facebook/Instagram: 30MB
- 微信/LinkedIn: 5MB

超限时自动降质重试 (quality 80)。

## 输出

```json
{
  "exports": [
    {
      "image_id": "img_ds_a1b2c3",
      "platform": "wechat_moment",
      "format_name": "moment_feed",
      "path": "/output/exports/img_ds_a1b2c3_wechat_moment_moment_feed.png",
      "dimensions": "1080x1080",
      "format": "PNG",
      "file_size_kb": 342.5,
      "size_warning": false
    }
  ],
  "summary": {
    "total_files": 8,
    "total_size_mb": 2.7,
    "export_dir": "/output/exports/"
  }
}
```

## 导出示例

```
输入: 3 张图 × 2 个平台 (微信朋友圈 + LinkedIn)
微信: moment_feed (1080×1080) + moment_banner (1080×568)
LinkedIn: sponsored_content (1200×627) + sponsored_messaging (800×400)
输出: 3 × 4 = 12 个文件
```

## 文件命名规范

```
{image_id}_{platform}_{format_name}.png
例: img_ds_a1b2c3_wechat_moment_moment_feed.png
```

## 禁止事项

- ❌ 不要覆盖原始图片
- ❌ 不要跳过安全区域检查
- ❌ 不要导出到 sandbox 外的路径
- ❌ 不要对超大文件放弃降质（至少尝试一次 quality=80）
