"""
Status command for bookworm CLI.

Shows the status of all BookwormPRO components.
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

from bwm_cli.auth import AuthError, resolve_provider
from bwm_cli.colors import Colors, color
from bwm_cli.config import get_env_path, get_env_value, get_hermes_home, load_config
from bwm_cli.models import provider_label
from bwm_cli.nous_subscription import get_nous_subscription_features
from bwm_cli.runtime_provider import resolve_requested_provider
from bwm_constants import OPENROUTER_MODELS_URL
from tools.tool_backend_helpers import managed_nous_tools_enabled

def check_mark(ok: bool) -> str:
    if ok:
        return color("[成功]", Colors.GREEN)
    return color("[失败]", Colors.RED)

def redact_key(key: str) -> str:
    """Redact an API key for display."""
    if not key:
        return "(not set)"
    if len(key) < 12:
        return "***"
    return key[:4] + "..." + key[-4:]


def _format_iso_timestamp(value) -> str:
    """Format ISO timestamps for status output, converting to local timezone."""
    if not value or not isinstance(value, str):
        return "(unknown)"
    from datetime import datetime, timezone
    text = value.strip()
    if not text:
        return "(unknown)"
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return value
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _configured_model_label(config: dict) -> str:
    """Return the configured default model from config.yaml."""
    model_cfg = config.get("model")
    if isinstance(model_cfg, dict):
        model = (model_cfg.get("default") or model_cfg.get("name") or "").strip()
    elif isinstance(model_cfg, str):
        model = model_cfg.strip()
    else:
        model = ""
    return model or "(not set)"


def _effective_provider_label() -> str:
    """Return the provider label matching current CLI runtime resolution."""
    requested = resolve_requested_provider()
    try:
        effective = resolve_provider(requested)
    except AuthError:
        effective = requested or "auto"

    if effective == "openrouter" and get_env_value("OPENAI_BASE_URL"):
        effective = "custom"

    return provider_label(effective)


from bwm_constants import is_termux as _is_termux
from bwm_cli.i18n import _



def show_status(args):
    """Show status of all BookwormPRO components."""
    show_all = getattr(args, 'all', False)
    deep = getattr(args, 'deep', False)
    
    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color(_("│                 [BWM] BookwormPRO Status                  │"), Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    
    # =========================================================================
    # Environment
    # =========================================================================
    print()
    print(color(_("◆ Environment"), Colors.CYAN, Colors.BOLD))
    print(_("  Project:      {PROJECT_ROOT}").format(PROJECT_ROOT=PROJECT_ROOT))
    print(_("  Python:       {sys}").format(sys=sys.version.split()[0]))
    
    env_path = get_env_path()
    print(f"  .env file:    {check_mark(env_path.exists())} {_('exists') if env_path.exists() else _('not found')}")

    try:
        config = load_config()
    except Exception:
        config = {}

    print(_("  Model:        {_configured_model_label}").format(_configured_model_label=_configured_model_label(config)))
    print(_("  Provider:     {_effective_provider_label}").format(_effective_provider_label=_effective_provider_label()))
    
    # =========================================================================
    # API Keys
    # =========================================================================
    print()
    print(color(_("◆ API Keys"), Colors.CYAN, Colors.BOLD))
    
    keys = {
        "OpenRouter": "OPENROUTER_API_KEY",
        "OpenAI": "OPENAI_API_KEY",
        "Z.AI/GLM": "GLM_API_KEY",
        "Kimi": "KIMI_API_KEY",
        "StepFun Step Plan": "STEPFUN_API_KEY",
        "MiniMax": "MINIMAX_API_KEY",
        "MiniMax-CN": "MINIMAX_CN_API_KEY",
        "Firecrawl": "FIRECRAWL_API_KEY",
        "Tavily": "TAVILY_API_KEY",
        "Browser Use": "BROWSER_USE_API_KEY",  # Optional — local browser works without this
        "Browserbase": "BROWSERBASE_API_KEY",  # Optional — direct credentials only
        "FAL": "FAL_KEY",
        "Tinker": "TINKER_API_KEY",
        "WandB": "WANDB_API_KEY",
        "ElevenLabs": "ELEVENLABS_API_KEY",
        "GitHub": "GITHUB_TOKEN",
    }
    
    for name, env_var in keys.items():
        value = get_env_value(env_var) or ""
        has_key = bool(value)
        display = redact_key(value) if not show_all else value
        print(f"  {name:<12}  {check_mark(has_key)} {display}")

    from bwm_cli.auth import get_anthropic_key
    anthropic_value = get_anthropic_key()
    anthropic_display = redact_key(anthropic_value) if not show_all else anthropic_value
    print(f"  {'Anthropic':<12}  {check_mark(bool(anthropic_value))} {anthropic_display}")

    # =========================================================================
    # Auth Providers (OAuth)
    # =========================================================================
    print()
    print(color(_("◆ Auth Providers"), Colors.CYAN, Colors.BOLD))

    try:
        from bwm_cli.auth import get_nous_auth_status, get_codex_auth_status, get_qwen_auth_status
        nous_status = get_nous_auth_status()
        codex_status = get_codex_auth_status()
        qwen_status = get_qwen_auth_status()
    except Exception:
        nous_status = {}
        codex_status = {}
        qwen_status = {}

    nous_logged_in = bool(nous_status.get("logged_in"))
    nous_error = nous_status.get("error")
    nous_label = _("logged in") if nous_logged_in else _("not logged in (run: bookworm auth add bookwormpro --type oauth)")
    print(
        f"  {'BookwormPRO Portal':<12}  {check_mark(nous_logged_in)} "
        f"{nous_label}"
    )
    portal_url = nous_status.get("portal_base_url") or "(unknown)"
    access_exp = _format_iso_timestamp(nous_status.get("access_expires_at"))
    key_exp = _format_iso_timestamp(nous_status.get("agent_key_expires_at"))
    refresh_label = "yes" if nous_status.get("has_refresh_token") else "no"
    if nous_logged_in or portal_url != "(unknown)" or nous_error:
        print(_("    Portal URL: {portal_url}").format(portal_url=portal_url))
    if nous_logged_in or nous_status.get("access_expires_at"):
        print(_("    Access exp: {access_exp}").format(access_exp=access_exp))
    if nous_logged_in or nous_status.get("agent_key_expires_at"):
        print(_("    Key exp:    {key_exp}").format(key_exp=key_exp))
    if nous_logged_in or nous_status.get("has_refresh_token"):
        print(_("    Refresh:    {refresh_label}").format(refresh_label=refresh_label))
    if nous_error and not nous_logged_in:
        print(_("    Error:      {nous_error}").format(nous_error=nous_error))

    codex_logged_in = bool(codex_status.get("logged_in"))
    print(
        f"  {'OpenAI Codex':<12}  {check_mark(codex_logged_in)} "
        f"{_('logged in') if codex_logged_in else _('not logged in (run: bookworm model)')}"
    )
    codex_auth_file = codex_status.get("auth_store")
    if codex_auth_file:
        print(_("    Auth file:  {codex_auth_file}").format(codex_auth_file=codex_auth_file))
    codex_last_refresh = _format_iso_timestamp(codex_status.get("last_refresh"))
    if codex_status.get("last_refresh"):
        print(_("    Refreshed:  {codex_last_refresh}").format(codex_last_refresh=codex_last_refresh))
    if codex_status.get("error") and not codex_logged_in:
        print(_("    Error:      {codex_status}").format(codex_status=codex_status.get('error')))

    qwen_logged_in = bool(qwen_status.get("logged_in"))
    print(
        f"  {'Qwen OAuth':<12}  {check_mark(qwen_logged_in)} "
        f"{_('logged in') if qwen_logged_in else _('not logged in (run: qwen auth qwen-oauth)')}"
    )
    qwen_auth_file = qwen_status.get("auth_file")
    if qwen_auth_file:
        print(_("    Auth file:  {qwen_auth_file}").format(qwen_auth_file=qwen_auth_file))
    qwen_exp = qwen_status.get("expires_at_ms")
    if qwen_exp:
        from datetime import datetime, timezone
        print(_("    Access exp: {datetime}").format(datetime=datetime.fromtimestamp(int(qwen_exp) / 1000, tz=timezone.utc).isoformat()))
    if qwen_status.get("error") and not qwen_logged_in:
        print(_("    Error:      {qwen_status}").format(qwen_status=qwen_status.get('error')))

    # =========================================================================
    # BookwormPRO Subscription Features
    # =========================================================================
    if managed_nous_tools_enabled():
        features = get_nous_subscription_features(config)
        print()
        print(color(_("◆ BookwormPRO Tool Gateway"), Colors.CYAN, Colors.BOLD))
        if not features.nous_auth_present:
            print("  BookwormPRO Portal   [失败] " + _("not logged in"))
        else:
            print("  BookwormPRO Portal   [成功] " + _("managed tools available"))
        for feature in features.items():
            if feature.managed_by_nous:
                state = _("active via BookwormPRO subscription")
            elif feature.active:
                current = feature.current_provider or _("configured provider")
                state = _("active via {current}").format(current=current)
            elif feature.included_by_default and features.nous_auth_present:
                state = _("included by subscription, not currently selected")
            elif feature.key == "modal" and features.nous_auth_present:
                state = _("available via subscription (optional)")
            else:
                state = _("not configured")
            print(f"  {feature.label:<15} {check_mark(feature.available or feature.active or feature.managed_by_nous)} {state}")
    elif nous_logged_in:
        # Logged into BookwormPRO but on the free tier — show upgrade nudge
        print()
        print(color(_("◆ BookwormPRO Tool Gateway"), Colors.CYAN, Colors.BOLD))
        print(_("  Your free-tier BookwormPRO account does not include Tool Gateway access."))
        print(_("  Upgrade your subscription to unlock managed web, image, TTS, and browser tools."))
        try:
            portal_url = nous_status.get("portal_base_url", "").rstrip("/")
            if portal_url:
                print(_("  Upgrade: {portal_url}").format(portal_url=portal_url))
        except Exception:
            pass

    # =========================================================================
    # API-Key Providers
    # =========================================================================
    print()
    print(color(_("◆ API-Key Providers"), Colors.CYAN, Colors.BOLD))

    apikey_providers = {
        "Z.AI / GLM":       ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
        "Kimi / Moonshot":  ("KIMI_API_KEY",),
        "StepFun Step Plan": ("STEPFUN_API_KEY",),
        "MiniMax":          ("MINIMAX_API_KEY",),
        "MiniMax (China)":  ("MINIMAX_CN_API_KEY",),
    }
    for pname, env_vars in apikey_providers.items():
        key_val = ""
        for ev in env_vars:
            key_val = get_env_value(ev) or ""
            if key_val:
                break
        configured = bool(key_val)
        label = "configured" if configured else "not configured (run: bookworm model)"
        print(f"  {pname:<16} {check_mark(configured)} {label}")

    # =========================================================================
    # Terminal Configuration
    # =========================================================================
    print()
    print(color(_("◆ Terminal Backend"), Colors.CYAN, Colors.BOLD))
    
    terminal_env = os.getenv("TERMINAL_ENV", "")
    if not terminal_env:
        # Fall back to config file value when env var isn't set
        # (bookworm status doesn't go through cli.py's config loading)
        try:
            _cfg = load_config()
            terminal_env = _cfg.get("terminal", {}).get("backend", "local")
        except Exception:
            terminal_env = "local"
    print(_("  Backend:      {terminal_env}").format(terminal_env=terminal_env))
    
    if terminal_env == "ssh":
        ssh_host = os.getenv("TERMINAL_SSH_HOST", "")
        ssh_user = os.getenv("TERMINAL_SSH_USER", "")
        print(_("  SSH Host:     {ssh_host}").format(ssh_host=ssh_host or '(not set)'))
        print(_("  SSH User:     {ssh_user}").format(ssh_user=ssh_user or '(not set)'))
    elif terminal_env == "docker":
        docker_image = os.getenv("TERMINAL_DOCKER_IMAGE", "python:3.11-slim")
        print(_("  Docker Image: {docker_image}").format(docker_image=docker_image))
    elif terminal_env == "daytona":
        daytona_image = os.getenv("TERMINAL_DAYTONA_IMAGE", "nikolaik/python-nodejs:python3.11-nodejs20")
        print(_("  Daytona Image: {daytona_image}").format(daytona_image=daytona_image))
    
    sudo_password = os.getenv("SUDO_PASSWORD", "")
    _sudo_state = '已启用' if sudo_password else '已禁用'
    print(f"  Sudo:         {check_mark(bool(sudo_password))} {_sudo_state}")
    
    # =========================================================================
    # Messaging Platforms
    # =========================================================================
    print()
    print(color(_("◆ Messaging Platforms"), Colors.CYAN, Colors.BOLD))
    
    platforms = {
        "Telegram": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_HOME_CHANNEL"),
        "Discord": ("DISCORD_BOT_TOKEN", "DISCORD_HOME_CHANNEL"),
        "WhatsApp": ("WHATSAPP_ENABLED", None),
        "Signal": ("SIGNAL_HTTP_URL", "SIGNAL_HOME_CHANNEL"),
        "Slack": ("SLACK_BOT_TOKEN", None),
        "Email": ("EMAIL_ADDRESS", "EMAIL_HOME_ADDRESS"),
        "SMS": ("TWILIO_ACCOUNT_SID", "SMS_HOME_CHANNEL"),
        "DingTalk": ("DINGTALK_CLIENT_ID", None),
        "Feishu": ("FEISHU_APP_ID", "FEISHU_HOME_CHANNEL"),
        "WeCom": ("WECOM_BOT_ID", "WECOM_HOME_CHANNEL"),
        "WeCom Callback": ("WECOM_CALLBACK_CORP_ID", None),
        "Weixin": ("WEIXIN_ACCOUNT_ID", "WEIXIN_HOME_CHANNEL"),
        "BlueBubbles": ("BLUEBUBBLES_SERVER_URL", "BLUEBUBBLES_HOME_CHANNEL"),
        "QQBot": ("QQ_APP_ID", "QQBOT_HOME_CHANNEL"),
    }
    
    for name, (token_var, home_var) in platforms.items():
        token = os.getenv(token_var, "")
        has_token = bool(token)
        
        home_channel = ""
        if home_var:
            home_channel = os.getenv(home_var, "")
        # Back-compat: QQBot home channel was renamed from QQ_HOME_CHANNEL to QQBOT_HOME_CHANNEL
        if not home_channel and home_var == "QQBOT_HOME_CHANNEL":
            home_channel = os.getenv("QQ_HOME_CHANNEL", "")
        
        status = "configured" if has_token else "not configured"
        if home_channel:
            status += f" (home: {home_channel})"
        
        print(f"  {name:<12}  {check_mark(has_token)} {status}")
    
    # =========================================================================
    # Gateway Status
    # =========================================================================
    print()
    print(color(_("◆ Gateway Service"), Colors.CYAN, Colors.BOLD))

    try:
        from bwm_cli.gateway import get_gateway_runtime_snapshot, _format_gateway_pids

        snapshot = get_gateway_runtime_snapshot()
        is_running = snapshot.running
        _gw_state = '运行中' if is_running else '已停止'
        print(f"  Status:       {check_mark(is_running)} {_gw_state}")
        print(_("  Manager:      {snapshot_manager}").format(snapshot_manager=snapshot.manager))
        if snapshot.gateway_pids:
            print(_("  PID(s):       {_format_gateway_pids}").format(_format_gateway_pids=_format_gateway_pids(snapshot.gateway_pids)))
        if snapshot.has_process_service_mismatch:
            print(_("  Service:      installed but not managing the current running gateway"))
        elif _is_termux() and not snapshot.gateway_pids:
            print(_("  Start with:   bookworm gateway"))
            print(_("  Note:         Android may stop background jobs when Termux is suspended"))
        elif snapshot.service_installed and not snapshot.service_running:
            print(_("  Service:      installed but stopped"))
    except Exception:
        if _is_termux():
            print(_("  Status:       {color}").format(color=color('unknown', Colors.DIM)))
            print(_("  Manager:      Termux / manual process"))
        elif sys.platform.startswith('linux'):
            print(_("  Status:       {color}").format(color=color('unknown', Colors.DIM)))
            print(_("  Manager:      systemd/manual"))
        elif sys.platform == 'darwin':
            print(_("  Status:       {color}").format(color=color('unknown', Colors.DIM)))
            print(_("  Manager:      launchd"))
        else:
            print(_("  Status:       {color}").format(color=color('N/A', Colors.DIM)))
            print(_("  Manager:      (not supported on this platform)"))
    
    # =========================================================================
    # Cron Jobs
    # =========================================================================
    print()
    print(color(_("◆ Scheduled Jobs"), Colors.CYAN, Colors.BOLD))
    
    jobs_file = get_hermes_home() / "cron" / "jobs.json"
    if jobs_file.exists():
        import json
        try:
            with open(jobs_file, encoding="utf-8") as f:
                data = json.load(f)
                jobs = data.get("jobs", [])
                enabled_jobs = [j for j in jobs if j.get("enabled", True)]
                print(_("  Jobs:         {len} active, {len_1} total").format(len=len(enabled_jobs), len_1=len(jobs)))
        except Exception:
            print(_("  Jobs:         (error reading jobs file)"))
    else:
        print(_("  Jobs:         0"))
    
    # =========================================================================
    # Sessions
    # =========================================================================
    print()
    print(color(_("◆ Sessions"), Colors.CYAN, Colors.BOLD))
    
    sessions_file = get_hermes_home() / "sessions" / "sessions.json"
    if sessions_file.exists():
        import json
        try:
            with open(sessions_file, encoding="utf-8") as f:
                data = json.load(f)
                print(_("  Active:       {len} session(s)").format(len=len(data)))
        except Exception:
            print(_("  Active:       (error reading sessions file)"))
    else:
        print(_("  Active:       0"))
    
    # =========================================================================
    # Deep checks
    # =========================================================================
    if deep:
        print()
        print(color(_("◆ Deep Checks"), Colors.CYAN, Colors.BOLD))
        
        # Check OpenRouter connectivity
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        if openrouter_key:
            try:
                import httpx
                response = httpx.get(
                    OPENROUTER_MODELS_URL,
                    headers={"Authorization": f"Bearer {openrouter_key}"},
                    timeout=10
                )
                ok = response.status_code == 200
                _or_state = '可访问' if ok else f'错误 ({response.status_code})'
                print(f"  OpenRouter:   {check_mark(ok)} {_or_state}")
            except Exception as e:
                print(_("  OpenRouter:   {check_mark} error: {e}").format(check_mark=check_mark(False), e=e))
        
        # Check gateway port
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 18789))
            sock.close()
            # Port in use = gateway likely running
            port_in_use = result == 0
            # This is informational, not necessarily bad
            _port_state = '已占用' if port_in_use else '可用'
            print(f"  Port 18789:   {_port_state}")
        except OSError:
            pass
    
    print()
    print(color("─" * 60, Colors.DIM))
    print(color(_("  Run 'bookworm doctor' for detailed diagnostics"), Colors.DIM))
    print(color(_("  Run 'bookworm setup' to configure"), Colors.DIM))
    print()
