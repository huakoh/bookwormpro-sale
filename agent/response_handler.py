"""
response_handler.py — Response formatting utilities extracted from run_agent.py.

Part of P2-1 Phase 2 — ResponseHandler extraction (2026-05-06).

Functions extracted:
    strip_think_blocks(content)      — Remove reasoning/thinking XML blocks
    has_natural_response_ending(content) — Heuristic: does text look finished?
    clean_error_message(error_msg)   — Clean up API error messages for display

All functions are pure (no AIAgent state dependency), suitable for import
and use from any context.
"""

from __future__ import annotations

import re
from typing import Dict, Any


# ── Think block stripping ─────────────────────────────────────────

_THINK_TAG_PATTERNS = [
    r"<think>.*?</think>",
    r"<thinking>.*?</thinking>",
    r"<reasoning>.*?</reasoning>",
    r"<REASONING_SCRATCHPAD>.*?</REASONING_SCRATCHPAD>",
    r"<thought>.*?</thought>",
]

_TOOL_CALL_TAG_NAMES = (
    "tool_call", "tool_calls", "tool_result",
    "function_call", "function_calls",
    # 影子模型(如 fable)偶发把工具调用文本化为 <invoke>/<parameter> XML 泄漏到正文，一并剥离
    "invoke", "antml:invoke", "parameter", "antml:parameter",
)

_ORPHAN_TAG_RE = re.compile(
    r"</?(?:think|thinking|reasoning|thought|REASONING_SCRATCHPAD)>\s*",
    re.IGNORECASE,
)

_ORPHAN_TOOL_CLOSE_RE = re.compile(
    r"</(?:(?:antml:)?invoke|(?:antml:)?parameter|tool_call|tool_calls|tool_result|function_call|function_calls|function)>\s*",
    re.IGNORECASE,
)


def strip_think_blocks(content: str) -> str:
    """Remove reasoning/thinking blocks from content, returning only visible text."""
    if not content:
        return ""

    # 1. Closed tag pairs
    for pattern in _THINK_TAG_PATTERNS:
        content = re.sub(pattern, "", content, flags=re.DOTALL | re.IGNORECASE)

    # 1b. Tool-call XML blocks
    for tc_name in _TOOL_CALL_TAG_NAMES:
        content = re.sub(
            rf"<{tc_name}\b[^>]*>.*?</{tc_name}>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # 1c. function name="..." — Gemma style, boundary-gated
    content = re.sub(
        r"(?:(?<=^)|(?<=[\n\r.!?:]))[ \t]*"
        r"<function\b[^>]*\bname\s*=[^>]*>"
        r"(?:(?:(?!</function>).)*)</function>",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 2. Unterminated reasoning block at block boundary
    content = re.sub(
        r"(?:^|\n)[ \t]*<(?:think|thinking|reasoning|thought|REASONING_SCRATCHPAD)\b[^>]*>.*$",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 3. Stray orphan open/close tags
    content = _ORPHAN_TAG_RE.sub("", content)

    # 3b. Stray tool-call closers
    content = _ORPHAN_TOOL_CLOSE_RE.sub("", content)

    return content


# ── Natural response ending heuristic ──────────────────────────────

_NATURAL_END_CHARS = set(".!?:)\"'\\]'}。！？：）】」』》```")


def has_natural_response_ending(content: str) -> bool:
    """Heuristic: does visible assistant text look intentionally finished?"""
    if not content:
        return False
    stripped = content.rstrip()
    if not stripped:
        return False
    if stripped.endswith("```"):
        return True
    return stripped[-1] in _NATURAL_END_CHARS


# ── Error message cleaning ─────────────────────────────────────────

def clean_error_message(error_msg: str) -> str:
    """Clean up error messages for user display."""
    if not error_msg:
        return "Unknown error"

    if error_msg.strip().startswith("<!DOCTYPE html") or "<html" in error_msg:
        return "Service temporarily unavailable (HTML error page returned)"

    cleaned = " ".join(error_msg.split())

    if len(cleaned) > 150:
        cleaned = cleaned[:150] + "..."

    return cleaned
