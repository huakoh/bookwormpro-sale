"""
License activation CLI for BookwormPRO Sale distribution.

Subcommands:
    bookworm activate <license-file>   Copy + validate license
    bookworm license status            Show current license info
    bookworm license hwid              Print machine HWID
    bookworm license deactivate        Remove license
"""

import json
import shutil
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from bwm_constants import get_hermes_home, display_hermes_home

_console = Console()


def _license_path() -> Path:
    return get_hermes_home() / ".license"


def do_activate(license_file: str, console: Console | None = None) -> None:
    """Validate and install a license file."""
    c = console or _console
    src = Path(license_file)

    if not src.exists():
        c.print(f"[bold red]Error:[/] File not found: {src}")
        return

    try:
        content = src.read_text(encoding="utf-8").strip()
        lic = json.loads(content)
    except json.JSONDecodeError:
        c.print("[bold red]Error:[/] License file is not valid JSON")
        return

    required = {"licensee", "hwid", "tier", "expires", "key", "signature"}
    missing = required - set(lic.keys())
    if missing:
        c.print(f"[bold red]Error:[/] License missing fields: {', '.join(sorted(missing))}")
        return

    from agent.skill_crypto import validate_license
    valid, reason = validate_license(lic)

    if not valid:
        c.print(f"\n[bold red]  ✗ License INVALID[/]: {reason}\n")
        if "hwid" in reason.lower():
            from agent.skill_crypto import get_machine_hwid
            c.print(f"  Your HWID: [cyan]{get_machine_hwid()}[/]")
            c.print("  Contact your vendor to bind this license to your machine.\n")
        return

    dst = _license_path()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

    c.print(Panel(
        f"[bold green]License activated[/]\n\n"
        f"  Licensee:  {lic['licensee']}\n"
        f"  Tier:      {lic['tier']}\n"
        f"  Expires:   {lic['expires']}\n"
        f"  Installed: {display_hermes_home()}/.license",
        title="Activation Successful",
        border_style="green",
    ))


def do_status(console: Console | None = None) -> None:
    """Show current license status."""
    c = console or _console
    dst = _license_path()

    if not dst.exists():
        c.print("\n  [dim]No license installed.[/]")
        c.print(f"  Run: [cyan]bookworm activate <license-file>[/]\n")
        return

    try:
        lic = json.loads(dst.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception):
        c.print("\n  [yellow]License file exists but is not valid JSON.[/]")
        c.print(f"  Path: {dst}\n")
        return

    from agent.skill_crypto import validate_license
    valid, reason = validate_license(lic)

    status = "[bold green]VALID[/]" if valid else f"[bold red]INVALID[/] ({reason})"

    c.print(Panel(
        f"  Status:    {status}\n"
        f"  Licensee:  {lic.get('licensee', 'N/A')}\n"
        f"  Tier:      {lic.get('tier', 'N/A')}\n"
        f"  Expires:   {lic.get('expires', 'N/A')}\n"
        f"  Path:      {dst}",
        title="License Status",
        border_style="green" if valid else "red",
    ))


def do_hwid(console: Console | None = None) -> None:
    """Print machine hardware ID."""
    c = console or _console
    from agent.skill_crypto import get_machine_hwid
    hwid = get_machine_hwid()
    c.print(f"\n  Machine HWID: [bold cyan]{hwid}[/]")
    c.print("  Send this to your vendor to generate a bound license.\n")


def do_deactivate(console: Console | None = None) -> None:
    """Remove installed license."""
    c = console or _console
    dst = _license_path()

    if not dst.exists():
        c.print("\n  [dim]No license installed.[/]\n")
        return

    dst.unlink()
    c.print("\n  [bold]License removed.[/]\n")

    from agent.skill_crypto import _cached_license
    import agent.skill_crypto
    agent.skill_crypto._cached_license = None


def license_command(args) -> None:
    """Router for `bookworm license <subcommand>`."""
    action = getattr(args, "license_action", None)

    if action == "status":
        do_status()
    elif action == "hwid":
        do_hwid()
    elif action == "deactivate":
        do_deactivate()
    else:
        _console.print("Usage: bookworm license [status|hwid|deactivate]")
        _console.print("       bookworm activate <license-file>\n")
