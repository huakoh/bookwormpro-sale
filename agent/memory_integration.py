"""
记忆系统集成 — 将三层时序记忆接入现有 MemoryManager

Usage (在 AIAgent.__init__ 或内存初始化处):
    from agent.memory_integration import TemporalMemoryProvider
    temporal_provider = TemporalMemoryProvider()
    self._memory_manager.add_provider(temporal_provider)

或在 memory_manager.py 构建 system prompt 时注入三层说明:
    from agent.memory_integration import get_temporal_memory_prompt
    prompt_parts.append(get_temporal_memory_prompt())
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_temporal_memory_prompt() -> str:
    """注入三层记忆系统提示到 agent prompt。"""
    try:
        from agent.memory_temporal import MEMORY_LAYERS_SYSTEM_PROMPT
        return MEMORY_LAYERS_SYSTEM_PROMPT
    except ImportError:
        return ""


def auto_record_memory(
    user_msg: str,
    assistant_response: str,
    *,
    existing_keys: Optional[List[str]] = None,
    session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """自动判断并记录值得保存的记忆。"""
    try:
        from agent.memory_temporal import auto_decide_save, MemoryLayerManager, MemoryLayer
        
        result = auto_decide_save(user_msg, assistant_response, existing_keys=existing_keys)
        if result:
            mgr = MemoryLayerManager()
            mgr.record_entry(
                result["key"],
                result.get("layer", MemoryLayer.SHORT_TERM),
                content_hash=result.get("hash", ""),
                source="auto",
                metadata={"session": session_id, "reason": result.get("reason", "")}
            )
            return result
    except Exception as e:
        logger.debug("自动记忆记录失败: %s", e)
    return None


def promote_memories_background() -> Dict[str, int]:
    """后台晋升记忆（可在 session 结束时调用）。"""
    try:
        from agent.memory_temporal import MemoryLayerManager
        mgr = MemoryLayerManager()
        return mgr.promote_memories()
    except Exception as e:
        logger.debug("记忆晋升失败: %s", e)
        return {"short_to_medium": 0, "medium_to_long": 0}
