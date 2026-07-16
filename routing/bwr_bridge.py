"""
BWR Bridge — Python → Node.js BWR 路由引擎调用

将用户查询传给 BookwormPRO/routing/ 中的 Node.js 引擎，
获取意图分类 + 技能路由结果，供 Agent 使用。
"""
import subprocess
import json
import os
from pathlib import Path

ROUTING_DIR = Path(__file__).parent  # BookwormPRO/routing/
BRIDGE_SCRIPT = ROUTING_DIR / "bridge.js"
ENGINE_SCRIPT = ROUTING_DIR / "route-engine.js"


def _ensure_bridge():
    """确保 bridge.js 存在"""
    if not BRIDGE_SCRIPT.exists():
        raise FileNotFoundError(f"BWR bridge not found: {BRIDGE_SCRIPT}")


def route_query(query: str, cwd: str = None) -> dict:
    """
    调用 BWR 路由引擎，返回路由结果。

    Args:
        query: 用户输入的查询文本
        cwd: 当前工作目录（可选，用于上下文检测）

    Returns:
        {
            "intent": {"intents": [...], "complexity": "simple|medium|complex"},
            "routing": {
                "primary": "skill-name",
                "confidence": 0.0-1.0,
                "candidates": [{"name": "...", "confidence": 0.0}, ...],
                "chain": [...]
            },
            "directive": "[BWR:xxx] ...",
            "recommendation": "route|recommend|fallback",
            "elapsed_ms": 123
        }
    """
    _ensure_bridge()

    payload = {"query": query}
    if cwd:
        payload["cwd"] = str(cwd)

    try:
        result = subprocess.run(
            ["node", str(BRIDGE_SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(ROUTING_DIR),
        )

        if result.returncode != 0:
            return _fallback_result(f"BWR exit code {result.returncode}: {result.stderr[:200]}")

        return json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        return _fallback_result("BWR timeout (>10s)")
    except FileNotFoundError:
        return _fallback_result("Node.js not found")
    except json.JSONDecodeError as e:
        return _fallback_result(f"BWR JSON parse error: {e}")
    except Exception as e:
        return _fallback_result(f"BWR error: {e}")


def _fallback_result(reason: str) -> dict:
    """BWR 不可用时的降级结果"""
    return {
        "intent": {"intents": ["general"], "complexity": "medium"},
        "routing": {
            "primary": "developer-expert",
            "confidence": 0.0,
            "candidates": [],
            "chain": [],
        },
        "directive": f"[BWR:fallback] {reason}",
        "recommendation": "fallback",
        "elapsed_ms": 0,
        "error": reason,
    }


def get_recommended_skill(query: str) -> str | None:
    """
    简要接口：返回推荐技能名，或 None（无需路由）。
    用于 prompt builder 快速调用。
    """
    result = route_query(query)
    routing = result.get("routing", {})
    confidence = routing.get("confidence", 0)

    # 高置信度 (>0.5) 且非 fallback → 推荐使用
    if confidence >= 0.5 and routing.get("primary") not in ("developer-expert", "none", None):
        return routing["primary"]

    return None
