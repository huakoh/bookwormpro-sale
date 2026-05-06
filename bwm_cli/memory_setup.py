"""bookworm memory setup|status — configure memory provider plugins.



Auto-detects installed memory providers via the plugin system.

Interactive curses-based UI for provider selection, then walks through

the provider's config schema. Writes config to config.yaml + .env.

"""



from __future__ import annotations



import getpass

import os

import sys

from pathlib import Path



from bwm_constants import get_hermes_home
from bwm_cli.i18n import _





# ---------------------------------------------------------------------------

# Curses-based interactive picker (same pattern as bookworm tools)

# ---------------------------------------------------------------------------



def _curses_select(title: str, items: list[tuple[str, str]], default: int = 0) -> int:

    """Interactive single-select with arrow keys.



    items: list of (label, description) tuples.

    Returns selected index, or default on escape/quit.

    """

    from bwm_cli.curses_ui import curses_radiolist

    # Format (label, desc) tuples into display strings

    display_items = [

        f"{label}  {desc}" if desc else label

        for label, desc in items

    ]

    return curses_radiolist(title, display_items, selected=default, cancel_returns=default)





def _prompt(label: str, default: str | None = None, secret: bool = False) -> str:

    """Prompt for a value with optional default and secret masking."""

    suffix = f" [{default}]" if default else ""

    if secret:

        sys.stdout.write(f"  {label}{suffix}: ")

        sys.stdout.flush()

        if sys.stdin.isatty():

            val = getpass.getpass(prompt="")

        else:

            val = sys.stdin.readline().strip()

    else:

        sys.stdout.write(f"  {label}{suffix}: ")

        sys.stdout.flush()

        val = sys.stdin.readline().strip()

    return val or (default or "")





# ---------------------------------------------------------------------------

# Provider discovery

# ---------------------------------------------------------------------------



def _install_dependencies(provider_name: str) -> None:

    """Install pip dependencies declared in plugin.yaml."""

    import subprocess

    from plugins.memory import find_provider_dir



    plugin_dir = find_provider_dir(provider_name)

    if not plugin_dir:

        return

    yaml_path = plugin_dir / "plugin.yaml"

    if not yaml_path.exists():

        return



    try:

        import yaml

        with open(yaml_path) as f:

            meta = yaml.safe_load(f) or {}

    except Exception:

        return



    pip_deps = meta.get("pip_dependencies", [])

    if not pip_deps:

        return



    # pip name → import name mapping for packages where they differ

    _IMPORT_NAMES = {

        "honcho-ai": "honcho",

        "mem0ai": "mem0",

        "hindsight-client": "hindsight_client",

        "hindsight-all": "hindsight",

    }



    # Check which packages are missing

    missing = []

    for dep in pip_deps:

        import_name = _IMPORT_NAMES.get(dep, dep.replace("-", "_").split("[")[0])

        try:

            __import__(import_name)

        except ImportError:

            missing.append(dep)



    if not missing:

        return



    print(_("\n  Installing dependencies: {join_missing}").format(join_missing=', '.join(missing)))



    import shutil

    uv_path = shutil.which("uv")

    if not uv_path:

        print(_("  [警告] uv not found — cannot install dependencies"))

        print(_("  Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"))

        print(_("  Then re-run: bookworm memory setup"))

        return



    try:

        subprocess.run(

            [uv_path, "pip", "install", "--python", sys.executable, "--quiet"] + missing,

            check=True, timeout=120,

            capture_output=True,

        )

        print(_("  [成功] Installed {join_missing}").format(join_missing=', '.join(missing)))

    except subprocess.CalledProcessError as e:

        print(_("  [警告] Failed to install {join_missing}").format(join_missing=', '.join(missing)))

        stderr = (e.stderr or b"").decode()[:200]

        if stderr:

            print(f"    {stderr}")

        print(_("  Run manually: uv pip install --python {sys_executable} {join_missing}").format(sys_executable=sys.executable, join_missing=' '.join(missing)))

    except Exception as e:

        print(_("  [警告] Install failed: {e}").format(e=e))

        print(_("  Run manually: uv pip install --python {sys_executable} {join_missing}").format(sys_executable=sys.executable, join_missing=' '.join(missing)))



    # Also show external dependencies (non-pip) if any

    import shlex as _shlex_mod

    # Whitelist of allowed binaries for external dependency checks.
    # Only these executables may be invoked via check_cmd from plugin.yaml.
    _ALLOWED_CHECK_BINARIES = frozenset({
        "docker", "ffmpeg", "ffprobe", "git", "node", "npm", "npx",
        "ollama", "python", "python3", "which", "where", "chroma",
        "java", "rustc", "cargo", "go", "gcc", "g++", "make", "cmake",
    })

    ext_deps = meta.get("external_dependencies", [])
    for dep in ext_deps:
        dep_name = dep.get("name", "")
        check_cmd = dep.get("check", "")
        install_cmd = dep.get("install", "")
        if check_cmd:
            try:
                check_args = _shlex_mod.split(check_cmd)
            except ValueError:
                print(_("\n  [警告] Invalid check command for '{dep_name}': {check_cmd}").format(dep_name=dep_name, check_cmd=check_cmd))
                continue
            if not check_args or check_args[0] not in _ALLOWED_CHECK_BINARIES:
                print(
                    f"\n  [警告] check command binary not in whitelist "
                    f"for '{dep_name}': {check_cmd}"
                )
                continue
            try:
                subprocess.run(
                    check_args, shell=False, capture_output=True, timeout=5
                )
            except Exception:
                if install_cmd:
                    print(_("\n  [警告] '{dep_name}' not found. Install with:").format(dep_name=dep_name))
                    print(f"    {install_cmd}")




def _get_available_providers() -> list:

    """Discover memory providers from plugins/memory/.



    Returns list of (name, description, provider_instance) tuples.

    """

    try:

        from plugins.memory import discover_memory_providers, load_memory_provider

        raw = discover_memory_providers()

    except Exception:

        raw = []



    results = []

    for name, desc, available in raw:

        try:

            provider = load_memory_provider(name)

            if not provider:

                continue

        except Exception:

            continue



        schema = provider.get_config_schema() if hasattr(provider, "get_config_schema") else []

        has_secrets = any(f.get("secret") for f in schema)

        has_non_secrets = any(not f.get("secret") for f in schema)

        if has_secrets and has_non_secrets:

            setup_hint = "API key / local"

        elif has_secrets:

            setup_hint = "requires API key"

        elif not schema:

            setup_hint = "no setup needed"

        else:

            setup_hint = "local"



        results.append((name, setup_hint, provider))

    return results





# ---------------------------------------------------------------------------

# Setup wizard

# ---------------------------------------------------------------------------



def cmd_setup_provider(provider_name: str) -> None:

    """Run memory setup for a specific provider, skipping the picker."""

    from bwm_cli.config import load_config, save_config



    providers = _get_available_providers()

    match = None

    for name, desc, provider in providers:

        if name == provider_name:

            match = (name, desc, provider)

            break



    if not match:

        print(_("\n  Memory provider '{provider_name}' not found.").format(provider_name=provider_name))

        print(_("  Run 'bookworm memory setup' to see available providers.\n"))

        return



    name, _, provider = match



    _install_dependencies(name)



    config = load_config()

    if not isinstance(config.get("memory"), dict):

        config["memory"] = {}



    if hasattr(provider, "post_setup"):

        hermes_home = str(get_hermes_home())

        provider.post_setup(hermes_home, config)

        return



    # Fallback: generic schema-based setup (same as cmd_setup)

    config["memory"]["provider"] = name

    save_config(config)

    print(_("\n  Memory provider: {name}").format(name=name))

    print(_("  Activation saved to config.yaml\n"))





def cmd_setup(args) -> None:

    """Interactive memory provider setup wizard."""

    from bwm_cli.config import load_config, save_config



    providers = _get_available_providers()



    if not providers:

        print(_("\n  No memory provider plugins detected."))

        print(_("  Install a plugin to ~/.bookwormpro/plugins/ and try again.\n"))

        return



    # Build picker items

    items = []

    for name, desc, _ in providers:

        items.append((name, f"— {desc}"))

    items.append(("Built-in only", "— MEMORY.md / USER.md (default)"))



    builtin_idx = len(items) - 1

    selected = _curses_select("Memory provider setup", items, default=builtin_idx)



    config = load_config()

    if not isinstance(config.get("memory"), dict):

        config["memory"] = {}



    # Built-in only

    if selected >= len(providers) or selected < 0:

        config["memory"]["provider"] = ""

        save_config(config)

        print(_("\n  [成功] Memory provider: built-in only"))

        print(_("  Saved to config.yaml\n"))

        return



    name, _, provider = providers[selected]



    # Install pip dependencies if declared in plugin.yaml

    _install_dependencies(name)



    # If the provider has a post_setup hook, delegate entirely to it.

    # The hook handles its own config, connection test, and activation.

    if hasattr(provider, "post_setup"):

        hermes_home = str(get_hermes_home())

        provider.post_setup(hermes_home, config)

        return



    schema = provider.get_config_schema() if hasattr(provider, "get_config_schema") else []



    provider_config = config["memory"].get(name, {})

    if not isinstance(provider_config, dict):

        provider_config = {}



    env_path = get_hermes_home() / ".env"

    env_writes = {}



    if schema:

        print(_("\n  Configuring {name}:\n").format(name=name))



        for field in schema:

            key = field["key"]

            desc = field.get("description", key)

            default = field.get("default")

            # Dynamic default: look up default from another field's value

            default_from = field.get("default_from")

            if default_from and isinstance(default_from, dict):

                ref_field = default_from.get("field", "")

                ref_map = default_from.get("map", {})

                ref_value = provider_config.get(ref_field, "")

                if ref_value and ref_value in ref_map:

                    default = ref_map[ref_value]

            is_secret = field.get("secret", False)

            choices = field.get("choices")

            env_var = field.get("env_var")

            url = field.get("url")



            # Skip fields whose "when" condition doesn't match

            when = field.get("when")

            if when and isinstance(when, dict):

                if not all(provider_config.get(k) == v for k, v in when.items()):

                    continue



            if choices and not is_secret:

                # Use curses picker for choice fields

                choice_items = [(c, "") for c in choices]

                current = provider_config.get(key, default)

                current_idx = 0

                if current and current in choices:

                    current_idx = choices.index(current)

                sel = _curses_select(f"  {desc}", choice_items, default=current_idx)

                provider_config[key] = choices[sel]

            elif is_secret:

                # Prompt for secret

                existing = os.environ.get(env_var, "") if env_var else ""

                if existing:

                    masked = f"...{existing[-4:]}" if len(existing) > 4 else "set"

                    val = _prompt(f"{desc} (current: {masked}, blank to keep)", secret=True)

                else:

                    hint = f"  Get yours at {url}" if url else ""

                    if hint:

                        print(hint)

                    val = _prompt(desc, secret=True)

                if val and env_var:

                    env_writes[env_var] = val

            else:

                # Regular text prompt

                current = provider_config.get(key)

                effective_default = current or default

                val = _prompt(desc, default=str(effective_default) if effective_default else None)

                if val:

                    provider_config[key] = val

                    # Also write to .env if this field has an env_var

                    if env_var and env_var not in env_writes:

                        env_writes[env_var] = val



    # Write activation key to config.yaml

    config["memory"]["provider"] = name

    save_config(config)



    # Write non-secret config to provider's native location

    hermes_home = str(get_hermes_home())

    if provider_config and hasattr(provider, "save_config"):

        try:

            provider.save_config(provider_config, hermes_home)

        except Exception as e:

            print(_("  Failed to write provider config: {e}").format(e=e))



    # Write secrets to .env

    if env_writes:

        _write_env_vars(env_path, env_writes)



    print(_("\n  Memory provider: {name}").format(name=name))

    print(_("  Activation saved to config.yaml"))

    if provider_config:

        print(_("  Provider config saved"))

    if env_writes:

        print(_("  API keys saved to .env"))

    print(_("\n  Start a new session to activate.\n"))





def _write_env_vars(env_path: Path, env_writes: dict) -> None:

    """Append or update env vars in .env file."""

    env_path.parent.mkdir(parents=True, exist_ok=True)



    existing_lines = []

    if env_path.exists():

        existing_lines = env_path.read_text().splitlines()



    updated_keys = set()

    new_lines = []

    for line in existing_lines:

        key_match = line.split("=", 1)[0].strip() if "=" in line else ""

        if key_match in env_writes:

            new_lines.append(f"{key_match}={env_writes[key_match]}")

            updated_keys.add(key_match)

        else:

            new_lines.append(line)



    for key, val in env_writes.items():

        if key not in updated_keys:

            new_lines.append(f"{key}={val}")



    env_path.write_text("\n".join(new_lines) + "\n")





# ---------------------------------------------------------------------------

# Status

# ---------------------------------------------------------------------------



def cmd_status(args) -> None:

    """Show current memory provider config."""

    from bwm_cli.config import load_config



    config = load_config()

    mem_config = config.get("memory", {})

    provider_name = mem_config.get("provider", "")



    print(_("\nMemory status\n") + "─" * 40)

    print(_("  Built-in:  always active"))

    print(_("  Provider:  {provider_name}").format(provider_name=provider_name or '(none — built-in only)'))



    if provider_name:

        provider_config = mem_config.get(provider_name, {})

        if provider_config:

            print(_("\n  {provider_name} config:").format(provider_name=provider_name))

            for key, val in provider_config.items():

                print(f"    {key}: {val}")



        providers = _get_available_providers()

        found = any(name == provider_name for name, _, _ in providers)

        if found:

            print(_("\n  Plugin:    installed [成功]"))

            for pname, _, p in providers:

                if pname == provider_name:

                    if p.is_available():

                        print(_("  Status:    available [成功]"))

                    else:

                        print(_("  Status:    not available [失败]"))

                        schema = p.get_config_schema() if hasattr(p, "get_config_schema") else []

                        # Check all fields that have env_var (both secret and non-secret)

                        required_fields = [f for f in schema if f.get("env_var")]

                        if required_fields:

                            print(_("  Missing:"))

                            for f in required_fields:

                                env_var = f.get("env_var", "")

                                url = f.get("url", "")

                                is_set = bool(os.environ.get(env_var))

                                mark = "[成功]" if is_set else "[失败]"

                                line = f"    {mark} {env_var}"

                                if url and not is_set:

                                    line += f"  → {url}"

                                print(line)

                    break

        else:

            print(_("\n  Plugin:    NOT installed [失败]"))

            print(_("  Install the '{provider_name}' memory plugin to ~/.bookwormpro/plugins/").format(provider_name=provider_name))



    providers = _get_available_providers()

    if providers:

        print(_("\n  Installed plugins:"))

        for pname, desc, _ in providers:

            active = " ← active" if pname == provider_name else ""

            print(f"    • {pname}  ({desc}){active}")



    print()





# ---------------------------------------------------------------------------

# Router

# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------

# show / why — built-in memory introspection

# ---------------------------------------------------------------------------



# Entry delimiter used by tools/memory_tool.py when persisting MEMORY.md

# entries.  Kept in lockstep with that module so split() yields the same

# units the agent itself reads.

_MEMORY_ENTRY_DELIM = "\n§\n"





def _builtin_memory_files() -> list[tuple[str, "Path"]]:

    """Return (label, path) tuples for built-in memory stores."""

    home = get_hermes_home()

    return [

        ("MEMORY.md", home / "memories" / "MEMORY.md"),

        ("USER.md", home / "memories" / "USER.md"),

    ]





def _split_entries(text: str) -> list[str]:

    """Split a memory file body into entries on the canonical delimiter."""

    if not text:

        return []

    return [chunk.strip() for chunk in text.split(_MEMORY_ENTRY_DELIM) if chunk.strip()]





def cmd_show(args) -> None:

    """Print contents of built-in memory stores with entry counts."""

    target = (getattr(args, "target", None) or "").strip().lower()

    files = _builtin_memory_files()

    if target in {"memory", "user"}:

        files = [(label, path) for label, path in files

                 if label.lower().startswith(target)]

    if not files:

        print(_("\n  No matching memory store.\n"))

        return



    print()

    for label, path in files:

        print(f"━━ {label} ━━ ({path})")

        if not path.exists():

            print(_("  (not present — nothing remembered yet)\n"))

            continue

        try:

            text = path.read_text(encoding="utf-8")

        except OSError as exc:

            print(_("  (read failed: {exc})\n").format(exc=exc))

            continue

        if not text.strip():

            print(_("  (empty)\n"))

            continue

        entries = _split_entries(text)

        size = path.stat().st_size

        print(_("  {len} entries · {size:,} bytes").format(len=len(entries), size=size))

        for idx, entry in enumerate(entries, 1):

            preview = entry if len(entry) <= 400 else entry[:397] + "..."

            print(_("\n  [{idx}]").format(idx=idx))

            for line in preview.splitlines():

                print(f"    {line}")

        print()





def cmd_why(args) -> None:

    """Find which memory entry surfaced a substring and explain its provenance.



    Helps users answer 'why does the agent think X?' by locating the source

    entry, its store, and the byte offset for direct editing.

    """

    needle = (getattr(args, "query", "") or "").strip()

    if not needle:

        print(_("\n  Usage: bookworm memory why <substring>\n"))

        return



    needle_lc = needle.lower()

    matches: list[tuple[str, "Path", int, str]] = []  # (label, path, idx, entry)

    for label, path in _builtin_memory_files():

        if not path.exists():

            continue

        try:

            text = path.read_text(encoding="utf-8")

        except OSError:

            continue

        for idx, entry in enumerate(_split_entries(text), 1):

            if needle_lc in entry.lower():

                matches.append((label, path, idx, entry))



    print()

    if not matches:

        print(_("  No memory entry mentions {needle}.").format(needle=repr(needle)))

        print(_("  The agent has no recorded reason — it may be inferring from"))

        print(_("  current context, project files, or skill defaults instead.\n"))

        return



    _n = len(matches)
    print(_("  找到 {n} 条匹配记忆条目，关键词: {needle}").format(n=_n, needle=repr(needle)))

    for label, path, idx, entry in matches:

        snippet = entry if len(entry) <= 600 else entry[:597] + "..."

        print(_("\n  ━━ {label} entry [{idx}] ━━").format(label=label, idx=idx))

        print(_("  source: {path}").format(path=path))

        for line in snippet.splitlines():

            print(f"    {line}")

    print()





# ---------------------------------------------------------------------------

# Router

# ---------------------------------------------------------------------------



def memory_command(args) -> None:

    """Route memory subcommands."""

    sub = getattr(args, "memory_command", None)

    if sub == "setup":

        cmd_setup(args)

    elif sub == "status":

        cmd_status(args)

    elif sub == "show":

        cmd_show(args)

    elif sub == "why":

        cmd_why(args)

    else:

        cmd_status(args)

