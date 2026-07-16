"""
Doctor command for bookworm CLI.

Diagnoses issues with BookwormPRO setup.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

from bwm_cli.config import get_project_root, get_hermes_home, get_env_path
from bwm_constants import display_hermes_home

PROJECT_ROOT = get_project_root()
BOOKWORMPRO_HOME = get_hermes_home()
_DHH = display_hermes_home()  # user-facing display path (e.g. ~/.bookwormpro or ~/.bookwormpro/profiles/coder)

# Load environment variables from ~/.bookwormpro/.env so API key checks work
from dotenv import load_dotenv
_env_path = get_env_path()
if _env_path.exists():
    try:
        load_dotenv(_env_path, encoding="utf-8")
    except UnicodeDecodeError:
        load_dotenv(_env_path, encoding="latin-1")
# Also try project .env as dev fallback
load_dotenv(PROJECT_ROOT / ".env", override=False, encoding="utf-8")

from bwm_cli.colors import Colors, color
from bwm_cli.i18n import _
from bwm_cli.models import _HERMES_USER_AGENT
from bwm_constants import OPENROUTER_MODELS_URL
from utils import base_url_host_matches


_PROVIDER_ENV_HINTS = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_TOKEN",
    "OPENAI_BASE_URL",
    "NOUS_API_KEY",
    "GLM_API_KEY",
    "ZAI_API_KEY",
    "Z_AI_API_KEY",
    "KIMI_API_KEY",
    "KIMI_CN_API_KEY",
    "MINIMAX_API_KEY",
    "MINIMAX_CN_API_KEY",
    "KILOCODE_API_KEY",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
    "HF_TOKEN",
    "AI_GATEWAY_API_KEY",
    "OPENCODE_ZEN_API_KEY",
    "OPENCODE_GO_API_KEY",
    "XIAOMI_API_KEY",
)


from bwm_constants import is_termux as _is_termux


def _python_install_cmd() -> str:
    return "python -m pip install" if _is_termux() else "uv pip install"


def _system_package_install_cmd(pkg: str) -> str:
    if _is_termux():
        return f"pkg install {pkg}"
    if sys.platform == "darwin":
        return f"brew install {pkg}"
    return f"sudo apt install {pkg}"


def _termux_browser_setup_steps(node_installed: bool) -> list[str]:
    steps: list[str] = []
    step = 1
    if not node_installed:
        steps.append(f"{step}) pkg install nodejs")
        step += 1
    steps.append(f"{step}) npm install -g agent-browser")
    steps.append(f"{step + 1}) agent-browser install")
    return steps


def _has_provider_env_config(content: str) -> bool:
    """Return True when ~/.bookwormpro/.env contains provider auth/base URL settings."""
    return any(key in content for key in _PROVIDER_ENV_HINTS)


def _honcho_is_configured_for_doctor() -> bool:
    """Return True when Honcho is configured, even if this process has no active session."""
    try:
        from plugins.memory.honcho.client import HonchoClientConfig

        cfg = HonchoClientConfig.from_global_config()
        return bool(cfg.enabled and (cfg.api_key or cfg.base_url))
    except Exception:
        return False


def _apply_doctor_tool_availability_overrides(available: list[str], unavailable: list[dict]) -> tuple[list[str], list[dict]]:
    """Adjust runtime-gated tool availability for doctor diagnostics."""
    if not _honcho_is_configured_for_doctor():
        return available, unavailable

    updated_available = list(available)
    updated_unavailable = []
    for item in unavailable:
        if item.get("name") == "honcho":
            if "honcho" not in updated_available:
                updated_available.append("honcho")
            continue
        updated_unavailable.append(item)
    return updated_available, updated_unavailable


def check_ok(text: str, detail: str = ""):
    print(f"  {color('[成功]', Colors.GREEN)} {_(text)}" + (f" {color(_(detail), Colors.DIM)}" if detail else ""))

def check_warn(text: str, detail: str = ""):
    print(f"  {color('[警告]', Colors.YELLOW)} {_(text)}" + (f" {color(_(detail), Colors.DIM)}" if detail else ""))

def check_fail(text: str, detail: str = ""):
    print(f"  {color('[失败]', Colors.RED)} {_(text)}" + (f" {color(_(detail), Colors.DIM)}" if detail else ""))

def check_info(text: str):
    print(f"    {color('→', Colors.CYAN)} {_(text)}")


def _check_gateway_service_linger(issues: list[str]) -> None:
    """Warn when a systemd user gateway service will stop after logout."""
    try:
        from bwm_cli.gateway import (
            get_systemd_linger_status,
            get_systemd_unit_path,
            is_linux,
        )
    except Exception as e:
        check_warn("Gateway service linger", f"(could not import gateway helpers: {e})")
        return

    if not is_linux():
        return

    unit_path = get_systemd_unit_path()
    if not unit_path.exists():
        return

    print()
    print(color(_("◆ Gateway Service"), Colors.CYAN, Colors.BOLD))

    linger_enabled, linger_detail = get_systemd_linger_status()
    if linger_enabled is True:
        check_ok("Systemd linger enabled", "(gateway service survives logout)")
    elif linger_enabled is False:
        check_warn("Systemd linger disabled", "(gateway may stop after logout)")
        check_info("Run: sudo loginctl enable-linger $USER")
        issues.append(_("Enable linger for the gateway user service: sudo loginctl enable-linger $USER"))
    else:
        check_warn("Could not verify systemd linger", f"({linger_detail})")


def _check_runtime_fs_capability(issues: list[str]) -> None:
    """Report what filesystem the agent can actually touch in this runtime.

    Surfaces the native / host-bridge / container distinction up-front so
    users know whether 'delete this Desktop file' will work before they
    waste time hitting the trained 'sandbox' refusal.
    """
    print()
    print(color(_("◆ Runtime Filesystem Capability"), Colors.CYAN, Colors.BOLD))

    try:
        from bwm_constants import is_container, is_host_bridge_active, is_native_install, is_wsl
    except Exception as exc:
        check_warn("Could not import runtime detectors", f"({exc})")
        return

    if is_native_install():
        check_ok("Native install — full host filesystem access",
                 "(no sandbox; tools run as your user)")
    elif is_host_bridge_active():
        check_ok("Host bridge mounted",
                 "(/host/desktop and /host/workspace are read-write)")
    elif is_container():
        check_warn("Container runtime without host bridge",
                   "(only /opt/data is writable)")
        check_info("To allow Desktop access: see docs/host-bridge.md")
        issues.append(_("Mount host paths via docker-compose host bridge "
                      "if you need the agent to touch local files."))
    else:
        check_info("Runtime: unknown environment shape")

    if is_wsl():
        check_info("WSL detected — Windows host visible at /mnt/c/")


def _check_memory_health(issues: list[str]) -> None:
    """Surface the persistent-memory state so users know if recall is on."""
    print()
    print(color(_("◆ Persistent Memory"), Colors.CYAN, Colors.BOLD))

    try:
        from bwm_constants import get_hermes_home as _hh
    except Exception as exc:
        check_warn("Could not resolve BOOKWORMPRO_HOME", f"({exc})")
        return

    mem_dir = _hh() / "memories"
    user_md = mem_dir / "USER.md"
    mem_md = mem_dir / "MEMORY.md"

    def _entry_stats(path) -> tuple[int, int]:
        if not path.exists():
            return (0, 0)
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return (0, 0)
        # Entries are separated by '\n§\n'; the leading '§' counts an empty
        # opener, so subtract 1 when present.
        n = max(0, text.count("\n§\n"))
        if text.strip().startswith("§"):
            n += 1
        return (n, len(text))

    user_entries, user_chars = _entry_stats(user_md)
    mem_entries, mem_chars = _entry_stats(mem_md)
    USER_LIMIT = 1375
    MEM_LIMIT = 2200

    def _fmt(name, n_entries, n_chars, limit, path):
        if not path.exists():
            check_warn(f"{name}: missing", f"(will be auto-seeded on next start)")
            return
        pct = int(n_chars * 100 / limit) if limit else 0
        if pct >= 90:
            check_warn(f"{name}: {n_entries} entries · {n_chars}/{limit} chars",
                       f"({pct}% — pruning recommended)")
        elif n_entries == 0:
            check_warn(f"{name}: empty", "(no recall yet)")
        else:
            check_ok(f"{name}: {n_entries} entries", f"({n_chars}/{limit} chars · {pct}%)")

    _fmt("USER.md", user_entries, user_chars, USER_LIMIT, user_md)
    _fmt("MEMORY.md", mem_entries, mem_chars, MEM_LIMIT, mem_md)

    if not user_md.exists() and not mem_md.exists():
        issues.append(
            _("Memory files missing under {mem_dir}. They auto-seed from "
            "docker/seed/ on container start, or you can `bookworm` once "
            "and use the memory tool to add entries.").format(mem_dir=mem_dir)
        )

    # External provider hint
    try:
        import yaml
        cfg_path = _hh() / "config.yaml"
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            mem_cfg = cfg.get("memory") if isinstance(cfg, dict) else None
            provider = (mem_cfg or {}).get("provider") if isinstance(mem_cfg, dict) else None
            if provider:
                check_info(_("External provider: {provider} (additive on top of builtin)").format(provider=provider))
    except Exception:
        pass


def _check_prompt_cache_freshness(issues: list[str]) -> None:
    """Confirm the disk snapshot isn't stale relative to prompt-shaping code."""
    print()
    print(color(_("◆ Prompt Cache Freshness"), Colors.CYAN, Colors.BOLD))

    try:
        from agent.prompt_builder import (
            _max_code_dep_mtime,
            _skills_prompt_snapshot_path,
        )
    except Exception as exc:
        check_warn("Could not import prompt-builder helpers", f"({exc})")
        return

    snap_path = _skills_prompt_snapshot_path()
    if not snap_path.exists():
        check_info("No snapshot yet — first session will populate it")
        return

    try:
        import json as _json
        snap = _json.loads(snap_path.read_text(encoding="utf-8"))
    except Exception:
        check_warn("Snapshot exists but is unreadable", "(will rebuild on next start)")
        return

    snap_stamp = snap.get("code_dep_mtime_ns") if isinstance(snap, dict) else None
    code_mtime = _max_code_dep_mtime()

    if snap_stamp is None:
        check_warn("Snapshot is from before the self-heal feature",
                   "(will auto-rebuild on next start)")
        return
    if code_mtime and code_mtime > snap_stamp:
        diff_s = (code_mtime - snap_stamp) / 1e9
        check_warn(_("Snapshot is stale by {diff_s:.1f}s").format(diff_s=diff_s),
                   "(will auto-rebuild on next start)")
        check_info(_("Snapshot path: {snap_path}").format(snap_path=snap_path))
    else:
        check_ok("Snapshot is current with prompt-shaping code")


def run_doctor(args):
    """Run diagnostic checks."""
    should_fix = getattr(args, 'fix', False)

    # Doctor runs from the interactive CLI, so CLI-gated tool availability
    # checks (like cronjob management) should see the same context as `bookworm`.
    os.environ.setdefault("BOOKWORMPRO_INTERACTIVE", "1")

    issues = []
    manual_issues = []  # issues that can't be auto-fixed
    fixed_count = 0

    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color(_("│                 [体检] BookwormPRO Doctor                        │"), Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))

    # =========================================================================
    # Check: Python version
    # =========================================================================
    print()
    print(color(_("◆ Python Environment"), Colors.CYAN, Colors.BOLD))

    py_version = sys.version_info
    if py_version >= (3, 11):
        check_ok(_("Python {major}.{minor}.{micro}").format(major=py_version.major, minor=py_version.minor, micro=py_version.micro))
    elif py_version >= (3, 10):
        check_ok(_("Python {major}.{minor}.{micro}").format(major=py_version.major, minor=py_version.minor, micro=py_version.micro))
        check_warn("Python 3.11+ recommended for RL Training tools (tinker requires >= 3.11)")
    elif py_version >= (3, 8):
        check_warn(_("Python {major}.{minor}.{micro}").format(major=py_version.major, minor=py_version.minor, micro=py_version.micro), "(3.10+ recommended)")
    else:
        check_fail(_("Python {major}.{minor}.{micro}").format(major=py_version.major, minor=py_version.minor, micro=py_version.micro), "(3.10+ required)")
        issues.append(_("Upgrade Python to 3.10+"))

    # Check if in virtual environment
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        check_ok("Virtual environment active")
    else:
        check_warn("Not in virtual environment", "(recommended)")

    # =========================================================================
    # Check: Required packages
    # =========================================================================
    print()
    print(color(_("◆ Required Packages"), Colors.CYAN, Colors.BOLD))

    required_packages = [
        ("openai", "OpenAI SDK"),
        ("rich", "Rich (terminal UI)"),
        ("dotenv", "python-dotenv"),
        ("yaml", "PyYAML"),
        ("httpx", "HTTPX"),
    ]

    optional_packages = [
        ("croniter", "Croniter (cron expressions)"),
        ("telegram", "python-telegram-bot"),
        ("discord", "discord.py"),
    ]

    for module, name in required_packages:
        try:
            __import__(module)
            check_ok(name)
        except ImportError:
            check_fail(name, "(missing)")
            issues.append(_("Install {name}: {cmd} {module}").format(name=name, cmd=_python_install_cmd(), module=module))

    for module, name in optional_packages:
        try:
            __import__(module)
            check_ok(name, "(optional)")
        except ImportError:
            check_warn(name, "(optional, not installed)")

    # =========================================================================
    # Check: Configuration files
    # =========================================================================
    print()
    print(color(_("◆ Configuration Files"), Colors.CYAN, Colors.BOLD))

    # Check ~/.bookwormpro/.env (primary location for user config)
    env_path = BOOKWORMPRO_HOME / '.env'
    if env_path.exists():
        check_ok(_("{dhh}/.env file exists").format(dhh=_DHH))

        # Check for common issues
        content = env_path.read_text()
        if _has_provider_env_config(content):
            check_ok("API key or custom endpoint configured")
        else:
            check_warn(_("No API key found in {dhh}/.env").format(dhh=_DHH))
            issues.append(_("Run 'bookworm setup' to configure API keys"))
    else:
        # Also check project root as fallback
        fallback_env = PROJECT_ROOT / '.env'
        if fallback_env.exists():
            check_ok(".env file exists (in project directory)")
        else:
            check_fail(_("{dhh}/.env file missing").format(dhh=_DHH))
            if should_fix:
                env_path.parent.mkdir(parents=True, exist_ok=True)
                env_path.touch()
                check_ok(_("Created empty {dhh}/.env").format(dhh=_DHH))
                check_info("Run 'bookworm setup' to configure API keys")
                fixed_count += 1
            else:
                check_info("Run 'bookworm setup' to create one")
                issues.append(_("Run 'bookworm setup' to create .env"))

    # Check ~/.bookwormpro/config.yaml (primary) or project cli-config.yaml (fallback)
    config_path = BOOKWORMPRO_HOME / 'config.yaml'
    if config_path.exists():
        check_ok(_("{dhh}/config.yaml exists").format(dhh=_DHH))

        # Validate model.provider and model.default values
        try:
            import yaml as _yaml
            cfg = _yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            model_section = cfg.get("model") or {}
            provider_raw = (model_section.get("provider") or "").strip()
            provider = provider_raw.lower()
            default_model = (model_section.get("default") or model_section.get("model") or "").strip()

            known_providers: set = set()
            try:
                from bwm_cli.auth import PROVIDER_REGISTRY
                known_providers = set(PROVIDER_REGISTRY.keys()) | {"openrouter", "custom", "auto"}
            except Exception:
                pass
            try:
                from bwm_cli.config import get_compatible_custom_providers as _compatible_custom_providers
                from bwm_cli.providers import resolve_provider_full as _resolve_provider_full
            except Exception:
                _compatible_custom_providers = None
                _resolve_provider_full = None

            custom_providers = []
            if _compatible_custom_providers is not None:
                try:
                    custom_providers = _compatible_custom_providers(cfg)
                except Exception:
                    custom_providers = []

            user_providers = cfg.get("providers")
            if isinstance(user_providers, dict):
                known_providers.update(str(name).strip().lower() for name in user_providers if str(name).strip())
            for entry in custom_providers:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or "").strip()
                if name:
                    known_providers.add("custom:" + name.lower().replace(" ", "-"))

            canonical_provider = provider
            if provider and _resolve_provider_full is not None and provider != "auto":
                provider_def = _resolve_provider_full(provider, user_providers, custom_providers)
                canonical_provider = provider_def.id if provider_def is not None else None

            if provider and provider != "auto":
                if canonical_provider is None or (known_providers and canonical_provider not in known_providers):
                    known_list = ", ".join(sorted(known_providers)) if known_providers else "(unavailable)"
                    check_fail(
                        _("model.provider '{provider_raw}' is not a recognised provider").format(provider_raw=provider_raw),
                        _("(known: {known_list})").format(known_list=known_list),
                    )
                    issues.append(
                        _("model.provider '{provider_raw}' is unknown. "
                        "Valid providers: {known_list}. "
                        "Fix: run 'bookworm config set model.provider <valid_provider>'").format(provider_raw=provider_raw, known_list=known_list)
                    )

            # Warn if model is set to a provider-prefixed name on a provider that doesn't use them
            if default_model and "/" in default_model and canonical_provider and canonical_provider not in ("openrouter", "custom", "auto", "ai-gateway", "kilocode", "opencode-zen", "huggingface", "bookwormpro"):
                check_warn(
                    _("model.default '{default_model}' uses a vendor/model slug but provider is '{provider_raw}'").format(default_model=default_model, provider_raw=provider_raw),
                    "(vendor-prefixed slugs belong to aggregators like openrouter)",
                )
                issues.append(
                    _("model.default '{default_model}' is vendor-prefixed but model.provider is '{provider_raw}'. "
                    "Either set model.provider to 'openrouter', or drop the vendor prefix.").format(default_model=default_model, provider_raw=provider_raw)
                )

            # Check credentials for the configured provider.
            # Limit to API-key providers in PROVIDER_REGISTRY — other provider
            # types (OAuth, SDK, openrouter/anthropic/custom/auto) have their
            # own env-var checks elsewhere in doctor, and get_auth_status()
            # returns a bare {logged_in: False} for anything it doesn't
            # explicitly dispatch, which would produce false positives.
            if canonical_provider and canonical_provider not in ("auto", "custom", "openrouter"):
                try:
                    from bwm_cli.auth import PROVIDER_REGISTRY, get_auth_status
                    pconfig = PROVIDER_REGISTRY.get(canonical_provider)
                    if pconfig and getattr(pconfig, "auth_type", "") == "api_key":
                        status = get_auth_status(canonical_provider) or {}
                        configured = bool(status.get("configured") or status.get("logged_in") or status.get("api_key"))
                        if not configured:
                            check_fail(
                                _("model.provider '{canonical_provider}' is set but no API key is configured").format(canonical_provider=canonical_provider),
                                "(check ~/.bookwormpro/.env or run 'bookworm setup')",
                            )
                            issues.append(
                                _("No credentials found for provider '{canonical_provider}'. "
                                "Run 'bookworm setup' or set the provider's API key in {dhh}/.env, "
                                "or switch providers with 'bookworm config set model.provider <name>'").format(canonical_provider=canonical_provider, dhh=_DHH)
                            )
                except Exception:
                    pass

        except Exception as e:
            check_warn("Could not validate model/provider config", f"({e})")
    else:
        fallback_config = PROJECT_ROOT / 'cli-config.yaml'
        if fallback_config.exists():
            check_ok("cli-config.yaml exists (in project directory)")
        else:
            example_config = PROJECT_ROOT / 'cli-config.yaml.example'
            if should_fix and example_config.exists():
                config_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(example_config), str(config_path))
                check_ok(_("Created {dhh}/config.yaml from cli-config.yaml.example").format(dhh=_DHH))
                fixed_count += 1
            elif should_fix:
                check_warn("config.yaml not found and no example to copy from")
                manual_issues.append(_("Create {dhh}/config.yaml manually").format(dhh=_DHH))
            else:
                check_warn("config.yaml not found", "(using defaults)")

    # Check config version and stale keys
    config_path = BOOKWORMPRO_HOME / 'config.yaml'
    if config_path.exists():
        try:
            from bwm_cli.config import check_config_version, migrate_config
            current_ver, latest_ver = check_config_version()
            if current_ver < latest_ver:
                check_warn(
                    _("Config version outdated (v{current_ver} → v{latest_ver})").format(current_ver=current_ver, latest_ver=latest_ver),
                    "(new settings available)"
                )
                if should_fix:
                    try:
                        migrate_config(interactive=False, quiet=False)
                        check_ok("Config migrated to latest version")
                        fixed_count += 1
                    except Exception as mig_err:
                        check_warn(_("Auto-migration failed: {mig_err}").format(mig_err=mig_err))
                        issues.append(_("Run 'bookworm setup' to migrate config"))
                else:
                    issues.append(_("Run 'bookworm doctor --fix' or 'bookworm setup' to migrate config"))
            else:
                check_ok(_("Config version up to date (v{current_ver})").format(current_ver=current_ver))
        except Exception:
            pass

        # Detect stale root-level model keys (known bug source — PR #4329)
        try:
            import yaml
            with open(config_path) as f:
                raw_config = yaml.safe_load(f) or {}
            stale_root_keys = [k for k in ("provider", "base_url") if k in raw_config and isinstance(raw_config[k], str)]
            if stale_root_keys:
                check_warn(
                    _("Stale root-level config keys: {keys}").format(keys=", ".join(stale_root_keys)),
                    "(should be under 'model:' section)"
                )
                if should_fix:
                    model_section = raw_config.setdefault("model", {})
                    for k in stale_root_keys:
                        if not model_section.get(k):
                            model_section[k] = raw_config.pop(k)
                        else:
                            raw_config.pop(k)
                    from utils import atomic_yaml_write
                    atomic_yaml_write(config_path, raw_config)
                    check_ok("Migrated stale root-level keys into model section")
                    fixed_count += 1
                else:
                    issues.append(_("Stale root-level provider/base_url in config.yaml — run 'bookworm doctor --fix'"))
        except Exception:
            pass

        # Validate config structure (catches malformed custom_providers, etc.)
        try:
            from bwm_cli.config import validate_config_structure
            config_issues = validate_config_structure()
            if config_issues:
                print()
                print(color(_("◆ Config Structure"), Colors.CYAN, Colors.BOLD))
                for ci in config_issues:
                    if ci.severity == "error":
                        check_fail(ci.message)
                    else:
                        check_warn(ci.message)
                    # Show the hint indented
                    for hint_line in ci.hint.splitlines():
                        check_info(hint_line)
                    issues.append(ci.message)
        except Exception:
            pass

    # =========================================================================
    # Check: Auth providers
    # =========================================================================
    print()
    print(color(_("◆ Auth Providers"), Colors.CYAN, Colors.BOLD))

    try:
        from bwm_cli.auth import (
            get_nous_auth_status,
            get_codex_auth_status,
            get_gemini_oauth_auth_status,
        )

        nous_status = get_nous_auth_status()
        if nous_status.get("logged_in"):
            check_ok("BookwormPRO Portal auth", "(logged in)")
        else:
            check_warn("BookwormPRO Portal auth", "(not logged in)")

        codex_status = get_codex_auth_status()
        if codex_status.get("logged_in"):
            check_ok("OpenAI Codex auth", "(logged in)")
        else:
            check_warn("OpenAI Codex auth", "(not logged in)")
            if codex_status.get("error"):
                check_info(codex_status["error"])

        gemini_status = get_gemini_oauth_auth_status()
        if gemini_status.get("logged_in"):
            email = gemini_status.get("email") or ""
            project = gemini_status.get("project_id") or ""
            pieces = []
            if email:
                pieces.append(email)
            if project:
                pieces.append(f"project={project}")
            suffix = f" ({', '.join(pieces)})" if pieces else ""
            check_ok("Google Gemini OAuth", _("(logged in{suffix})").format(suffix=suffix))
        else:
            check_warn("Google Gemini OAuth", "(not logged in)")
    except Exception as e:
        check_warn("Auth provider status", _("(could not check: {e})").format(e=e))

    if shutil.which("codex"):
        check_ok("codex CLI")
    else:
        check_warn("codex CLI not found", "(required for openai-codex login)")

    # =========================================================================
    # Check: Directory structure
    # =========================================================================
    print()
    print(color(_("◆ Directory Structure"), Colors.CYAN, Colors.BOLD))

    hermes_home = BOOKWORMPRO_HOME
    if hermes_home.exists():
        check_ok(_("{dhh} directory exists").format(dhh=_DHH))
    else:
        if should_fix:
            hermes_home.mkdir(parents=True, exist_ok=True)
            check_ok(_("Created {dhh} directory").format(dhh=_DHH))
            fixed_count += 1
        else:
            check_warn(_("{dhh} not found").format(dhh=_DHH), "(will be created on first use)")

    # Check expected subdirectories
    expected_subdirs = ["cron", "sessions", "logs", "skills", "memories"]
    for subdir_name in expected_subdirs:
        subdir_path = hermes_home / subdir_name
        if subdir_path.exists():
            check_ok(_("{dhh}/{subdir_name}/ exists").format(dhh=_DHH, subdir_name=subdir_name))
        else:
            if should_fix:
                subdir_path.mkdir(parents=True, exist_ok=True)
                check_ok(_("Created {dhh}/{subdir_name}/").format(dhh=_DHH, subdir_name=subdir_name))
                fixed_count += 1
            else:
                check_warn(_("{dhh}/{subdir_name}/ not found").format(dhh=_DHH, subdir_name=subdir_name), "(will be created on first use)")

    # Check for SOUL.md persona file
    soul_path = hermes_home / "SOUL.md"
    if soul_path.exists():
        content = soul_path.read_text(encoding="utf-8").strip()
        # Check if it's just the template comments (no real content)
        lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith(("<!--", "-->", "#"))]
        if lines:
            check_ok(_("{dhh}/SOUL.md exists (persona configured)").format(dhh=_DHH))
        else:
            check_info(_("{dhh}/SOUL.md exists but is empty — edit it to customize personality").format(dhh=_DHH))
    else:
        check_warn(_("{dhh}/SOUL.md not found").format(dhh=_DHH), "(create it to give BookwormPRO a custom personality)")
        if should_fix:
            soul_path.parent.mkdir(parents=True, exist_ok=True)
            soul_path.write_text(
                "# BookwormPRO Persona\n\n"
                "<!-- Edit this file to customize how BookwormPRO communicates. -->\n\n"
                "You are BookwormPRO, a helpful AI assistant.\n",
                encoding="utf-8",
            )
            check_ok(_("Created {dhh}/SOUL.md with basic template").format(dhh=_DHH))
            fixed_count += 1

    # Check memory directory
    memories_dir = hermes_home / "memories"
    if memories_dir.exists():
        check_ok(_("{dhh}/memories/ directory exists").format(dhh=_DHH))
        memory_file = memories_dir / "MEMORY.md"
        user_file = memories_dir / "USER.md"
        if memory_file.exists():
            size = len(memory_file.read_text(encoding="utf-8").strip())
            check_ok(_("MEMORY.md exists ({size} chars)").format(size=size))
        else:
            check_info("MEMORY.md not created yet (will be created when the agent first writes a memory)")
        if user_file.exists():
            size = len(user_file.read_text(encoding="utf-8").strip())
            check_ok(_("USER.md exists ({size} chars)").format(size=size))
        else:
            check_info("USER.md not created yet (will be created when the agent first writes a memory)")
    else:
        check_warn(_("{dhh}/memories/ not found").format(dhh=_DHH), "(will be created on first use)")
        if should_fix:
            memories_dir.mkdir(parents=True, exist_ok=True)
            check_ok(_("Created {dhh}/memories/").format(dhh=_DHH))
            fixed_count += 1

    # Check SQLite session store
    state_db_path = hermes_home / "state.db"
    if state_db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(state_db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            count = cursor.fetchone()[0]
            conn.close()
            check_ok(_("{dhh}/state.db exists ({count} sessions)").format(dhh=_DHH, count=count))
        except Exception as e:
            check_warn(_("{dhh}/state.db exists but has issues: {e}").format(dhh=_DHH, e=e))
    else:
        check_info(_("{dhh}/state.db not created yet (will be created on first session)").format(dhh=_DHH))

    # Check WAL file size (unbounded growth indicates missed checkpoints)
    wal_path = hermes_home / "state.db-wal"
    if wal_path.exists():
        try:
            wal_size = wal_path.stat().st_size
            if wal_size > 50 * 1024 * 1024:  # 50 MB
                check_warn(
                    _("WAL file is large ({size} MB)").format(size=wal_size // (1024*1024)),
                    "(may indicate missed checkpoints)"
                )
                if should_fix:
                    import sqlite3
                    conn = sqlite3.connect(str(state_db_path))
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    conn.close()
                    new_size = wal_path.stat().st_size if wal_path.exists() else 0
                    check_ok(_("WAL checkpoint performed ({old}K → {new}K)").format(old=wal_size // 1024, new=new_size // 1024))
                    fixed_count += 1
                else:
                    issues.append(_("Large WAL file — run 'bookworm doctor --fix' to checkpoint"))
            elif wal_size > 10 * 1024 * 1024:  # 10 MB
                check_info(_("WAL file is {size} MB (normal for active sessions)").format(size=wal_size // (1024*1024)))
        except Exception:
            pass

    _check_gateway_service_linger(issues)

    # =========================================================================
    # Check: Command installation (bookworm bin symlink)
    # =========================================================================
    if sys.platform != "win32":
        print()
        print(color(_("◆ Command Installation"), Colors.CYAN, Colors.BOLD))

        # Determine the venv entry point location
        _venv_bin = None
        for _venv_name in ("venv", ".venv"):
            _candidate = PROJECT_ROOT / _venv_name / "bin" / "bookworm"
            if _candidate.exists():
                _venv_bin = _candidate
                break

        # Determine the expected command link directory (mirrors install.sh logic)
        _prefix = os.environ.get("PREFIX", "")
        _is_termux_env = bool(os.environ.get("TERMUX_VERSION")) or "com.termux/files/usr" in _prefix
        if _is_termux_env and _prefix:
            _cmd_link_dir = Path(_prefix) / "bin"
            _cmd_link_display = "$PREFIX/bin"
        else:
            _cmd_link_dir = Path.home() / ".local" / "bin"
            _cmd_link_display = "~/.local/bin"
        _cmd_link = _cmd_link_dir / "bookworm"

        if _venv_bin is None:
            check_warn(
                "Venv entry point not found",
                "(bookworm not in venv/bin/ or .venv/bin/ — reinstall with pip install -e '.[all]')"
            )
            manual_issues.append(
                _("Reinstall entry point: cd {project_root} && source venv/bin/activate && pip install -e '.[all]'").format(project_root=PROJECT_ROOT)
            )
        else:
            check_ok(_("Venv entry point exists ({venv_bin})").format(venv_bin=_venv_bin.relative_to(PROJECT_ROOT)))

            # Check the symlink at the command link location
            if _cmd_link.is_symlink():
                _target = _cmd_link.resolve()
                _expected = _venv_bin.resolve()
                if _target == _expected:
                    check_ok(_("{cmd_link_display}/bookworm → correct target").format(cmd_link_display=_cmd_link_display))
                else:
                    check_warn(
                        _("{cmd_link_display}/bookworm points to wrong target").format(cmd_link_display=_cmd_link_display),
                        _("(→ {target}, expected → {expected})").format(target=_target, expected=_expected)
                    )
                    if should_fix:
                        _cmd_link.unlink()
                        _cmd_link.symlink_to(_venv_bin)
                        check_ok(_("Fixed symlink: {cmd_link_display}/bookworm → {venv_bin}").format(cmd_link_display=_cmd_link_display, venv_bin=_venv_bin))
                        fixed_count += 1
                    else:
                        issues.append(_("Broken symlink at {cmd_link_display}/bookworm — run 'bookworm doctor --fix'").format(cmd_link_display=_cmd_link_display))
            elif _cmd_link.exists():
                # It's a regular file, not a symlink — possibly a wrapper script
                check_ok(_("{cmd_link_display}/bookworm exists (non-symlink)").format(cmd_link_display=_cmd_link_display))
            else:
                check_fail(
                    _("{cmd_link_display}/bookworm not found").format(cmd_link_display=_cmd_link_display),
                    "(bookworm command may not work outside the venv)"
                )
                if should_fix:
                    _cmd_link_dir.mkdir(parents=True, exist_ok=True)
                    _cmd_link.symlink_to(_venv_bin)
                    check_ok(_("Created symlink: {cmd_link_display}/bookworm → {venv_bin}").format(cmd_link_display=_cmd_link_display, venv_bin=_venv_bin))
                    fixed_count += 1

                    # Check if the link dir is on PATH
                    _path_dirs = os.environ.get("PATH", "").split(os.pathsep)
                    if str(_cmd_link_dir) not in _path_dirs:
                        check_warn(
                            _("{cmd_link_display} is not on your PATH").format(cmd_link_display=_cmd_link_display),
                            "(add it to your shell config: export PATH=\"$HOME/.local/bin:$PATH\")"
                        )
                        manual_issues.append(_("Add {cmd_link_display} to your PATH").format(cmd_link_display=_cmd_link_display))
                else:
                    issues.append(_("Missing {cmd_link_display}/bookworm symlink — run 'bookworm doctor --fix'").format(cmd_link_display=_cmd_link_display))

    # =========================================================================
    # Check: External tools
    # =========================================================================
    print()
    print(color(_("◆ External Tools"), Colors.CYAN, Colors.BOLD))

    # Git
    if shutil.which("git"):
        check_ok("git")
    else:
        check_warn("git not found", "(optional)")

    # ripgrep (optional, for faster file search)
    if shutil.which("rg"):
        check_ok("ripgrep (rg)", "(faster file search)")
    else:
        check_warn("ripgrep (rg) not found", "(file search uses grep fallback)")
        check_info(_("Install for faster search: {cmd}").format(cmd=_system_package_install_cmd('ripgrep')))

    # Docker (optional)
    terminal_env = os.getenv("TERMINAL_ENV", "local")
    if terminal_env == "docker":
        if shutil.which("docker"):
            # Check if docker daemon is running
            try:
                result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
            except subprocess.TimeoutExpired:
                result = None
            if result is not None and result.returncode == 0:
                check_ok("docker", "(daemon running)")
            else:
                check_fail("docker daemon not running")
                issues.append(_("Start Docker daemon"))
        else:
            check_fail("docker not found", "(required for TERMINAL_ENV=docker)")
            issues.append(_("Install Docker or change TERMINAL_ENV"))
    else:
        if shutil.which("docker"):
            check_ok("docker", "(optional)")
        else:
            if _is_termux():
                check_info("Docker backend is not available inside Termux (expected on Android)")
            else:
                check_warn("docker not found", "(optional)")

    # SSH (if using ssh backend)
    if terminal_env == "ssh":
        ssh_host = os.getenv("TERMINAL_SSH_HOST")
        if ssh_host:
            # Try to connect
            try:
                result = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", ssh_host, "echo ok"],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
            except subprocess.TimeoutExpired:
                result = None
            if result is not None and result.returncode == 0:
                check_ok(_("SSH connection to {ssh_host}").format(ssh_host=ssh_host))
            else:
                check_fail(_("SSH connection to {ssh_host}").format(ssh_host=ssh_host))
                issues.append(_("Check SSH configuration for {ssh_host}").format(ssh_host=ssh_host))
        else:
            check_fail("TERMINAL_SSH_HOST not set", "(required for TERMINAL_ENV=ssh)")
            issues.append(_("Set TERMINAL_SSH_HOST in .env"))

    # Daytona (if using daytona backend)
    if terminal_env == "daytona":
        daytona_key = os.getenv("DAYTONA_API_KEY")
        if daytona_key:
            check_ok("Daytona API key", "(configured)")
        else:
            check_fail("DAYTONA_API_KEY not set", "(required for TERMINAL_ENV=daytona)")
            issues.append(_("Set DAYTONA_API_KEY environment variable"))
        try:
            from daytona import Daytona  # noqa: F401 — SDK presence check
            check_ok("daytona SDK", "(installed)")
        except ImportError:
            check_fail("daytona SDK not installed", "(pip install daytona)")
            issues.append(_("Install daytona SDK: pip install daytona"))

    # Node.js + agent-browser (for browser automation tools)
    if shutil.which("node"):
        check_ok("Node.js")
        # Check if agent-browser is installed
        agent_browser_path = PROJECT_ROOT / "node_modules" / "agent-browser"
        if agent_browser_path.exists():
            check_ok("agent-browser (Node.js)", "(browser automation)")
        else:
            if _is_termux():
                check_info("agent-browser is not installed (expected in the tested Termux path)")
                check_info("Install it manually later with: npm install -g agent-browser && agent-browser install")
                check_info("Termux browser setup:")
                for step in _termux_browser_setup_steps(node_installed=True):
                    check_info(step)
            else:
                check_warn("agent-browser not installed", "(run: npm install)")
    else:
        if _is_termux():
            check_info("Node.js not found (browser tools are optional in the tested Termux path)")
            check_info("Install Node.js on Termux with: pkg install nodejs")
            check_info("Termux browser setup:")
            for step in _termux_browser_setup_steps(node_installed=False):
                check_info(step)
        else:
            check_warn("Node.js not found", "(optional, needed for browser tools)")

    # npm audit for all Node.js packages
    if shutil.which("npm"):
        npm_dirs = [
            (PROJECT_ROOT, "Browser tools (agent-browser)"),
            (PROJECT_ROOT / "scripts" / "whatsapp-bridge", "WhatsApp bridge"),
        ]
        for npm_dir, label in npm_dirs:
            if not (npm_dir / "node_modules").exists():
                continue
            try:
                audit_result = subprocess.run(
                    ["npm", "audit", "--json"],
                    cwd=str(npm_dir),
                    capture_output=True, text=True, timeout=30,
                )
                import json as _json
                audit_data = _json.loads(audit_result.stdout) if audit_result.stdout.strip() else {}
                vuln_count = audit_data.get("metadata", {}).get("vulnerabilities", {})
                critical = vuln_count.get("critical", 0)
                high = vuln_count.get("high", 0)
                moderate = vuln_count.get("moderate", 0)
                total = critical + high + moderate
                if total == 0:
                    check_ok(_("{label} deps").format(label=label), "(no known vulnerabilities)")
                elif critical > 0 or high > 0:
                    check_warn(
                        _("{label} deps").format(label=label),
                        _("({critical} critical, {high} high, {moderate} moderate — run: cd {npm_dir} && npm audit fix)").format(critical=critical, high=high, moderate=moderate, npm_dir=npm_dir)
                    )
                    issues.append(_("{label} has {total} npm vulnerability(ies)").format(label=label, total=total))
                else:
                    check_ok(_("{label} deps").format(label=label), _("({moderate} moderate vulnerability(ies))").format(moderate=moderate))
            except Exception:
                pass

    # =========================================================================
    # Check: API connectivity
    # =========================================================================
    print()
    print(color(_("◆ API Connectivity"), Colors.CYAN, Colors.BOLD))

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        print("  " + _("Checking OpenRouter API..."), end="", flush=True)
        try:
            import httpx
            response = httpx.get(
                OPENROUTER_MODELS_URL,
                headers={"Authorization": f"Bearer {openrouter_key}"},
                timeout=10
            )
            if response.status_code == 200:
                print(f"\r  {color('[成功]', Colors.GREEN)} " + _("OpenRouter API") + "                          ")
            elif response.status_code == 401:
                print(f"\r  {color('[失败]', Colors.RED)} " + _("OpenRouter API") + " " + color(_("(invalid API key)"), Colors.DIM) + "                ")
                issues.append(_("Check OPENROUTER_API_KEY in .env"))
            elif response.status_code == 402:
                print(f"\r  {color('[失败]', Colors.RED)} " + _("OpenRouter API") + " " + color(_("(out of credits — payment required)"), Colors.DIM))
                issues.append(
                    _("OpenRouter account has insufficient credits. "
                    "Fix: run 'bookworm config set model.provider <provider>' to switch providers, "
                    "or fund your OpenRouter account at https://openrouter.ai/settings/credits")
                )
            elif response.status_code == 429:
                print(f"\r  {color('[失败]', Colors.RED)} " + _("OpenRouter API") + " " + color(_("(rate limited)"), Colors.DIM) + "                ")
                issues.append(_("OpenRouter rate limit hit — consider switching to a different provider or waiting"))
            else:
                print(f"\r  {color('[失败]', Colors.RED)} " + _("OpenRouter API") + " " + color(_("(HTTP {status_code})").format(status_code=response.status_code), Colors.DIM) + "                ")
        except Exception as e:
            print(f"\r  {color('[失败]', Colors.RED)} " + _("OpenRouter API") + " " + color(f"({e})", Colors.DIM) + "                ")
            issues.append(_("Check network connectivity"))
    else:
        check_warn("OpenRouter API", "(not configured)")

    from bwm_cli.auth import get_anthropic_key
    anthropic_key = get_anthropic_key()
    if anthropic_key:
        print("  " + _("Checking Anthropic API..."), end="", flush=True)
        try:
            import httpx
            from agent.anthropic_adapter import _is_oauth_token, _COMMON_BETAS, _OAUTH_ONLY_BETAS

            headers = {"anthropic-version": "2023-06-01"}
            if _is_oauth_token(anthropic_key):
                headers["Authorization"] = f"Bearer {anthropic_key}"
                headers["anthropic-beta"] = ",".join(_COMMON_BETAS + _OAUTH_ONLY_BETAS)
            else:
                headers["x-api-key"] = anthropic_key
            response = httpx.get(
                "https://api.anthropic.com/v1/models",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                print(f"\r  {color('[成功]', Colors.GREEN)} " + _("Anthropic API") + "                           ")
            elif response.status_code == 401:
                print(f"\r  {color('[失败]', Colors.RED)} " + _("Anthropic API") + " " + color(_("(invalid API key)"), Colors.DIM) + "                 ")
            else:
                print(f"\r  {color('[警告]', Colors.YELLOW)} " + _("Anthropic API") + " " + color(_("(couldn't verify)"), Colors.DIM) + "                 ")
        except Exception as e:
            print(f"\r  {color('[警告]', Colors.YELLOW)} " + _("Anthropic API") + " " + color(f"({e})", Colors.DIM) + "                 ")

    # -- API-key providers --
    # Tuple: (name, env_vars, default_url, base_env, supports_models_endpoint)
    # If supports_models_endpoint is False, we skip the health check and just show "configured"
    _apikey_providers = [
        ("Z.AI / GLM",      ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"), "https://api.z.ai/api/paas/v4/models", "GLM_BASE_URL", True),
        ("Kimi / Moonshot",  ("KIMI_API_KEY",),                              "https://api.moonshot.ai/v1/models",   "KIMI_BASE_URL", True),
        ("StepFun Step Plan",   ("STEPFUN_API_KEY",),                           "https://api.stepfun.ai/step_plan/v1/models", "STEPFUN_BASE_URL", True),
        ("Kimi / Moonshot (China)", ("KIMI_CN_API_KEY",),                    "https://api.moonshot.cn/v1/models",   None, True),
        ("Arcee AI",         ("ARCEEAI_API_KEY",),                            "https://api.arcee.ai/api/v1/models",  "ARCEE_BASE_URL", True),
        ("DeepSeek",         ("DEEPSEEK_API_KEY",),                           "https://api.deepseek.com/v1/models",  "DEEPSEEK_BASE_URL", True),
        ("Hugging Face",     ("HF_TOKEN",),                                   "https://router.huggingface.co/v1/models", "HF_BASE_URL", True),
        ("NVIDIA NIM",       ("NVIDIA_API_KEY",),                             "https://integrate.api.nvidia.com/v1/models", "NVIDIA_BASE_URL", True),
        ("Alibaba/DashScope", ("DASHSCOPE_API_KEY",),                         "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models", "DASHSCOPE_BASE_URL", True),
        # MiniMax: the /anthropic endpoint doesn't support /models, but the /v1 endpoint does.
        ("MiniMax",          ("MINIMAX_API_KEY",),                            "https://api.minimax.io/v1/models",    "MINIMAX_BASE_URL", True),
        ("MiniMax (China)",  ("MINIMAX_CN_API_KEY",),                         "https://api.minimaxi.com/v1/models",  "MINIMAX_CN_BASE_URL", True),
        ("Vercel AI Gateway",       ("AI_GATEWAY_API_KEY",),                          "https://ai-gateway.vercel.sh/v1/models", "AI_GATEWAY_BASE_URL", True),
        ("Kilo Code",        ("KILOCODE_API_KEY",),                            "https://api.kilo.ai/api/gateway/models",  "KILOCODE_BASE_URL", True),
        ("OpenCode Zen",     ("OPENCODE_ZEN_API_KEY",),                        "https://opencode.ai/zen/v1/models",  "OPENCODE_ZEN_BASE_URL", True),
        # OpenCode Go has no shared /models endpoint; skip the health check.
        ("OpenCode Go",      ("OPENCODE_GO_API_KEY",),                         None,                                  "OPENCODE_GO_BASE_URL", False),
    ]
    for _pname, _env_vars, _default_url, _base_env, _supports_health_check in _apikey_providers:
        _key = ""
        for _ev in _env_vars:
            _key = os.getenv(_ev, "")
            if _key:
                break
        if _key:
            _label = _pname.ljust(20)
            # Some providers (like MiniMax) don't support /models endpoint
            if not _supports_health_check:
                print(f"  {color('[成功]', Colors.GREEN)} {_label} {color(_('(key configured)'), Colors.DIM)}")
                continue
            print("  " + _("Checking {pname} API...").format(pname=_pname), end="", flush=True)
            try:
                import httpx
                _base = os.getenv(_base_env, "") if _base_env else ""
                # Auto-detect Kimi Code keys (sk-kimi-) → api.kimi.com/coding/v1
                # (OpenAI-compat surface, which exposes /models for health check).
                if not _base and _key.startswith("sk-kimi-"):
                    _base = "https://api.kimi.com/coding/v1"
                # Anthropic-compat endpoints (/anthropic, api.kimi.com/coding
                # with no /v1) don't support /models.  Rewrite to the OpenAI-compat
                # /v1 surface for health checks.
                if _base and _base.rstrip("/").endswith("/anthropic"):
                    from agent.auxiliary_client import _to_openai_base_url
                    _base = _to_openai_base_url(_base)
                if base_url_host_matches(_base, "api.kimi.com") and _base.rstrip("/").endswith("/coding"):
                    _base = _base.rstrip("/") + "/v1"
                _url = (_base.rstrip("/") + "/models") if _base else _default_url
                _headers = {
                    "Authorization": f"Bearer {_key}",
                    "User-Agent": _HERMES_USER_AGENT,
                }
                if base_url_host_matches(_base, "api.kimi.com"):
                    _headers["User-Agent"] = "claude-code/0.1.0"
                _resp = httpx.get(
                    _url,
                    headers=_headers,
                    timeout=10,
                )
                if _resp.status_code == 200:
                    print(_("\r  {color} {_label}                          ").format(color=color('[成功]', Colors.GREEN), _label=_label))
                elif _resp.status_code == 401:
                    print(f"\r  {color('[失败]', Colors.RED)} {_label} {color(_('(invalid API key)'), Colors.DIM)}           ")
                    issues.append(_("Check {env_var} in .env").format(env_var=_env_vars[0]))
                else:
                    print(f"\r  {color('[警告]', Colors.YELLOW)} {_label} {color(_('(HTTP {status_code})').format(status_code=_resp.status_code), Colors.DIM)}           ")
            except Exception as _e:
                print(_("\r  {color} {_label} {color(f'({_e})', Colors.DIM)}           ").format(color=color('[警告]', Colors.YELLOW), _label=_label, _e=_e))

    # -- AWS Bedrock --
    # Bedrock uses the AWS SDK credential chain, not API keys.
    try:
        from agent.bedrock_adapter import has_aws_credentials, resolve_aws_auth_env_var, resolve_bedrock_region
        if has_aws_credentials():
            _auth_var = resolve_aws_auth_env_var()
            _region = resolve_bedrock_region()
            _label = "AWS Bedrock".ljust(20)
            print("  " + _("Checking AWS Bedrock..."), end="", flush=True)
            try:
                import boto3
                _br_client = boto3.client("bedrock", region_name=_region)
                _br_resp = _br_client.list_foundation_models()
                _model_count = len(_br_resp.get("modelSummaries", []))
                print(f"\r  {color('[成功]', Colors.GREEN)} {_label} {color(_('({auth_var}, {region}, {model_count} models)').format(auth_var=_auth_var, region=_region, model_count=_model_count), Colors.DIM)}           ")
            except ImportError:
                print(f"\r  {color('[警告]', Colors.YELLOW)} {_label} {color(_('(boto3 not installed — {exe} -m pip install boto3)').format(exe=sys.executable), Colors.DIM)}           ")
                issues.append(_("Install boto3 for Bedrock: {exe} -m pip install boto3").format(exe=sys.executable))
            except Exception as _e:
                _err_name = type(_e).__name__
                print(_("\r  {color} {_label} {color(f'({_err_name}: {_e})', Colors.DIM)}           ").format(color=color('[警告]', Colors.YELLOW), _label=_label, _err_name=_err_name, _e=_e))
                issues.append(_("AWS Bedrock: {err_name} — check IAM permissions for bedrock:ListFoundationModels").format(err_name=_err_name))
    except ImportError:
        pass  # bedrock_adapter not available — skip silently

    # =========================================================================
    # Check: Submodules
    # =========================================================================
    print()
    print(color(_("◆ Submodules"), Colors.CYAN, Colors.BOLD))

    # tinker-atropos (RL training backend)
    tinker_dir = PROJECT_ROOT / "tinker-atropos"
    if tinker_dir.exists() and (tinker_dir / "pyproject.toml").exists():
        if py_version >= (3, 11):
            try:
                __import__("tinker_atropos")
                check_ok("tinker-atropos", "(RL training backend)")
            except ImportError:
                install_cmd = f"{_python_install_cmd()} -e ./tinker-atropos"
                check_warn("tinker-atropos found but not installed", _("(run: {install_cmd})").format(install_cmd=install_cmd))
                issues.append(_("Install tinker-atropos: {install_cmd}").format(install_cmd=install_cmd))
        else:
            check_warn("tinker-atropos requires Python 3.11+", _("(current: {major}.{minor})").format(major=py_version.major, minor=py_version.minor))
    else:
        check_warn("tinker-atropos not found", "(run: git submodule update --init --recursive)")

    # =========================================================================
    # Check: Tool Availability
    # =========================================================================
    print()
    print(color(_("◆ Tool Availability"), Colors.CYAN, Colors.BOLD))

    try:
        # Add project root to path for imports
        sys.path.insert(0, str(PROJECT_ROOT))
        from model_tools import check_tool_availability, TOOLSET_REQUIREMENTS

        available, unavailable = check_tool_availability()
        available, unavailable = _apply_doctor_tool_availability_overrides(available, unavailable)

        for tid in available:
            info = TOOLSET_REQUIREMENTS.get(tid, {})
            check_ok(info.get("name", tid))

        for item in unavailable:
            env_vars = item.get("missing_vars") or item.get("env_vars") or []
            if env_vars:
                vars_str = ", ".join(env_vars)
                check_warn(item["name"], _("(missing {vars_str})").format(vars_str=vars_str))
            else:
                check_warn(item["name"], "(system dependency not met)")

        # Count disabled tools with API key requirements
        api_disabled = [u for u in unavailable if (u.get("missing_vars") or u.get("env_vars"))]
        if api_disabled:
            issues.append(_("Run 'bookworm setup' to configure missing API keys for full tool access"))
    except Exception as e:
        check_warn("Could not check tool availability", f"({e})")

    # =========================================================================
    # Check: Skills Hub
    # =========================================================================
    print()
    print(color(_("◆ Skills Hub"), Colors.CYAN, Colors.BOLD))

    hub_dir = BOOKWORMPRO_HOME / "skills" / ".hub"
    if hub_dir.exists():
        check_ok("Skills Hub directory exists")
        lock_file = hub_dir / "lock.json"
        if lock_file.exists():
            try:
                import json
                lock_data = json.loads(lock_file.read_text())
                count = len(lock_data.get("installed", {}))
                check_ok(_("Lock file OK ({count} hub-installed skill(s))").format(count=count))
            except Exception:
                check_warn("Lock file", "(corrupted or unreadable)")
        quarantine = hub_dir / "quarantine"
        q_count = sum(1 for d in quarantine.iterdir() if d.is_dir()) if quarantine.exists() else 0
        if q_count > 0:
            check_warn(_("{q_count} skill(s) in quarantine").format(q_count=q_count), "(pending review)")
    else:
        check_warn("Skills Hub directory not initialized", "(run: bookworm skills list)")

    from bwm_cli.config import get_env_value
    github_token = get_env_value("GITHUB_TOKEN") or get_env_value("GH_TOKEN")
    if github_token:
        check_ok("GitHub token configured (authenticated API access)")
    else:
        check_warn("No GITHUB_TOKEN", _("(60 req/hr rate limit — set in {dhh}/.env for better rates)").format(dhh=_DHH))

    # =========================================================================
    # Memory Provider (only check the active provider, if any)
    # =========================================================================
    print()
    print(color(_("◆ Memory Provider"), Colors.CYAN, Colors.BOLD))

    _active_memory_provider = ""
    try:
        import yaml as _yaml
        _mem_cfg_path = BOOKWORMPRO_HOME / "config.yaml"
        if _mem_cfg_path.exists():
            with open(_mem_cfg_path) as _f:
                _raw_cfg = _yaml.safe_load(_f) or {}
            _active_memory_provider = (_raw_cfg.get("memory") or {}).get("provider", "")
    except Exception:
        pass

    if not _active_memory_provider:
        check_ok("Built-in memory active", "(no external provider configured — this is fine)")
    elif _active_memory_provider == "honcho":
        try:
            from plugins.memory.honcho.client import HonchoClientConfig, resolve_config_path
            hcfg = HonchoClientConfig.from_global_config()
            _honcho_cfg_path = resolve_config_path()

            if not _honcho_cfg_path.exists():
                check_warn("Honcho config not found", "run: bookworm memory setup")
            elif not hcfg.enabled:
                check_info(_("Honcho disabled (set enabled: true in {honcho_cfg_path} to activate)").format(honcho_cfg_path=_honcho_cfg_path))
            elif not (hcfg.api_key or hcfg.base_url):
                check_fail("Honcho API key or base URL not set", "run: bookworm memory setup")
                issues.append(_("No Honcho API key — run 'bookworm memory setup'"))
            else:
                from plugins.memory.honcho.client import get_honcho_client, reset_honcho_client
                reset_honcho_client()
                try:
                    get_honcho_client(hcfg)
                    check_ok(
                        "Honcho connected",
                        f"workspace={hcfg.workspace_id} mode={hcfg.recall_mode} freq={hcfg.write_frequency}",
                    )
                except Exception as _e:
                    check_fail("Honcho connection failed", str(_e))
                    issues.append(_("Honcho unreachable: {e}").format(e=_e))
        except ImportError:
            check_fail("honcho-ai not installed", "pip install honcho-ai")
            issues.append(_("Honcho is set as memory provider but honcho-ai is not installed"))
        except Exception as _e:
            check_warn("Honcho check failed", str(_e))
    elif _active_memory_provider == "mem0":
        try:
            from plugins.memory.mem0 import _load_config as _load_mem0_config
            mem0_cfg = _load_mem0_config()
            mem0_key = mem0_cfg.get("api_key", "")
            if mem0_key:
                check_ok("Mem0 API key configured")
                check_info(f"user_id={mem0_cfg.get('user_id', '?')}  agent_id={mem0_cfg.get('agent_id', '?')}")
            else:
                check_fail("Mem0 API key not set", "(set MEM0_API_KEY in .env or run bookworm memory setup)")
                issues.append(_("Mem0 is set as memory provider but API key is missing"))
        except ImportError:
            check_fail("Mem0 plugin not loadable", "pip install mem0ai")
            issues.append(_("Mem0 is set as memory provider but mem0ai is not installed"))
        except Exception as _e:
            check_warn("Mem0 check failed", str(_e))
    else:
        # Generic check for other memory providers (openviking, hindsight, etc.)
        try:
            from plugins.memory import load_memory_provider
            _provider = load_memory_provider(_active_memory_provider)
            if _provider and _provider.is_available():
                check_ok(_("{provider} provider active").format(provider=_active_memory_provider))
            elif _provider:
                check_warn(_("{provider} configured but not available").format(provider=_active_memory_provider), "run: bookworm memory status")
            else:
                check_warn(_("{provider} plugin not found").format(provider=_active_memory_provider), "run: bookworm memory setup")
        except Exception as _e:
            check_warn(_("{provider} check failed").format(provider=_active_memory_provider), str(_e))

    # =========================================================================
    # Profiles
    # =========================================================================
    try:
        from bwm_cli.profiles import list_profiles, _get_wrapper_dir, profile_exists
        import re as _re

        named_profiles = [p for p in list_profiles() if not p.is_default]
        if named_profiles:
            print()
            print(color(_("◆ Profiles"), Colors.CYAN, Colors.BOLD))
            check_ok(_("{count} profile(s) found").format(count=len(named_profiles)))
            wrapper_dir = _get_wrapper_dir()
            for p in named_profiles:
                parts = []
                if p.gateway_running:
                    parts.append(_("gateway running"))
                if p.model:
                    parts.append(p.model[:30])
                if not (p.path / "config.yaml").exists():
                    parts.append(_("[警告] missing config"))
                if not (p.path / ".env").exists():
                    parts.append(_("no .env"))
                wrapper = wrapper_dir / p.name
                if not wrapper.exists():
                    parts.append(_("no alias"))
                status = ", ".join(parts) if parts else _("configured")
                check_ok(f"  {p.name}: {status}")

            # Check for orphan wrappers
            if wrapper_dir.is_dir():
                for wrapper in wrapper_dir.iterdir():
                    if not wrapper.is_file():
                        continue
                    try:
                        content = wrapper.read_text()
                        if "bookworm -p" in content:
                            _m = _re.search(r"bookworm -p (\S+)", content)
                            if _m and not profile_exists(_m.group(1)):
                                check_warn(_("Orphan alias: {wrapper_name} → profile '{profile}' no longer exists").format(wrapper_name=wrapper.name, profile=_m.group(1)))
                    except Exception:
                        pass
    except ImportError:
        pass
    except Exception:
        pass

    # =========================================================================
    # Check: Runtime filesystem capability
    # =========================================================================
    _check_runtime_fs_capability(issues)

    # =========================================================================
    # Check: Persistent memory health
    # =========================================================================
    _check_memory_health(issues)

    # =========================================================================
    # Check: Prompt cache freshness
    # =========================================================================
    _check_prompt_cache_freshness(issues)

    # =========================================================================
    # Summary
    # =========================================================================
    print()
    remaining_issues = issues + manual_issues
    if should_fix and fixed_count > 0:
        print(color("─" * 60, Colors.GREEN))
        print(color(_("  Fixed {fixed_count} issue(s).").format(fixed_count=fixed_count), Colors.GREEN, Colors.BOLD), end="")
        if remaining_issues:
            print(color(_(" {count} issue(s) require manual intervention.").format(count=len(remaining_issues)), Colors.YELLOW, Colors.BOLD))
        else:
            print()
        print()
        if remaining_issues:
            for i, issue in enumerate(remaining_issues, 1):
                print(f"  {i}. {issue}")
            print()
    elif remaining_issues:
        print(color("─" * 60, Colors.YELLOW))
        print(color(_("  Found {count} issue(s) to address:").format(count=len(remaining_issues)), Colors.YELLOW, Colors.BOLD))
        print()
        for i, issue in enumerate(remaining_issues, 1):
            print(f"  {i}. {issue}")
        print()
        if not should_fix:
            print(color(_("  Tip: run 'bookworm doctor --fix' to auto-fix what's possible."), Colors.DIM))
    else:
        print(color("─" * 60, Colors.GREEN))
        print(color(_("  All checks passed! [完成]"), Colors.GREEN, Colors.BOLD))

    print()
