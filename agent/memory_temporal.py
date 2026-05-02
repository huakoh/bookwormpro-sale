"""
三层时序记忆系统 (Three-Layer Temporal Memory System)

在现有 MEMORY.md 文件记忆基础上增加时序维度，实现短期/中期/长期
三层记忆的自动晋升和衰减管理。

三层架构:
  SHORT_TERM  (短期)  0-24 小时   — 最近对话上下文，频繁访问
  MEDIUM_TERM (中期)  24 小时-7 天 — 项目相关、需复习的内容
  LONG_TERM   (长期)  7 天以上     — 核心知识、用户偏好、持久信息

核心功能:
  promote_memories()    — 扫描 MEMORY.md 条目，按时间晋升层级
  decay_check()         — 检查中期记忆是否应晋升为长期
  auto_decide_save()    — 分析对话，自动判断是否值得保存

数据库: ~/.bookwormpro/memory_layers.db

使用方法:
  from agent.memory_temporal import (
      MemoryLayer,
      MemoryLayerManager,
      promote_memories,
      auto_decide_save,
      MEMORY_LAYERS_SYSTEM_PROMPT,
  )

  mgr = MemoryLayerManager()
  mgr.ensure_schema()
  mgr.record_entry("/memory add ...", MemoryLayer.SHORT_TERM)
  promoted = mgr.promote_memories()
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bwm_constants import get_hermes_home
from bwm_cli.i18n import _

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 记忆层级定义
# ---------------------------------------------------------------------------


class MemoryLayer(Enum):
    """三层时序记忆层级。"""
    SHORT_TERM = "short_term"    # 0-24 小时
    MEDIUM_TERM = "medium_term"  # 24 小时 - 7 天
    LONG_TERM = "long_term"      # 7 天以上


# 层级阈值
_SHORT_TERM_MAX_HOURS = 24
_MEDIUM_TERM_MAX_HOURS = 24 * 7  # 168 小时 = 7 天

# 层级中文标签
_LAYER_LABELS: Dict[str, str] = {
    "short_term": "短期记忆",
    "medium_term": "中期记忆",
    "long_term": "长期记忆",
}

_LAYER_EMOJI: Dict[str, str] = {
    "short_term": "[短期]",
    "medium_term": "[中期]",
    "long_term": "[长期]",
}

# 层级排序权重
_LAYER_ORDER: Dict[str, int] = {
    "long_term": 3,
    "medium_term": 2,
    "short_term": 1,
}

# 数据库文件名
_MEMORY_DB_NAME = "memory_layers.db"

# MEMORY.md 文件路径（相对于 BOOKWORMPRO_HOME）
_MEMORY_MD_RELATIVE = "MEMORY.md"

# ---------------------------------------------------------------------------
# 记忆条目解析
# ---------------------------------------------------------------------------

# MEMORY.md 条目格式:
#   ## Category
#   - Key: Value (YYYY-MM-DD)
#   - Key: Value
# 或者:
#   - **Category**: description (YYYY-MM-DD)

_ENTRY_PATTERN = re.compile(
    r"^\s*[-*]\s+(?:\*\*)?([^*:\n]+?)(?:\*\*)?\s*:\s*(.+?)(?:\s*\((\d{4}-\d{2}-\d{2})\))?\s*$",
    re.MULTILINE,
)

_CATEGORY_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _db_path() -> Path:
    """返回记忆层级数据库的完整路径。"""
    return get_hermes_home() / _MEMORY_DB_NAME


def _memory_md_path() -> Path:
    """返回 MEMORY.md 文件的完整路径。"""
    return get_hermes_home() / _MEMORY_MD_RELATIVE


def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """获取 SQLite 连接。"""
    path = db_path or _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ---------------------------------------------------------------------------
# Schema 管理
# ---------------------------------------------------------------------------


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """创建记忆层级追踪表。"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memory_entries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_key       TEXT NOT NULL,
            category        TEXT DEFAULT '',
            content_hash    TEXT NOT NULL,
            layer           TEXT NOT NULL DEFAULT 'short_term',
            created_at      TEXT NOT NULL,
            promoted_at     TEXT,
            last_accessed   TEXT,
            access_count    INTEGER DEFAULT 0,
            source          TEXT DEFAULT 'auto',   -- 'auto', 'manual', 'migration'
            metadata_json   TEXT DEFAULT '{}',
            UNIQUE(entry_key, content_hash)
        );

        CREATE INDEX IF NOT EXISTS idx_memory_entries_layer
            ON memory_entries(layer);

        CREATE INDEX IF NOT EXISTS idx_memory_entries_created
            ON memory_entries(created_at);

        CREATE INDEX IF NOT EXISTS idx_memory_entries_key
            ON memory_entries(entry_key);

        CREATE TABLE IF NOT EXISTS memory_layer_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id        INTEGER,
            from_layer      TEXT,
            to_layer        TEXT,
            reason          TEXT,
            timestamp       TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (entry_id) REFERENCES memory_entries(id)
        );

        CREATE INDEX IF NOT EXISTS idx_memory_layer_log_entry
            ON memory_layer_log(entry_id);
    """)
    conn.commit()


def ensure_schema(db_path: Optional[Path] = None) -> None:
    """公开的 schema 初始化入口。"""
    conn = _get_connection(db_path)
    try:
        _ensure_schema(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# MemoryLayerManager 核心类
# ---------------------------------------------------------------------------


class MemoryLayerManager:
    """三层时序记忆管理器。

    管理 MEMORY.md 条目在三个层级之间的生命周期：
    短期 -> 中期 -> 长期，以及衰减和清理。
    """

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or _db_path()

    # -- Schema ---------------------------------------------------------------

    def ensure_schema(self) -> None:
        """初始化数据库 Schema（幂等）。"""
        conn = _get_connection(self._db_path)
        try:
            _ensure_schema(conn)
        finally:
            conn.close()

    # -- 条目管理 -------------------------------------------------------------

    def record_entry(
        self,
        entry_key: str,
        layer: MemoryLayer = MemoryLayer.SHORT_TERM,
        *,
        category: str = "",
        content_hash: str = "",
        source: str = "auto",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """记录或更新一个记忆条目。

        Args:
            entry_key:    条目唯一键（如 "User:preferred_language"）。
            layer:        初始层级。
            category:     分类标签。
            content_hash: 内容哈希（用于去重检测）。
            source:       来源标记（auto/manual/migration）。
            metadata:     附加元数据。

        Returns:
            插入或更新的行 ID。
        """
        conn = _get_connection(self._db_path)
        try:
            _ensure_schema(conn)

            now = datetime.now(timezone.utc).isoformat()
            meta_json = json.dumps(metadata or {}, ensure_ascii=False, default=str)

            # UPSERT: 如果 entry_key + content_hash 已存在则更新
            conn.execute(
                """INSERT INTO memory_entries
                   (entry_key, category, content_hash, layer, created_at, source, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(entry_key, content_hash) DO UPDATE SET
                       layer = excluded.layer,
                       last_accessed = excluded.created_at,
                       access_count = access_count + 1,
                       metadata_json = excluded.metadata_json""",
                (entry_key, category, content_hash, layer.value, now, source, meta_json),
            )
            conn.commit()

            row = conn.execute(
                "SELECT id, layer FROM memory_entries WHERE entry_key = ? AND content_hash = ?",
                (entry_key, content_hash),
            ).fetchone()

            logger.debug(
                "记忆条目已记录: key=%s layer=%s id=%s", entry_key, layer.value, row["id"]
            )
            return row["id"]
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def promote_memories(self) -> Dict[str, int]:
        """晋升记忆：将到期的短期记忆升为中期，中期记忆升为长期。

        规则:
          - 短期记忆超过 24 小时 -> 中期记忆
          - 中期记忆超过 7 天   -> 长期记忆

        Returns:
            {"short_to_medium": N, "medium_to_long": N} 晋升计数。
        """
        conn = _get_connection(self._db_path)
        try:
            _ensure_schema(conn)

            now = datetime.now(timezone.utc)
            short_cutoff = (now - timedelta(hours=_SHORT_TERM_MAX_HOURS)).isoformat()
            medium_cutoff = (now - timedelta(hours=_MEDIUM_TERM_MAX_HOURS)).isoformat()

            promoted: Dict[str, int] = {"short_to_medium": 0, "medium_to_long": 0}

            # 短期 -> 中期
            short_entries = conn.execute(
                """SELECT id, entry_key FROM memory_entries
                   WHERE layer = 'short_term' AND created_at <= ?""",
                (short_cutoff,),
            ).fetchall()

            for entry in short_entries:
                conn.execute(
                    """UPDATE memory_entries
                       SET layer = 'medium_term', promoted_at = ?
                       WHERE id = ?""",
                    (now.isoformat(), entry["id"]),
                )
                self._log_promotion(conn, entry["id"], "short_term", "medium_term", "超过24小时自动晋升")
                promoted["short_to_medium"] += 1

            # 中期 -> 长期
            medium_entries = conn.execute(
                """SELECT id, entry_key FROM memory_entries
                   WHERE layer = 'medium_term' AND created_at <= ?""",
                (medium_cutoff,),
            ).fetchall()

            for entry in medium_entries:
                conn.execute(
                    """UPDATE memory_entries
                       SET layer = 'long_term', promoted_at = ?
                       WHERE id = ?""",
                    (now.isoformat(), entry["id"]),
                )
                self._log_promotion(conn, entry["id"], "medium_term", "long_term", "超过7天自动晋升")
                promoted["medium_to_long"] += 1

            conn.commit()

            if promoted["short_to_medium"] or promoted["medium_to_long"]:
                logger.info(
                    "记忆晋升完成: 短期->中期 %d, 中期->长期 %d",
                    promoted["short_to_medium"],
                    promoted["medium_to_long"],
                )

            return promoted
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def decay_check(self) -> Dict[str, Any]:
        """衰减检查：评估中期记忆是否应晋升或降级。

        检查逻辑:
          - 中期记忆超过 7 天且访问次数 >= 2 -> 晋升为长期
          - 中期记忆超过 7 天且访问次数 < 2  -> 标记可清理（不自动删除）

        Returns:
            包含 promoted、stale（可清理）、unchanged 计数的字典。
        """
        conn = _get_connection(self._db_path)
        try:
            _ensure_schema(conn)

            now = datetime.now(timezone.utc)
            cutoff = (now - timedelta(hours=_MEDIUM_TERM_MAX_HOURS)).isoformat()

            result: Dict[str, Any] = {
                "promoted": 0,
                "stale": 0,
                "unchanged": 0,
                "stale_entries": [],
            }

            entries = conn.execute(
                """SELECT id, entry_key, access_count FROM memory_entries
                   WHERE layer = 'medium_term' AND created_at <= ?""",
                (cutoff,),
            ).fetchall()

            for entry in entries:
                if entry["access_count"] >= 2:
                    # 有足够访问 -> 晋升
                    conn.execute(
                        """UPDATE memory_entries
                           SET layer = 'long_term', promoted_at = ?
                           WHERE id = ?""",
                        (now.isoformat(), entry["id"]),
                    )
                    self._log_promotion(
                        conn, entry["id"], "medium_term", "long_term",
                        f"衰减检查: 访问次数 {entry['access_count']} >= 2，晋升"
                    )
                    result["promoted"] += 1
                else:
                    # 访问不足 -> 标记为过期
                    conn.execute(
                        """UPDATE memory_entries
                           SET metadata_json = json_set(
                               COALESCE(metadata_json, '{}'),
                               '$.decay_marked_at', ?,
                               '$.decay_reason', 'low_access'
                           )
                           WHERE id = ?""",
                        (now.isoformat(), entry["id"]),
                    )
                    result["stale"] += 1
                    result["stale_entries"].append({
                        "id": entry["id"],
                        "key": entry["entry_key"],
                        "access_count": entry["access_count"],
                    })

            conn.commit()

            if result["promoted"] or result["stale"]:
                logger.info(
                    "衰减检查完成: 晋升 %d, 过期 %d, 未变 %d",
                    result["promoted"],
                    result["stale"],
                    result["unchanged"],
                )

            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_entries_by_layer(
        self,
        layer: Optional[MemoryLayer] = None,
        *,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """按层级查询记忆条目。

        Args:
            layer:    过滤层级（None = 全部）。
            category: 过滤分类。
            limit:    最大返回条数。

        Returns:
            条目字典列表。
        """
        conn = _get_connection(self._db_path)
        try:
            _ensure_schema(conn)

            conditions: List[str] = []
            params: List[Any] = []

            if layer is not None:
                conditions.append("layer = ?")
                params.append(layer.value)

            if category is not None:
                conditions.append("category = ?")
                params.append(category)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            rows = conn.execute(
                f"""SELECT * FROM memory_entries {where_clause}
                    ORDER BY
                      CASE layer
                        WHEN 'long_term' THEN 3
                        WHEN 'medium_term' THEN 2
                        WHEN 'short_term' THEN 1
                      END DESC,
                      last_accessed DESC
                    LIMIT ?""",
                params + [limit],
            ).fetchall()

            entries: List[Dict[str, Any]] = []
            for row in rows:
                entry = dict(row)
                try:
                    entry["metadata"] = json.loads(entry.pop("metadata_json", "{}"))
                except (json.JSONDecodeError, TypeError):
                    entry["metadata"] = {}
                entries.append(entry)

            return entries
        finally:
            conn.close()

    def get_layer_counts(self) -> Dict[str, int]:
        """获取各层级条目计数。"""
        conn = _get_connection(self._db_path)
        try:
            _ensure_schema(conn)
            rows = conn.execute(
                "SELECT layer, COUNT(*) as cnt FROM memory_entries GROUP BY layer"
            ).fetchall()
            return {r["layer"]: r["cnt"] for r in rows}
        finally:
            conn.close()

    def get_promotion_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取晋升日志。"""
        conn = _get_connection(self._db_path)
        try:
            _ensure_schema(conn)
            rows = conn.execute(
                """SELECT mll.*, me.entry_key
                   FROM memory_layer_log mll
                   LEFT JOIN memory_entries me ON mll.entry_id = me.id
                   ORDER BY mll.timestamp DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def sync_from_memory_md(self) -> int:
        """从 MEMORY.md 文件同步条目到数据库。

        解析 MEMORY.md 中的条目并记录到数据库。用于初始化或修复。

        Returns:
            同步的条目数量。
        """
        md_path = _memory_md_path()
        if not md_path.exists():
            logger.debug("MEMORY.md 不存在，跳过同步")
            return 0

        content = md_path.read_text(encoding="utf-8", errors="replace")
        entries = self._parse_memory_md(content)

        synced = 0
        for entry in entries:
            try:
                content_hash = self._hash_content(entry["value"])
                self.record_entry(
                    entry_key=entry["key"],
                    category=entry.get("category", ""),
                    content_hash=content_hash,
                    source="sync",
                    metadata={"raw_value": entry["value"][:200]},
                )
                synced += 1
            except Exception as e:
                logger.warning("同步条目失败: %s (%s)", entry.get("key"), e)

        logger.info("从 MEMORY.md 同步了 %d 条记忆条目", synced)
        return synced

    def build_system_prompt(self) -> str:
        """构建 MEMORY_LAYERS 系统提示块。

        返回包含三层记忆架构说明和当前记忆统计的提示文本。
        """
        counts = self.get_layer_counts()

        lines = [
            "## MEMORY_LAYERS",
            "",
            "你拥有三层时序记忆系统，用于管理不同时效的信息：",
            "",
            "1. **短期记忆 (SHORT_TERM)** — 最近 24 小时内的对话上下文",
            "   - 当前会话中的文件修改、工具调用、用户指令",
            "   - 自动在 24 小时后晋升为中期记忆",
            f"   - 当前条目数: {counts.get('short_term', 0)}",
            "",
            "2. **中期记忆 (MEDIUM_TERM)** — 24 小时到 7 天的信息",
            "   - 项目上下文、正在进行中的任务、临时偏好",
            "   - 访问次数 >= 2 时在 7 天后晋升为长期记忆",
            f"   - 当前条目数: {counts.get('medium_term', 0)}",
            "",
            "3. **长期记忆 (LONG_TERM)** — 超过 7 天的持久信息",
            "   - 用户核心偏好、重要决策、项目关键知识",
            "   - 不会被自动清理，需要手动管理",
            f"   - 当前条目数: {counts.get('long_term', 0)}",
            "",
            "使用建议:",
            "- 新信息先写入短期记忆，由系统自动晋升",
            "- 会话中频繁引用的信息会自动获得更高优先级",
            "- 过期且未被访问的中期记忆会被标记为可清理",
        ]

        return "\n".join(lines)

    # -- 内部方法 -------------------------------------------------------------

    @staticmethod
    def _log_promotion(
        conn: sqlite3.Connection,
        entry_id: int,
        from_layer: str,
        to_layer: str,
        reason: str,
    ) -> None:
        """记录晋升事件到日志表。"""
        conn.execute(
            """INSERT INTO memory_layer_log (entry_id, from_layer, to_layer, reason, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (
                entry_id,
                from_layer,
                to_layer,
                reason,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    @staticmethod
    def _parse_memory_md(content: str) -> List[Dict[str, str]]:
        """解析 MEMORY.md 内容，提取条目。

        Returns:
            条目列表，每项包含 key, value, category, date。
        """
        entries: List[Dict[str, str]] = []
        current_category = ""

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            # 分类标题
            cat_match = _CATEGORY_PATTERN.match(line)
            if cat_match:
                current_category = cat_match.group(1).strip()
                continue

            # 条目
            entry_match = _ENTRY_PATTERN.match(line)
            if entry_match:
                key = entry_match.group(1).strip()
                value = entry_match.group(2).strip()
                date_str = entry_match.group(3) or ""
                entries.append({
                    "key": f"{current_category}:{key}" if current_category else key,
                    "value": value,
                    "category": current_category,
                    "date": date_str,
                })

        return entries

    @staticmethod
    def _hash_content(content: str) -> str:
        """生成内容的简单哈希（用于去重）。"""
        import hashlib
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 模块级便捷函数（向后兼容，推荐使用 MemoryLayerManager）
# ---------------------------------------------------------------------------

_default_manager: Optional[MemoryLayerManager] = None


def _get_manager() -> MemoryLayerManager:
    """获取默认管理器实例（懒加载单例）。"""
    global _default_manager
    if _default_manager is None:
        _default_manager = MemoryLayerManager()
        _default_manager.ensure_schema()
    return _default_manager


def promote_memories() -> Dict[str, int]:
    """晋升记忆（便捷函数）。"""
    return _get_manager().promote_memories()


def decay_check() -> Dict[str, Any]:
    """衰减检查（便捷函数）。"""
    return _get_manager().decay_check()


# ---------------------------------------------------------------------------
# MEMORY_LAYERS 系统提示块（供 MemoryManager 注入）
# ---------------------------------------------------------------------------

MEMORY_LAYERS_SYSTEM_PROMPT = """
## MEMORY_LAYERS

你拥有三层时序记忆系统，用于管理不同时效的信息：

1. **短期记忆 (SHORT_TERM)** — 最近 24 小时内的对话上下文
   - 当前会话中的文件修改、工具调用、用户指令
   - 自动在 24 小时后晋升为中期记忆

2. **中期记忆 (MEDIUM_TERM)** — 24 小时到 7 天的信息
   - 项目上下文、正在进行中的任务、临时偏好
   - 访问次数 >= 2 时在 7 天后晋升为长期记忆

3. **长期记忆 (LONG_TERM)** — 超过 7 天的持久信息
   - 用户核心偏好、重要决策、项目关键知识
   - 不会被自动清理，需要手动管理

使用建议:
- 新信息先写入短期记忆，由系统自动晋升
- 会话中频繁引用的信息会自动获得更高优先级
- 过期且未被访问的中期记忆会被标记为可清理
""".strip()


# ---------------------------------------------------------------------------
# 自动保存决策
# ---------------------------------------------------------------------------

# 触发自动保存的关键词模式
_SAVE_SIGNALS_PATTERNS = [
    # 用户明确偏好
    (re.compile(r"(?:我喜欢|我偏好|我习惯|我常用的|我的.*是)"), "用户偏好"),
    (re.compile(r"(?:记住|记下|保存|别忘了|提醒我)"), "明确记忆指令"),
    # 重要决策
    (re.compile(r"(?:决定|确认|最终方案|就这样|确定使用)"), "重要决策"),
    # 项目关键信息
    (re.compile(r"(?:项目名称|项目路径|仓库地址|API.?[Kk]ey|环境变量)"), "项目关键信息"),
    # 错误和修复
    (re.compile(r"(?:修复了|解决了|问题在于|根本原因是)"), "问题解决经验"),
    # 联系人/身份信息
    (re.compile(r"(?:我的邮箱|我的账号|我的电话|我的 ID)"), "身份信息"),
    # 学习成果
    (re.compile(r"(?:学会了|理解了|终于搞懂|总结一下)"), "学习成果"),
]


def auto_decide_save(
    user_msg: str,
    assistant_response: str,
    *,
    existing_keys: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """分析对话，自动判断是否值得保存到记忆系统。

    检查用户消息和助手回复中是否包含值得长期记忆的内容。

    Args:
        user_msg:           用户消息。
        assistant_response: 助手回复。
        existing_keys:      已有记忆条目键列表（用于去重）。

    Returns:
        如果值得保存，返回包含 key、value、layer、reason 的字典。
        如果不值得保存，返回 None。
    """
    combined = f"{user_msg}\n{assistant_response}"

    existing_set = set(existing_keys or [])

    for pattern, reason in _SAVE_SIGNALS_PATTERNS:
        match = pattern.search(combined)
        if match:
            # 提取关键信息
            snippet = _extract_snippet(combined, match.start(), max_len=200)

            # 生成条目键
            key = _generate_key(user_msg, reason)

            if key in existing_set:
                logger.debug("条目已存在，跳过: %s", key)
                return None

            return {
                "key": key,
                "value": snippet,
                "layer": MemoryLayer.SHORT_TERM,
                "reason": reason,
                "source": "auto_decide",
            }

    return None


def _extract_snippet(text: str, match_pos: int, max_len: int = 200) -> str:
    """从匹配位置提取上下文片段。"""
    start = max(0, match_pos - 20)
    end = min(len(text), match_pos + max_len)

    snippet = text[start:end].strip()

    # 尝试在句子边界处截断
    for sep in (". ", "。", "\n", "! ", "? "):
        idx = snippet.rfind(sep, 0, min(180, len(snippet)))
        if idx > 40:
            snippet = snippet[: idx + len(sep)]
            break

    return snippet


def _generate_key(user_msg: str, reason: str) -> str:
    """生成记忆条目的唯一键。"""
    import hashlib
    content_hash = hashlib.sha256(user_msg.encode("utf-8")).hexdigest()[:8]
    return f"auto:{reason}:{content_hash}"


# ---------------------------------------------------------------------------
# 维护函数
# ---------------------------------------------------------------------------


def run_maintenance() -> Dict[str, Any]:
    """运行完整的记忆维护周期。

    1. 晋升到期的短期记忆
    2. 衰减检查中期记忆
    3. 从 MEMORY.md 同步（如果数据库为空）

    Returns:
        包含各步骤结果的汇总字典。
    """
    manager = _get_manager()

    result: Dict[str, Any] = {}

    # 促销
    result["promotions"] = manager.promote_memories()

    # 衰减
    result["decay"] = manager.decay_check()

    # 如果数据库为空，从 MEMORY.md 同步
    counts = manager.get_layer_counts()
    total = sum(counts.values())
    if total == 0:
        result["sync"] = manager.sync_from_memory_md()
    else:
        result["sync"] = 0

    result["layer_counts"] = counts

    logger.info("记忆维护周期完成: %s", json.dumps(result, default=str))
    return result


# ---------------------------------------------------------------------------
# 自检入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== BookwormPRO 三层时序记忆系统自检 ===\n")

    manager = MemoryLayerManager()
    manager.ensure_schema()
    print("Schema 初始化: 成功")

    # 测试条目记录
    eid1 = manager.record_entry(
        "test:language",
        MemoryLayer.SHORT_TERM,
        category="User",
        content_hash="abc123",
        metadata={"version": 1},
    )
    print(f"记录条目 1: id={eid1}")

    eid2 = manager.record_entry(
        "test:project",
        MemoryLayer.SHORT_TERM,
        category="Project",
        content_hash="def456",
    )
    print(f"记录条目 2: id={eid2}")

    # 层级计数
    counts = manager.get_layer_counts()
    print(f"层级计数: {counts}")

    # 系统提示
    prompt = manager.build_system_prompt()
    print(f"\n系统提示片段:\n{prompt[:300]}...\n")

    # 自动保存决策测试
    decision = auto_decide_save(
        "我喜欢用 Python 做后端开发，记住这个偏好",
        "好的，已记录您的编程语言偏好。",
    )
    print(f"自动保存决策: {decision}")

    # 无保存的场景
    no_decision = auto_decide_save("今天天气不错", "是的，阳光很好。")
    print(f"无保存决策: {no_decision}")

    # 清理测试数据
    conn = _get_connection()
    conn.execute("DELETE FROM memory_entries WHERE entry_key LIKE 'test:%'")
    conn.execute("DELETE FROM memory_layer_log")
    conn.commit()
    conn.close()

    print("\n自检完成。")
