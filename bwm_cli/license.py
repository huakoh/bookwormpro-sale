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


TRIAL_API = "https://portable.bookwormweb.com/api/trial"


def do_trial(console: Console | None = None) -> None:
    """Request a 7-day trial license from the server."""
    import json as _json
    c = console or _console

    dst = _license_path()
    if dst.exists():
        try:
            lic = _json.loads(dst.read_text(encoding="utf-8"))
            from agent.skill_crypto import validate_license
            valid, _ = validate_license(lic)
            if valid:
                c.print("\n  [yellow]You already have a valid license installed.[/]")
                c.print("  Run [cyan]bookworm license status[/] to check details.\n")
                return
        except Exception:
            pass

    from agent.skill_crypto import get_machine_hwid
    hwid = get_machine_hwid()
    c.print(f"\n  Machine HWID: [dim]{hwid[:24]}...[/]")
    c.print("  [bold]Requesting 7-day trial license...[/]")

    try:
        import httpx
        resp = httpx.post(TRIAL_API, json={"hwid": hwid}, timeout=15)
        data = resp.json()
    except Exception as e:
        c.print(f"  [bold red]Network error:[/] {e}")
        c.print("  Please check your internet connection and try again.\n")
        return

    if resp.status_code == 409:
        c.print(f"\n  [yellow]{data.get('message', 'Trial already used for this machine.')}[/]")
        c.print("  Contact sales for a full license: [cyan]https://portable.bookwormweb.com/#pricing[/]\n")
        return

    if resp.status_code != 200:
        c.print(f"\n  [bold red]Error:[/] {data.get('error', 'Unknown error')}\n")
        return

    lic = data.get("license")
    if not lic:
        c.print("\n  [bold red]Error:[/] Invalid server response\n")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(_json.dumps(lic, indent=2, ensure_ascii=False), encoding="utf-8")

    import agent.skill_crypto
    agent.skill_crypto._cached_license = None

    c.print(Panel(
        f"[bold green]Trial activated![/]\n\n"
        f"  Tier:      {lic.get('tier', 'trial')}\n"
        f"  Expires:   {lic.get('expires', 'N/A')}  ({data.get('days', 7)} days)\n"
        f"  Installed: {display_hermes_home()}/.license\n\n"
        f"  [dim]Enjoy BookwormPRO! Upgrade at https://portable.bookwormweb.com/#pricing[/]",
        title="7-Day Free Trial",
        border_style="green",
    ))


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
