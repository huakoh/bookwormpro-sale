"""Tests for /resume gateway slash command (Claude Code style).

Tests the _handle_resume_command handler which lists all recent sessions
and allows resuming by number, title, or session ID.
"""

import time as _time
from unittest.mock import MagicMock, AsyncMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource, build_session_key


def _make_event(text="/resume", platform=Platform.TELEGRAM,
                user_id="12345", chat_id="67890"):
    source = SessionSource(
        platform=platform,
        user_id=user_id,
        chat_id=chat_id,
        user_name="testuser",
    )
    return MessageEvent(text=text, source=source)


def _session_key_for_event(event):
    return build_session_key(event.source)


def _make_runner(session_db=None, current_session_id="current_session_001",
                 event=None):
    from gateway.run import GatewayRunner
    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._session_db = session_db
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._resume_session_cache = {}
    runner._background_tasks = set()

    session_key = build_session_key(event.source) if event else "agent:main:telegram:dm"

    mock_session_entry = MagicMock()
    mock_session_entry.session_id = current_session_id
    mock_session_entry.session_key = session_key
    mock_store = MagicMock()
    mock_store.get_or_create_session.return_value = mock_session_entry
    mock_store.load_transcript.return_value = []
    mock_store.switch_session.return_value = mock_session_entry
    runner.session_store = mock_store

    runner._async_flush_memories = AsyncMock()

    return runner


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class TestResumeListSessions:

    @pytest.mark.asyncio
    async def test_no_session_db(self):
        runner = _make_runner(session_db=None)
        event = _make_event(text="/resume")
        result = await runner._handle_resume_command(event)
        assert "not available" in result.lower()

    @pytest.mark.asyncio
    async def test_lists_all_sessions_including_untitled(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("sess_001", "telegram", user_id="12345")
        db.append_message("sess_001", "user", "Hello world")
        db.create_session("sess_002", "telegram", user_id="12345")
        db.set_session_title("sess_002", "Coding")
        db.append_message("sess_002", "user", "Fix the bug")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)

        assert "Recent Conversations" in result
        assert "Coding" in result
        assert "Hello world" in result
        assert "/resume <number>" in result
        db.close()

    @pytest.mark.asyncio
    async def test_no_previous_sessions(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)
        assert "No previous sessions" in result
        db.close()

    @pytest.mark.asyncio
    async def test_current_session_excluded_from_list(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("current_session_001", "telegram", user_id="12345")
        db.set_session_title("current_session_001", "Active Now")
        db.create_session("old_session", "telegram", user_id="12345")
        db.set_session_title("old_session", "Old Work")

        event = _make_event(text="/resume")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)

        assert "Old Work" in result
        assert "Active Now" not in result
        db.close()

    @pytest.mark.asyncio
    async def test_numbered_entries(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("sess_a", "telegram", user_id="12345")
        db.append_message("sess_a", "user", "First session")
        db.create_session("sess_b", "telegram", user_id="12345")
        db.append_message("sess_b", "user", "Second session")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)

        assert "1." in result
        assert "2." in result
        db.close()

    @pytest.mark.asyncio
    async def test_user_isolation(self, tmp_path):
        """User A must not see user B's sessions."""
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("sess_user_a", "telegram", user_id="12345")
        db.set_session_title("sess_user_a", "A's Work")
        db.create_session("sess_user_b", "telegram", user_id="99999")
        db.set_session_title("sess_user_b", "B's Secret")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume", user_id="12345")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)

        assert "A's Work" in result
        assert "B's Secret" not in result
        db.close()


# ---------------------------------------------------------------------------
# Numeric selection
# ---------------------------------------------------------------------------


class TestResumeByNumber:

    @pytest.mark.asyncio
    async def test_resume_by_number(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("sess_a", "telegram", user_id="12345")
        db.append_message("sess_a", "user", "First session")
        db.create_session("sess_b", "telegram", user_id="12345")
        db.append_message("sess_b", "user", "Second session")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume")
        runner = _make_runner(session_db=db, event=event,
                              current_session_id="current_session_001")

        await runner._handle_resume_command(event)

        pick_event = _make_event(text="/resume 1")
        result = await runner._handle_resume_command(pick_event)

        assert "Resumed" in result
        runner.session_store.switch_session.assert_called_once()
        db.close()

    @pytest.mark.asyncio
    async def test_invalid_number_too_high(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("sess_a", "telegram", user_id="12345")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume")
        runner = _make_runner(session_db=db, event=event)
        await runner._handle_resume_command(event)

        pick_event = _make_event(text="/resume 99")
        result = await runner._handle_resume_command(pick_event)
        assert "Invalid number" in result
        db.close()

    @pytest.mark.asyncio
    async def test_zero_falls_to_title_resolution(self, tmp_path):
        """0 is not a valid selection (>=1 required), falls to title/ID path."""
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume 0")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)
        assert "No session found" in result
        db.close()

    @pytest.mark.asyncio
    async def test_negative_number_falls_to_title_resolution(self, tmp_path):
        """-1 is not a valid int via try/except path, goes to title resolution."""
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume -1")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)
        assert "No session found" in result
        db.close()

    @pytest.mark.asyncio
    async def test_number_without_cache_shows_list_first(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("sess_a", "telegram", user_id="12345")
        db.append_message("sess_a", "user", "Hello")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume 1")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)

        assert "Recent Conversations" in result
        assert "/resume <number>" in result
        db.close()

    @pytest.mark.asyncio
    async def test_stale_cache_is_refreshed(self, tmp_path):
        """Cache older than 60s should trigger a fresh listing."""
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("sess_a", "telegram", user_id="12345")
        db.append_message("sess_a", "user", "Hello")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume")
        runner = _make_runner(session_db=db, event=event)
        await runner._handle_resume_command(event)

        # Manually expire the cache
        key = _session_key_for_event(event)
        runner._resume_session_cache[key]["ts"] = _time.time() - 120

        pick_event = _make_event(text="/resume 1")
        result = await runner._handle_resume_command(pick_event)

        # Should show listing again (stale cache), not switch
        assert "Recent Conversations" in result
        db.close()


# ---------------------------------------------------------------------------
# Title & ID resolution
# ---------------------------------------------------------------------------


class TestResumeByTitleAndId:

    @pytest.mark.asyncio
    async def test_resume_by_title(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("old_session_abc", "telegram", user_id="12345")
        db.set_session_title("old_session_abc", "My Project")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume My Project")
        runner = _make_runner(session_db=db, current_session_id="current_session_001",
                              event=event)
        result = await runner._handle_resume_command(event)

        assert "Resumed" in result
        assert "My Project" in result
        runner.session_store.switch_session.assert_called_once()
        call_args = runner.session_store.switch_session.call_args
        assert call_args[0][1] == "old_session_abc"
        db.close()

    @pytest.mark.asyncio
    async def test_resume_by_session_id(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("20260505_120000_abc123", "telegram", user_id="12345")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume 20260505_120000_abc123")
        runner = _make_runner(session_db=db, current_session_id="current_session_001",
                              event=event)
        result = await runner._handle_resume_command(event)

        assert "Resumed" in result
        db.close()

    @pytest.mark.asyncio
    async def test_resume_nonexistent(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume Nonexistent Session")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)
        assert "No session found" in result
        db.close()

    @pytest.mark.asyncio
    async def test_resume_already_on_session(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("current_session_001", "telegram", user_id="12345")
        db.set_session_title("current_session_001", "Active Project")

        event = _make_event(text="/resume Active Project")
        runner = _make_runner(session_db=db, current_session_id="current_session_001",
                              event=event)
        result = await runner._handle_resume_command(event)
        assert "Already on" in result
        db.close()

    @pytest.mark.asyncio
    async def test_resume_auto_lineage(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("sess_v1", "telegram", user_id="12345")
        db.set_session_title("sess_v1", "My Project")
        db.create_session("sess_v2", "telegram", user_id="12345")
        db.set_session_title("sess_v2", "My Project #2")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume My Project")
        runner = _make_runner(session_db=db, current_session_id="current_session_001",
                              event=event)
        result = await runner._handle_resume_command(event)

        assert "Resumed" in result
        call_args = runner.session_store.switch_session.call_args
        assert call_args[0][1] == "sess_v2"
        db.close()

    @pytest.mark.asyncio
    async def test_markdown_injection_escaped(self, tmp_path):
        """User-supplied text with Markdown chars must not break formatting."""
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume **bold** [link](http://evil)")
        runner = _make_runner(session_db=db, event=event)
        result = await runner._handle_resume_command(event)

        assert "**bold**" not in result
        assert "\\*\\*bold\\*\\*" in result
        db.close()


# ---------------------------------------------------------------------------
# Session switch mechanics
# ---------------------------------------------------------------------------


class TestResumeSwitchMechanics:

    @pytest.mark.asyncio
    async def test_follows_compression_continuation(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("compressed_root", "telegram", user_id="12345")
        db.set_session_title("compressed_root", "Compressed Work")
        db.end_session("compressed_root", "compression")
        db.create_session("compressed_child", "telegram",
                          parent_session_id="compressed_root", user_id="12345")
        db.append_message("compressed_child", "user", "hello from continuation")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume Compressed Work")
        runner = _make_runner(
            session_db=db,
            current_session_id="current_session_001",
            event=event,
        )
        runner.session_store.load_transcript.side_effect = (
            lambda session_id: [{"role": "user", "content": "hello from continuation"}]
            if session_id == "compressed_child"
            else []
        )

        result = await runner._handle_resume_command(event)

        assert "Resumed session" in result
        assert "(1 message)" in result
        call_args = runner.session_store.switch_session.call_args
        assert call_args[0][1] == "compressed_child"
        db.close()

    @pytest.mark.asyncio
    async def test_clears_running_agent(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("old_session", "telegram", user_id="12345")
        db.set_session_title("old_session", "Old Work")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume Old Work")
        runner = _make_runner(session_db=db, current_session_id="current_session_001",
                              event=event)
        real_key = _session_key_for_event(event)
        runner._running_agents[real_key] = MagicMock()
        runner._running_agents_ts[real_key] = _time.time()

        await runner._handle_resume_command(event)

        assert real_key not in runner._running_agents
        db.close()

    @pytest.mark.asyncio
    async def test_flushes_memories(self, tmp_path):
        from bwm_state import SessionDB
        db = SessionDB(db_path=tmp_path / "state.db")
        db.create_session("old_session", "telegram", user_id="12345")
        db.set_session_title("old_session", "Old Work")
        db.create_session("current_session_001", "telegram", user_id="12345")

        event = _make_event(text="/resume Old Work")
        runner = _make_runner(
            session_db=db,
            current_session_id="current_session_001",
            event=event,
        )

        await runner._handle_resume_command(event)

        runner._async_flush_memories.assert_called_once_with(
            "current_session_001",
            "agent:main:telegram:dm:67890",
        )
        db.close()


# ---------------------------------------------------------------------------
# _relative_time_str + _escape_md
# ---------------------------------------------------------------------------


class TestHelpers:

    def test_relative_time_none(self):
        from gateway.run import GatewayRunner
        assert GatewayRunner._relative_time_str(None) == ""

    def test_relative_time_recent_epoch(self):
        from gateway.run import GatewayRunner
        assert GatewayRunner._relative_time_str(_time.time() - 30) == "just now"

    def test_relative_time_minutes(self):
        from gateway.run import GatewayRunner
        assert "m ago" in GatewayRunner._relative_time_str(_time.time() - 600)

    def test_relative_time_hours(self):
        from gateway.run import GatewayRunner
        assert "h ago" in GatewayRunner._relative_time_str(_time.time() - 7200)

    def test_escape_md_asterisks(self):
        from gateway.run import GatewayRunner
        assert GatewayRunner._escape_md("**bold**") == "\\*\\*bold\\*\\*"

    def test_escape_md_brackets(self):
        from gateway.run import GatewayRunner
        assert "\\[" in GatewayRunner._escape_md("[link]")
