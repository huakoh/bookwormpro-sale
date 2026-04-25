"""Welcome banner, ASCII art, skills summary, and update check for the CLI.

Pure display functions with no HermesCLI state dependency.
"""

import json
import logging
import shutil
import subprocess
import threading
import time
from pathlib import Path
from bwm_constants import get_hermes_home
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from prompt_toolkit import print_formatted_text as _pt_print
from prompt_toolkit.formatted_text import ANSI as _PT_ANSI

logger = logging.getLogger(__name__)


# =========================================================================
# ANSI building blocks for conversation display
# =========================================================================

_GOLD = "\033[1;38;2;255;215;0m"  # True-color #FFD700 bold
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RST = "\033[0m"


def cprint(text: str):
    """Print ANSI-colored text through prompt_toolkit's renderer."""
    _pt_print(_PT_ANSI(text))


# =========================================================================
# Skin-aware color helpers
# =========================================================================

def _skin_color(key: str, fallback: str) -> str:
    """Get a color from the active skin, or return fallback."""
    try:
        from bwm_cli.skin_engine import get_active_skin
        return get_active_skin().get_color(key, fallback)
    except Exception:
        return fallback


def _skin_branding(key: str, fallback: str) -> str:
    """Get a branding string from the active skin, or return fallback."""
    try:
        from bwm_cli.skin_engine import get_active_skin
        return get_active_skin().get_branding(key, fallback)
    except Exception:
        return fallback


# =========================================================================
# ASCII Art & Branding
# =========================================================================

from bwm_cli import __version__ as VERSION, __release_date__ as RELEASE_DATE

# Hero ASCII (raw, 不含 markup; 颜色由 banner 渲染时套上)
_HERO_LINES = [
    " ____              _                                   ",
    "| __ )  ___   ___ | | ____      _____  _ __ _ __ ___   ",
    "|  _ \\ / _ \\ / _ \\| |/ /\\ \\ /\\ / / _ \\| '__| '_ ` _ \\  ",
    "| |_) | (_) | (_) |   <  \\ V  V / (_) | |  | | | | | | ",
    "|____/ \\___/ \\___/|_|\\_\\  \\_/\\_/ \\___/|_|  |_| |_| |_| ",
]


def _render_hero(color: str = "bold cyan") -> str:
    """渲染 Hero ASCII (rich-safe, 转义反斜杠中的特殊字符)。"""
    from rich.markup import escape as _esc
    return "\n".join(f"[{color}]{_esc(line)}[/]" for line in _HERO_LINES)


BOOKWORMPRO_HERO_ART = _render_hero()

BOOKWORMPRO_AGENT_LOGO = ""  # 旧 logo 已合并到主 panel

BOOKWORMPRO_CADUCEUS = ""  # decorative caduceus disabled in BookwormPRO朴素风格



# =========================================================================
# Skills scanning
# =========================================================================

def get_available_skills() -> Dict[str, List[str]]:
    """Return skills grouped by category, filtered by platform and disabled state.

    Delegates to ``_find_all_skills()`` from ``tools/skills_tool`` which already
    handles platform gating (``platforms:`` frontmatter) and respects the
    user's ``skills.disabled`` config list.
    """
    try:
        from tools.skills_tool import _find_all_skills
        all_skills = _find_all_skills()  # already filtered
    except Exception:
        return {}

    skills_by_category: Dict[str, List[str]] = {}
    for skill in all_skills:
        category = skill.get("category") or "general"
        skills_by_category.setdefault(category, []).append(skill["name"])
    return skills_by_category


# =========================================================================
# Update check
# =========================================================================

# Cache update check results for 6 hours to avoid repeated git fetches
_UPDATE_CHECK_CACHE_SECONDS = 6 * 3600


def check_for_updates() -> Optional[int]:
    """Check how many commits behind origin/main the local repo is.

    Does a ``git fetch`` at most once every 6 hours (cached to
    ``~/.bookwormpro/.update_check``).  Returns the number of commits behind,
    or ``None`` if the check fails or isn't applicable.
    """
    hermes_home = get_hermes_home()
    repo_dir = hermes_home / "bookwormpro"
    cache_file = hermes_home / ".update_check"

    # Must be a git repo — fall back to project root for dev installs
    if not (repo_dir / ".git").exists():
        repo_dir = Path(__file__).parent.parent.resolve()
    if not (repo_dir / ".git").exists():
        return None

    # Read cache
    now = time.time()
    try:
        if cache_file.exists():
            cached = json.loads(cache_file.read_text())
            if now - cached.get("ts", 0) < _UPDATE_CHECK_CACHE_SECONDS:
                return cached.get("behind")
    except Exception:
        pass

    # Fetch latest refs (fast — only downloads ref metadata, no files)
    try:
        subprocess.run(
            ["git", "fetch", "origin", "--quiet"],
            capture_output=True, timeout=10,
            cwd=str(repo_dir),
        )
    except Exception:
        pass  # Offline or timeout — use stale refs, that's fine

    # Count commits behind
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            capture_output=True, text=True, timeout=5,
            cwd=str(repo_dir),
        )
        if result.returncode == 0:
            behind = int(result.stdout.strip())
        else:
            behind = None
    except Exception:
        behind = None

    # Write cache
    try:
        cache_file.write_text(json.dumps({"ts": now, "behind": behind}))
    except Exception:
        pass

    return behind


def _resolve_repo_dir() -> Optional[Path]:
    """Return the active BookwormPRO git checkout, or None if this isn't a git install."""
    hermes_home = get_hermes_home()
    repo_dir = hermes_home / "bookwormpro"
    if not (repo_dir / ".git").exists():
        repo_dir = Path(__file__).parent.parent.resolve()
    return repo_dir if (repo_dir / ".git").exists() else None


def _git_short_hash(repo_dir: Path, rev: str) -> Optional[str]:
    """Resolve a git revision to an 8-character short hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", rev],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(repo_dir),
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    value = (result.stdout or "").strip()
    return value or None


def get_git_banner_state(repo_dir: Optional[Path] = None) -> Optional[dict]:
    """Return upstream/local git hashes for the startup banner."""
    repo_dir = repo_dir or _resolve_repo_dir()
    if repo_dir is None:
        return None

    upstream = _git_short_hash(repo_dir, "origin/main")
    local = _git_short_hash(repo_dir, "HEAD")
    if not upstream or not local:
        return None

    ahead = 0
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "origin/main..HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(repo_dir),
        )
        if result.returncode == 0:
            ahead = int((result.stdout or "0").strip() or "0")
    except Exception:
        ahead = 0

    return {"upstream": upstream, "local": local, "ahead": max(ahead, 0)}


_RELEASE_URL_BASE = "https://github.com/huakoh/BookwormPRO/releases/tag"
_latest_release_cache: Optional[tuple] = None  # (tag, url) once resolved


def get_latest_release_tag(repo_dir: Optional[Path] = None) -> Optional[tuple]:
    """Return ``(tag, release_url)`` for the latest git tag, or None.

    Local-only — runs ``git describe --tags --abbrev=0`` against the
    BookwormPRO checkout. Cached per-process. Release URL always points at the
    canonical huakoh/BookwormPRO repo (forks don't get a link).
    """
    global _latest_release_cache
    if _latest_release_cache is not None:
        return _latest_release_cache or None

    repo_dir = repo_dir or _resolve_repo_dir()
    if repo_dir is None:
        _latest_release_cache = ()  # falsy sentinel — skip future lookups
        return None

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            timeout=3,
            cwd=str(repo_dir),
        )
    except Exception:
        _latest_release_cache = ()
        return None

    if result.returncode != 0:
        _latest_release_cache = ()
        return None

    tag = (result.stdout or "").strip()
    if not tag:
        _latest_release_cache = ()
        return None

    url = f"{_RELEASE_URL_BASE}/{tag}"
    _latest_release_cache = (tag, url)
    return _latest_release_cache


def format_banner_version_label() -> str:
    """Return the version label shown in the startup banner title."""
    return f"BookwormPRO v{VERSION} ({RELEASE_DATE})"


# =========================================================================
# Non-blocking update check
# =========================================================================

_update_result: Optional[int] = None
_update_check_done = threading.Event()


def prefetch_update_check():
    """Kick off update check in a background daemon thread."""
    def _run():
        global _update_result
        _update_result = check_for_updates()
        _update_check_done.set()
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def get_update_result(timeout: float = 0.5) -> Optional[int]:
    """Get result of prefetched check. Returns None if not ready."""
    _update_check_done.wait(timeout=timeout)
    return _update_result


# =========================================================================
# Welcome banner
# =========================================================================

def _format_context_length(tokens: int) -> str:
    """Format a token count for display (e.g. 128000 → '128K', 1048576 → '1M')."""
    if tokens >= 1_000_000:
        val = tokens / 1_000_000
        rounded = round(val)
        if abs(val - rounded) < 0.05:
            return f"{rounded}M"
        return f"{val:.1f}M"
    elif tokens >= 1_000:
        val = tokens / 1_000
        rounded = round(val)
        if abs(val - rounded) < 0.05:
            return f"{rounded}K"
        return f"{val:.1f}K"
    return str(tokens)


def _display_toolset_name(toolset_name: str) -> str:
    """Normalize internal/legacy toolset identifiers for banner display."""
    if not toolset_name:
        return "unknown"
    return (
        toolset_name[:-6]
        if toolset_name.endswith("_tools")
        else toolset_name
    )


def build_welcome_banner(console: Console, model: str, cwd: str,
                         tools: List[dict] = None,
                         enabled_toolsets: List[str] = None,
                         session_id: str = None,
                         get_toolset_for_tool=None,
                         context_length: int = None):
    """Build and print a welcome banner with caduceus on left and info on right.

    Args:
        console: Rich Console instance.
        model: Current model name.
        cwd: Current working directory.
        tools: List of tool definitions.
        enabled_toolsets: List of enabled toolset names.
        session_id: Session identifier.
        get_toolset_for_tool: Callable to map tool name -> toolset name.
        context_length: Model's context window size in tokens.
    """
    from model_tools import check_tool_availability, TOOLSET_REQUIREMENTS
    if get_toolset_for_tool is None:
        from model_tools import get_toolset_for_tool

    tools = tools or []
    enabled_toolsets = enabled_toolsets or []

    _, unavailable_toolsets = check_tool_availability(quiet=True)
    disabled_tools = set()
    # Tools whose toolset has a check_fn are lazy-initialized (e.g. honcho,
    # homeassistant) — they show as unavailable at banner time because the
    # check hasn't run yet, but they aren't misconfigured.
    lazy_tools = set()
    for item in unavailable_toolsets:
        toolset_name = item.get("name", "")
        ts_req = TOOLSET_REQUIREMENTS.get(toolset_name, {})
        tools_in_ts = item.get("tools", [])
        if ts_req.get("check_fn"):
            lazy_tools.update(tools_in_ts)
        else:
            disabled_tools.update(tools_in_ts)

    # 单列居中布局，避免左右错位/换行折断
    layout_table = Table.grid(padding=(0, 1))
    layout_table.add_column("center", justify="center")

    # 蓝色主题
    accent = _skin_color("banner_accent", "#5DADE2")
    dim = _skin_color("banner_dim", "#1F618D")
    text = _skin_color("banner_text", "#D6EAF8")
    session_color = _skin_color("session_border", "#566573")

    # 加载 skin (用于 branding/颜色)
    try:
        from bwm_cli.skin_engine import get_active_skin
        _bskin = get_active_skin()
    except Exception:
        _bskin = None

    _hero = BOOKWORMPRO_HERO_ART
    # 数据收集
    try:
        from tools.mcp_tool import get_mcp_status
        mcp_status = get_mcp_status()
    except Exception:
        mcp_status = []

    skills_by_category = get_available_skills()
    total_skills = sum(len(s) for s in skills_by_category.values())
    mcp_connected = sum(1 for s in mcp_status if s["connected"]) if mcp_status else 0

    model_short = model.split("/")[-1] if "/" in model else model
    if model_short.endswith(".gguf"):
        model_short = model_short[:-5]
    if len(model_short) > 28:
        model_short = model_short[:25] + "..."

    # 单列布局: 顶部 Hero ASCII + 副标题 + 信息行
    lines: List[str] = [""]
    lines.append(_hero)
    lines.append(f"[bold {accent}]BookwormPRO[/]  [dim {dim}]·[/]  [bright_cyan]自托管 AI 研究助手[/]")
    lines.append("")

    # 模型行 (左对齐至最大字段)
    model_line = f"  [{accent}]{model_short}[/]"
    if context_length:
        model_line += f"  [dim {dim}]·  {_format_context_length(context_length)} 上下文[/]"
    lines.append(model_line)

    # 工作目录
    lines.append(f"  [dim {dim}]{cwd}[/]")

    # 会话 ID
    if session_id:
        lines.append(f"  [dim {session_color}]{session_id}[/]")

    # profile (非 default 时)
    try:
        from bwm_cli.profiles import get_active_profile_name
        _profile_name = get_active_profile_name()
        if _profile_name and _profile_name != "default":
            lines.append(f"  [dim {dim}]档案 · {_profile_name}[/]")
    except Exception:
        pass

    # 能力汇总
    summary_parts = [f"{len(tools)} 工具", f"{total_skills} 技能"]
    if mcp_connected:
        summary_parts.append(f"{mcp_connected} MCP")
    summary_parts.append("/help")
    lines.append(f"  [dim {dim}]{' · '.join(summary_parts)}[/]")

    # 运行时能力声明 — 让用户一眼看到 agent 有什么权限。
    # 也是给模型自己的"能力锚点"：banner 会出现在 conversation 顶部，
    # 配合 system prompt 的 NATIVE_HOST_ENVIRONMENT_HINT 双保险消除
    # "server-side sandbox" 幻觉拒绝。
    try:
        from bwm_constants import is_container, is_host_bridge_active, is_native_install, is_wsl
        capability_parts: List[str] = []
        if is_native_install():
            capability_parts.append("[bright_green]✓[/] 文件系统全访问 [dim]· 原生模式[/]")
        elif is_host_bridge_active():
            capability_parts.append("[bright_green]✓[/] 桥接 [dim]/host/desktop[/] [dim]·[/] [dim]/host/workspace[/]")
        elif is_container():
            capability_parts.append("[yellow]◐[/] 沙箱模式 [dim]· 仅 /opt/data 可写[/]")
        if is_wsl():
            capability_parts.append("[dim]/mnt/c/[/] WSL")
        # 记忆条数（builtin layer）
        try:
            mem_dir = get_hermes_home() / "memories"
            mem_count = 0
            user_count = 0
            if (mem_dir / "MEMORY.md").exists():
                mem_count = (mem_dir / "MEMORY.md").read_text(encoding="utf-8").count("\n§\n")
            if (mem_dir / "USER.md").exists():
                user_count = (mem_dir / "USER.md").read_text(encoding="utf-8").count("\n§\n")
            if mem_count or user_count:
                capability_parts.append(
                    f"[bright_green]✓[/] 记忆 [dim]{mem_count}+{user_count} 条[/]"
                )
        except Exception:
            pass
        if capability_parts:
            lines.append(f"  [dim {dim}]能力 ·[/] {'  '.join(capability_parts)}")
    except Exception:
        pass  # banner 永不因能力探测失败而崩

    # 更新提示 (仅当落后 ≥ 50 个提交时才显示)
    try:
        behind = get_update_result(timeout=0.5)
        if behind and behind >= 50:
            from bwm_cli.config import recommended_update_command
            lines.append(
                f"  [dim yellow]更新可用 ({behind})  ·  {recommended_update_command()}[/]"
            )
    except Exception:
        pass

    lines.append("")
    layout_table.add_row("\n".join(lines))

    agent_name = _skin_branding("agent_name", "BookwormPRO")
    title_color = _skin_color("banner_title", "#5DADE2")
    border_color = _skin_color("banner_border", "#2874A6")
    version_label = format_banner_version_label()
    release_info = get_latest_release_tag()
    if release_info:
        _tag, _url = release_info
        title_markup = f"[bold {title_color}][link={_url}]{version_label}[/link][/]"
    else:
        title_markup = f"[bold {title_color}]{version_label}[/]"
    term_width = shutil.get_terminal_size().columns
    outer_panel = Panel(
        layout_table,
        title=title_markup,
        border_style=border_color,
        padding=(0, 2),
        expand=True,
        width=term_width,
    )

    console.print()
    console.print(outer_panel)
