"""
自动化审计系统 (Automated Audit System for BookwormPRO Agent Operations)

持久化所有关键操作事件到 SQLite + FTS5 全文搜索。
支持：事件日志、查询、统计、导出、90天滚动保留。

Usage:
    bookworm audit show [--since 7d] [--limit 50]
    bookworm audit search <keyword>
    bookworm audit stats [--days 30]
    bookworm audit export [--output audit.jsonl]
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from bwm_constants import get_hermes_home, display_hermes_home
from bwm_cli.i18n import _


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

class AuditEvent(str, Enum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    SHELL_COMMAND = "shell_command"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    MEMORY_WRITE = "memory_write"
    AGENT_ERROR = "agent_error"
    SECURITY_ALERT = "security_alert"
    DELEGATION = "delegation"
    CRON_RUN = "cron_run"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_DB: Optional[sqlite3.Connection] = None
_RETENTION_DAYS = 90


def _get_db_path() -> Path:
    return get_hermes_home() / "audit.db"


def _connect() -> sqlite3.Connection:
    global _DB
    if _DB is not None:
        return _DB
    db_path = _get_db_path()
    _DB = sqlite3.connect(str(db_path))
    _DB.row_factory = sqlite3.Row
    _DB.execute("PRAGMA journal_mode=WAL")
    _DB.execute("PRAGMA synchronous=NORMAL")
    _ensure_schema(_DB)
    return _DB


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            session_id TEXT,
            timestamp TEXT NOT NULL,
            data_json TEXT NOT NULL,
            summary TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events(timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events(session_id)
    """)
    # FTS5 for full-text search
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS audit_fts
            USING fts5(event_type, summary, data_json, content='audit_events', content_rowid='id')
        """)
    except Exception:
        pass  # FTS5 may already exist
    conn.commit()


def log_event(
    event_type: AuditEvent,
    data: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
    summary: Optional[str] = None,
) -> int:
    """记录一条审计事件。返回事件ID。"""
    try:
        conn = _connect()
        ts = datetime.now(timezone.utc).isoformat()
        data_json = json.dumps(data, ensure_ascii=False, default=str)
        if summary is None:
            summary = _auto_summary(event_type, data)
        cur = conn.execute(
            "INSERT INTO audit_events (event_type, session_id, timestamp, data_json, summary) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_type.value, session_id, ts, data_json, summary),
        )
        conn.commit()
        return cur.lastrowid or 0
    except Exception as e:
        logger.debug("审计事件记录失败: %s", e)
        return 0


def _auto_summary(event_type: AuditEvent, data: Dict[str, Any]) -> str:
    if event_type == AuditEvent.TOOL_CALL:
        return f"[工具调用] {data.get('tool_name', '?')}: {str(data.get('args', {}))[:200]}"
    elif event_type == AuditEvent.FILE_MODIFY:
        return f"[文件修改] {data.get('path', '?')}"
    elif event_type == AuditEvent.FILE_DELETE:
        return f"[文件删除] {data.get('path', '?')}"
    elif event_type == AuditEvent.SHELL_COMMAND:
        return f"[Shell] {data.get('command', '?')[:200]}"
    elif event_type == AuditEvent.SESSION_START:
        return f"[会话开始] {data.get('platform', '?')}"
    elif event_type == AuditEvent.SESSION_END:
        return f"[会话结束] {data.get('turns', '?')} turns"
    elif event_type == AuditEvent.MEMORY_WRITE:
        return f"[记忆写入] {data.get('target', '?')}: {data.get('content', '')[:100]}"
    elif event_type == AuditEvent.AGENT_ERROR:
        return f"[错误] {data.get('error', '?')[:200]}"
    elif event_type == AuditEvent.SECURITY_ALERT:
        return f"[安全告警] {data.get('reason', '?')[:200]}"
    elif event_type == AuditEvent.DELEGATION:
        return f"[委托] {data.get('goal', '?')[:200]}"
    elif event_type == AuditEvent.CRON_RUN:
        return f"[定时任务] {data.get('job_name', '?')}"
    return str(data)[:200]


def query_audit(
    since: Optional[str] = None,
    until: Optional[str] = None,
    event_types: Optional[List[str]] = None,
    session_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """查询审计事件。"""
    try:
        conn = _connect()

        if search:
            # FTS5 full-text search
            rows = conn.execute(
                "SELECT ae.* FROM audit_events ae "
                "JOIN audit_fts aft ON ae.id = aft.rowid "
                "WHERE audit_fts MATCH ? "
                "ORDER BY ae.timestamp DESC LIMIT ? OFFSET ?",
                (search, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

        conditions = []
        params: list = []

        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("timestamp <= ?")
            params.append(until)
        if event_types:
            placeholders = ",".join("?" for _ in event_types)
            conditions.append(f"event_type IN ({placeholders})")
            params.extend(event_types)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        rows = conn.execute(
            f"SELECT * FROM audit_events WHERE {where} "
            "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("审计查询失败: %s", e)
        return []


def get_stats(days: int = 30) -> Dict[str, Any]:
    """获取审计统计信息。"""
    try:
        conn = _connect()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        total = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE timestamp >= ?", (since,)
        ).fetchone()[0]

        by_type = {}
        for row in conn.execute(
            "SELECT event_type, COUNT(*) as cnt FROM audit_events "
            "WHERE timestamp >= ? GROUP BY event_type ORDER BY cnt DESC",
            (since,),
        ):
            by_type[row["event_type"]] = row["cnt"]

        db_size = _get_db_path().stat().st_size if _get_db_path().exists() else 0

        return {
            "total_events": total,
            "days": days,
            "by_type": by_type,
            "db_size_bytes": db_size,
            "db_path": str(_get_db_path()),
        }
    except Exception as e:
        return {"error": str(e)}


def cleanup_old_events(retention_days: int = _RETENTION_DAYS) -> int:
    """清理过期审计事件。返回删除数量。"""
    try:
        conn = _connect()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        cur = conn.execute("DELETE FROM audit_events WHERE timestamp < ?", (cutoff,))
        deleted = cur.rowcount
        conn.commit()
        logger.info("审计清理: 删除 %d 条过期事件 (保留 %d 天)", deleted, retention_days)
        return deleted
    except Exception as e:
        logger.warning("审计清理失败: %s", e)
        return 0


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def audit_show(args) -> None:
    """显示最近的审计事件。"""
    since = None
    if getattr(args, "since", None):
        since = _parse_time(args.since)
    limit = getattr(args, "limit", 50) or 50
    etypes = getattr(args, "event_types", None)

    events = query_audit(since=since, event_types=etypes, limit=limit)
    if not events:
        print("\n  " + _("[信息] 暂无审计事件记录") + "\n")
        return

    print(_("\n  === 审计事件 (最近 {len} 条) ===\n").format(len=len(events)))
    for evt in events:
        ts = evt["timestamp"][:19].replace("T", " ")
        etype = evt["event_type"]
        summary = evt["summary"] or ""
        print(f"  [{ts}] {etype:16s} | {summary[:100]}")
    print(_("\n  共 {len} 条记录\n").format(len=len(events)))


def audit_search(args) -> None:
    """全文搜索审计事件。"""
    query = args.query
    events = query_audit(search=query, limit=getattr(args, "limit", 50) or 50)
    if not events:
        print(_("\n  [信息] 未找到匹配 '{query}' 的审计事件\n").format(query=query))
        return

    print(_("\n  === 搜索: '{query}' ({len} 条) ===\n").format(query=query, len=len(events)))
    for evt in events:
        ts = evt["timestamp"][:19].replace("T", " ")
        print(f"  [{ts}] {evt['event_type']:16s} | {evt.get('summary', '')[:120]}")
    print()


def audit_stats(args) -> None:
    """显示审计统计。"""
    days = getattr(args, "days", 30) or 30
    stats = get_stats(days)

    print(_("\n  === 审计统计 ({days}天) ===\n").format(days=days))
    print(_("  总事件数:    {stats:,}").format(stats=stats.get('total_events', 0)))
    print(_("  数据库:      {stats}").format(stats=stats.get('db_path', '?')))
    print(_("  数据库大小:  {stats:.1f} KB").format(stats=stats.get('db_size_bytes', 0) / 1024))
    print()
    by_type = stats.get("by_type", {})
    if by_type:
        print(_("  按类型分布:"))
        for etype, cnt in by_type.items():
            bar = "█" * min(cnt // max(1, max(by_type.values()) // 30), 30)
            print(f"    {etype:20s} {cnt:>6d}  {bar}")
    print()


def audit_export(args) -> None:
    """导出审计事件。"""
    output = getattr(args, "output", None) or "audit-export.jsonl"
    since = _parse_time(getattr(args, "since", "90d")) if getattr(args, "since", None) else None

    events = query_audit(since=since, limit=100000)
    if not events:
        print(_("\n  [信息] 无审计事件可导出\n"))
        return

    outpath = Path(output).expanduser()
    with open(outpath, "w", encoding="utf-8") as f:
        for evt in events:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")

    print(_("\n  [完成] 导出 {len} 条审计事件到 {outpath}\n").format(len=len(events), outpath=outpath))


def audit_cleanup(args) -> None:
    """手动清理过期事件。"""
    days = getattr(args, "days", _RETENTION_DAYS) or _RETENTION_DAYS
    deleted = cleanup_old_events(days)
    print(_("\n  [完成] 清理 {deleted} 条过期事件 (保留 {days} 天)\n").format(deleted=deleted, days=days))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_time(s: str) -> Optional[str]:
    """解析时间字符串如 '7d', '24h', '2026-01-01'。"""
    s = s.strip()
    if s.endswith("d"):
        try:
            days = int(s[:-1])
            dt = datetime.now(timezone.utc) - timedelta(days=days)
            return dt.isoformat()
        except ValueError:
            pass
    if s.endswith("h"):
        try:
            hours = int(s[:-1])
            dt = datetime.now(timezone.utc) - timedelta(hours=hours)
            return dt.isoformat()
        except ValueError:
            pass
    # Try ISO date
    try:
        datetime.fromisoformat(s)
        return s
    except ValueError:
        return None


def setup_audit_hooks() -> None:
    """自动注册审计钩子到 agent 事件系统。
    
    在 agent 初始化完成后调用，会 patch 关键函数添加审计日志。
    """
    logger.info("审计钩子已就绪，等待 agent 初始化后注入")
    # Actual hook injection happens in run_agent.py via audit_log_event wrapper
