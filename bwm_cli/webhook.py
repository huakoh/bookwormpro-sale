"""bookworm webhook — manage dynamic webhook subscriptions from the CLI.

Usage:
    bookworm webhook subscribe <name> [options]
    bookworm webhook list
    bookworm webhook remove <name>
    bookworm webhook test <name> [--payload '{"key": "value"}']

Subscriptions persist to ~/.bookwormpro/webhook_subscriptions.json and are
hot-reloaded by the webhook adapter without a gateway restart.
"""

import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Dict

from bwm_constants import display_hermes_home
from bwm_cli.i18n import _



_SUBSCRIPTIONS_FILENAME = "webhook_subscriptions.json"


def _hermes_home() -> Path:
    from bwm_constants import get_hermes_home
    return get_hermes_home()


def _subscriptions_path() -> Path:
    return _hermes_home() / _SUBSCRIPTIONS_FILENAME


def _load_subscriptions() -> Dict[str, dict]:
    path = _subscriptions_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_subscriptions(subs: Dict[str, dict]) -> None:
    path = _subscriptions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(subs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(str(tmp_path), str(path))


def _get_webhook_config() -> dict:
    """Load webhook platform config. Returns {} if not configured."""
    try:
        from bwm_cli.config import load_config
        cfg = load_config()
        return cfg.get("platforms", {}).get("webhook", {})
    except Exception:
        return {}


def _is_webhook_enabled() -> bool:
    return bool(_get_webhook_config().get("enabled"))


def _get_webhook_base_url() -> str:
    wh = _get_webhook_config().get("extra", {})
    host = wh.get("host", "0.0.0.0")
    port = wh.get("port", 8644)
    display_host = "localhost" if host == "0.0.0.0" else host
    return f"http://{display_host}:{port}"


def _setup_hint() -> str:
    _dhh = display_hermes_home()
    return f"""
  Webhook platform is not enabled. To set it up:

  1. Run the gateway setup wizard:
     bookworm gateway setup

  2. Or manually add to {_dhh}/config.yaml:
     platforms:
       webhook:
         enabled: true
         extra:
           host: "0.0.0.0"
           port: 8644
           secret: "your-global-hmac-secret"

  3. Or set environment variables in {_dhh}/.env:
     WEBHOOK_ENABLED=true
     WEBHOOK_PORT=8644
     WEBHOOK_SECRET=your-global-secret

  Then start the gateway: bookworm gateway run
"""


def _require_webhook_enabled() -> bool:
    """Check webhook is enabled. Print setup guide and return False if not."""
    if _is_webhook_enabled():
        return True
    print(_setup_hint())
    return False


def webhook_command(args):
    """Entry point for 'bookworm webhook' subcommand."""
    sub = getattr(args, "webhook_action", None)

    if not sub:
        print(_("Usage: bookworm webhook {subscribe|list|remove|test}"))
        print(_("Run 'bookworm webhook --help' for details."))
        return

    if not _require_webhook_enabled():
        return

    if sub in ("subscribe", "add"):
        _cmd_subscribe(args)
    elif sub in ("list", "ls"):
        _cmd_list(args)
    elif sub in ("remove", "rm"):
        _cmd_remove(args)
    elif sub == "test":
        _cmd_test(args)


def _cmd_subscribe(args):
    name = args.name.strip().lower().replace(" ", "-")
    if not re.match(r'^[a-z0-9][a-z0-9_-]*$', name):
        print(_("Error: Invalid name '{name}'. Use lowercase alphanumeric with hyphens/underscores.").format(name=name))
        return

    subs = _load_subscriptions()
    is_update = name in subs

    secret = args.secret or secrets.token_urlsafe(32)
    events = [e.strip() for e in args.events.split(",")] if args.events else []

    route = {
        "description": args.description or f"Agent-created subscription: {name}",
        "events": events,
        "secret": secret,
        "prompt": args.prompt or "",
        "skills": [s.strip() for s in args.skills.split(",")] if args.skills else [],
        "deliver": args.deliver or "log",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if getattr(args, "deliver_only", False):
        if route["deliver"] == "log":
            print(
                "Error: --deliver-only requires --deliver to be a real target "
                "(telegram, discord, slack, github_comment, etc.) — not 'log'."
            )
            return
        route["deliver_only"] = True

    if args.deliver_chat_id:
        route["deliver_extra"] = {"chat_id": args.deliver_chat_id}

    subs[name] = route
    _save_subscriptions(subs)

    base_url = _get_webhook_base_url()
    status = "Updated" if is_update else "Created"

    print(_("\n  {status} webhook subscription: {name}").format(status=status, name=name))
    print(_("  URL:    {base_url}/webhooks/{name}").format(base_url=base_url, name=name))
    print(_("  Secret: {secret}").format(secret=secret))
    if events:
        print(_("  Events: {join_events}").format(join_events=', '.join(events)))
    else:
        print(_("  Events: (all)"))
    print(_("  Deliver: {route}").format(route=route['deliver']))
    if route.get("deliver_only"):
        print(_("  Mode: direct delivery (no agent, zero LLM cost)"))
    if route.get("prompt"):
        prompt_preview = route["prompt"][:80] + ("..." if len(route["prompt"]) > 80 else "")
        label = "Message" if route.get("deliver_only") else "Prompt"
        print(f"  {label}: {prompt_preview}")
    print(_("\n  Configure your service to POST to the URL above."))
    print(_("  Use the secret for HMAC-SHA256 signature validation."))
    print(_("  The gateway must be running to receive events (bookworm gateway run).\n"))


def _cmd_list(args):
    subs = _load_subscriptions()
    if not subs:
        print(_("  No dynamic webhook subscriptions."))
        print(_("  Create one with: bookworm webhook subscribe <name>"))
        return

    base_url = _get_webhook_base_url()
    print(_("\n  {len} webhook subscription(s):\n").format(len=len(subs)))
    for name, route in subs.items():
        events = ", ".join(route.get("events", [])) or "(all)"
        deliver = route.get("deliver", "log")
        if route.get("deliver_only"):
            deliver = f"{deliver} (direct — no agent)"
        desc = route.get("description", "")
        print(f"  ◆ {name}")
        if desc:
            print(f"    {desc}")
        print(_("    URL:     {base_url}/webhooks/{name}").format(base_url=base_url, name=name))
        print(_("    Events:  {events}").format(events=events))
        print(_("    Deliver: {deliver}").format(deliver=deliver))
        print()


def _cmd_remove(args):
    name = args.name.strip().lower()
    subs = _load_subscriptions()

    if name not in subs:
        print(_("  No subscription named '{name}'.").format(name=name))
        print(_("  Note: Static routes from config.yaml cannot be removed here."))
        return

    del subs[name]
    _save_subscriptions(subs)
    print(_("  Removed webhook subscription: {name}").format(name=name))


def _cmd_test(args):
    """Send a test POST to a webhook route."""
    name = args.name.strip().lower()
    subs = _load_subscriptions()

    if name not in subs:
        print(_("  No subscription named '{name}'.").format(name=name))
        return

    route = subs[name]
    secret = route.get("secret", "")
    base_url = _get_webhook_base_url()
    url = f"{base_url}/webhooks/{name}"

    payload = args.payload or '{"test": true, "event_type": "test", "message": "Hello from bookworm webhook test"}'

    import hmac
    import hashlib
    sig = "sha256=" + hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    print(_("  Sending test POST to {url}").format(url=url))
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            data=payload.encode(),
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "test",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            print(_("  Response ({resp_status}): {body}").format(resp_status=resp.status, body=body))
    except Exception as e:
        print(_("  Error: {e}").format(e=e))
        print(_("  Is the gateway running? (bookworm gateway run)"))
