"""Tests for the /cost slash command — registry presence + dispatch wiring."""

import pytest

from bwm_cli.commands import (
    COMMAND_REGISTRY,
    COMMANDS,
    COMMANDS_BY_CATEGORY,
    resolve_command,
)


class TestCostCommandRegistry:
    """The /cost command is wired into the central registry."""

    def test_resolve_command_finds_cost(self):
        cmd = resolve_command("cost")
        assert cmd is not None
        assert cmd.name == "cost"

    def test_resolve_command_finds_cost_with_slash(self):
        cmd = resolve_command("/cost")
        assert cmd is not None
        assert cmd.name == "cost"

    def test_cost_lives_in_info_category(self):
        cmd = resolve_command("cost")
        assert cmd.category == "Info"

    def test_cost_in_flat_dict(self):
        assert "/cost" in COMMANDS
        assert "rollup" in COMMANDS["/cost"].lower()

    def test_cost_in_categorized_dict(self):
        info = COMMANDS_BY_CATEGORY.get("Info", {})
        assert "/cost" in info

    def test_cost_not_gateway_only(self):
        cmd = resolve_command("cost")
        # Available in CLI sessions (not strictly gateway).
        assert cmd.gateway_only is False

    def test_cost_short_description(self):
        cmd = resolve_command("cost")
        # Stay glanceable in /help
        assert len(cmd.description) <= 60
