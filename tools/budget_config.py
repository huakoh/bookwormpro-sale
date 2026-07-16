"""Configurable budget constants for tool result persistence.

Overridable at the RL environment level via HermesAgentEnvConfig fields.
Per-tool resolution: pinned > config overrides > registry > default.
"""

from dataclasses import dataclass, field
from typing import Dict

# Tools whose thresholds must never be overridden.
# read_file=inf prevents infinite persist->read->persist loops.
PINNED_THRESHOLDS: Dict[str, float] = {
    "read_file": float("inf"),
}

# Defaults matching the current hardcoded values in tool_result_storage.py.
# Kept here as the single source of truth; tool_result_storage.py imports these.
DEFAULT_RESULT_SIZE_CHARS: int = 100_000
DEFAULT_TURN_BUDGET_CHARS: int = 200_000
DEFAULT_PREVIEW_SIZE_CHARS: int = 1_500


@dataclass(frozen=True)
class BudgetConfig:
    """Immutable budget constants for the 3-layer tool result persistence system.

    Layer 2 (per-result): resolve_threshold(tool_name) -> threshold in chars.
    Layer 3 (per-turn):   turn_budget -> aggregate char budget across all tool
                          results in a single assistant turn.
    Preview:              preview_size -> inline snippet size after persistence.
    """

    default_result_size: int = DEFAULT_RESULT_SIZE_CHARS
    turn_budget: int = DEFAULT_TURN_BUDGET_CHARS
    preview_size: int = DEFAULT_PREVIEW_SIZE_CHARS
    tool_overrides: Dict[str, int] = field(default_factory=dict)

    def resolve_threshold(self, tool_name: str) -> int | float:
        """Resolve the persistence threshold for a tool.

        Priority: pinned -> tool_overrides -> registry per-tool -> default.
        """
        if tool_name in PINNED_THRESHOLDS:
            return PINNED_THRESHOLDS[tool_name]
        if tool_name in self.tool_overrides:
            return self.tool_overrides[tool_name]
        from tools.registry import registry
        registry_value = registry.get_max_result_size(tool_name, default=self.default_result_size)
        if registry_value == float("inf"):
            return registry_value
        # 将注册表值限制在 default_result_size 以内，防止小模型下
        # 工具自声明的大阈值突破上下文窗口（防 context flooding）。
        return min(registry_value, self.default_result_size)


# Default config -- matches current hardcoded behavior exactly.
DEFAULT_BUDGET = BudgetConfig()


# Token<->char 换算，用于按模型上下文窗口缩放预算。
# 与估算器一致采用约 4 字符/token 的保守比例。
_CHARS_PER_TOKEN: int = 4

# 单个工具结果 / 整轮工具输出允许占据上下文窗口的比例。
# 系统提示、工具 schema、历史、模型回复都要占窗口，故远低于 1.0。
_PER_RESULT_WINDOW_FRACTION: float = 0.15
_PER_TURN_WINDOW_FRACTION: float = 0.30

# 下限：即使极小模型也保留可用预览/结果，而非 0 字符预算。
_MIN_RESULT_SIZE_CHARS: int = 8_000
_MIN_TURN_BUDGET_CHARS: int = 16_000


def budget_for_context_window(context_length):
    """返回按当前模型上下文窗口缩放后的 BudgetConfig。

    固定默认值（100K结果/200K轮）适用于大模型，但对小模型（如65K token）
    会让单个工具结果接近或超过整个窗口。缩放时大模型保持不变（比例值被
    clamp 到默认值上限），小模型按窗口比例缩小并设下限。
    """
    if not context_length or context_length <= 0:
        return DEFAULT_BUDGET

    window_chars = context_length * _CHARS_PER_TOKEN
    per_result = int(window_chars * _PER_RESULT_WINDOW_FRACTION)
    per_turn = int(window_chars * _PER_TURN_WINDOW_FRACTION)

    per_result = max(_MIN_RESULT_SIZE_CHARS, min(per_result, DEFAULT_RESULT_SIZE_CHARS))
    per_turn = max(_MIN_TURN_BUDGET_CHARS, min(per_turn, DEFAULT_TURN_BUDGET_CHARS))

    return BudgetConfig(
        default_result_size=per_result,
        turn_budget=per_turn,
        preview_size=DEFAULT_PREVIEW_SIZE_CHARS,
    )
