"""Phantom-refusal detection and override.

Even with NATIVE_HOST_ENVIRONMENT_HINT and HOST_BRIDGE_ENVIRONMENT_HINT in
the system prompt, the trained refusal behavior of large models occasionally
still leaks through, producing replies like:

    "I can only operate server-side files, not your local Mac/Windows files."
    "运行在服务器端的沙箱环境中，无法访问你本地电脑的文件系统。"

These are *phantom* refusals — the runtime has no sandbox, the agent has
full filesystem access via its tools, and the user explicitly asked for the
operation. This module detects such replies and gives the chat loop a
single-shot opportunity to retry with an explicit override nudge.

Detection is intentionally conservative: it fires only when
  (a) the runtime advertises full FS access (native install or host bridge),
  (b) the reply matches at least one bilingual refusal pattern, AND
  (c) the reply is short enough to plausibly be a refusal (not a substantive
      reply that happens to mention sandboxes in a code example).

This module has no I/O side effects and no agent dependencies — pure
string + env logic. Callable from the public chat() entry point.
"""

from __future__ import annotations

import logging
import re

from bwm_constants import is_host_bridge_active, is_native_install

logger = logging.getLogger(__name__)


# English + Chinese phantom-refusal markers. Patterns are deliberately broad
# enough to catch paraphrases without matching legitimate technical
# discussions (which tend to be longer than the length cap below).
_PHANTOM_REFUSAL_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        # English
        r"server[-\s]?side sandbox",
        r"agent runs in a (?:server[-\s]?side )?sandbox",
        r"cannot access (?:the |your |user'?s )?local (?:filesystem|files?|desktop|machine)",
        r"can(?:not|'t) (?:read|write|delete|move|access) (?:files? )?on (?:your|the user'?s) (?:local )?(?:machine|computer|desktop|mac|windows|laptop)",
        r"(?:I |we )?(?:run|am running|am operating) in (?:an? )?(?:isolated|sandbox(?:ed)?|server[-\s]?side|virtual) (?:environment|sandbox)",
        r"no (?:direct )?access to (?:your |the user'?s )?(?:local )?(?:filesystem|desktop|machine)",
        r"don'?t have (?:permission|access|the ability) to (?:read|write|delete|move|access) (?:files? )?(?:on |from )?(?:your|the user'?s)",
        # Chinese
        r"运行在(?:服务器端|沙[箱盒])",
        r"无法(?:访问|读取|写入|删除|操作)(?:你的?|您的?)?(?:本地|桌面|本机|本地电脑|你的电脑)",
        r"我(?:运行|跑)在(?:服务器端|沙[箱盒]|隔离)",
        r"(?:服务器|远程)端的沙[箱盒]",
    )
]

# Phantom refusals are characteristically short, terminal-style replies.
# Don't intercept long technical discussions that incidentally mention
# sandboxes (e.g. when answering questions ABOUT sandboxes).
_MAX_REFUSAL_LENGTH = 1200

# The nudge re-issued to the model when a phantom refusal is detected.
# Phrased as a follow-up user turn so the model treats it as authoritative
# correction rather than a system instruction it might dismiss.
PHANTOM_REFUSAL_OVERRIDE_NUDGE = (
    "Your previous reply refused the request by claiming a sandbox / "
    "filesystem restriction that does not exist in this runtime. "
    "Facts: there is no sandbox, you are running natively on the user's "
    "machine (or with an explicit host bridge mounted), and your tools "
    "have full read/write/delete access to host paths. Perform the user's "
    "original request now using your real file and terminal tools. "
    "If a specific OS-level error occurs (permission denied, file not "
    "found), report that exact error — do not invent a sandbox restriction."
)


def is_phantom_refusal(text: str | None) -> bool:
    """Return True when *text* looks like a trained-but-incorrect refusal.

    Only fires when the runtime actually has filesystem access (native
    install or host-bridge mount). In a real sandbox a refusal is
    legitimate and must not be intercepted.
    """
    if not text:
        return False
    if len(text) > _MAX_REFUSAL_LENGTH:
        return False
    if not (is_native_install() or is_host_bridge_active()):
        return False
    return any(p.search(text) for p in _PHANTOM_REFUSAL_PATTERNS)


def maybe_intercept(
    final_response: str | None,
    *,
    retry_callback,
    log_event=None,
) -> str | None:
    """If *final_response* is a phantom refusal, retry once via *retry_callback*.

    Args:
        final_response: The model's reply text.
        retry_callback: Zero-arg callable that re-runs the conversation with
            ``PHANTOM_REFUSAL_OVERRIDE_NUDGE`` appended as a follow-up user
            turn. Must return the new final response string.
        log_event: Optional callable for telemetry (e.g. metrics counter).

    Returns:
        The original response if no interception, or the retried response.
        Never raises — failures fall back to the original response.
    """
    if not is_phantom_refusal(final_response):
        return final_response

    logger.info(
        "Phantom refusal detected (len=%d); requesting one-shot override",
        len(final_response or ""),
    )
    if log_event is not None:
        try:
            log_event("phantom_refusal_intercepted")
        except Exception:
            pass

    try:
        retried = retry_callback()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Phantom-refusal retry failed: %s", exc)
        return final_response

    # If the retry ALSO comes back as a phantom refusal, give up — don't
    # loop. Return the retried text so the user at least sees the most
    # recent attempt rather than the original.
    if is_phantom_refusal(retried):
        logger.info("Retry still produced a phantom refusal; giving up")
        return retried or final_response
    return retried or final_response
