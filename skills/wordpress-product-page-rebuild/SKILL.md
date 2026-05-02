---
name: wordpress-product-page-rebuild
description: >
  Rebuild a messed-up WordPress product page template from clean Python data
  instead of string patching. When multiple sed/Python string replacements
  have corrupted the HTML structure (div imbalance, missing tags), generate
  the entire template from structured product data. Trigger: 产品页乱了,
  div不平衡, 模板重建, page-products.php rebuild
maturity: stable
cost_level: medium
---

# WordPress 产品页模板重建

## 触发条件

- 多次 sed/Python 字符串替换后导致 HTML 结构损坏
- div 开闭标签不平衡（`<div>` count ≠ `</div>` count）
- 页面渲染异常但 PHP 语法检查通过
- 原始备份模板丢失

## 方法：从数据结构生成模板

不要逐个字符串替换。用 Python 定义产品数据，一次性生成完整的干净模板。

### 1. 定义产品数据结构

```python
products = [
    {
        "name": "产品名称",
        "desc": "产品描述",
        "img": "product-xxx.jpg",
        "alt": "Alt text with keywords",
        "features": ["特性1", "特性2", ...],
        "scenarios": ["场景1", "场景2", "场景3"],
        "specs": [("参数名", "参数值"), ...],
        "alt_section": False,  # True = 交替背景色
    },
    ...
]
```

### 2. 逐产品生成 HTML

```python
for p in products:
    cls = ' section--alt' if p['alt_section'] else ''
    rev = ' product-grid--reverse' if p['alt_section'] else ''
    lines.append(f'<section class="product-detail section{cls}">')
    lines.append(f'<div class="product-grid{rev}">')
    lines.append('<div class="product-grid__image">')
    lines.append(f'<img src=".../{p["img"]}" ...>')
    lines.append('</div>')
    lines.append('<div class="product-grid__content">')
    # ... name, desc, features, scenarios, specs
    lines.append('</div></div></section>')
```

### 3. 验证

```python
d_open = content.count('<div')
d_close = content.count('</div>')
assert d_open == d_close, f"div imbalance: {d_open}/{d_close}"
```

## 关键原则

1. **从不 patch，只重建** — 3 次以上字符串替换 → 直接重建
2. **数据驱动** — 产品信息放在数据结构里，不在字符串里
3. **生成后立即验证** — PHP syntax + div balance
4. **保留 messy 备份** — `page-products.php.messy-bak`

## 配套 CSS

产品详情页需要专门的 2 列布局，覆盖默认的 3 列卡片网格：

```css
.product-detail .product-grid {
    grid-template-columns: 1fr 1fr;
}
.product-detail .product-grid--reverse {
    direction: rtl;  /* 交替左右 */
}
@media (max-width: 768px) {
    .product-detail .product-grid {
        grid-template-columns: 1fr;
    }
}
```

## 常见陷阱

| 陷阱 | 表现 | 解决 |
|------|------|------|
| 卡片 grid 冲突 | 产品详情被切成 3 列 | 加 `.product-detail .product-grid` 覆盖 |
| section--alt 无样式 | 交替背景不显示 | CSS 中补充 `.section--alt { background: ... }` |
| 字符串替换累积 | div 越来越不平衡 | 重建而非修补 |
| shell 转义破坏 | `@`/`$`/`&` 被 shell 解释 | 用 Python 文件上传执行 |
