"""
from bwm_cli.i18n import _
CLI commands for the DM pairing system.

Usage:
    bookworm pairing list              # Show all pending + approved users
    bookworm pairing approve <platform> <code>  # Approve a pairing code
    bookworm pairing revoke <platform> <user_id> # Revoke user access
    bookworm pairing clear-pending     # Clear all expired/pending codes
"""

def pairing_command(args):
    """Handle bookworm pairing subcommands."""
    from gateway.pairing import PairingStore

    store = PairingStore()
    action = getattr(args, "pairing_action", None)

    if action == "list":
        _cmd_list(store)
    elif action == "approve":
        _cmd_approve(store, args.platform, args.code)
    elif action == "revoke":
        _cmd_revoke(store, args.platform, args.user_id)
    elif action == "clear-pending":
        _cmd_clear_pending(store)
    else:
        print(_("Usage: bookworm pairing {list|approve|revoke|clear-pending}"))
        print(_("Run 'bookworm pairing --help' for details."))


def _cmd_list(store):
    """List all pending and approved users."""
    pending = store.list_pending()
    approved = store.list_approved()

    if not pending and not approved:
        print(_("No pairing data found. No one has tried to pair yet~"))
        return

    if pending:
        print(_("\n  Pending Pairing Requests ({len}):").format(len=len(pending)))
        print(f"  {'Platform':<12} {'Code':<10} {'User ID':<20} {'Name':<20} {'Age'}")
        print(f"  {'--------':<12} {'----':<10} {'-------':<20} {'----':<20} {'---'}")
        for p in pending:
            print(
                f"  {p['platform']:<12} {p['code']:<10} {p['user_id']:<20} "
                f"{(p.get('user_name') or ''):<20} {p['age_minutes']}m ago"
            )
    else:
        print(_("\n  No pending pairing requests."))

    if approved:
        print(_("\n  Approved Users ({len}):").format(len=len(approved)))
        print(f"  {'Platform':<12} {'User ID':<20} {'Name':<20}")
        print(f"  {'--------':<12} {'-------':<20} {'----':<20}")
        for a in approved:
            print(f"  {a['platform']:<12} {a['user_id']:<20} {(a.get('user_name') or ''):<20}")
    else:
        print(_("\n  No approved users."))

    print()


def _cmd_approve(store, platform: str, code: str):
    """Approve a pairing code."""
    platform = platform.lower().strip()
    code = code.upper().strip()

    result = store.approve_code(platform, code)
    if result:
        uid = result["user_id"]
        name = result.get("user_name") or ""
        display = f"{name} ({uid})" if name else uid
        print(_("\n  Approved! User {display} on {platform} can now use the bot~").format(display=display, platform=platform))
        print(_("  They'll be recognized automatically on their next message.\n"))
    elif store._is_locked_out(platform):
        import time as _time
        limits = store._load_json(store._rate_limit_path())
        lockout_until = limits.get(f"_lockout:{platform}", 0)
        remaining = max(0, int(lockout_until - _time.time()))
        mins = remaining // 60
        print(
            _("\n  Platform '{platform}' is locked out after too many failed "
              "approval attempts.").format(platform=platform)
        )
        print(_("  Lockout clears in ~{mins} minute(s).").format(mins=mins))
        print(
            _("  To reset sooner, delete the '_lockout:{platform}' entry from "
              "~/.hermes/platforms/pairing/_rate_limits.json\n").format(platform=platform)
        )
    else:
        print(_("\n  Code '{code}' not found or expired for platform '{platform}'.").format(code=code, platform=platform))
        print(_("  Run 'bookworm pairing list' to see pending codes.\n"))


def _cmd_revoke(store, platform: str, user_id: str):
    """Revoke a user's access."""
    platform = platform.lower().strip()

    if store.revoke(platform, user_id):
        print(_("\n  Revoked access for user {user_id} on {platform}.\n").format(user_id=user_id, platform=platform))
    else:
        print(_("\n  User {user_id} not found in approved list for {platform}.\n").format(user_id=user_id, platform=platform))


def _cmd_clear_pending(store):
    """Clear all pending pairing codes."""
    count = store.clear_pending()
    if count:
        print(_("\n  Cleared {count} pending pairing request(s).\n").format(count=count))
    else:
        print(_("\n  No pending requests to clear.\n"))
