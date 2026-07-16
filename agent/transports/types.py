"""Shared types for normalized provider responses.

Pydantic models defining the canonical shape that all provider adapters
normalize responses to.  The shared surface is intentionally minimal —
only fields that every downstream consumer reads are top-level.
Protocol-specific state goes in ``provider_data`` dicts (response-level
and per-tool-call) so that protocol-aware code paths can access it
without polluting the shared type.

Migrated from dataclasses to Pydantic v2 BaseModel for runtime validation.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Canonical finish_reason values used across all transports.
VALID_FINISH_REASONS = frozenset({
    "stop", "tool_calls", "length", "content_filter",
})


class ToolCall(BaseModel):
    """A normalized tool call from any provider.

    ``id`` is the protocol's canonical identifier — what gets used in
    ``tool_call_id`` / ``tool_use_id`` when constructing tool result
    messages.  May be ``None`` when the provider omits it; the agent
    fills it via ``_deterministic_call_id()`` before storing in history.

    ``provider_data`` carries per-tool-call protocol metadata that only
    protocol-aware code reads:

    * Codex: ``{"call_id": "call_XXX", "response_item_id": "fc_XXX"}``
    * Gemini: ``{"extra_content": {"google": {"thought_signature": "..."}}}``
    * Others: ``None``
    """

    model_config = ConfigDict(frozen=False, populate_by_name=True)

    id: Optional[str] = None
    name: str
    arguments: str = "{}"
    provider_data: Optional[Dict[str, Any]] = Field(default=None, repr=False)

    @field_validator("name")
    @classmethod
    def _name_must_be_nonempty(cls, v: str) -> str:
        if not v.strip():
            logger.warning("ToolCall created with empty name — defaulting to 'unknown'")
            return "unknown"
        return v

    @field_validator("arguments", mode="before")
    @classmethod
    def _coerce_and_validate_arguments(cls, v: Any) -> str:
        if isinstance(v, (dict, list)):
            return json.dumps(v)
        if not isinstance(v, str):
            return "{}"
        if not v.strip():
            return "{}"
        try:
            json.loads(v)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning(
                "ToolCall arguments failed JSON parse (len=%d) — keeping raw for downstream repair",
                len(v),
            )
        return v

    # ── Backward compatibility ──────────────────────────────────
    # The agent loop reads tc.function.name / tc.function.arguments
    # throughout run_agent.py (45+ sites).
    @property
    def type(self) -> str:
        return "function"

    @property
    def function(self) -> "ToolCall":
        """Return self so tc.function.name / tc.function.arguments work."""
        return self

    @property
    def call_id(self) -> Optional[str]:
        """Codex call_id from provider_data."""
        return (self.provider_data or {}).get("call_id")

    @property
    def response_item_id(self) -> Optional[str]:
        """Codex response_item_id from provider_data."""
        return (self.provider_data or {}).get("response_item_id")

    @property
    def extra_content(self) -> Optional[Dict[str, Any]]:
        """Gemini extra_content (thought_signature) from provider_data."""
        return (self.provider_data or {}).get("extra_content")


class Usage(BaseModel):
    """Token usage from an API response."""

    model_config = ConfigDict(frozen=False)

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

    @field_validator("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens")
    @classmethod
    def _tokens_non_negative(cls, v: int) -> int:
        return max(0, v) if isinstance(v, int) else 0


class NormalizedResponse(BaseModel):
    """Normalized API response from any provider.

    Shared fields are truly cross-provider — every caller can rely on
    them without branching on api_mode.  Protocol-specific state goes in
    ``provider_data`` so that only protocol-aware code paths read it.

    Response-level ``provider_data`` examples:

    * Anthropic: ``{"reasoning_details": [...]}``
    * Codex: ``{"codex_reasoning_items": [...]}``
    * Others: ``None``
    """

    model_config = ConfigDict(frozen=False)

    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: str = "stop"
    reasoning: Optional[str] = None
    usage: Optional[Usage] = None
    provider_data: Optional[Dict[str, Any]] = Field(default=None, repr=False)

    @field_validator("finish_reason")
    @classmethod
    def _normalize_finish_reason(cls, v: str) -> str:
        if v in VALID_FINISH_REASONS:
            return v
        logger.debug("Unknown finish_reason '%s' — normalizing to 'stop'", v)
        return "stop"

    # ── Backward compatibility ──────────────────────────────────
    @property
    def reasoning_content(self) -> Optional[str]:
        pd = self.provider_data or {}
        return pd.get("reasoning_content")

    @property
    def reasoning_details(self):
        pd = self.provider_data or {}
        return pd.get("reasoning_details")

    @property
    def codex_reasoning_items(self):
        pd = self.provider_data or {}
        return pd.get("codex_reasoning_items")


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def build_tool_call(
    id: Optional[str],
    name: str,
    arguments: Any,
    **provider_fields: Any,
) -> ToolCall:
    """Build a ``ToolCall``, auto-serialising *arguments* if it's a dict.

    Any extra keyword arguments are collected into ``provider_data``.
    """
    args_str = json.dumps(arguments) if isinstance(arguments, dict) else str(arguments)
    pd = dict(provider_fields) if provider_fields else None
    return ToolCall(id=id, name=name, arguments=args_str, provider_data=pd)


def map_finish_reason(reason: Optional[str], mapping: Dict[str, str]) -> str:
    """Translate a provider-specific stop reason to the normalised set.

    Falls back to ``"stop"`` for unknown or ``None`` reasons.
    """
    if reason is None:
        return "stop"
    return mapping.get(reason, "stop")
