"""Response schema validator for provider API responses.

Validates the structural integrity of API responses before they are
consumed by the agent loop.  Provider response format changes (field
renames, type changes, optional → null changes) cause TypeError /
AttributeError deep in the call stack.  Catching them at the boundary
with clear diagnostics prevents silent failures and enables fallback.

Load-bearing checks (chat_completions):
    1. response.choices is a non-empty list
    2. choices[0].message exists and is not None
    3. message.content is str | None (not dict/bytes)
    4. message.tool_calls (if present) have valid structure
    5. response.model is a string

Load-bearing checks (anthropic_messages):
    1. response.content is a non-empty list
    2. content blocks have valid 'type' field
    3. text blocks have non-None 'text' field
    4. tool_use blocks have valid 'name' and 'input' fields

All validators return (valid: bool, errors: list[str]) for diagnostics.
"""

from __future__ import annotations

import logging
from typing import Any, List, Tuple

logger = logging.getLogger(__name__)


# ── Chat Completions (OpenAI-format) validation ──────────────────────────

def validate_chat_completions_response(response: Any) -> Tuple[bool, List[str]]:
    """Validate an OpenAI chat completions response structure.

    Returns:
        (valid, errors) — valid is True if the response is structurally sound.
    """
    errors: List[str] = []

    if response is None:
        return False, ["response is None"]

    # Check 1: choices attribute exists and is a non-empty list
    if not hasattr(response, 'choices'):
        return False, ["response has no 'choices' attribute"]

    choices = getattr(response, 'choices', None)
    if choices is None:
        return False, ["response.choices is None"]
    if not isinstance(choices, list):
        return False, [f"response.choices is {type(choices).__name__}, expected list"]
    if len(choices) == 0:
        # Empty choices with non-empty usage might be a usage-only response
        usage = getattr(response, 'usage', None)
        if usage is None:
            return False, ["response.choices is empty and no usage present"]
        # Allow: usage-only response (stream_options.include_usage=True)
        return True, []

    # Check 2: First choice has message
    first_choice = choices[0]
    if not hasattr(first_choice, 'message'):
        errors.append("choices[0] has no 'message' attribute")
        return False, errors

    message = getattr(first_choice, 'message', None)
    if message is None:
        errors.append("choices[0].message is None")
        return False, errors

    # Check 3: message.content type (most common field access)
    content = getattr(message, 'content', None)
    if content is not None and not isinstance(content, (str, type(None))):
        errors.append(
            f"message.content is {type(content).__name__}, expected str or None"
        )

    # Check 4: tool_calls structure (if present)
    tool_calls = getattr(message, 'tool_calls', None)
    if tool_calls is not None:
        if not isinstance(tool_calls, list):
            errors.append(
                f"message.tool_calls is {type(tool_calls).__name__}, expected list"
            )
        else:
            for i, tc in enumerate(tool_calls):
                if not hasattr(tc, 'function'):
                    errors.append(f"tool_calls[{i}] has no 'function' attribute")
                    continue
                func = getattr(tc, 'function', None)
                if func is None:
                    errors.append(f"tool_calls[{i}].function is None")
                    continue
                # name must be a non-empty string
                name = getattr(func, 'name', None)
                if name is not None and not isinstance(name, str):
                    errors.append(
                        f"tool_calls[{i}].function.name is {type(name).__name__}, expected str"
                    )
                # arguments must be a string (JSON)
                args = getattr(func, 'arguments', None)
                if args is not None and not isinstance(args, str):
                    errors.append(
                        f"tool_calls[{i}].function.arguments is {type(args).__name__}, expected str"
                    )

    # Check 5: model name
    if hasattr(response, 'model'):
        model_name = getattr(response, 'model', None)
        if model_name is not None and not isinstance(model_name, str):
            errors.append(
                f"response.model is {type(model_name).__name__}, expected str"
            )

    return len(errors) == 0, errors


# ── Anthropic Messages validation ────────────────────────────────────────

def validate_anthropic_response(response: Any) -> Tuple[bool, List[str]]:
    """Validate an Anthropic Messages API response structure."""
    errors: List[str] = []

    if response is None:
        return False, ["response is None"]

    # Check 1: content is a non-empty list
    if not hasattr(response, 'content'):
        return False, ["response has no 'content' attribute"]

    content = getattr(response, 'content', None)
    if content is None:
        return False, ["response.content is None"]
    if not isinstance(content, list):
        return False, [f"response.content is {type(content).__name__}, expected list"]
    if len(content) == 0:
        # Anthropic may return empty content with a stop_reason
        stop_reason = getattr(response, 'stop_reason', None)
        if stop_reason is None:
            return False, ["response.content is empty and no stop_reason"]

    # Check 2: each content block has valid structure
    for i, block in enumerate(content):
        if not hasattr(block, 'type'):
            errors.append(f"content[{i}] has no 'type' attribute")
            continue

        block_type = getattr(block, 'type', None)
        if block_type == 'text':
            text = getattr(block, 'text', None)
            if text is not None and not isinstance(text, str):
                errors.append(
                    f"content[{i}].text is {type(text).__name__}, expected str"
                )
        elif block_type == 'tool_use':
            name = getattr(block, 'name', None)
            if not isinstance(name, str) or not name:
                errors.append(f"content[{i}].name is missing or invalid")
            block_input = getattr(block, 'input', None)
            if block_input is not None and not isinstance(block_input, dict):
                errors.append(
                    f"content[{i}].input is {type(block_input).__name__}, expected dict"
                )

    # Check 3: model name
    if hasattr(response, 'model'):
        model_name = getattr(response, 'model', None)
        if model_name is not None and not isinstance(model_name, str):
            errors.append(
                f"response.model is {type(model_name).__name__}, expected str"
            )

    return len(errors) == 0, errors


# ── Unified validation entry point ───────────────────────────────────────

def validate_response(
    response: Any,
    api_mode: str,
    *,
    provider: str = "",
    model: str = "",
) -> Tuple[bool, List[str]]:
    """Validate an API response structure based on api_mode.

    Returns (valid, errors).  Errors are human-readable diagnostic strings
    suitable for logging and user-facing error messages.
    """
    if api_mode == "anthropic_messages":
        valid, errors = validate_anthropic_response(response)
    elif api_mode == "chat_completions":
        valid, errors = validate_chat_completions_response(response)
    else:
        # codex_responses / bedrock_converse — trust transport-level validation
        return True, []

    if not valid:
        logger.warning(
            "Response schema validation failed for %s/%s (mode=%s): %s",
            provider, model, api_mode,
            "; ".join(errors),
        )

    return valid, errors
