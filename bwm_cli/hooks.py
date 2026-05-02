"""bookworm hooks — inspect and manage shell-script hooks.

Usage::

    bookworm hooks list
    bookworm hooks test <event> [--for-tool X] [--payload-file F]
    bookworm hooks revoke <command>
    bookworm hooks doctor

Consent records live under ``~/.bookwormpro/shell-hooks-allowlist.json`` and
hook definitions come from the ``hooks:`` block in ``~/.bookwormpro/config.yaml``
(the same config read by the CLI / gateway at startup).

This module is a thin CLI shell over :mod:`agent.shell_hooks`; every
shared concern (payload serialisation, response parsing, allowlist
format) lives there.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from bwm_cli.i18n import _



def hooks_command(args) -> None:
    """Entry point for ``bookworm hooks`` — dispatches to the requested action."""
    sub = getattr(args, "hooks_action", None)

    if not sub:
        print(_("Usage: bookworm hooks {list|test|revoke|doctor}"))
        print(_("Run 'bookworm hooks --help' for details."))
        return

    if sub in ("list", "ls"):
        _cmd_list(args)
    elif sub == "test":
        _cmd_test(args)
    elif sub in ("revoke", "remove", "rm"):
        _cmd_revoke(args)
    elif sub == "doctor":
        _cmd_doctor(args)
    else:
        print(_("Unknown hooks subcommand: {sub}").format(sub=sub))


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def _cmd_list(_args) -> None:
    from bwm_cli.config import load_config
    from agent import shell_hooks

    specs = shell_hooks.iter_configured_hooks(load_config())

    if not specs:
        print(_("No shell hooks configured in ~/.bookwormpro/config.yaml."))
        print(_("See `bookworm hooks --help` or"))
        print(_("    website/docs/user-guide/features/hooks.md"))
        print(_("for the config schema and worked examples."))
        return

    by_event: Dict[str, List] = {}
    for spec in specs:
        by_event.setdefault(spec.event, []).append(spec)

    allowlist = shell_hooks.load_allowlist()
    approved = {
        (e.get("event"), e.get("command"))
        for e in allowlist.get("approvals", [])
        if isinstance(e, dict)
    }

    print(_("Configured shell hooks ({len} total):\n").format(len=len(specs)))

    for event in sorted(by_event.keys()):
        print(f"  [{event}]")
        for spec in by_event[event]:
            is_approved = (spec.event, spec.command) in approved
            status = "[成功] allowed" if is_approved else "[失败] not allowlisted"
            matcher_part = f" matcher={spec.matcher!r}" if spec.matcher else ""
            print(
                f"    - {spec.command}{matcher_part} "
                f"(timeout={spec.timeout}s, {status})"
            )

            if is_approved:
                entry = shell_hooks.allowlist_entry_for(spec.event, spec.command)
                if entry and entry.get("approved_at"):
                    print(_("      approved_at: {entry}").format(entry=entry['approved_at']))
                    mtime_now = shell_hooks.script_mtime_iso(spec.command)
                    mtime_at = entry.get("script_mtime_at_approval")
                    if mtime_now and mtime_at and mtime_now > mtime_at:
                        print(
                            f"      [警告] script modified since approval "
                            f"(was {mtime_at}, now {mtime_now}) — "
                            f"run `bookworm hooks doctor` to re-validate"
                        )
        print()


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------

# Synthetic kwargs matching the real invoke_hook() call sites — these are
# passed verbatim to agent.shell_hooks.run_once(), which routes them through
# the same _serialize_payload() that production firings use.  That way the
# stdin a script sees under `bookworm hooks test` and `bookworm hooks doctor`
# is identical in shape to what it will see at runtime.
_DEFAULT_PAYLOADS = {
    "pre_tool_call": {
        "tool_name": "terminal",
        "args": {"command": "echo hello"},
        "session_id": "test-session",
        "task_id": "test-task",
        "tool_call_id": "test-call",
    },
    "post_tool_call": {
        "tool_name": "terminal",
        "args": {"command": "echo hello"},
        "session_id": "test-session",
        "task_id": "test-task",
        "tool_call_id": "test-call",
        "result": '{"output": "hello"}',
    },
    "pre_llm_call": {
        "session_id": "test-session",
        "user_message": "What is the weather?",
        "conversation_history": [],
        "is_first_turn": True,
        "model": "gpt-4",
        "platform": "cli",
    },
    "post_llm_call": {
        "session_id": "test-session",
        "model": "gpt-4",
        "platform": "cli",
    },
    "on_session_start": {"session_id": "test-session"},
    "on_session_end": {"session_id": "test-session"},
    "on_session_finalize": {"session_id": "test-session"},
    "on_session_reset": {"session_id": "test-session"},
    "pre_api_request": {
        "session_id": "test-session",
        "task_id": "test-task",
        "platform": "cli",
        "model": "claude-sonnet-4-6",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_mode": "anthropic_messages",
        "api_call_count": 1,
        "message_count": 4,
        "tool_count": 12,
        "approx_input_tokens": 2048,
        "request_char_count": 8192,
        "max_tokens": 4096,
    },
    "post_api_request": {
        "session_id": "test-session",
        "task_id": "test-task",
        "platform": "cli",
        "model": "claude-sonnet-4-6",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_mode": "anthropic_messages",
        "api_call_count": 1,
        "api_duration": 1.234,
        "finish_reason": "stop",
        "message_count": 4,
        "response_model": "claude-sonnet-4-6",
        "usage": {"input_tokens": 2048, "output_tokens": 512},
        "assistant_content_chars": 1200,
        "assistant_tool_call_count": 0,
    },
    "subagent_stop": {
        "parent_session_id": "parent-sess",
        "child_role": None,
        "child_summary": "Synthetic summary for hooks test",
        "child_status": "completed",
        "duration_ms": 1234,
    },
}


def _cmd_test(args) -> None:
    from bwm_cli.config import load_config
    from bwm_cli.plugins import VALID_HOOKS
    from agent import shell_hooks

    event = args.event
    if event not in VALID_HOOKS:
        print(_("Unknown event: {event}").format(event=repr(event)))
        print(_("Valid events: {join_events}").format(join_events=', '.join(sorted(VALID_HOOKS))))
        return

    # Synthetic kwargs in the same shape invoke_hook() would pass.  Merged
    # with --for-tool (overrides tool_name) and --payload-file (extra kwargs).
    payload = dict(_DEFAULT_PAYLOADS.get(event, {"session_id": "test-session"}))

    if getattr(args, "for_tool", None):
        payload["tool_name"] = args.for_tool

    if getattr(args, "payload_file", None):
        try:
            custom = json.loads(Path(args.payload_file).read_text())
            if isinstance(custom, dict):
                payload.update(custom)
            else:
                print(_("Warning: {args_payload_file} is not a JSON object; ignoring").format(args_payload_file=args.payload_file))
        except Exception as exc:
            print(_("Error reading payload file: {exc}").format(exc=exc))
            return

    specs = shell_hooks.iter_configured_hooks(load_config())
    specs = [s for s in specs if s.event == event]

    if getattr(args, "for_tool", None):
        specs = [
            s for s in specs
            if s.event not in ("pre_tool_call", "post_tool_call")
            or s.matches_tool(args.for_tool)
        ]

    if not specs:
        print(_("No shell hooks configured for event: {event}").format(event=event))
        if getattr(args, "for_tool", None):
            print(_("(with matcher filter --for-tool={args_for_tool})").format(args_for_tool=args.for_tool))
        return

    print(_("Firing {len} hook(s) for event '{event}':\n").format(len=len(specs), event=event))
    for spec in specs:
        print(f"  → {spec.command}")
        result = shell_hooks.run_once(spec, payload)
        _print_run_result(result)
        print()


def _print_run_result(result: Dict[str, Any]) -> None:
    if result.get("error"):
        print(_("      [失败] error: {result}").format(result=result['error']))
        return
    if result.get("timed_out"):
        print(_("      [失败] timed out after {result}s").format(result=result['elapsed_seconds']))
        return

    rc = result.get("returncode")
    elapsed = result.get("elapsed_seconds", 0)
    print(_("      exit={rc}  elapsed={elapsed}s").format(rc=rc, elapsed=elapsed))

    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    if stdout:
        print(_("      stdout: {_truncate}").format(_truncate=_truncate(stdout, 400)))
    if stderr:
        print(_("      stderr: {_truncate}").format(_truncate=_truncate(stderr, 400)))

    parsed = result.get("parsed")
    if parsed:
        print(_("      parsed (BookwormPRO wire shape): {json}").format(json=json.dumps(parsed)))
    else:
        print(_("      parsed: <none — hook contributed nothing to the dispatcher>"))


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


# ---------------------------------------------------------------------------
# revoke
# ---------------------------------------------------------------------------

def _cmd_revoke(args) -> None:
    from agent import shell_hooks

    removed = shell_hooks.revoke(args.command)
    if removed == 0:
        print(_("No allowlist entry found for command: {args_command}").format(args_command=args.command))
        return
    print(_("Removed {removed} allowlist entry/entries for: {args_command}").format(removed=removed, args_command=args.command))
    print(
        "Note: currently running CLI / gateway processes keep their "
        "already-registered callbacks until they restart."
    )


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

def _cmd_doctor(_args) -> None:
    from bwm_cli.config import load_config
    from agent import shell_hooks

    specs = shell_hooks.iter_configured_hooks(load_config())

    if not specs:
        print(_("No shell hooks configured — nothing to check."))
        return

    print(_("Checking {len} configured shell hook(s)...\n").format(len=len(specs)))

    problems = 0
    for spec in specs:
        print(f"  [{spec.event}] {spec.command}")
        problems += _doctor_one(spec, shell_hooks)
        print()

    if problems:
        print(_("{problems} issue(s) found.  Fix before relying on these hooks.").format(problems=problems))
    else:
        print(_("All shell hooks look healthy."))


def _doctor_one(spec, shell_hooks) -> int:
    problems = 0

    # 1. Script exists and is executable
    if shell_hooks.script_is_executable(spec.command):
        print(_("      [成功] script exists and is executable"))
    else:
        problems += 1
        print(_("      [失败] 脚本缺失或不可执行 (chmod +x 该文件，或修正路径)"))

    # 2. Allowlist status
    entry = shell_hooks.allowlist_entry_for(spec.event, spec.command)
    if entry:
        print(_("      [成功] allowlisted (approved {entry})").format(entry=entry.get('approved_at', '?')))
    else:
        problems += 1
        print(_("      [失败] 未在白名单中 — 运行时不会触发 (使用 --accept-hooks 运行一次，或在终端确认)"))

    # 3. Mtime drift
    if entry and entry.get("script_mtime_at_approval"):
        mtime_now = shell_hooks.script_mtime_iso(spec.command)
        mtime_at = entry["script_mtime_at_approval"]
        if mtime_now and mtime_at and mtime_now > mtime_at:
            problems += 1
            print(_("      [警告] 脚本自审批后已修改 (原: {mtime_at}, 现: {mtime_now}) — 请检查变更，然后 `bookworm hooks revoke` 并重新审批").format(mtime_at=mtime_at, mtime_now=mtime_now))
        elif mtime_now and mtime_at and mtime_now == mtime_at:
            print(_("      [成功] script unchanged since approval"))

    # 4. Produces valid JSON for a synthetic payload — only when the entry
    # is already allowlisted.  Otherwise `bookworm hooks doctor` would execute
    # every script listed in a freshly-pulled config before the user has
    # reviewed them, which directly contradicts the documented workflow
    # ("spot newly-added hooks *before they register*").
    if not entry:
        print(_("      ℹ 跳过 JSON 冒烟测试 — 尚未加入白名单。请先审批 (在终端确认或使用 --accept-hooks)，然后重新运行 `bookworm hooks doctor`。"))
    elif shell_hooks.script_is_executable(spec.command):
        payload = _DEFAULT_PAYLOADS.get(spec.event, {"extra": {}})
        result = shell_hooks.run_once(spec, payload)
        if result.get("timed_out"):
            problems += 1
            print(_("      [失败] 合成负载超时 (已等待: {elapsed}s, 超时设置: {timeout}s)").format(elapsed=result['elapsed_seconds'], timeout=spec.timeout))
        elif result.get("error"):
            problems += 1
            print(_("      [失败] execution error: {result}").format(result=result['error']))
        else:
            rc = result.get("returncode")
            elapsed = result.get("elapsed_seconds", 0)
            stdout = (result.get("stdout") or "").strip()
            if stdout:
                try:
                    json.loads(stdout)
                    print(_("      [成功] 合成负载返回有效 JSON (exit={rc}, {elapsed}s)").format(rc=rc, elapsed=elapsed))
                except json.JSONDecodeError:
                    problems += 1
                    print(_("      [失败] stdout 不是有效 JSON (exit={rc}, {elapsed}s): {output}").format(rc=rc, elapsed=elapsed, output=_truncate(stdout, 120)))
            else:
                print(_("      [成功] 空 stdout 正常退出 (exit={rc}, {elapsed}s) — hook 为纯观察模式").format(rc=rc, elapsed=elapsed))

    return problems
