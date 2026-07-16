"""
审计集成模块 — 在 run_agent.py 中引入，即可自动记录所有工具调用事件

Usage (在 run_agent.py 顶部添加):
    from agent.audit_integration import audit_tool_call, audit_session_event

然后在 AIAgent 类的 tool call 处理位置:
    audit_tool_call(self.session_id, function_name, function_args, function_result)

会话开始/结束:
    audit_session_event("session_start", self.session_id, {"platform": self.platform})
    audit_session_event("session_end", self.session_id, {"turns": turn_count})
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_AUDIT_ENABLED = True


def audit_tool_call(
    session_id: Optional[str],
    tool_name: str,
    tool_args: Dict[str, Any],
    result: Any = None,
    *,
    error: Optional[str] = None,
) -> None:
    """记录一次工具调用到审计系统。"""
    if not _AUDIT_ENABLED:
        return
    try:
        from bwm_cli.audit import log_event, AuditEvent
        data = {
            "tool_name": tool_name,
            "args": tool_args,
            "result_preview": str(result)[:200] if result else "",
        }
        if error:
            data["error"] = error
            log_event(AuditEvent.TOOL_CALL, data, session_id=session_id,
                      summary=f"[工具调用错误] {tool_name}: {error[:100]}")
        else:
            log_event(AuditEvent.TOOL_CALL, data, session_id=session_id)
    except Exception:
        pass  # 审计不应影响主流程


def audit_session_event(
    event: str,
    session_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """记录会话事件。"""
    if not _AUDIT_ENABLED:
        return
    try:
        from bwm_cli.audit import log_event, AuditEvent
        etype = AuditEvent.SESSION_START if event == "session_start" else AuditEvent.SESSION_END
        log_event(etype, data or {}, session_id=session_id)
    except Exception:
        pass


def audit_file_modify(path: str, session_id: Optional[str] = None) -> None:
    """记录文件修改。"""
    if not _AUDIT_ENABLED:
        return
    try:
        from bwm_cli.audit import log_event, AuditEvent
        log_event(AuditEvent.FILE_MODIFY, {"path": path}, session_id=session_id)
    except Exception:
        pass


def audit_shell_command(command: str, session_id: Optional[str] = None) -> None:
    """记录 Shell 命令。"""
    if not _AUDIT_ENABLED:
        return
    try:
        from bwm_cli.audit import log_event, AuditEvent
        log_event(AuditEvent.SHELL_COMMAND, {"command": command}, session_id=session_id)
    except Exception:
        pass


def audit_memory_write(target: str, content: str, session_id: Optional[str] = None) -> None:
    """记录记忆写入。"""
    if not _AUDIT_ENABLED:
        return
    try:
        from bwm_cli.audit import log_event, AuditEvent
        log_event(AuditEvent.MEMORY_WRITE, {"target": target, "content": content[:200]},
                  session_id=session_id)
    except Exception:
        pass
