# -*- coding: utf-8 -*-
"""记忆全文检索 — 对 MEMORY.md / USER.md 建立 FTS5 关键词索引。

设计动机（借鉴 hermes 索引化内存，按架构师建议落地）：
  BookwormPRO 已有三层时序记忆（agent/memory_temporal.py），但那是"层级
  追踪表"，只存 content_hash 不存原文，无法做关键词检索。本模块不改动
  已有系统，纯增量：直接对 memories/MEMORY.md + USER.md 的**条目原文**
  建立 SQLite FTS5 索引，提供 /记忆搜索 <关键词> 能力。

  索引是"派生缓存"——每次搜索前按源文件 mtime 判断是否需要重建，
  源文件才是真实来源（single source of truth），避免双轨一致性问题。

依赖：仅标准库 sqlite3（需 FTS5，Python 3.7+ 默认自带）。
条目分隔符与 memory_tool 保持一致：§（section sign）。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 与 tools/memory_tool.py 的 ENTRY_DELIMITER 保持一致。
_ENTRY_DELIMITER = "§"

# 索引数据库名（放在 memories 目录下，与源文件同级）。
_INDEX_DB_NAME = "memory_search_index.db"


def _memory_dir() -> Path:
    """返回记忆目录（复用 memory_tool 的真实路径解析）。"""
    try:
        from tools.memory_tool import get_memory_dir
        return get_memory_dir()
    except Exception:
        from bwm_constants import get_bookwormpro_home
        return get_bookwormpro_home() / "memories"


def _index_db_path() -> Path:
    return _memory_dir() / _INDEX_DB_NAME


def _source_files() -> List[Path]:
    d = _memory_dir()
    return [d / "MEMORY.md", d / "USER.md"]


def _fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE _fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE _fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


def _parse_entries(path: Path) -> List[str]:
    """把一个 MEMORY.md/USER.md 拆成条目列表（按 § 分隔）。"""
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.debug("读取 %s 失败: %s", path, e)
        return []
    entries = [e.strip() for e in text.split(_ENTRY_DELIMITER)]
    return [e for e in entries if e]


def _newest_source_mtime() -> float:
    mtimes = [p.stat().st_mtime for p in _source_files() if p.exists()]
    return max(mtimes) if mtimes else 0.0


def _needs_rebuild(conn: sqlite3.Connection) -> bool:
    """索引落后于源文件 mtime 时需要重建。"""
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'source_mtime'"
        ).fetchone()
    except sqlite3.OperationalError:
        return True
    if not row:
        return True
    try:
        indexed_mtime = float(row[0])
    except (TypeError, ValueError):
        return True
    return _newest_source_mtime() > indexed_mtime


def _build_index(conn: sqlite3.Connection) -> int:
    """重建 FTS5 索引，返回索引的条目数。"""
    conn.executescript(
        """
        DROP TABLE IF EXISTS entries;
        CREATE VIRTUAL TABLE entries USING fts5(
            source,      -- 'MEMORY' | 'USER'
            content,
            tokenize = 'trigram'
        );
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    count = 0
    for path in _source_files():
        source_label = path.stem.upper()  # MEMORY / USER
        for entry in _parse_entries(path):
            conn.execute(
                "INSERT INTO entries (source, content) VALUES (?, ?)",
                (source_label, entry),
            )
            count += 1
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('source_mtime', ?)",
        (str(_newest_source_mtime()),),
    )
    conn.commit()
    logger.debug("记忆索引重建完成：%d 条", count)
    return count


def _escape_fts_query(query: str) -> str:
    """把用户输入包成 FTS5 安全的短语查询。

    FTS5 对 `-`、`"`、`*`、`:` 等有特殊含义；中文关键词或含特殊字符的
    查询直接当短语处理最稳妥。多个空格分隔的词按 OR 组合以提高召回。
    """
    tokens = [t for t in query.replace('"', " ").split() if t]
    if not tokens:
        return '""'
    # 每个词包成带引号的短语，用 OR 连接（宽召回）。
    return " OR ".join(f'"{t}"' for t in tokens)


def search_memory(query: str, *, limit: int = 10) -> List[Dict[str, Any]]:
    """检索记忆条目，返回按相关度排序的结果列表。

    每项：{"source": "MEMORY"|"USER", "content": str, "rank": float}
    索引不存在或过期时自动重建。FTS5 不可用时降级为纯 Python 子串匹配。
    """
    query = (query or "").strip()
    if not query:
        return []

    db_path = _index_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        if not _fts5_available(conn):
            logger.debug("FTS5 不可用，降级为子串匹配")
            return _fallback_search(query, limit=limit)

        if _needs_rebuild(conn):
            _build_index(conn)

        # trigram 分词器要求匹配串 >= 3 字符；更短的查询用子串匹配更可靠。
        if len(query.strip()) < 3:
            return _fallback_search(query, limit=limit)

        fts_query = _escape_fts_query(query)
        try:
            rows = conn.execute(
                "SELECT source, content, rank FROM entries "
                "WHERE entries MATCH ? ORDER BY rank LIMIT ?",
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError as e:
            logger.debug("FTS 查询失败(%s)，降级子串匹配", e)
            return _fallback_search(query, limit=limit)

        return [
            {"source": r[0], "content": r[1], "rank": r[2]}
            for r in rows
        ]
    finally:
        conn.close()


def _fallback_search(query: str, *, limit: int = 10) -> List[Dict[str, Any]]:
    """FTS5 不可用时的纯 Python 降级：大小写不敏感子串匹配。"""
    q = query.lower()
    results: List[Dict[str, Any]] = []
    for path in _source_files():
        source_label = path.stem.upper()
        for entry in _parse_entries(path):
            if q in entry.lower():
                results.append({"source": source_label, "content": entry, "rank": 0.0})
                if len(results) >= limit:
                    return results
    return results


def format_search_results(query: str, results: List[Dict[str, Any]]) -> str:
    """把搜索结果格式化为终端可读的中文输出。"""
    if not results:
        return f"  未找到与「{query}」相关的记忆。"
    lines = [f"  🔍 记忆检索「{query}」— 命中 {len(results)} 条：", ""]
    for i, r in enumerate(results, 1):
        content = r["content"].replace("\n", " ").strip()
        if len(content) > 160:
            content = content[:160] + "…"
        lines.append(f"  {i}. [{r['source']}] {content}")
    return "\n".join(lines)


__all__ = ["search_memory", "format_search_results"]
