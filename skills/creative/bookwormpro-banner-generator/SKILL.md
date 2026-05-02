---
name: bookwormpro-banner-generator
description: 生成 BookwormPRO 规格的全幅终端横幅 — 双栏布局(Rich Panel) + ◈✦✓结构化信息卡 + 蓝色主题。用于节日、公告、里程碑等场景。
version: 1.0.0
tags: [banner, rich, panel, dual-column, ascii-art, bookwormpro]
---

# BookwormPRO 规格横幅生成器

生成与 BookwormPRO 启动横幅格式完全一致的全幅终端横幅。

## 核心规格 (来自 bwm_cli/banner.py build_welcome_banner)

### 外框
- Rich `Panel`, 默认 `╭─╮│╰─╯` border
- 顶部 title 栏: `[bold #5DADE2]标题文本[/]`
- border_style: `#2874A6`

### 配色方案 (蓝色主题)
```
ACCENT  = "#5DADE2"   # 节标题、Hero ASCII、高亮值
DIM     = "#1F618D"   # 分隔线、标签、副文本、边框内侧
TEXT    = "#D6EAF8"   # 正文、标语斜体
BORDER  = "#2874A6"   # Panel 外框
TITLE   = "#5DADE2"   # Panel 标题
bright_cyan           # 关键数值/高亮
dim                   # 通用弱化文本
```

### 布局结构
```
┌─ Panel(title) ──────────────────────────────────────────┐
│  左栏(58列, no_wrap)  │  ┊(3列) │  右栏(自适应)        │
│                       │        │                      │
│  Hero ASCII (bold)    │        │  ◈ 区块1              │
│  Sub ASCII (dim)      │        │    label: value       │
│                       │        │  ─── 分隔线 ───       │
│  ╭─ Box1(40列居中)─╮  │        │  ✦ 区块2              │
│  │  标语1           │  │        │    label: value       │
│  │  标语2           │  │        │  ─── 分隔线 ───       │
│  ╰──────────────────╯  │        │  ✓ 区块3              │
│                       │        │    label: value       │
│  ╭─ Box2(30列右齐)─╮  │        │                      │
│  │  信息行1         │  │        │                      │
│  │  信息行2         │  │        │                      │
│  ╰──────────────────╯  │        │                      │
└─────────────────────────────────────────────────────────┘
```

- 左栏 58 列 + 分隔线 3 列 + 右栏 min 40 列
- 终端 < 110 列自动退化为单栏堆叠
- 双栏高度取 max(左行数, 右行数)

### 中文标签对齐
```python
def LBL(s):
    dw = sum(2 if ord(c) > 127 else 1 for c in s)
    return f"[dim]{s}{' ' * max(0, 8 - dw)}[/]"
```
中文占 2 列显示宽度，pad 到 8 列。

## 生成流程

### 1. 确定主题
- 节日（劳动节、国庆、春节...）
- 里程碑（版本发布、项目上线...）
- 公告（维护通知、新功能...）

### 2. 准备左栏内容
- **Hero ASCII**: 主题大字，用 pyfiglet 或 asciified API 生成，控制宽度 ≤ 52 列
- **Sub ASCII**: 副标题，dim 样式
- **Box 1**: 38-40 列宽居中标语框
- **Box 2**: 28-30 列宽右对齐信息框

### 3. 准备右栏内容
- **◈ 区块**: 基本信息档案
- **✦ 区块**: 背景/来源/数据
- **✓ 区块**: 状态/精神/号召

### 4. 代码模板
参考 `output/laborday-banner.py` 作为完整模板。关键点：
- 左栏每个逻辑块是列表的一个元素（可能内含 `\n` 多行）
- 右栏每行一个元素
- Rich mode: 用 `_RTable.grid` + `Panel` 组装
- Raw mode: 用 `strip_rich()` 去标记 + 展平多行 + 逐行拼接

## 已知陷阱

1. **终端宽度检测**: 非 TTY 下 `shutil.get_terminal_size()` 返回 80，用 `--wide N` 强制指定
2. **Rich 标记剥离**: 正则用 `r'\[[^\]]*\]'`，不要用 `[a-z# ]` 字符类——会漏掉 `bright_cyan`、`#5DADE2` 等
3. **多行内容展平**: Raw 模式下必须 `.split('\n')` 展平每个逻辑块，不能直接用 `left_lines[i]`
4. **Windows 路径**: Git Bash 用 `/c/Users/...` 格式
5. **左栏宽度**: ASCII 行严格 ≤ 58 列，超出会导致双栏布局错位

## 运行方式
```bash
python banner.py               # Rich 彩色版
python banner.py --raw         # 纯文本版
python banner.py --wide 140    # 强制终端宽度
python banner.py --raw --wide 120  # 组合
```
