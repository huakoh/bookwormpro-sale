"""Tests for the BookwormPRO-BookwormPRO-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"bookworm"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``bookworm-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "bookworm" tag namespace.

``is_nous_hermes_non_agentic`` should only match the actual BookwormPRO Project
BookwormPRO-3 / BookwormPRO-4 chat family.
"""

from __future__ import annotations

import pytest

from bwm_cli.model_switch import (
    _HERMES_MODEL_WARNING,
    _check_hermes_model_warning,
    is_nous_hermes_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "BookwormPRO/BookwormPRO-3-Llama-3.1-70B",
        "BookwormPRO/BookwormPRO-3-Llama-3.1-405B",
        "bookworm-3",
        "BookwormPRO-3",
        "bookworm-4",
        "bookworm-4-405b",
        "hermes_4_70b",
        "openrouter/hermes3:70b",
        "openrouter/nousresearch/bookworm-4-405b",
        "BookwormPRO/Hermes3",
        "bookworm-3.1",
    ],
)
def test_matches_real_nous_hermes_chat_models(model_name: str) -> None:
    assert is_nous_hermes_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as BookwormPRO BookwormPRO 3/4"
    )
    assert _check_hermes_model_warning(model_name) == _HERMES_MODEL_WARNING


@pytest.mark.parametrize(
    "model_name",
    [
        # Kyle's local Modelfile — qwen3:14b under a custom tag
        "bookworm-brain:qwen3-14b-ctx16k",
        "bookworm-brain:qwen3-14b-ctx32k",
        "bookworm-honcho:qwen3-8b-ctx8k",
        # Plain unrelated models
        "qwen3:14b",
        "qwen3-coder:30b",
        "qwen2.5:14b",
        "claude-opus-4-6",
        "anthropic/claude-sonnet-4.5",
        "gpt-5",
        "openai/gpt-4o",
        "google/gemini-2.5-flash",
        "deepseek-chat",
        # Non-chat BookwormPRO models we don't warn about
        "bookworm-llm-2",
        "hermes2-pro",
        "bookwormpro-bookworm-2-mistral",
        # Edge cases
        "",
        "bookworm",  # bare "bookworm" isn't the 3/4 family
        "bookworm-brain",
        "brain-bookworm-3-impostor",  # "3" not preceded by /: boundary
    ],
)
def test_does_not_match_unrelated_models(model_name: str) -> None:
    assert not is_nous_hermes_non_agentic(model_name), (
        f"expected {model_name!r} NOT to be flagged as BookwormPRO BookwormPRO 3/4"
    )
    assert _check_hermes_model_warning(model_name) == ""


def test_none_like_inputs_are_safe() -> None:
    assert is_nous_hermes_non_agentic("") is False
    # Defensive: the helper shouldn't crash on None-ish falsy input either.
    assert _check_hermes_model_warning("") == ""
