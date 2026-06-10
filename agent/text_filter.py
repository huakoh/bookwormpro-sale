"""Text filtering utilities shared across the codebase.

Extracted from run_agent.py::_strip_think_blocks and cli.py::_strip_reasoning_tags
(P1-1 deduplication).  Also used by agent/auxiliary_client.py and
gateway/stream_consumer.py.

Ported from openclaw/openclaw#67318.
"""

import re
from typing import Tuple

# Reasoning/thinking tags emitted by reasoning models.
# Must stay in sync with gateway/stream_consumer.py _OPEN_THINK_TAGS / _CLOSE_THINK_TAGS.
_REASONING_TAGS: Tuple[str, ...] = (
    "REASONING_SCRATCHPAD",
    "think",
    "thinking",
    "reasoning",
    "thought",
)

# Tool-call XML tag names that some open models leak into visible content
# instead of emitting via the structured tool_calls field.
_TOOL_CALL_TAGS: Tuple[str, ...] = (
    "tool_call",
    "tool_calls",
    "tool_result",
    "function_call",
    "function_calls",
)


def strip_reasoning_tags(text: str) -> str:
    """Remove reasoning/thinking blocks from content, returning only visible text.

    Handles four cases:

      1. Closed tag pairs (``<think>…</think>``) — the common path when
         the provider emits complete reasoning blocks.
      2. Unterminated open tag at a block boundary (start of text or
         after a newline) — e.g. MiniMax M2.7 / NIM endpoints where the
         closing tag is dropped.  Everything from the open tag to end
         of string is stripped.  The block-boundary check mirrors
         ``gateway/stream_consumer.py``'s filter so models that mention
         ``<think>`` in prose aren't over-stripped.
      3. Stray orphan open/close tags that slip through.
      4. Tag variants: ``<think>``, ``<thinking>``, ``<reasoning>``,
         ``<REASONING_SCRATCHPAD>``, ``<thought>`` (Gemma 4), all
         case-insensitive.

    Additionally strips standalone tool-call XML blocks that some open
    models (notably Gemma variants on OpenRouter) emit inside assistant
    content instead of via the structured ``tool_calls`` field:

      * ``<tool_call>…</tool_call>``
      * ``<tool_calls>…</tool_calls>``
      * ``<tool_result>…</tool_result>``
      * ``<function_call>…</function_call>``
      * ``<function_calls>…</function_calls>``
      * ``<function name="…">…</function>`` (Gemma style)

    The ``<function>`` variant is boundary-gated (only strips when the
    tag sits at start-of-line or after punctuation and carries a
    ``name="..."`` attribute) so prose mentions like "Use <function> in
    JavaScript" are preserved.

    Returns the cleaned string.  Callers are responsible for applying
    ``.strip()`` on the result when whitespace-only results should be
    treated as empty.
    """
    if not text:
        return ""

    cleaned = text

    # 1. Closed tag pairs — case-insensitive for all variants so
    #    mixed-case tags (<THINK>, <Thinking>) don't slip through to
    #    the unterminated-tag pass and take trailing content with them.
    for tag in _REASONING_TAGS:
        cleaned = re.sub(
            rf"<{tag}>.*?</{tag}>\s*",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # 1b. Tool-call XML blocks (openclaw/openclaw#67318).  Handle the
    #     generic tag names first — they have no attribute gating since
    #     a literal <tool_call> in prose is already vanishingly rare.
    for tc_name in _TOOL_CALL_TAGS:
        cleaned = re.sub(
            rf"<{tc_name}\b[^>]*>.*?</{tc_name}>\s*",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # 1c. <function name="...">...</function> — Gemma-style standalone
    #     tool call.  Only strip when the tag sits at a block boundary
    #     (start of text, after a newline, or after sentence-ending
    #     punctuation) AND carries a name="..." attribute.  This keeps
    #     prose mentions like "Use <function> to declare" safe.
    cleaned = re.sub(
        r'(?:(?<=^)|(?<=[\n\r.!?:]))[ \t]*'
        r'<function\b[^>]*\bname\s*=[^>]*>'
        r'(?:(?:(?!</function>).)*)</function>\s*',
        '',
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 2. Unterminated reasoning block — open tag at a block boundary
    #    (start of text, or after a newline) with no matching close.
    #    Strip from the tag to end of string.  Fixes #8878 / #9568
    #    (MiniMax M2.7 leaking raw reasoning into assistant content).
    cleaned = re.sub(
        r'(?:^|\n)[ \t]*<(?:think|thinking|reasoning|thought|REASONING_SCRATCHPAD)\b[^>]*>.*$',
        '',
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 3. Stray orphan open/close tags that slipped through.
    cleaned = re.sub(
        r'</?(?:think|thinking|reasoning|thought|REASONING_SCRATCHPAD)>\s*',
        '',
        cleaned,
        flags=re.IGNORECASE,
    )

    # 3b. Stray tool-call closers.  (We do NOT strip bare <function> or
    #     unterminated <function name="..."> because a truncated tail
    #     during streaming may still be valuable to the user; matches
    #     OpenClaw's intentional asymmetry.)
    cleaned = re.sub(
        r'</(?:tool_call|tool_calls|tool_result|function_call|function_calls|function)>\s*',
        '',
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned
