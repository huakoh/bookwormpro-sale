---
name: screenshot-ocr-fallback
description: OCR fallback for screenshots when vision_analyze fails due to model not supporting multimodal (deepseek-v4-pro, etc.). Uses OCR.space free API with pure Python stdlib — no installs needed.
version: 1.1.0
author: BookwormPRO
license: MIT
metadata:
  bookworm:
    tags: [OCR, Screenshot, Vision, Fallback, Image]
    related_skills: [ocr-and-documents]
---

# Screenshot OCR Fallback

当 `vision_analyze` 因当前模型不支持多模态输入而失败时（典型错误: `unknown variant image_url, expected text`），使用 OCR.space 免费 API 作为降级方案从截图中提取文字。纯 Python 标准库，无需安装任何依赖。

## 触发条件

- `vision_analyze` 返回 `unknown variant image_url` 或 `400 - invalid_request_error`
- 用户分享截图/图片询问内容，但当前模型（如 deepseek-v4-pro、deepseek-chat 等纯文本模型）无法直接读取图片

## 步骤

### 1. 可选：缩小图片减少传输体积

```python
from PIL import Image
img = Image.open(r'原始图片路径')
img = img.resize((img.width//2, img.height//2), Image.LANCZOS)
img.convert('RGB').save(r'临时输出路径.jpg', 'JPEG', quality=60)
```

如果 PIL 不可用，可以直接用原图 base64 发送（上限约 1MB）。

### 2. Base64 编码并调用 OCR.space API

```python
import base64, json, urllib.request, urllib.parse

with open(r'图片路径.jpg', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()

url = 'https://api.ocr.space/parse/image'
data = urllib.parse.urlencode({
    'apikey': 'helloworld',          # 免费 key，无需注册
    'base64Image': 'data:image/jpeg;base64,' + b64,
    'language': 'chs',               # chs=简体中文, eng=英文, cht=繁体
    'isOverlayRequired': 'false',
}).encode()

req = urllib.request.Request(url, data=data)
resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read().decode())

text = result['ParsedResults'][0]['ParsedText']
print(text)
```

### 3. 参数速查

| 参数 | 常用值 | 说明 |
|------|--------|------|
| `apikey` | `helloworld` | 免费 key，500次/天，够用 |
| `language` | `chs` / `eng` / `cht` | OCR 识别语言 |
| `isOverlayRequired` | `false` / `true` | 是否返回文字坐标 |

### 4. 返回结构

```json
{
  "ParsedResults": [{
    "ParsedText": "识别出的文字...",
    "FileParseExitCode": 1
  }],
  "OCRExitCode": 1,
  "ProcessingTimeInMilliseconds": "328"
}
```

- `OCRExitCode=1` = 成功
- 中文 OCR 有误差，需结合上下文理解（终端截图常有中英混杂）

### 2b. curl 降级（Python urllib 失败时使用）

Git Bash on Windows 下 Python 的 `urllib.request.urlopen` 可能直接退出 (exit code 49，无输出)，但 curl 通常可用：

```bash
B64="data:image/png;base64,$(base64 -w0 '图片路径.png')"
curl -s --connect-timeout 60 -X POST https://api.ocr.space/parse/image \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "apikey=helloworld" \
  --data-urlencode "language=chs" \
  --data-urlencode "isOverlayRequired=false" \
  --data-urlencode "base64Image=${B64}"
```

注意：必须加 `data:image/png;base64,` 前缀，否则 API 返回 `E501: Not an image or PDF`。Windows 下 `base64 -w0` (no line wrap)；Linux 可用 `base64 -w0`。

## 批量 OCR 多张截图

处理多张截图时（如用户一次发 6 张），用 PIL 先统一压缩到 1200px 宽以内：

```python
from PIL import Image
import os

files = [r'path1.png', r'path2.png', ...]
out_dir = r'C:\Users\BOOKWORMPRO_USER\Pictures\Screenshots\_ocr'
os.makedirs(out_dir, exist_ok=True)

for i, f in enumerate(files):
    img = Image.open(f)
    w, h = img.size
    if max(w, h) > 1200:
        ratio = 1200 / max(w, h)
        img = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
    out = os.path.join(out_dir, f'img{i+1}.jpg')
    img.convert('RGB').save(out, 'JPEG', quality=75)
```

然后逐张 OCR（间隔 1s 避免 rate limit），输出到 stdout 供分析。

## 注意事项

- 图片太大时先 resize，否则 base64 可能超限
- Content-Type: JPEG 用 `image/jpeg`，PNG 用 `image/png`
- Python 标准库方法在 Windows Git Bash 下可能因网络/代理问题失败 (exit 49)，此时用 curl 降级
- 无需 pip install 任何东西，Python 标准库即可
- **批量处理**：多张图先统一压缩到 `<1200px` + JPEG 75% 质量（<70KB 时最稳定）
- OCR.space 免费 API 有频率限制，多张图时加 `time.sleep(1)` 间隔
- 中文终端截图 OCR 会有乱码，需结合上下文还原（如 "生黑考"→"思考"，"0会0"→"学会"，"5n"→"5K"）

## 备选方案优先级

1. **vision_analyze** — 首选，但需模型支持多模态
2. **OCR.space API** ← 本技能（零依赖，最快降级）
3. **本地 Tesseract** — `pip install pytesseract` + 系统安装 Tesseract + chi_sim 语言包
4. **本地 EasyOCR** — `pip install easyocr`，首次自动下载模型，慢但准确率高
