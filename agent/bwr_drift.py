"""
BWR Route Drift Auto-Correction Module
路由偏移自动纠错系统 — 三层防御:
1. Alias层 (已实现在 skills_tool.py)
2. 反馈学习层 — 用户覆盖/拒绝路由时自动调权
3. 漂移检测层 — 低置信度趋势检测 + 索引自愈

存储: ~/.bookwormpro/bwr-drift.db (SQLite)
"""
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BWR_HOME = Path.home() / ".bookwormpro"
DB_PATH = BWR_HOME / "bwr-drift.db"
INDEX_PATH = BWR_HOME / "skills-index.json"

# ─── Configuration ──────────────────────────────────────────────
DRIFT_WINDOW_HOURS = 24        # 漂移检测窗口
DRIFT_THRESHOLD = 5            # 窗口内 drift 事件阈值 → 触发自愈
LOW_CONFIDENCE_THRESHOLD = 0.5 # 低置信度阈值
FEEDBACK_DECAY_RATE = 0.95     # 反馈权重衰减系数 (每天)
MAX_BOOST = 0.3                # 最大提权幅度
MAX_PENALTY = -0.2             # 最大降权幅度
REBUILD_COOLDOWN_HOURS = 6     # 自愈冷却时间


class BwrDriftCorrector:
    """BWR 路由偏移自动纠错器"""

    _instance: Optional["BwrDriftCorrector"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "BwrDriftCorrector":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._db_lock = threading.Lock()
        self._init_db()
        self._adjustments_cache: Optional[Dict[str, float]] = None
        self._cache_ts: float = 0

    def _init_db(self):
        """初始化 SQLite 存储"""
        BWR_HOME.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS route_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    trace_id TEXT,
                    prompt_hash TEXT,
                    routed_skill TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    is_override INTEGER DEFAULT 0,
                    override_target TEXT,
                    is_drift INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS skill_adjustments (
                    skill_name TEXT PRIMARY KEY,
                    boost REAL DEFAULT 0.0,
                    penalty REAL DEFAULT 0.0,
                    last_positive TEXT,
                    last_negative TEXT,
                    positive_count INTEGER DEFAULT 0,
                    negative_count INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS drift_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    window_hours INTEGER NOT NULL,
                    action_taken TEXT,
                    resolved INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_route_events_ts
                    ON route_events(ts);
                CREATE INDEX IF NOT EXISTS idx_route_events_skill
                    ON route_events(routed_skill);
            """)

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    # ─── 事件记录 ─────────────────────────────────────────────────

    def record_route(
        self,
        routed_skill: str,
        confidence: float,
        trace_id: str = "",
        prompt_hash: str = "",
    ) -> Dict:
        """记录一次路由事件，返回纠错建议"""
        now = datetime.now(timezone.utc).isoformat()
        is_drift = 1 if confidence < LOW_CONFIDENCE_THRESHOLD else 0

        with self._db_lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO route_events 
                       (ts, trace_id, prompt_hash, routed_skill, confidence, is_drift)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (now, trace_id, prompt_hash, routed_skill, confidence, is_drift),
                )

        # 检查是否需要触发漂移告警
        result = {"recorded": True, "drift": bool(is_drift)}
        if is_drift:
            alert = self._check_drift_threshold()
            if alert:
                result["alert"] = alert
        return result

    def record_override(
        self,
        original_skill: str,
        override_target: str,
        confidence: float,
        trace_id: str = "",
    ):
        """记录用户手动覆盖路由（负样本）"""
        now = datetime.now(timezone.utc).isoformat()

        with self._db_lock:
            with self._get_conn() as conn:
                # 记录覆盖事件
                conn.execute(
                    """INSERT INTO route_events
                       (ts, trace_id, routed_skill, confidence, is_override, override_target, is_drift)
                       VALUES (?, ?, ?, ?, 1, ?, 1)""",
                    (now, trace_id, original_skill, confidence, override_target),
                )

                # 对原路由目标降权
                self._apply_penalty(conn, original_skill, now)
                # 对覆盖目标提权
                self._apply_boost(conn, override_target, now)

        # 失效缓存
        self._adjustments_cache = None
        logger.info(
            f"BWR override: {original_skill} → {override_target} "
            f"(confidence was {confidence:.2f})"
        )

    def record_skill_not_found(self, skill_name: str, trace_id: str = ""):
        """记录技能不存在事件（alias 缺失信号）"""
        now = datetime.now(timezone.utc).isoformat()
        with self._db_lock:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO route_events
                       (ts, trace_id, routed_skill, confidence, is_drift)
                       VALUES (?, ?, ?, 0.0, 1)""",
                    (now, trace_id, skill_name),
                )
        logger.warning(f"BWR skill not found: {skill_name} — may need new alias")

    # ─── 反馈学习 ─────────────────────────────────────────────────

    def _apply_penalty(self, conn: sqlite3.Connection, skill: str, ts: str):
        """对技能施加降权"""
        row = conn.execute(
            "SELECT * FROM skill_adjustments WHERE skill_name = ?", (skill,)
        ).fetchone()

        if row:
            new_penalty = max(row["penalty"] - 0.05, MAX_PENALTY)
            new_neg = row["negative_count"] + 1
            conn.execute(
                """UPDATE skill_adjustments 
                   SET penalty = ?, negative_count = ?, last_negative = ?, updated_at = ?
                   WHERE skill_name = ?""",
                (new_penalty, new_neg, ts, ts, skill),
            )
        else:
            conn.execute(
                """INSERT INTO skill_adjustments
                   (skill_name, penalty, negative_count, last_negative, updated_at)
                   VALUES (?, -0.05, 1, ?, ?)""",
                (skill, ts, ts),
            )

    def _apply_boost(self, conn: sqlite3.Connection, skill: str, ts: str):
        """对技能施加提权"""
        row = conn.execute(
            "SELECT * FROM skill_adjustments WHERE skill_name = ?", (skill,)
        ).fetchone()

        if row:
            new_boost = min(row["boost"] + 0.05, MAX_BOOST)
            new_pos = row["positive_count"] + 1
            conn.execute(
                """UPDATE skill_adjustments
                   SET boost = ?, positive_count = ?, last_positive = ?, updated_at = ?
                   WHERE skill_name = ?""",
                (new_boost, new_pos, ts, ts, skill),
            )
        else:
            conn.execute(
                """INSERT INTO skill_adjustments
                   (skill_name, boost, positive_count, last_positive, updated_at)
                   VALUES (?, 0.05, 1, ?, ?)""",
                (skill, ts, ts),
            )

    def get_adjustment(self, skill_name: str) -> float:
        """获取技能的净调权值（用于路由排序时叠加）"""
        adjustments = self._get_all_adjustments()
        return adjustments.get(skill_name, 0.0)

    def _get_all_adjustments(self) -> Dict[str, float]:
        """获取所有技能调权值（带缓存，60s TTL）"""
        now = time.time()
        if self._adjustments_cache is not None and (now - self._cache_ts) < 60:
            return self._adjustments_cache

        result = {}
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT skill_name, boost, penalty FROM skill_adjustments"
            ).fetchall()
            for row in rows:
                net = row["boost"] + row["penalty"]  # penalty is negative
                if abs(net) > 0.01:
                    result[row["skill_name"]] = net

        self._adjustments_cache = result
        self._cache_ts = now
        return result

    def apply_adjustments_to_candidates(
        self, candidates: List[Dict]
    ) -> List[Dict]:
        """将调权值应用到路由候选列表"""
        adjustments = self._get_all_adjustments()
        if not adjustments:
            return candidates

        for candidate in candidates:
            name = candidate.get("name", "")
            adj = adjustments.get(name, 0.0)
            if adj != 0.0:
                candidate["score"] = candidate.get("score", 0.0) + adj
                candidate["_feedbackAdj"] = adj

        # 重排序
        candidates.sort(key=lambda c: c.get("score", 0.0), reverse=True)
        return candidates

    # ─── 漂移检测 ─────────────────────────────────────────────────

    def _check_drift_threshold(self) -> Optional[Dict]:
        """检查是否超过漂移阈值"""
        cutoff = datetime.now(timezone.utc).isoformat()[: -(len("2026-01-01T00:00:00") - 10)]
        # 简单计算: 过去 DRIFT_WINDOW_HOURS 小时内的 drift 事件数
        with self._get_conn() as conn:
            # 使用 SQLite datetime 比较
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM route_events
                   WHERE is_drift = 1
                   AND ts > datetime('now', ?)""",
                (f"-{DRIFT_WINDOW_HOURS} hours",),
            ).fetchone()

            drift_count = row["cnt"] if row else 0

            if drift_count >= DRIFT_THRESHOLD:
                # 检查冷却
                last_alert = conn.execute(
                    """SELECT ts FROM drift_alerts
                       ORDER BY id DESC LIMIT 1"""
                ).fetchone()

                if last_alert:
                    from datetime import timedelta

                    last_ts = datetime.fromisoformat(last_alert["ts"])
                    cooldown = timedelta(hours=REBUILD_COOLDOWN_HOURS)
                    if datetime.now(timezone.utc) - last_ts < cooldown:
                        return None  # 冷却中

                # 触发告警
                action = self._trigger_self_heal(conn, drift_count)
                return {
                    "type": "drift_alert",
                    "drift_count": drift_count,
                    "window_hours": DRIFT_WINDOW_HOURS,
                    "action": action,
                }

        return None

    def _trigger_self_heal(self, conn: sqlite3.Connection, event_count: int) -> str:
        """触发自愈动作"""
        now = datetime.now(timezone.utc).isoformat()
        action = "index_keywords_refresh"

        # 记录告警
        conn.execute(
            """INSERT INTO drift_alerts (ts, event_count, window_hours, action_taken)
               VALUES (?, ?, ?, ?)""",
            (now, event_count, DRIFT_WINDOW_HOURS, action),
        )

        # 分析最常漂移的技能
        frequent_drifts = conn.execute(
            """SELECT routed_skill, COUNT(*) as cnt
               FROM route_events
               WHERE is_drift = 1
               AND ts > datetime('now', ?)
               GROUP BY routed_skill
               ORDER BY cnt DESC
               LIMIT 5""",
            (f"-{DRIFT_WINDOW_HOURS} hours",),
        ).fetchall()

        if frequent_drifts:
            logger.warning(
                f"BWR DRIFT ALERT: {event_count} events in {DRIFT_WINDOW_HOURS}h. "
                f"Top offenders: {[dict(r) for r in frequent_drifts]}"
            )

        return action

    # ─── 权重衰减 (每日调用) ──────────────────────────────────────

    def decay_adjustments(self):
        """每日衰减调权值，防止过拟合"""
        with self._db_lock:
            with self._get_conn() as conn:
                conn.execute(
                    """UPDATE skill_adjustments
                       SET boost = boost * ?,
                           penalty = penalty * ?,
                           updated_at = datetime('now')
                       WHERE ABS(boost) > 0.01 OR ABS(penalty) > 0.01""",
                    (FEEDBACK_DECAY_RATE, FEEDBACK_DECAY_RATE),
                )
                # 清理微小值
                conn.execute(
                    """DELETE FROM skill_adjustments
                       WHERE ABS(boost) < 0.01 AND ABS(penalty) < 0.01"""
                )
        self._adjustments_cache = None
        logger.info("BWR adjustments decayed")

    # ─── 诊断 ─────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """获取路由偏移统计"""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM route_events").fetchone()[0]
            drifts = conn.execute(
                "SELECT COUNT(*) FROM route_events WHERE is_drift = 1"
            ).fetchone()[0]
            overrides = conn.execute(
                "SELECT COUNT(*) FROM route_events WHERE is_override = 1"
            ).fetchone()[0]
            alerts = conn.execute("SELECT COUNT(*) FROM drift_alerts").fetchone()[0]

            recent_drifts = conn.execute(
                """SELECT COUNT(*) FROM route_events
                   WHERE is_drift = 1 AND ts > datetime('now', '-24 hours')"""
            ).fetchone()[0]

            top_adjusted = conn.execute(
                """SELECT skill_name, boost, penalty, 
                          (boost + penalty) as net
                   FROM skill_adjustments
                   ORDER BY ABS(boost + penalty) DESC
                   LIMIT 10"""
            ).fetchall()

            avg_confidence = conn.execute(
                """SELECT AVG(confidence) FROM route_events
                   WHERE ts > datetime('now', '-24 hours')"""
            ).fetchone()[0]

        return {
            "total_events": total,
            "total_drifts": drifts,
            "total_overrides": overrides,
            "total_alerts": alerts,
            "drifts_24h": recent_drifts,
            "avg_confidence_24h": round(avg_confidence, 3) if avg_confidence else None,
            "drift_rate": round(drifts / max(total, 1), 3),
            "top_adjusted": [dict(r) for r in top_adjusted],
        }

    def get_recent_drifts(self, limit: int = 10) -> List[Dict]:
        """获取最近的漂移事件"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT ts, trace_id, routed_skill, confidence, 
                          is_override, override_target
                   FROM route_events
                   WHERE is_drift = 1
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


# ─── Module-level convenience ─────────────────────────────────────
def get_corrector() -> BwrDriftCorrector:
    """获取单例纠错器"""
    return BwrDriftCorrector()
