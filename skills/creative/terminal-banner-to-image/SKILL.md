---
name: terminal-banner-to-image
description: 将终端代码文字横幅（ASCII art + CJK 混排）渲染为高分辨率 4:3/16:9 图片。保留所有框线字符、砖块字、颜色方案，支持中英文混排。常用于节日横幅、启动画面、社交媒体素材。
version: 1.0.0
---

# Terminal Banner → Image

将终端代码文字横幅（含 ASCII art、框线字符、CJK 混排）精确渲染为高分辨率 PNG 图片。

## 适用场景

- 节日/活动横幅 → 4:3 图片（如劳动节、春节）
- BookwormPRO 启动 banner → 截图级高清图
- 终端截图 → 高清渲染
- 代码文字宣传素材

## 核心策略

### 1. 字体选择（关键）

**Windows CJK 等宽顺序**：
1. `simsun.ttc` — 宋体，CJK width ≈ 1.6× ASCII width，兼容最好
2. `simhei.ttf` — 黑体，CJK 宽度类似
3. `msyh.ttc` — 微软雅黑，CJK 宽度偏大

**Linux/Mac**：优先 `Noto Sans Mono CJK` 或 `Sarasa Mono SC`

**避免**：Consolas/Courier New — 不支持中文，汉字变 tofu

### 2. 逐字符宽度测量

CJK 和 ASCII 宽度不同，不能假设固定 char_w。必须逐字符测量：

```python
def is_cjk(ch): return ord(ch) > 127
def line_width(line):
    return sum(cjk_w if is_cjk(ch) else ascii_w for ch in line)
```

### 3. 颜色映射

按行内容分类上色，保留终端配色风格：
- 框线字符 (`╔═╗║╚═╝╭─╮╰─╯│`) → 边框色
- 砖块字 (`█▄▀▌▐`) → 强调色
- 中文/标语 → 金色或主题色
- 普通 ASCII → 正文色

### 4. 自动字号适配

```
目标: 文字区占画面 92-94%，留边距 3-4%
算法: 从 24px 开始递减，直到 max_line_w ≤ target_w
      每次递减重测 char_w 和 cjk_w
```

## BookwormPRO 配色参考

| 角色 | 颜色 | Hex |
|------|------|-----|
| 背景 | 深蓝黑 | #0A0F1C |
| 外框 | 边框蓝 | #2874A6 |
| 内框 | 暗蓝 | #1F618D |
| 强调 | 亮蓝 | #5DADE2 |
| 正文 | 蓝白 | #D6EAF8 |
| 标语 | 金色 | #FFD700 |

## 步骤模板

1. **准备横幅文本** — 完整 ASCII art 字符串（含所有框线、CJK）
2. **检测字体** — 优先 CJK 等宽，fallback 到黑体
3. **计算字号** — 自动适配到 92% 画布宽度
4. **逐行渲染** — 逐字符测量宽度，处理 CJK 偏移
5. **颜色覆盖** — 按行内容/字符类型分色
6. **背景光晕** — 中心微光增加层次感
7. **保存 PNG** — 4:3 (1600×1200) 或自定义尺寸

## 已知陷阱

- **Consolas 无 CJK**：中文显示为方块，必须用 SimSun/SimHei
- **TTC 字体**：SimSun 是 TTC，PIL 自动选 index 0
- **getbbox ≠ advance width**：用 `getbbox()[2]-getbbox()[0]` 近似
- **行间距**：`char_h + 3~4px` 防止粘连
- **框线字符宽度**：Unicode box-drawing 在 SimSun 中宽度 = ASCII width

## 示例输出

1600×1200 PNG, SimSun 19px, 36 行 × 76 列, ~50KB

可生成 `--size=1200x900` 或 `--size=1920x1080` 等任意 4:3/16:9 规格。
