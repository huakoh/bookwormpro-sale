"""
BWR Hook — 非侵入式路由集成

用法:
    from routing.bwr_hook import BWRHook
    hook = BWRHook()
    routing = hook.route(user_message)
    if routing["recommend"]:
        user_message = routing["directive"] + "\n" + user_message
"""
import json, subprocess
from pathlib import Path

ROUTING_DIR = Path(__file__).parent
BRIDGE_SCRIPT = ROUTING_DIR / "bridge.js"


class BWRHook:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self._cache = {}
        self._ok = None

    def route(self, query, cwd=None):
        if not self.enabled:
            return self._fallback()
        key = query[:100].strip().lower()
        if key in self._cache:
            return self._cache[key]
        if self._ok is None:
            self._ok = BRIDGE_SCRIPT.exists()
        if not self._ok:
            return self._fallback()
        result = self._call(query, cwd)
        if len(self._cache) >= 100:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = result
        return result

    def _call(self, query, cwd=None):
        payload = {"query": query}
        if cwd:
            payload["cwd"] = str(cwd)
        try:
            proc = subprocess.run(
                ["node", str(BRIDGE_SCRIPT)],
                input=json.dumps(payload), capture_output=True, text=True,
                timeout=10, cwd=str(ROUTING_DIR))
            if proc.returncode != 0:
                return self._fallback()
            data = json.loads(proc.stdout)
            r = data.get("routing", {})
            c = r.get("confidence", 0)
            p = r.get("primary", "")
            return {
                **data,
                "recommend": c >= 0.5 and p not in ("developer-expert", "none", ""),
                "must_invoke": data.get("intent", {}).get("complexity") == "complex",
                "recommendation": "route" if c >= 0.8 else ("recommend" if c >= 0.5 else "fallback"),
            }
        except Exception:
            return self._fallback()

    def _fallback(self):
        return {"recommend": False, "must_invoke": False, "recommendation": "fallback", "elapsed_ms": 0}

    def inject_directive(self, user_message, cwd=None):
        r = self.route(user_message, cwd)
        if r.get("recommend") or r.get("must_invoke"):
            d = r.get("directive", "")
            if d:
                return d + "\n" + user_message
        return user_message

    def report_actual(self, query: str, actual_skill: str):
        """Agent 调用 Skill 后回填实际结果，供反馈闭环学习"""
        try:
            from routing.bwr_reporter import report_skill_usage
            last = self._cache.get(query[:100].strip().lower(), {})
            predicted = last.get('routing', {}).get('primary')
            confidence = last.get('routing', {}).get('confidence')
            report_skill_usage(query, actual_skill, predicted, confidence)
        except Exception:
            pass

    def flush_cache(self):
        self._cache.clear()
