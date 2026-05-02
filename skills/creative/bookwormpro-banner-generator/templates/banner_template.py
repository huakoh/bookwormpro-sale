#!/usr/bin/env python3
"""BookwormPRO 规格横幅模板
   双栏布局: 左58列 + ┊ + 右自适应, 终端<110列退化为单栏
   用法: python banner.py [--raw] [--wide N]

   替换标记:
     {{HERO_LINES}}    — 左栏 Hero ASCII (列表, 每行≤52列)
     {{SUB_LINES}}     — 左栏 Sub ASCII (列表)
     {{BOX1_TITLE}}    — Box1 第一行 (38列宽, 居中)
     {{BOX1_SUB}}      — Box1 第二行
     {{BOX2_LINE1}}    — Box2 第一行 (28列宽, 右对齐)
     {{BOX2_LINE2}}    — Box2 第二行
     {{RIGHT_BLOCKS}}  — 右栏内容 (列表, 含 ◈✦✓ 分隔)
     {{OUTER_TITLE}}   — Panel 标题
     {{BOTTOM_LINE}}   — Panel 底部标语
"""
import shutil, sys, os, re

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table as _RTable
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ── 终端宽度 ──
if "--wide" in sys.argv:
    idx = sys.argv.index("--wide")
    term_width = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 120
else:
    try:
        term_width = int(os.environ.get("COLUMNS", shutil.get_terminal_size().columns))
    except Exception:
        term_width = 120
term_width = max(term_width, 80)

RAW = "--raw" in sys.argv

LEFT_W = 58
DIV_W = 3
RIGHT_W_MIN = 40
USE_DUAL = (term_width - 8 - LEFT_W - DIV_W) >= RIGHT_W_MIN

# ── 蓝色主题 (BookwormPRO 默认) ──
A  = "#5DADE2"
D  = "#1F618D"
T  = "#D6EAF8"
BD = "#2874A6"
TL = "#5DADE2"

# =====================================================================
# 左栏内容
# =====================================================================

HL = {{HERO_LINES}}   # e.g. ["  ██╗  ...", ...]
SL = {{SUB_LINES}}    # e.g. ["  ___  ...", ...]

def mk_rich(lines, style):
    return "\n".join(f"[{style}]{l}[/]" for l in lines)

LH = mk_rich(HL, f"bold {A}")
LS = mk_rich(SL, f"dim {A}")

left_lines = [LH, "", LS, ""]

# Box 1 (38列, 居中)
b1w, b1p = 38, (LEFT_W - 38) // 2
t1 = f"  {{BOX1_TITLE}}  "   # Rich 格式
s1 = f"   {{BOX1_SUB}}   "
left_lines.append(f"{' '*b1p}[dim {D}]╭{'─'*b1w}╮[/]")
left_lines.append(f"{' '*b1p}[dim {D}]│[/]{t1}[dim {D}]│[/]")
left_lines.append(f"{' '*b1p}[dim {D}]│[/]{s1}[dim {D}]│[/]")
left_lines.append(f"{' '*b1p}[dim {D}]╰{'─'*b1w}╯[/]")
left_lines.append("")

# Box 2 (28列, 右对齐)
b2w, b2p = 28, LEFT_W - 28 - 2
d1 = f"  {{BOX2_LINE1}}  "
d2 = f"  {{BOX2_LINE2}}  "
left_lines.append(f"{' '*b2p}[dim {D}]╭{'─'*b2w}╮[/]")
left_lines.append(f"{' '*b2p}[dim {D}]│[/]{d1}[dim {D}]│[/]")
left_lines.append(f"{' '*b2p}[dim {D}]│[/]{d2}[dim {D}]│[/]")
left_lines.append(f"{' '*b2p}[dim {D}]╰{'─'*b2w}╯[/]")

left_content = "\n".join(left_lines)

# =====================================================================
# 右栏内容
# =====================================================================

def LBL(s):
    dw = sum(2 if ord(c)>127 else 1 for c in s)
    return f"[dim]{s}{' '*(max(0,8-dw))}[/]"

right_lines = [""]
SEP = f"[dim {D}]{'─'*36}[/]"

{{RIGHT_BLOCKS}}   # 列表, e.g.:
# right_lines += [
#     f"[bold {A}]◈ 区块1[/]",
#     f"{LBL('标签')} [bold bright_cyan]值[/]",
#     SEP,
#     f"[bold {A}]✦ 区块2[/]",
#     f"{LBL('标签')} [bright_cyan]值[/] [dim]备注[/]",
#     SEP,
#     f"[bold {A}]✓ 区块3[/]",
#     f"{LBL('标签')} [green]✓[/] [white]值[/]",
# ]

right_content = "\n".join(right_lines)

# =====================================================================
# 渲染
# =====================================================================

def strip_rich(s):
    return re.sub(r'\[[^\]]*\]', '', s)

OUTER_TITLE = "{{OUTER_TITLE}}"
BOTTOM_LINE = "{{BOTTOM_LINE}}"

if RAW or not HAS_RICH:
    lines_out = []
    lines_out.append(f"┌{'─'*(term_width-2)}┐")
    lines_out.append(f"│{OUTER_TITLE:^{(term_width-2)}}│")
    lines_out.append(f"├{'─'*(term_width-2)}┤")

    if USE_DUAL:
        RW = term_width - 8 - LEFT_W - DIV_W
        flat_L = []
        NL = chr(10)
        for blk in left_lines:
            flat_L.extend(strip_rich(blk).split(NL))
        flat_R = []
        for blk in right_lines:
            flat_R.extend(strip_rich(blk).split(NL))
        pad_fn = lambda s, w: s + ' ' * max(0, w - len(s))
        max_n = max(len(flat_L), len(flat_R))
        for i in range(max_n):
            l = flat_L[i] if i < len(flat_L) else ""
            r = flat_R[i] if i < len(flat_R) else ""
            if len(l) > LEFT_W:
                l = l[:LEFT_W-1] + "…"
            lines_out.append(f"│ {pad_fn(l, LEFT_W)} ┊ {pad_fn(r, RW)} │")
    else:
        for ln in left_lines:
            s = strip_rich(ln)
            lines_out.append(f"│ {s:<{term_width-4}} │")
        lines_out.append(f"│{'─'*(term_width-4)}│")
        for ln in right_lines:
            s = strip_rich(ln)
            lines_out.append(f"│ {s:<{term_width-4}} │")

    lines_out.append(f"└{'─'*(term_width-2)}┘")
    lines_out.append("")
    lines_out.append(f"      {BOTTOM_LINE}")
    print("\n".join(lines_out))

else:
    console = Console(force_terminal=True, color_system="truecolor")
    lt = _RTable.grid(padding=(0,0), expand=False)

    if USE_DUAL:
        RW = term_width - 8 - LEFT_W - DIV_W
        lt.add_column("L", justify="left", no_wrap=True, width=LEFT_W)
        lt.add_column("|", justify="center", no_wrap=True, width=DIV_W)
        lt.add_column("R", justify="left", no_wrap=False, width=RW)
        nd = max(len(left_lines), len(right_lines))
        dv = "\n".join([f"[dim cyan]┊[/]"]*nd)
        lt.add_row(left_content, dv, right_content)
    else:
        lt.add_column("C", justify="left")
        lt.add_row(left_content)
        lt.add_row("")
        lt.add_row(right_content)

    panel = Panel(
        lt,
        title=f"[bold {TL}]{OUTER_TITLE}[/]",
        border_style=BD,
        padding=(0,2),
        expand=True,
        width=term_width,
    )
    console.print()
    console.print(panel)
    console.print()
    console.print(f"      [bold {A}]✦[/] [dim]{BOTTOM_LINE[2:] if BOTTOM_LINE.startswith('✦ ') else BOTTOM_LINE}[/] [bold {A}]✦[/]")
    console.print()
