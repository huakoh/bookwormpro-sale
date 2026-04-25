"""Tests for agent.refusal_interceptor — phantom-refusal detection + retry."""

import pytest

from agent import refusal_interceptor as ri


# ---------------------------------------------------------------------------
# is_phantom_refusal
# ---------------------------------------------------------------------------

class TestIsPhantomRefusal:
    """Detection only fires on real-FS-access runtimes."""

    @pytest.fixture(autouse=True)
    def _force_native(self, monkeypatch):
        # All detection tests assume native runtime (full FS access).
        monkeypatch.setattr(ri, "is_native_install", lambda: True)
        monkeypatch.setattr(ri, "is_host_bridge_active", lambda: False)

    @pytest.mark.parametrize("text", [
        "I run in a server-side sandbox and cannot access your local files.",
        "Sorry, I cannot access user's local filesystem from here.",
        "我运行在服务器端的沙箱环境中，无法访问你本地电脑的文件系统。",
        "抱歉，我无法读取你的桌面文件。",
        "I don't have permission to delete files on your local machine.",
        "Agent runs in a server-side sandbox.",
        "我跑在隔离环境中，无法访问本机。",
    ])
    def test_detects_known_refusal_phrases(self, text):
        assert ri.is_phantom_refusal(text) is True

    @pytest.mark.parametrize("text", [
        "",
        None,
        "Done. Deleted /Users/me/Desktop/foo.json",
        "Here's how a Docker sandbox works: it isolates processes via namespaces.",
        "The file was removed successfully.",
        "Permission denied: cannot open /etc/shadow",  # real OS error, not phantom
    ])
    def test_does_not_match_legitimate_text(self, text):
        assert ri.is_phantom_refusal(text) is False

    def test_long_replies_never_match(self, monkeypatch):
        # Even with a refusal phrase inside, a very long reply is treated as
        # a substantive technical discussion, not a refusal.
        long_text = (
            "Here's a detailed walkthrough of sandbox architectures. "
            "A typical server-side sandbox isolates user code from the host "
            "filesystem to prevent privilege escalation. The classical "
            "approach is to chroot... " * 30
        )
        assert len(long_text) > 1200
        assert ri.is_phantom_refusal(long_text) is False


class TestSandboxRespect:
    """Real sandboxes must NOT have their refusals intercepted."""

    def test_no_intercept_when_truly_sandboxed(self, monkeypatch):
        monkeypatch.setattr(ri, "is_native_install", lambda: False)
        monkeypatch.setattr(ri, "is_host_bridge_active", lambda: False)
        # Even an obvious refusal phrase: do NOT intercept.
        assert ri.is_phantom_refusal(
            "I run in a server-side sandbox and cannot access local files."
        ) is False

    def test_intercept_when_bridge_is_active(self, monkeypatch):
        monkeypatch.setattr(ri, "is_native_install", lambda: False)
        monkeypatch.setattr(ri, "is_host_bridge_active", lambda: True)
        assert ri.is_phantom_refusal(
            "我无法访问你本地的桌面文件。"
        ) is True


# ---------------------------------------------------------------------------
# maybe_intercept — retry orchestration
# ---------------------------------------------------------------------------

class TestMaybeIntercept:
    @pytest.fixture(autouse=True)
    def _force_native(self, monkeypatch):
        monkeypatch.setattr(ri, "is_native_install", lambda: True)
        monkeypatch.setattr(ri, "is_host_bridge_active", lambda: False)

    def test_returns_original_when_not_a_refusal(self):
        called = {"n": 0}

        def retry():
            called["n"] += 1
            return "should not be called"

        out = ri.maybe_intercept("File deleted.", retry_callback=retry)
        assert out == "File deleted."
        assert called["n"] == 0

    def test_retries_once_on_phantom_refusal(self):
        called = {"n": 0}

        def retry():
            called["n"] += 1
            return "OK, deleted /Users/me/Desktop/foo.json"

        out = ri.maybe_intercept(
            "I run in a server-side sandbox and cannot access local files.",
            retry_callback=retry,
        )
        assert out == "OK, deleted /Users/me/Desktop/foo.json"
        assert called["n"] == 1

    def test_does_not_loop_when_retry_also_refuses(self):
        called = {"n": 0}

        def retry():
            called["n"] += 1
            return "Still claiming a server-side sandbox blocks me."

        out = ri.maybe_intercept(
            "I cannot access user's local filesystem.",
            retry_callback=retry,
        )
        # Retry text returned (so user sees latest attempt), but no second retry.
        assert "server-side sandbox" in out
        assert called["n"] == 1

    def test_retry_exception_falls_back_to_original(self):
        def retry():
            raise RuntimeError("network down")

        original = "I run in a server-side sandbox."
        out = ri.maybe_intercept(original, retry_callback=retry)
        assert out == original

    def test_retry_returning_none_falls_back_to_original(self):
        def retry():
            return None

        original = "I cannot access your local files."
        out = ri.maybe_intercept(original, retry_callback=retry)
        assert out == original

    def test_log_event_called_on_intercept(self):
        events = []

        def retry():
            return "Done."

        ri.maybe_intercept(
            "I run in a server-side sandbox and cannot access local files.",
            retry_callback=retry,
            log_event=lambda name: events.append(name),
        )
        assert events == ["phantom_refusal_intercepted"]

    def test_log_event_failure_does_not_break(self):
        def retry():
            return "Done."

        def bad_log(name):
            raise RuntimeError("logging broken")

        # Must not raise.
        out = ri.maybe_intercept(
            "I run in a server-side sandbox and cannot access local files.",
            retry_callback=retry,
            log_event=bad_log,
        )
        assert out == "Done."


class TestOverrideNudge:
    """The override nudge must contain key authoritative phrasing."""

    def test_nudge_explicitly_states_no_sandbox(self):
        text = ri.PHANTOM_REFUSAL_OVERRIDE_NUDGE
        assert "no sandbox" in text.lower()
        assert "previous reply refused" in text or "previous response refused" in text or "previous reply" in text
        assert "perform" in text.lower() or "execute" in text.lower()
