"""Shared curses-based UI components for BookwormPRO CLI.

Used by `bookworm tools` and `bookworm skills` for interactive checklists.
Provides a curses multi-select with keyboard navigation, plus a
text-based numbered fallback for terminals without curses support.
"""
import sys
from typing import Callable, List, Optional, Set

from bwm_cli.colors import Colors, color
from bwm_cli.i18n import _



def _open_conout():
    """Open a direct UTF-8 handle to the Windows console (CONOUT$).

    Bypasses any sys.stdout interception by prompt_toolkit / pipes / wrappers,
    so ANSI escape sequences are interpreted by the terminal instead of
    being printed as literal text.  Returns a file-like object the caller
    must close in a finally block.

    Raises:
        RuntimeError: If called on a non-Windows platform (CONOUT$ is a
            Windows-specific console device).  All callers must guard with
            ``sys.platform == "win32"``.
    """
    import io
    if sys.platform != "win32":
        raise RuntimeError("_open_conout() is Windows-only (CONOUT$ does not exist on this platform)")
    raw = io.FileIO("CONOUT$", "w")
    return io.TextIOWrapper(raw, encoding="utf-8", write_through=True, newline="")


def _display_width(s: str) -> int:
    """Visual column width of a string in a terminal.

    East-Asian Wide / Fullwidth chars count 2 columns, others 1.
    Approximation — does not handle zero-width joiners or grapheme clusters.
    """
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _truncate_to_width(s: str, max_width: int) -> str:
    """Truncate string so its terminal column width <= max_width."""
    import unicodedata
    if max_width <= 0:
        return ""
    out: list[str] = []
    w = 0
    for c in s:
        cw = 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
        if w + cw > max_width:
            break
        out.append(c)
        w += cw
    return "".join(out)


from contextlib import contextmanager


# Terminal control sequences (not in Colors — those are SGR text-style codes only).
# Kept inline because they have no equivalent in the Colors palette.
_ALT_SCREEN_ENTER = "\x1b[?1049h"
_ALT_SCREEN_LEAVE = "\x1b[?1049l"
_CURSOR_HIDE = "\x1b[?25l"
_CURSOR_SHOW = "\x1b[?25h"
_CURSOR_HOME = "\x1b[H"
_CLEAR_SCREEN = "\x1b[2J"


@contextmanager
def _alt_screen_session():
    """Context manager: enter Windows alternate screen + hide cursor.

    Yields a CONOUT$ writable handle.  On exit (normal or exception),
    leaves alt-screen, restores cursor, closes the handle, and drains
    any residual keystrokes from the OS input buffer so that subsequent
    input() / getpass() do not consume stale arrow-key bytes.

    Also forces the console output/input code pages to UTF-8 (65001)
    while the picker is active.  CONOUT$ writes raw bytes — the console
    interprets them per its active code page, so a default CP936 (GBK)
    Chinese Windows would mojibake our UTF-8 output (e.g. '↑↓' rendered
    as '鈫戔啌').  Restored to the original code pages on exit.
    """
    import msvcrt
    import ctypes
    k32 = ctypes.windll.kernel32
    old_out_cp = k32.GetConsoleOutputCP()
    old_in_cp = k32.GetConsoleCP()
    if old_out_cp != 65001:
        k32.SetConsoleOutputCP(65001)
    if old_in_cp != 65001:
        k32.SetConsoleCP(65001)

    out = _open_conout()
    out.write(_ALT_SCREEN_ENTER + _CURSOR_HIDE)
    out.flush()
    try:
        yield out
    finally:
        try:
            try:
                out.write(_CURSOR_SHOW + _ALT_SCREEN_LEAVE)
                out.flush()
            finally:
                out.close()
            try:
                while msvcrt.kbhit():
                    msvcrt.getwch()
            except Exception:
                pass
        finally:
            if old_out_cp != 65001:
                k32.SetConsoleOutputCP(old_out_cp)
            if old_in_cp != 65001:
                k32.SetConsoleCP(old_in_cp)


def _win_read_key() -> str:
    """Read one key from msvcrt and normalize to a canonical name.

    Returns one of: 'UP', 'DOWN', 'LEFT', 'RIGHT', 'ENTER', 'ESC',
    'SPACE', 'CTRL_C', 'q', 'j', 'k', or '' (unrecognized).

    Note: 'q' is treated as a cancel shortcut by all current pickers
    (consistent with vim/less conventions).  Only safe for navigation-only
    pickers — DO NOT reuse this helper for free-text input fields where
    'q' is a valid character.
    """
    import msvcrt
    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        ch2 = msvcrt.getwch()
        return {
            "H": "UP",
            "P": "DOWN",
            "K": "LEFT",
            "M": "RIGHT",
        }.get(ch2, "")
    if ch == "\x03":
        return "CTRL_C"
    if ch == "\r":
        return "ENTER"
    if ch == "\x1b":
        return "ESC"
    if ch == " ":
        return "SPACE"
    if ch in ("q", "j", "k"):
        return ch
    return ""


def flush_stdin() -> None:
    """Flush any stray bytes from the stdin input buffer.

    Must be called after ``curses.wrapper()`` (or any terminal-mode library
    like simple_term_menu) returns, **before** the next ``input()`` /
    ``getpass.getpass()`` call.  ``curses.endwin()`` restores the terminal
    but does NOT drain the OS input buffer — leftover escape-sequence bytes
    (from arrow keys, terminal mode-switch responses, or rapid keypresses)
    remain buffered and silently get consumed by the next ``input()`` call,
    corrupting user data (e.g. writing ``^[^[`` into .env files).

    On non-TTY stdin (piped, redirected) or Windows, this is a no-op.
    """
    try:
        if not sys.stdin.isatty():
            return
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass


def _win_checklist(
    title: str,
    items: list[str],
    selected: set[int],
    cancel_returns: set[int],
    status_fn: Optional[Callable[[Set[int]], str]] = None,
) -> set[int]:
    """Windows-native multi-select checklist using msvcrt + ANSI."""
    import os

    if not items:
        return cancel_returns

    chosen = set(selected)
    cursor = 0
    scroll_offset = 0
    R = Colors.RESET
    H = Colors.BOLD + Colors.YELLOW
    S = Colors.BOLD + Colors.GREEN
    D = Colors.DIM

    with _alt_screen_session() as out:
        while True:
            try:
                cols, rows = os.get_terminal_size()
            except OSError:
                cols, rows = 80, 24
            footer = 1 if status_fn else 0
            visible = max(rows - 4 - footer, 1)

            if cursor < scroll_offset:
                scroll_offset = cursor
            elif cursor >= scroll_offset + visible:
                scroll_offset = cursor - visible + 1

            out.write(_CURSOR_HOME + _CLEAR_SCREEN)
            out.write(f"{H}{title}{R}\n")
            out.write(f"{D}  ↑↓ navigate  SPACE toggle  ENTER confirm  ESC cancel{R}\n\n")

            end = min(len(items), scroll_offset + visible)
            for i in range(scroll_offset, end):
                check = "x" if i in chosen else " "
                label = _truncate_to_width(items[i], max(cols - 10, 1))
                if i == cursor:
                    out.write(f" {S}→ [{check}] {label}{R}\n")
                else:
                    out.write(f"   [{check}] {label}\n")

            if status_fn:
                st = status_fn(chosen) or ""
                out.write(f"\n{D}{st}{R}")

            out.flush()

            key = _win_read_key()
            if key == "UP" or key == "k":
                cursor = (cursor - 1) % len(items)
            elif key == "DOWN" or key == "j":
                cursor = (cursor + 1) % len(items)
            elif key == "CTRL_C":
                raise KeyboardInterrupt
            elif key == "SPACE":
                chosen.symmetric_difference_update({cursor})
            elif key == "ENTER":
                return set(chosen)
            elif key == "ESC" or key == "q":
                return cancel_returns

    return cancel_returns


def _win_radiolist(
    title: str,
    items: list[str],
    selected: int,
    cancel_returns: int,
    description: str | None = None,
) -> int:
    """Windows-native radio-select using msvcrt + ANSI."""
    import os

    if not items:
        return cancel_returns

    cursor = selected
    scroll_offset = 0
    desc_lines = (description or "").splitlines()
    R = Colors.RESET
    H = Colors.BOLD + Colors.YELLOW
    S = Colors.BOLD + Colors.GREEN
    D = Colors.DIM

    with _alt_screen_session() as out:
        while True:
            try:
                cols, rows = os.get_terminal_size()
            except OSError:
                cols, rows = 80, 24
            header_rows = 2 + len(desc_lines) + 1
            visible = max(rows - header_rows - 1, 1)

            if cursor < scroll_offset:
                scroll_offset = cursor
            elif cursor >= scroll_offset + visible:
                scroll_offset = cursor - visible + 1

            out.write(_CURSOR_HOME + _CLEAR_SCREEN)
            out.write(f"{H}{title}{R}\n")
            for dl in desc_lines:
                out.write(f"{dl}\n")
            out.write(f"{D}  ↑↓ navigate  ENTER/SPACE select  ESC cancel{R}\n\n")

            end = min(len(items), scroll_offset + visible)
            for i in range(scroll_offset, end):
                radio = "●" if i == selected else "○"
                label = _truncate_to_width(items[i], max(cols - 10, 1))
                if i == cursor:
                    out.write(f" {S}→ ({radio}) {label}{R}\n")
                else:
                    out.write(f"   ({radio}) {label}\n")

            out.flush()

            key = _win_read_key()
            if key == "UP" or key == "k":
                cursor = (cursor - 1) % len(items)
            elif key == "DOWN" or key == "j":
                cursor = (cursor + 1) % len(items)
            elif key == "CTRL_C":
                raise KeyboardInterrupt
            elif key in ("SPACE", "ENTER"):
                return cursor
            elif key == "ESC" or key == "q":
                return cancel_returns

    return cancel_returns


def curses_checklist(
    title: str,
    items: List[str],
    selected: Set[int],
    *,
    cancel_returns: Set[int] | None = None,
    status_fn: Optional[Callable[[Set[int]], str]] = None,
) -> Set[int]:
    """Curses multi-select checklist. Returns set of selected indices.

    Args:
        title: Header line displayed above the checklist.
        items: Display labels for each row.
        selected: Indices that start checked (pre-selected).
        cancel_returns: Returned on ESC/q. Defaults to the original *selected*.
        status_fn: Optional callback ``f(chosen_indices) -> str`` whose return
            value is rendered on the bottom row of the terminal.  Use this for
            live aggregate info (e.g. estimated token counts).
    """
    if cancel_returns is None:
        cancel_returns = set(selected)

    # Safety: curses and input() both hang or spin when stdin is not a
    # terminal (e.g. subprocess pipe).  Return defaults immediately.
    if not sys.stdin.isatty():
        return cancel_returns

    if sys.platform == "win32":
        return _win_checklist(title, items, selected, cancel_returns, status_fn)

    try:
        import curses
        chosen = set(selected)
        result_holder: list = [None]

        def _draw(stdscr):
            curses.curs_set(0)
            if curses.has_colors():
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_GREEN, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
                curses.init_pair(3, 8, -1)  # dim gray
            cursor = 0
            scroll_offset = 0

            while True:
                stdscr.clear()
                max_y, max_x = stdscr.getmaxyx()

                # Reserve bottom row for status bar when status_fn provided
                footer_rows = 1 if status_fn else 0

                # Header
                try:
                    hattr = curses.A_BOLD
                    if curses.has_colors():
                        hattr |= curses.color_pair(2)
                    stdscr.addnstr(0, 0, title, max_x - 1, hattr)
                    stdscr.addnstr(
                        1, 0,
                        "  ↑↓ navigate  SPACE toggle  ENTER confirm  ESC cancel",
                        max_x - 1, curses.A_DIM,
                    )
                except curses.error:
                    pass

                # Scrollable item list
                visible_rows = max_y - 3 - footer_rows
                if cursor < scroll_offset:
                    scroll_offset = cursor
                elif cursor >= scroll_offset + visible_rows:
                    scroll_offset = cursor - visible_rows + 1

                for draw_i, i in enumerate(
                    range(scroll_offset, min(len(items), scroll_offset + visible_rows))
                ):
                    y = draw_i + 3
                    if y >= max_y - 1 - footer_rows:
                        break
                    check = "[成功]" if i in chosen else " "
                    arrow = "→" if i == cursor else " "
                    line = f" {arrow} [{check}] {items[i]}"
                    attr = curses.A_NORMAL
                    if i == cursor:
                        attr = curses.A_BOLD
                        if curses.has_colors():
                            attr |= curses.color_pair(1)
                    try:
                        stdscr.addnstr(y, 0, line, max_x - 1, attr)
                    except curses.error:
                        pass

                # Status bar (bottom row, right-aligned)
                if status_fn:
                    try:
                        status_text = status_fn(chosen)
                        if status_text:
                            # Right-align on the bottom row
                            sx = max(0, max_x - len(status_text) - 1)
                            sattr = curses.A_DIM
                            if curses.has_colors():
                                sattr |= curses.color_pair(3)
                            stdscr.addnstr(max_y - 1, sx, status_text, max_x - sx - 1, sattr)
                    except curses.error:
                        pass

                stdscr.refresh()
                key = stdscr.getch()

                if key in (curses.KEY_UP, ord("k")):
                    cursor = (cursor - 1) % len(items)
                elif key in (curses.KEY_DOWN, ord("j")):
                    cursor = (cursor + 1) % len(items)
                elif key == ord(" "):
                    chosen.symmetric_difference_update({cursor})
                elif key in (curses.KEY_ENTER, 10, 13):
                    result_holder[0] = set(chosen)
                    return
                elif key in (27, ord("q")):
                    result_holder[0] = cancel_returns
                    return

        curses.wrapper(_draw)
        flush_stdin()
        return result_holder[0] if result_holder[0] is not None else cancel_returns

    except Exception:
        return _numbered_fallback(title, items, selected, cancel_returns, status_fn)


def curses_radiolist(
    title: str,
    items: List[str],
    selected: int = 0,
    *,
    cancel_returns: int | None = None,
    description: str | None = None,
) -> int:
    """Curses single-select radio list. Returns the selected index.

    Args:
        title: Header line displayed above the list.
        items: Display labels for each row.
        selected: Index that starts selected (pre-selected).
        cancel_returns: Returned on ESC/q. Defaults to the original *selected*.
        description: Optional multi-line text shown between the title and
            the item list.  Useful for context that should survive the
            curses screen clear.
    """
    if cancel_returns is None:
        cancel_returns = selected

    if not sys.stdin.isatty():
        return cancel_returns

    if sys.platform == "win32":
        return _win_radiolist(title, items, selected, cancel_returns, description)

    desc_lines: list[str] = []
    if description:
        desc_lines = description.splitlines()

    try:
        import curses
        result_holder: list = [None]

        def _draw(stdscr):
            curses.curs_set(0)
            if curses.has_colors():
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_GREEN, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
            cursor = selected
            scroll_offset = 0

            while True:
                stdscr.clear()
                max_y, max_x = stdscr.getmaxyx()

                row = 0

                # Header
                try:
                    hattr = curses.A_BOLD
                    if curses.has_colors():
                        hattr |= curses.color_pair(2)
                    stdscr.addnstr(row, 0, title, max_x - 1, hattr)
                    row += 1

                    # Description lines
                    for dline in desc_lines:
                        if row >= max_y - 1:
                            break
                        stdscr.addnstr(row, 0, dline, max_x - 1, curses.A_NORMAL)
                        row += 1

                    stdscr.addnstr(
                        row, 0,
                        "  \u2191\u2193 navigate  ENTER/SPACE select  ESC cancel",
                        max_x - 1, curses.A_DIM,
                    )
                    row += 1
                except curses.error:
                    pass

                # Scrollable item list
                items_start = row + 1
                visible_rows = max_y - items_start - 1
                if cursor < scroll_offset:
                    scroll_offset = cursor
                elif cursor >= scroll_offset + visible_rows:
                    scroll_offset = cursor - visible_rows + 1

                for draw_i, i in enumerate(
                    range(scroll_offset, min(len(items), scroll_offset + visible_rows))
                ):
                    y = draw_i + items_start
                    if y >= max_y - 1:
                        break
                    radio = "\u25cf" if i == selected else "\u25cb"
                    arrow = "\u2192" if i == cursor else " "
                    line = f" {arrow} ({radio}) {items[i]}"
                    attr = curses.A_NORMAL
                    if i == cursor:
                        attr = curses.A_BOLD
                        if curses.has_colors():
                            attr |= curses.color_pair(1)
                    try:
                        stdscr.addnstr(y, 0, line, max_x - 1, attr)
                    except curses.error:
                        pass

                stdscr.refresh()
                key = stdscr.getch()

                if key in (curses.KEY_UP, ord("k")):
                    cursor = (cursor - 1) % len(items)
                elif key in (curses.KEY_DOWN, ord("j")):
                    cursor = (cursor + 1) % len(items)
                elif key in (ord(" "), curses.KEY_ENTER, 10, 13):
                    result_holder[0] = cursor
                    return
                elif key in (27, ord("q")):
                    result_holder[0] = cancel_returns
                    return

        curses.wrapper(_draw)
        flush_stdin()
        return result_holder[0] if result_holder[0] is not None else cancel_returns

    except Exception:
        return _radio_numbered_fallback(title, items, selected, cancel_returns)


def _radio_numbered_fallback(
    title: str,
    items: List[str],
    selected: int,
    cancel_returns: int,
) -> int:
    """Text-based numbered fallback for radio selection."""
    print(color(_("\n  {title}").format(title=title), Colors.YELLOW))
    print(color(_("  Select by number, Enter to confirm.\n"), Colors.DIM))

    for i, label in enumerate(items):
        marker = color("(\u25cf)", Colors.GREEN) if i == selected else "(\u25cb)"
        print(f"  {marker} {i + 1:>2}. {label}")
    print()
    try:
        val = input(color(f"  Choice [default {selected + 1}]: ", Colors.DIM)).strip()
        if not val:
            return selected
        idx = int(val) - 1
        if 0 <= idx < len(items):
            return idx
        return selected
    except (ValueError, KeyboardInterrupt, EOFError):
        return cancel_returns


def _win_single_select(
    title: str,
    items: list[str],
    default_index: int = 0,
    cancel_label: str = "Cancel",
) -> int | None:
    """Windows-native single-select using msvcrt + ANSI escape codes.

    Bypasses curses entirely — windows-curses (PDCurses) cannot receive
    arrow keys through ConPTY because ConPTY converts Windows Console
    INPUT_RECORDs into VT sequences that PDCurses does not parse.
    msvcrt.getwch() reads the Win32 input handle directly.

    Output goes to CONOUT$ (not sys.stdout) so prompt_toolkit's stdout
    interception does not turn ANSI escape sequences into literal text.
    """
    import os

    if not items:
        return None

    all_items = list(items) + [cancel_label]
    cancel_idx = len(items)
    cursor = min(default_index, len(all_items) - 1)
    scroll_offset = 0
    R = Colors.RESET
    H = Colors.BOLD + Colors.YELLOW
    S = Colors.BOLD + Colors.GREEN
    D = Colors.DIM

    with _alt_screen_session() as out:
        while True:
            try:
                cols, rows = os.get_terminal_size()
            except OSError:
                cols, rows = 80, 24
            visible = max(rows - 4, 1)

            if cursor < scroll_offset:
                scroll_offset = cursor
            elif cursor >= scroll_offset + visible:
                scroll_offset = cursor - visible + 1

            out.write(_CURSOR_HOME + _CLEAR_SCREEN)
            out.write(f"{H}{title}{R}\n")
            out.write(f"{D}  ↑↓ navigate  ENTER confirm  ESC/q cancel{R}\n\n")

            end = min(len(all_items), scroll_offset + visible)
            for i in range(scroll_offset, end):
                label = _truncate_to_width(all_items[i], max(cols - 5, 1))
                if i == cursor:
                    out.write(f" {S}→ {label}{R}\n")
                else:
                    out.write(f"   {label}\n")

            out.flush()

            key = _win_read_key()
            if key == "UP" or key == "k":
                cursor = (cursor - 1) % len(all_items)
            elif key == "DOWN" or key == "j":
                cursor = (cursor + 1) % len(all_items)
            elif key == "CTRL_C":
                raise KeyboardInterrupt
            elif key == "ENTER":
                break
            elif key == "ESC" or key == "q":
                cursor = cancel_idx
                break

    if cursor >= cancel_idx:
        return None
    return cursor


def curses_single_select(
    title: str,
    items: List[str],
    default_index: int = 0,
    *,
    cancel_label: str = "Cancel",
) -> int | None:
    """Curses single-select menu. Returns selected index or None on cancel.

    Works inside prompt_toolkit because curses.wrapper() restores the terminal
    safely, unlike simple_term_menu which conflicts with /dev/tty.
    """
    if not sys.stdin.isatty():
        return None

    if sys.platform == "win32":
        return _win_single_select(title, items, default_index, cancel_label)

    try:
        import curses
        result_holder: list = [None]

        all_items = list(items) + [cancel_label]
        cancel_idx = len(items)

        def _draw(stdscr):
            curses.curs_set(0)
            if curses.has_colors():
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_GREEN, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
            cursor = min(default_index, len(all_items) - 1)
            scroll_offset = 0

            while True:
                stdscr.clear()
                max_y, max_x = stdscr.getmaxyx()

                try:
                    hattr = curses.A_BOLD
                    if curses.has_colors():
                        hattr |= curses.color_pair(2)
                    stdscr.addnstr(0, 0, title, max_x - 1, hattr)
                    stdscr.addnstr(
                        1, 0,
                        "  ↑↓ navigate  ENTER confirm  ESC/q cancel",
                        max_x - 1, curses.A_DIM,
                    )
                except curses.error:
                    pass

                visible_rows = max_y - 3
                if cursor < scroll_offset:
                    scroll_offset = cursor
                elif cursor >= scroll_offset + visible_rows:
                    scroll_offset = cursor - visible_rows + 1

                for draw_i, i in enumerate(
                    range(scroll_offset, min(len(all_items), scroll_offset + visible_rows))
                ):
                    y = draw_i + 3
                    if y >= max_y - 1:
                        break
                    arrow = "→" if i == cursor else " "
                    line = f" {arrow} {all_items[i]}"
                    attr = curses.A_NORMAL
                    if i == cursor:
                        attr = curses.A_BOLD
                        if curses.has_colors():
                            attr |= curses.color_pair(1)
                    try:
                        stdscr.addnstr(y, 0, line, max_x - 1, attr)
                    except curses.error:
                        pass

                stdscr.refresh()
                key = stdscr.getch()

                if key in (curses.KEY_UP, ord("k")):
                    cursor = (cursor - 1) % len(all_items)
                elif key in (curses.KEY_DOWN, ord("j")):
                    cursor = (cursor + 1) % len(all_items)
                elif key in (curses.KEY_ENTER, 10, 13):
                    result_holder[0] = cursor
                    return
                elif key in (27, ord("q")):
                    result_holder[0] = None
                    return

        curses.wrapper(_draw)
        flush_stdin()
        if result_holder[0] is not None and result_holder[0] >= cancel_idx:
            return None
        return result_holder[0]

    except Exception:
        all_items = list(items) + [cancel_label]
        cancel_idx = len(items)
        return _numbered_single_fallback(title, all_items, cancel_idx)


def _numbered_single_fallback(
    title: str,
    items: List[str],
    cancel_idx: int,
) -> int | None:
    """Text-based numbered fallback for single-select."""
    print(_("\n  {title}\n").format(title=title))
    for i, label in enumerate(items, 1):
        print(f"  {i}. {label}")
    print()
    try:
        val = input(_("  Choice [1-{len}]: ").format(len=len(items))).strip()
        if not val:
            return None
        idx = int(val) - 1
        if 0 <= idx < len(items) and idx < cancel_idx:
            return idx
        if idx == cancel_idx:
            return None
    except (ValueError, KeyboardInterrupt, EOFError):
        pass
    return None


def _numbered_fallback(
    title: str,
    items: List[str],
    selected: Set[int],
    cancel_returns: Set[int],
    status_fn: Optional[Callable[[Set[int]], str]] = None,
) -> Set[int]:
    """Text-based toggle fallback for terminals without curses."""
    chosen = set(selected)
    print(color(_("\n  {title}").format(title=title), Colors.YELLOW))
    print(color(_("  Toggle by number, Enter to confirm.\n"), Colors.DIM))

    while True:
        for i, label in enumerate(items):
            marker = color("[[成功]]", Colors.GREEN) if i in chosen else "[ ]"
            print(f"  {marker} {i + 1:>2}. {label}")
        if status_fn:
            status_text = status_fn(chosen)
            if status_text:
                print(color(_("\n  {status_text}").format(status_text=status_text), Colors.DIM))
        print()
        try:
            val = input(color("  Toggle # (or Enter to confirm): ", Colors.DIM)).strip()
            if not val:
                break
            idx = int(val) - 1
            if 0 <= idx < len(items):
                chosen.symmetric_difference_update({idx})
        except (ValueError, KeyboardInterrupt, EOFError):
            return cancel_returns
        print()

    return chosen
