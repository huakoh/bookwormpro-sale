"""Tests for bwm_constants module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import bwm_constants
from bwm_constants import (
    get_default_hermes_root,
    is_bww_relay_url,
    is_container,
    is_host_bridge_active,
    is_native_install,
)


class TestGetDefaultHermesRoot:
    """Tests for get_default_hermes_root() — Docker/custom deployment awareness."""

    def test_no_hermes_home_returns_native(self, tmp_path, monkeypatch):
        """When BOOKWORMPRO_HOME is not set, returns ~/.bookwormpro."""
        monkeypatch.delenv("BOOKWORMPRO_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert get_default_hermes_root() == tmp_path / ".bookwormpro"

    def test_hermes_home_is_native(self, tmp_path, monkeypatch):
        """When BOOKWORMPRO_HOME = ~/.bookwormpro, returns ~/.bookwormpro."""
        native = tmp_path / ".bookwormpro"
        native.mkdir()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(native))
        assert get_default_hermes_root() == native

    def test_hermes_home_is_profile(self, tmp_path, monkeypatch):
        """When BOOKWORMPRO_HOME is a profile under ~/.bookwormpro, returns ~/.bookwormpro."""
        native = tmp_path / ".bookwormpro"
        profile = native / "profiles" / "coder"
        profile.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(profile))
        assert get_default_hermes_root() == native

    def test_hermes_home_is_docker(self, tmp_path, monkeypatch):
        """When BOOKWORMPRO_HOME points outside ~/.bookwormpro (Docker), returns BOOKWORMPRO_HOME."""
        docker_home = tmp_path / "opt" / "data"
        docker_home.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(docker_home))
        assert get_default_hermes_root() == docker_home

    def test_hermes_home_is_custom_path(self, tmp_path, monkeypatch):
        """Any BOOKWORMPRO_HOME outside ~/.bookwormpro is treated as the root."""
        custom = tmp_path / "my-bookworm-data"
        custom.mkdir()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(custom))
        assert get_default_hermes_root() == custom

    def test_docker_profile_active(self, tmp_path, monkeypatch):
        """When a Docker profile is active (BOOKWORMPRO_HOME=<root>/profiles/<name>),
        returns the Docker root, not the profile dir."""
        docker_root = tmp_path / "opt" / "data"
        profile = docker_root / "profiles" / "coder"
        profile.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("BOOKWORMPRO_HOME", str(profile))
        assert get_default_hermes_root() == docker_root


class TestIsContainer:
    """Tests for is_container() — Docker/Podman detection."""

    def _reset_cache(self, monkeypatch):
        """Reset the cached detection result before each test."""
        monkeypatch.setattr(bwm_constants, "_container_detected", None)

    def test_detects_dockerenv(self, monkeypatch, tmp_path):
        """/.dockerenv triggers container detection."""
        self._reset_cache(monkeypatch)
        monkeypatch.setattr(os.path, "exists", lambda p: p == "/.dockerenv")
        assert is_container() is True

    def test_detects_containerenv(self, monkeypatch, tmp_path):
        """/run/.containerenv triggers container detection (Podman)."""
        self._reset_cache(monkeypatch)
        monkeypatch.setattr(os.path, "exists", lambda p: p == "/run/.containerenv")
        assert is_container() is True

    def test_detects_cgroup_docker(self, monkeypatch, tmp_path):
        """/proc/1/cgroup containing 'docker' triggers detection."""
        import builtins
        self._reset_cache(monkeypatch)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        cgroup_file = tmp_path / "cgroup"
        cgroup_file.write_text("12:memory:/docker/abc123\n")
        _real_open = builtins.open
        monkeypatch.setattr("builtins.open", lambda p, *a, **kw: _real_open(str(cgroup_file), *a, **kw) if p == "/proc/1/cgroup" else _real_open(p, *a, **kw))
        assert is_container() is True

    def test_negative_case(self, monkeypatch, tmp_path):
        """Returns False on a regular Linux host."""
        import builtins
        self._reset_cache(monkeypatch)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        cgroup_file = tmp_path / "cgroup"
        cgroup_file.write_text("12:memory:/\n")
        _real_open = builtins.open
        monkeypatch.setattr("builtins.open", lambda p, *a, **kw: _real_open(str(cgroup_file), *a, **kw) if p == "/proc/1/cgroup" else _real_open(p, *a, **kw))
        assert is_container() is False

    def test_caches_result(self, monkeypatch):
        """Second call uses cached value without re-probing."""
        monkeypatch.setattr(bwm_constants, "_container_detected", True)
        assert is_container() is True
        # Even if we make os.path.exists return False, cached value wins
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        assert is_container() is True


class TestIsHostBridgeActive:
    """Tests for is_host_bridge_active() — BOOKWORMPRO_HOST_BRIDGE env detection."""

    def _reset_cache(self, monkeypatch):
        monkeypatch.setattr(bwm_constants, "_host_bridge_detected", None)

    def test_unset_is_false(self, monkeypatch):
        self._reset_cache(monkeypatch)
        monkeypatch.delenv("BOOKWORMPRO_HOST_BRIDGE", raising=False)
        assert is_host_bridge_active() is False

    def test_explicit_one_is_true(self, monkeypatch):
        self._reset_cache(monkeypatch)
        monkeypatch.setenv("BOOKWORMPRO_HOST_BRIDGE", "1")
        assert is_host_bridge_active() is True

    def test_truthy_words_are_true(self, monkeypatch):
        for val in ("true", "yes", "on", "TRUE", "  Yes  "):
            self._reset_cache(monkeypatch)
            monkeypatch.setenv("BOOKWORMPRO_HOST_BRIDGE", val)
            assert is_host_bridge_active() is True, f"failed for {val!r}"

    def test_falsy_values_are_false(self, monkeypatch):
        for val in ("0", "false", "no", "off", "", "random"):
            self._reset_cache(monkeypatch)
            monkeypatch.setenv("BOOKWORMPRO_HOST_BRIDGE", val)
            assert is_host_bridge_active() is False, f"failed for {val!r}"

    def test_caches_result(self, monkeypatch):
        monkeypatch.setattr(bwm_constants, "_host_bridge_detected", True)
        monkeypatch.delenv("BOOKWORMPRO_HOST_BRIDGE", raising=False)
        assert is_host_bridge_active() is True


class TestIsBwwRelayUrl:
    """Tests for is_bww_relay_url() — hostname-precise matching."""

    def test_full_https_url(self):
        assert is_bww_relay_url("https://bww.letcareme.com/v1") is True

    def test_http_url(self):
        assert is_bww_relay_url("http://bww.letcareme.com/v1") is True

    def test_bare_host(self):
        assert is_bww_relay_url("bww.letcareme.com") is True

    def test_bare_host_with_path(self):
        assert is_bww_relay_url("bww.letcareme.com/v1") is True

    def test_case_insensitive(self):
        assert is_bww_relay_url("https://BWW.LETCAREME.COM/v1") is True

    def test_none(self):
        assert is_bww_relay_url(None) is False

    def test_empty(self):
        assert is_bww_relay_url("") is False

    def test_subdomain_no_false_positive(self):
        assert is_bww_relay_url("https://evil-bww.letcareme.com/v1") is False

    def test_parent_domain_no_false_positive(self):
        assert is_bww_relay_url("https://bww.letcareme.com.evil.com/v1") is False

    def test_unrelated_host(self):
        assert is_bww_relay_url("https://api.deepseek.com/v1") is False

    def test_host_as_path_component_no_false_positive(self):
        assert is_bww_relay_url("https://evil.com/bww.letcareme.com") is False


class TestIsNativeInstall:
    """Tests for is_native_install() — true when not container and not WSL."""

    def test_native_when_neither(self, monkeypatch):
        monkeypatch.setattr(bwm_constants, "is_container", lambda: False)
        monkeypatch.setattr(bwm_constants, "is_wsl", lambda: False)
        assert is_native_install() is True

    def test_not_native_when_container(self, monkeypatch):
        monkeypatch.setattr(bwm_constants, "is_container", lambda: True)
        monkeypatch.setattr(bwm_constants, "is_wsl", lambda: False)
        assert is_native_install() is False

    def test_not_native_when_wsl(self, monkeypatch):
        monkeypatch.setattr(bwm_constants, "is_container", lambda: False)
        monkeypatch.setattr(bwm_constants, "is_wsl", lambda: True)
        assert is_native_install() is False
