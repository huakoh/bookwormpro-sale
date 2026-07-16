"""
BWR Feedback Reporter — 从 Agent 回填实际使用的 Skill

用法: 在 Agent 调用 Skill 后调用 report()

    from routing.bwr_reporter import report_skill_usage
    report_skill_usage(user_query, actual_skill_name)
"""
import json, os, time
from pathlib import Path

FEEDBACK_FILE = Path.home() / '.bookwormpro' / 'debug' / 'route-feedback-live.jsonl'


def report_skill_usage(query: str, actual_skill: str, predicted_skill: str = None, confidence: float = None):
    """Agent 调用 Skill 后回填实际使用的技能名"""
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "query": (query or "")[:200],
        "actualSkill": actual_skill,
    }
    if predicted_skill:
        entry["predictedSkill"] = predicted_skill
    if confidence is not None:
        entry["confidence"] = confidence
    if predicted_skill and predicted_skill != actual_skill:
        entry["mismatch"] = True

    try:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass  # fail silently — feedback is non-critical


def get_feedback_stats():
    """读取反馈统计"""
    if not FEEDBACK_FILE.exists():
        return {"total": 0, "mismatches": 0, "accuracy": None}
    
    total = 0
    mismatches = 0
    with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                e = json.loads(line)
                total += 1
                if e.get('mismatch'):
                    mismatches += 1
            except Exception:
                pass
    
    return {
        "total": total,
        "mismatches": mismatches,
        "accuracy": (total - mismatches) / total if total > 0 else None
    }
