"""Tests for the ChatCompletionsTransport."""

import pytest
from types import SimpleNamespace

from agent.transports import get_transport
from agent.transports.types import NormalizedResponse, ToolCall


@pytest.fixture
def transport():
    import agent.transports.chat_completions  # noqa: F401
    return get_transport("chat_completions")


class TestChatCompletionsBasic:

    def test_api_mode(self, transport):
        assert transport.api_mode == "chat_completions"

    def test_registered(self, transport):
        assert transport is not None

    def test_convert_tools_identity(self, transport):
        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
        assert transport.convert_tools(tools) is tools

    def test_convert_messages_no_codex_leaks(self, transport):
        msgs = [{"role": "user", "content": "hi"}]
        result = transport.convert_messages(msgs)
        assert result is msgs  # no copy needed

    def test_convert_messages_strips_codex_fields(self, transport):
        msgs = [
            {"role": "assistant", "content": "ok", "codex_reasoning_items": [{"id": "rs_1"}],
             "tool_calls": [{"id": "call_1", "call_id": "call_1", "response_item_id": "fc_1",
                            "type": "function", "function": {"name": "t", "arguments": "{}"}}]},
        ]
        result = transport.convert_messages(msgs)
        assert "codex_reasoning_items" not in result[0]
        assert "call_id" not in result[0]["tool_calls"][0]
        assert "response_item_id" not in result[0]["tool_calls"][0]
        # Original list untouched (deepcopy-on-demand)
        assert "codex_reasoning_items" in msgs[0]


class TestChatCompletionsBuildKwargs:

    def test_basic_kwargs(self, transport):
        msgs = [{"role": "user", "content": "Hello"}]
        kw = transport.build_kwargs(model="gpt-4o", messages=msgs, timeout=30.0)
        assert kw["model"] == "gpt-4o"
        assert kw["messages"][0]["content"] == "Hello"
        assert kw["timeout"] == 30.0

    def test_developer_role_swap(self, transport):
        msgs = [{"role": "system", "content": "You are helpful"}, {"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(model="gpt-5.4", messages=msgs, model_lower="gpt-5.4")
        assert kw["messages"][0]["role"] == "developer"

    def test_no_developer_swap_for_non_gpt5(self, transport):
        msgs = [{"role": "system", "content": "You are helpful"}, {"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(model="claude-sonnet-4", messages=msgs, model_lower="claude-sonnet-4")
        assert kw["messages"][0]["role"] == "system"

    def test_tools_included(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
        kw = transport.build_kwargs(model="gpt-4o", messages=msgs, tools=tools)
        assert kw["tools"] == tools

    def test_openrouter_provider_prefs(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-4o", messages=msgs,
            is_openrouter=True,
            provider_preferences={"only": ["openai"]},
        )
        assert kw["extra_body"]["provider"] == {"only": ["openai"]}

    def test_nous_tags(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(model="gpt-4o", messages=msgs, is_nous=True)
        assert kw["extra_body"]["tags"] == ["product=bookwormpro"]

    def test_reasoning_default(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-4o", messages=msgs,
            supports_reasoning=True,
        )
        assert kw["extra_body"]["reasoning"] == {"enabled": True, "effort": "medium"}

    def test_nous_omits_disabled_reasoning(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-4o", messages=msgs,
            supports_reasoning=True,
            is_nous=True,
            reasoning_config={"enabled": False},
        )
        # BookwormPRO rejects enabled=false; reasoning omitted entirely
        assert "reasoning" not in kw.get("extra_body", {})

    def test_ollama_num_ctx(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="llama3", messages=msgs,
            ollama_num_ctx=32768,
        )
        assert kw["extra_body"]["options"]["num_ctx"] == 32768

    def test_custom_think_false(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="qwen3", messages=msgs,
            is_custom_provider=True,
            reasoning_config={"effort": "none"},
        )
        assert kw["extra_body"]["think"] is False

    def test_max_tokens_with_fn(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-4o", messages=msgs,
            max_tokens=4096,
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        assert kw["max_tokens"] == 4096

    def test_ephemeral_overrides_max_tokens(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-4o", messages=msgs,
            max_tokens=4096,
            ephemeral_max_output_tokens=2048,
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        assert kw["max_tokens"] == 2048

    def test_nvidia_default_max_tokens(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="glm-4.7", messages=msgs,
            is_nvidia_nim=True,
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        # NVIDIA default: 16384
        assert kw["max_tokens"] == 16384

    def test_qwen_default_max_tokens(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="qwen3-coder-plus", messages=msgs,
            is_qwen_portal=True,
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        # Qwen default: 65536
        assert kw["max_tokens"] == 65536

    def test_anthropic_max_output_for_claude_on_aggregator(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="anthropic/claude-sonnet-4.6", messages=msgs,
            is_openrouter=True,
            anthropic_max_output=64000,
        )
        # Set as plain max_tokens (not via fn) because the aggregator proxies to
        # Anthropic Messages API which requires the field.
        assert kw["max_tokens"] == 64000

    def test_request_overrides_last(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(
            model="gpt-4o", messages=msgs,
            request_overrides={"service_tier": "priority"},
        )
        assert kw["service_tier"] == "priority"

    def test_fixed_temperature(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(model="gpt-4o", messages=msgs, fixed_temperature=0.6)
        assert kw["temperature"] == 0.6

    def test_omit_temperature(self, transport):
        msgs = [{"role": "user", "content": "Hi"}]
        kw = transport.build_kwargs(model="gpt-4o", messages=msgs, omit_temperature=True, fixed_temperature=0.5)
        # omit wins
        assert "temperature" not in kw


class TestChatCompletionsKimi:
    """Regression tests for the Kimi/Moonshot quirks migrated into the transport."""

    def test_kimi_max_tokens_default(self, transport):
        kw = transport.build_kwargs(
            model="kimi-k2", messages=[{"role": "user", "content": "Hi"}],
            is_kimi=True,
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        # Kimi CLI default: 32000
        assert kw["max_tokens"] == 32000

    def test_kimi_reasoning_effort_top_level(self, transport):
        kw = transport.build_kwargs(
            model="kimi-k2", messages=[{"role": "user", "content": "Hi"}],
            is_kimi=True,
            reasoning_config={"effort": "high"},
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        # Kimi requires reasoning_effort as a top-level parameter
        assert kw["reasoning_effort"] == "high"

    def test_kimi_reasoning_effort_omitted_when_thinking_disabled(self, transport):
        kw = transport.build_kwargs(
            model="kimi-k2", messages=[{"role": "user", "content": "Hi"}],
            is_kimi=True,
            reasoning_config={"enabled": False},
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        # Mirror Kimi CLI: omit reasoning_effort entirely when thinking off
        assert "reasoning_effort" not in kw

    def test_kimi_thinking_enabled_extra_body(self, transport):
        kw = transport.build_kwargs(
            model="kimi-k2", messages=[{"role": "user", "content": "Hi"}],
            is_kimi=True,
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        assert kw["extra_body"]["thinking"] == {"type": "enabled"}

    def test_kimi_thinking_disabled_extra_body(self, transport):
        kw = transport.build_kwargs(
            model="kimi-k2", messages=[{"role": "user", "content": "Hi"}],
            is_kimi=True,
            reasoning_config={"enabled": False},
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        assert kw["extra_body"]["thinking"] == {"type": "disabled"}

    def test_moonshot_tool_schemas_are_sanitized_by_model_name(self, transport):
        """Aggregator routes (BookwormPRO, OpenRouter) hit Moonshot by model name, not base URL."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "q": {"description": "query"},  # missing type
                        },
                    },
                },
            },
        ]
        kw = transport.build_kwargs(
            model="moonshotai/kimi-k2.6",
            messages=[{"role": "user", "content": "Hi"}],
            tools=tools,
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        assert kw["tools"][0]["function"]["parameters"]["properties"]["q"]["type"] == "string"

    def test_non_moonshot_tools_are_not_mutated(self, transport):
        """Other models don't go through the Moonshot sanitizer."""
        original_params = {
            "type": "object",
            "properties": {"q": {"description": "query"}},  # missing type
        }
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": original_params,
                },
            },
        ]
        kw = transport.build_kwargs(
            model="anthropic/claude-sonnet-4.6",
            messages=[{"role": "user", "content": "Hi"}],
            tools=tools,
            max_tokens_param_fn=lambda n: {"max_tokens": n},
        )
        # The parameters dict is passed through untouched (no synthetic type)
        assert "type" not in kw["tools"][0]["function"]["parameters"]["properties"]["q"]


class TestChatCompletionsValidate:

    def test_none(self, transport):
        assert transport.validate_response(None) is False

    def test_no_choices(self, transport):
        r = SimpleNamespace(choices=None)
        assert transport.validate_response(r) is False

    def test_empty_choices(self, transport):
        r = SimpleNamespace(choices=[])
        assert transport.validate_response(r) is False

    def test_valid(self, transport):
        r = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))])
        assert transport.validate_response(r) is True


class TestChatCompletionsNormalize:

    def test_text_response(self, transport):
        r = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="Hello", tool_calls=None, reasoning_content=None),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        nr = transport.normalize_response(r)
        assert isinstance(nr, NormalizedResponse)
        assert nr.content == "Hello"
        assert nr.finish_reason == "stop"
        assert nr.tool_calls is None

    def test_tool_call_response(self, transport):
        tc = SimpleNamespace(
            id="call_123",
            function=SimpleNamespace(name="terminal", arguments='{"command": "ls"}'),
        )
        r = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[tc], reasoning_content=None),
                finish_reason="tool_calls",
            )],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )
        nr = transport.normalize_response(r)
        assert len(nr.tool_calls) == 1
        assert nr.tool_calls[0].name == "terminal"
        assert nr.tool_calls[0].id == "call_123"

    def test_tool_call_extra_content_preserved(self, transport):
        """Gemini 3 thinking models attach extra_content with thought_signature
        on tool_calls.  Without this replay on the next turn, the API rejects
        the request with 400.  The transport MUST surface extra_content so the
        agent loop can write it back into the assistant message."""
        tc = SimpleNamespace(
            id="call_gem",
            function=SimpleNamespace(name="terminal", arguments='{"command": "ls"}'),
            extra_content={"google": {"thought_signature": "SIG_ABC123"}},
        )
        r = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[tc], reasoning_content=None),
                finish_reason="tool_calls",
            )],
            usage=None,
        )
        nr = transport.normalize_response(r)
        assert nr.tool_calls[0].provider_data == {
            "extra_content": {"google": {"thought_signature": "SIG_ABC123"}}
        }

    def test_reasoning_content_preserved_separately(self, transport):
        """DeepSeek/Moonshot use reasoning_content distinct from reasoning.
        Don't merge them — the thinking-prefill retry check reads each field
        separately."""
        r = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content=None, tool_calls=None,
                    reasoning="summary text",
                    reasoning_content="detailed scratchpad",
                ),
                finish_reason="stop",
            )],
            usage=None,
        )
        nr = transport.normalize_response(r)
        assert nr.reasoning == "summary text"
        assert nr.provider_data == {"reasoning_content": "detailed scratchpad"}


class TestChatCompletionsCacheStats:

    def test_no_usage(self, transport):
        r = SimpleNamespace(usage=None)
        assert transport.extract_cache_stats(r) is None

    def test_no_details(self, transport):
        r = SimpleNamespace(usage=SimpleNamespace(prompt_tokens_details=None))
        assert transport.extract_cache_stats(r) is None

    def test_with_cache(self, transport):
        details = SimpleNamespace(cached_tokens=500, cache_write_tokens=100)
        r = SimpleNamespace(usage=SimpleNamespace(prompt_tokens_details=details))
        result = transport.extract_cache_stats(r)
        assert result == {"cached_tokens": 500, "creation_tokens": 100}


# BWW relay (bww.letcareme.com) handles all OpenAI→Anthropic conversion
# internally.  convert_messages must NOT pre-convert to Anthropic blocks —
# doing so causes double-conversion (relay re-processes already-converted
# blocks, producing empty-type blocks → HTTP 400/429).

class TestBwwRelayNoPreConversion:

    def _assistant_msg(
        self, content="going to call tool", reasoning="thought 1",
        tc_args='{"path":"/tmp/x"}',
    ):
        return {
            "role": "assistant",
            "content": content,
            "reasoning_content": reasoning,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "terminal", "arguments": tc_args},
            }],
        }

    def _tool_msg(self, tool_call_id="call_1", content="result text"):
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }

    def test_assistant_stays_openai_format(self, transport):
        """Assistant messages keep OpenAI format — no Anthropic block conversion."""
        msgs = [self._assistant_msg(), self._tool_msg()]
        out = transport.convert_messages(msgs)
        assert out is msgs
        assert out[0]["content"] == "going to call tool"
        assert "tool_calls" in out[0]
        assert out[0]["tool_calls"][0]["id"] == "call_1"

    def test_tool_stays_openai_format(self, transport):
        msgs = [self._assistant_msg(), self._tool_msg(content="found at C:/x.json")]
        out = transport.convert_messages(msgs)
        assert out is msgs
        assert out[1]["role"] == "tool"
        assert out[1]["content"] == "found at C:/x.json"

    def test_codex_fields_stripped_but_no_block_conversion(self, transport):
        """Codex fields are stripped but messages stay in OpenAI format."""
        msgs = [
            {
                "role": "assistant",
                "content": "calling",
                "codex_reasoning_items": [{"id": "rs_1"}],
                "tool_calls": [{
                    "id": "call_1", "call_id": "call_1", "response_item_id": "fc_1",
                    "type": "function",
                    "function": {"name": "terminal", "arguments": "{}"},
                }],
            },
            self._tool_msg(),
        ]
        out = transport.convert_messages(msgs)
        assert "codex_reasoning_items" not in out[0]
        assert "call_id" not in out[0]["tool_calls"][0]
        assert out[0]["content"] == "calling"
        assert isinstance(out[0]["content"], str)

    def test_multiple_tool_calls_preserved(self, transport):
        msg = {
            "role": "assistant",
            "content": "two calls",
            "reasoning_content": "thinking",
            "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "a", "arguments": "{}"}},
                {"id": "c2", "type": "function",
                 "function": {"name": "b", "arguments": '{"k":"v"}'}},
            ],
        }
        out = transport.convert_messages([msg, self._tool_msg("c1"), self._tool_msg("c2")])
        assert out is [msg] or len(out[0]["tool_calls"]) == 2

    def test_plain_messages_pass_through(self, transport):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        out = transport.convert_messages(msgs)
        assert out is msgs


class TestBwwRelayDeepSeekResponse:

    def _resp(self, content):
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=None,
                    reasoning=None,
                    reasoning_content=None,
                ),
                finish_reason="stop",
            )],
            usage=None,
        )

    def test_blocks_extract_thinking_into_reasoning_content(self, transport):
        content_blocks = [
            {"type": "thinking", "thinking": "step plan"},
            {"type": "text", "text": "final answer"},
        ]
        nr = transport.normalize_response(self._resp(content_blocks))
        assert nr.content == "final answer"
        assert nr.provider_data == {"reasoning_content": "step plan"}

    def test_blocks_text_only(self, transport):
        nr = transport.normalize_response(self._resp([
            {"type": "text", "text": "hello"},
        ]))
        assert nr.content == "hello"
        assert nr.provider_data is None

    def test_blocks_thinking_only(self, transport):
        nr = transport.normalize_response(self._resp([
            {"type": "thinking", "thinking": "thoughts"},
        ]))
        assert nr.content is None
        assert nr.provider_data == {"reasoning_content": "thoughts"}

    def test_blocks_concat_multiple_text(self, transport):
        nr = transport.normalize_response(self._resp([
            {"type": "thinking", "thinking": "A"},
            {"type": "text", "text": "part1 "},
            {"type": "text", "text": "part2"},
        ]))
        assert nr.content == "part1 part2"
        assert nr.provider_data == {"reasoning_content": "A"}

    def test_string_content_unchanged(self, transport):
        nr = transport.normalize_response(self._resp("plain string"))
        assert nr.content == "plain string"
        assert nr.provider_data is None

    def test_reasoning_content_field_takes_precedence(self, transport):
        r = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content=[{"type": "thinking", "thinking": "from blocks"}],
                    tool_calls=None,
                    reasoning=None,
                    reasoning_content="from openai field",
                ),
                finish_reason="stop",
            )],
            usage=None,
        )
        nr = transport.normalize_response(r)
        assert nr.provider_data == {"reasoning_content": "from openai field"}

    def test_tool_use_blocks_become_tool_calls(self, transport):
        nr = transport.normalize_response(self._resp([
            {"type": "thinking", "thinking": "plan"},
            {"type": "tool_use", "id": "tu_1", "name": "find_files",
             "input": {"path": "/tmp"}},
        ]))
        assert nr.tool_calls is not None
        assert len(nr.tool_calls) == 1
        tc = nr.tool_calls[0]
        assert tc.id == "tu_1"
        assert tc.name == "find_files"
        import json as _json
        assert _json.loads(tc.arguments) == {"path": "/tmp"}
        assert nr.provider_data == {"reasoning_content": "plan"}

    def test_tool_use_does_not_overwrite_existing_tool_calls(self, transport):
        existing = SimpleNamespace(
            id="orig_id",
            function=SimpleNamespace(name="orig_name", arguments="{}"),
            extra_content=None,
        )
        r = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content=[{"type": "tool_use", "id": "block_id",
                             "name": "block_name", "input": {}}],
                    tool_calls=[existing],
                    reasoning=None,
                    reasoning_content=None,
                ),
                finish_reason="stop",
            )],
            usage=None,
        )
        nr = transport.normalize_response(r)
        # SDK-supplied tool_calls win over reconstructed-from-blocks.
        assert nr.tool_calls[0].id == "orig_id"

    def test_tool_use_string_input_passthrough(self, transport):
        nr = transport.normalize_response(self._resp([
            {"type": "tool_use", "id": "x", "name": "f", "input": "raw-string"},
        ]))
        assert nr.tool_calls[0].arguments == "raw-string"


class TestBwwRelayThinkingBlockInjection:
    """P0 #8: BWW relay + DeepSeek requires assistant content to contain
    Anthropic-style {type:thinking} blocks.  _inject_thinking_blocks converts
    reasoning_content → block list while preserving tool_calls as-is."""

    def test_reasoning_converted_to_thinking_block(self, transport):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "answer", "reasoning_content": "thought process"},
        ]
        result = transport._inject_thinking_blocks(msgs)
        assert result[0] is msgs[0]  # user msg untouched
        ast = result[1]
        assert isinstance(ast["content"], list)
        assert ast["content"][0] == {"type": "thinking", "thinking": "thought process"}
        assert ast["content"][1] == {"type": "text", "text": "answer"}
        assert "reasoning_content" not in ast

    def test_tool_calls_preserved(self, transport):
        msgs = [{
            "role": "assistant",
            "content": "calling tool",
            "reasoning_content": "thinking",
            "tool_calls": [{"id": "c1", "type": "function",
                           "function": {"name": "t", "arguments": "{}"}}],
        }]
        result = transport._inject_thinking_blocks(msgs)
        assert result[0]["tool_calls"] == msgs[0]["tool_calls"]
        assert isinstance(result[0]["content"], list)
        assert result[0]["content"][0]["type"] == "thinking"

    def test_no_reasoning_no_transform(self, transport):
        msgs = [
            {"role": "assistant", "content": "plain answer"},
        ]
        result = transport._inject_thinking_blocks(msgs)
        assert result is msgs

    def test_tool_messages_untouched(self, transport):
        msgs = [
            {"role": "tool", "tool_call_id": "c1", "content": "result"},
        ]
        result = transport._inject_thinking_blocks(msgs)
        assert result is msgs
        assert result[0]["content"] == "result"

    def test_already_block_content_skipped(self, transport):
        msgs = [{
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": "already blocks"}],
            "reasoning_content": "dup",
        }]
        result = transport._inject_thinking_blocks(msgs)
        assert result is msgs

    def test_reasoning_field_fallback(self, transport):
        msgs = [{"role": "assistant", "content": "ans", "reasoning": "via reasoning field"}]
        result = transport._inject_thinking_blocks(msgs)
        assert result[0]["content"][0] == {"type": "thinking", "thinking": "via reasoning field"}
        assert "reasoning" not in result[0]

    def test_none_content_gets_thinking_only(self, transport):
        msgs = [{"role": "assistant", "content": None, "reasoning_content": "thoughts"}]
        result = transport._inject_thinking_blocks(msgs)
        assert len(result[0]["content"]) == 1
        assert result[0]["content"][0]["type"] == "thinking"

    def test_build_kwargs_no_thinking_injection_for_bww(self, transport):
        """BWW relay rejects thinking blocks — build_kwargs must NOT inject them."""
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "answer", "reasoning_content": "think"},
            {"role": "user", "content": "follow up"},
        ]
        kw = transport.build_kwargs(
            model="deepseek-v4-pro",
            messages=msgs,
            base_url="https://bww.letcareme.com/v1",
        )
        ast = kw["messages"][1]
        assert isinstance(ast["content"], str)
        assert ast["content"] == "answer"
        assert ast.get("reasoning_content") == "think"
