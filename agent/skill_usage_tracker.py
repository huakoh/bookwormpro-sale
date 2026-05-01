"""
技能使用跟踪 — 记录每次技能调用，用于度量分析和冷门检测

Usage:
    from agent.skill_usage_tracker import track_skill_usage
    track_skill_usage("developer-expert", trigger="slash_command")

数据格式 (skill-usage.jsonl):
    {"ts":"2026-05-01T01:00:00","skill":"developer-expert","trigger":"slash","tokens":1200}
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _get_usage_path() -> Path:
    return Path(os.path.expanduser("~/.bookwormpro/skill-usage.jsonl"))


def track_skill_usage(
    skill_name: str,
    *,
    trigger: str = "manual",
    tokens: int = 0,
    session_id: Optional[str] = None,
) -> None:
    """记录技能使用事件。"""
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "skill": skill_name,
            "trigger": trigger,
            "tokens": tokens,
        }
        if session_id:
            entry["session"] = session_id

        path = _get_usage_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug("技能使用记录失败: %s", e)


def get_skill_stats(days: int = 30) -> dict:
    """获取技能使用统计。"""
    path = _get_usage_path()
    if not path.exists():
        return {"total": 0, "top": [], "cold": []}

    cutoff = time.time() - days * 86400
    skill_counts: dict = {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry["ts"]).timestamp()
                    if ts < cutoff:
                        continue
                    skill = entry["skill"]
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception:
        pass

    sorted_skills = sorted(skill_counts.items(), key=lambda x: -x[1])
    return {
        "total": sum(skill_counts.values()),
        "top": sorted_skills[:10],
        "cold": [s for s, c in sorted_skills if c == 0][:10],
        "count": len(skill_counts),
    }
