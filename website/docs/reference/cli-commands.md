---
sidebar_position: 1
title: "CLI Commands Reference"
description: "Authoritative reference for BookwormPRO terminal commands and command families"
---

# CLI Commands Reference

This page covers the **terminal commands** you run from your shell.

For in-chat slash commands, see [Slash Commands Reference](./slash-commands.md).

## Global entrypoint

```bash
bookworm [global-options] <command> [subcommand/options]
```

### Global options

| Option | Description |
|--------|-------------|
| `--version`, `-V` | Show version and exit. |
| `--profile <name>`, `-p <name>` | Select which BookwormPRO profile to use for this invocation. Overrides the sticky default set by `bookworm profile use`. |
| `--resume <session>`, `-r <session>` | Resume a previous session by ID or title. |
| `--continue [name]`, `-c [name]` | Resume the most recent session, or the most recent session matching a title. |
| `--worktree`, `-w` | Start in an isolated git worktree for parallel-agent workflows. |
| `--yolo` | Bypass dangerous-command approval prompts. |
| `--pass-session-id` | Include the session ID in the agent's system prompt. |
| `--ignore-user-config` | Ignore `~/.bookwormpro/config.yaml` and fall back to built-in defaults. Credentials in `.env` are still loaded. |
| `--ignore-rules` | Skip auto-injection of `AGENTS.md`, `SOUL.md`, `.cursorrules`, memory, and preloaded skills. |
| `--tui` | Launch the [TUI](../user-guide/tui.md) instead of the classic CLI. Equivalent to `BOOKWORMPRO_TUI=1`. |
| `--dev` | With `--tui`: run the TypeScript sources directly via `tsx` instead of the prebuilt bundle (for TUI contributors). |

## Top-level commands

| Command | Purpose |
|---------|---------|
| `bookworm chat` | Interactive or one-shot chat with the agent. |
| `bookworm model` | Interactively choose the default provider and model. |
| `bookworm gateway` | Run or manage the messaging gateway service. |
| `bookworm setup` | Interactive setup wizard for all or part of the configuration. |
| `bookworm whatsapp` | Configure and pair the WhatsApp bridge. |
| `bookworm auth` | Manage credentials — add, list, remove, reset, set strategy. Handles OAuth flows for Codex/BookwormPRO/Anthropic. |
| `bookworm login` / `logout` | **Deprecated** — use `bookworm auth` instead. |
| `bookworm status` | Show agent, auth, and platform status. |
| `bookworm cron` | Inspect and tick the cron scheduler. |
| `bookworm webhook` | Manage dynamic webhook subscriptions for event-driven activation. |
| `bookworm doctor` | Diagnose config and dependency issues. |
| `bookworm dump` | Copy-pasteable setup summary for support/debugging. |
| `bookworm debug` | Debug tools — upload logs and system info for support. |
| `bookworm backup` | Back up BookwormPRO home directory to a zip file. |
| `bookworm import` | Restore a BookwormPRO backup from a zip file. |
| `bookworm logs` | View, tail, and filter agent/gateway/error log files. |
| `bookworm config` | Show, edit, migrate, and query configuration files. |
| `bookworm pairing` | Approve or revoke messaging pairing codes. |
| `bookworm skills` | Browse, install, publish, audit, and configure skills. |
| `bookworm honcho` | Manage Honcho cross-session memory integration. |
| `bookworm memory` | Configure external memory provider. |
| `bookworm acp` | Run BookwormPRO as an ACP server for editor integration. |
| `bookworm mcp` | Manage MCP server configurations and run BookwormPRO as an MCP server. |
| `bookworm plugins` | Manage BookwormPRO plugins (install, enable, disable, remove). |
| `bookworm tools` | Configure enabled tools per platform. |
| `bookworm sessions` | Browse, export, prune, rename, and delete sessions. |
| `bookworm insights` | Show token/cost/activity analytics. |
| `bookworm claw` | OpenClaw migration helpers. |
| `bookworm dashboard` | Launch the web dashboard for managing config, API keys, and sessions. |
| `bookworm profile` | Manage profiles — multiple isolated BookwormPRO instances. |
| `bookworm completion` | Print shell completion scripts (bash/zsh). |
| `bookworm version` | Show version information. |
| `bookworm update` | Pull latest code and reinstall dependencies. |
| `bookworm uninstall` | Remove BookwormPRO from the system. |

## `bookworm chat`

```bash
bookworm chat [options]
```

Common options:

| Option | Description |
|--------|-------------|
| `-q`, `--query "..."` | One-shot, non-interactive prompt. |
| `-m`, `--model <model>` | Override the model for this run. |
| `-t`, `--toolsets <csv>` | Enable a comma-separated set of toolsets. |
| `--provider <provider>` | Force a provider: `auto`, `openrouter`, `bookwormpro`, `openai-codex`, `copilot-acp`, `copilot`, `anthropic`, `gemini`, `google-gemini-cli`, `huggingface`, `zai`, `kimi-coding`, `kimi-coding-cn`, `minimax`, `minimax-cn`, `kilocode`, `xiaomi`, `arcee`, `alibaba`, `deepseek`, `nvidia`, `ollama-cloud`, `xai` (alias `grok`), `qwen-oauth`, `bedrock`, `opencode-zen`, `opencode-go`, `ai-gateway`. |
| `-s`, `--skills <name>` | Preload one or more skills for the session (can be repeated or comma-separated). |
| `-v`, `--verbose` | Verbose output. |
| `-Q`, `--quiet` | Programmatic mode: suppress banner/spinner/tool previews. |
| `--image <path>` | Attach a local image to a single query. |
| `--resume <session>` / `--continue [name]` | Resume a session directly from `chat`. |
| `--worktree` | Create an isolated git worktree for this run. |
| `--checkpoints` | Enable filesystem checkpoints before destructive file changes. |
| `--yolo` | Skip approval prompts. |
| `--pass-session-id` | Pass the session ID into the system prompt. |
| `--ignore-user-config` | Ignore `~/.bookwormpro/config.yaml` and use built-in defaults. Credentials in `.env` are still loaded. Useful for isolated CI runs, reproducible bug reports, and third-party integrations. |
| `--ignore-rules` | Skip auto-injection of `AGENTS.md`, `SOUL.md`, `.cursorrules`, persistent memory, and preloaded skills. Combine with `--ignore-user-config` for a fully isolated run. |
| `--source <tag>` | Session source tag for filtering (default: `cli`). Use `tool` for third-party integrations that should not appear in user session lists. |
| `--max-turns <N>` | Maximum tool-calling iterations per conversation turn (default: 90, or `agent.max_turns` in config). |

Examples:

```bash
bookworm
bookworm chat -q "Summarize the latest PRs"
bookworm chat --provider openrouter --model anthropic/claude-sonnet-4.6
bookworm chat --toolsets web,terminal,skills
bookworm chat --quiet -q "Return only JSON"
bookworm chat --worktree -q "Review this repo and open a PR"
bookworm chat --ignore-user-config --ignore-rules -q "Repro without my personal setup"
```

## `bookworm model`

Interactive provider + model selector. **This is the command for adding new providers, setting up API keys, and running OAuth flows.** Run it from your terminal — not from inside an active BookwormPRO chat session.

```bash
bookworm model
```

Use this when you want to:
- **add a new provider** (OpenRouter, Anthropic, Copilot, DeepSeek, custom, etc.)
- log into OAuth-backed providers (Anthropic, Copilot, Codex, BookwormPRO Portal)
- enter or update API keys
- pick from provider-specific model lists
- configure a custom/self-hosted endpoint
- save the new default into config

:::warning bookworm model vs /model — know the difference
**`bookworm model`** (run from your terminal, outside any BookwormPRO session) is the **full provider setup wizard**. It can add new providers, run OAuth flows, prompt for API keys, and configure endpoints.

**`/model`** (typed inside an active BookwormPRO chat session) can only **switch between providers and models you've already set up**. It cannot add new providers, run OAuth, or prompt for API keys.

**If you need to add a new provider:** Exit your BookwormPRO session first (`Ctrl+C` or `/quit`), then run `bookworm model` from your terminal prompt.
:::

### `/model` slash command (mid-session)

Switch between already-configured models without leaving a session:

```
/model                              # Show current model and available options
/model claude-sonnet-4              # Switch model (auto-detects provider)
/model zai:glm-5                    # Switch provider and model
/model custom:qwen-2.5              # Use model on your custom endpoint
/model custom                       # Auto-detect model from custom endpoint
/model custom:local:qwen-2.5        # Use a named custom provider
/model openrouter:anthropic/claude-sonnet-4  # Switch back to cloud
```

By default, `/model` changes apply **to the current session only**. Add `--global` to persist the change to `config.yaml`:

```
/model claude-sonnet-4 --global     # Switch and save as new default
```

:::info What if I only see OpenRouter models?
If you've only configured OpenRouter, `/model` will only show OpenRouter models. To add another provider (Anthropic, DeepSeek, Copilot, etc.), exit your session and run `bookworm model` from the terminal.
:::

Provider and base URL changes are persisted to `config.yaml` automatically. When switching away from a custom endpoint, the stale base URL is cleared to prevent it leaking into other providers.

## `bookworm gateway`

```bash
bookworm gateway <subcommand>
```

Subcommands:

| Subcommand | Description |
|------------|-------------|
| `run` | Run the gateway in the foreground. Recommended for WSL, Docker, and Termux. |
| `start` | Start the installed systemd/launchd background service. |
| `stop` | Stop the service (or foreground process). |
| `restart` | Restart the service. |
| `status` | Show service status. |
| `install` | Install as a systemd (Linux) or launchd (macOS) background service. |
| `uninstall` | Remove the installed service. |
| `setup` | Interactive messaging-platform setup. |

:::tip WSL users
Use `bookworm gateway run` instead of `bookworm gateway start` — WSL's systemd support is unreliable. Wrap it in tmux for persistence: `tmux new -s bookworm 'bookworm gateway run'`. See [WSL FAQ](/docs/reference/faq#wsl-gateway-keeps-disconnecting-or-bookworm-gateway-start-fails) for details.
:::

## `bookworm setup`

```bash
bookworm setup [model|tts|terminal|gateway|tools|agent] [--non-interactive] [--reset]
```

Use the full wizard or jump into one section:

| Section | Description |
|---------|-------------|
| `model` | Provider and model setup. |
| `terminal` | Terminal backend and sandbox setup. |
| `gateway` | Messaging platform setup. |
| `tools` | Enable/disable tools per platform. |
| `agent` | Agent behavior settings. |

Options:

| Option | Description |
|--------|-------------|
| `--non-interactive` | Use defaults / environment values without prompts. |
| `--reset` | Reset configuration to defaults before setup. |

## `bookworm whatsapp`

```bash
bookworm whatsapp
```

Runs the WhatsApp pairing/setup flow, including mode selection and QR-code pairing.

## `bookworm login` / `bookworm logout` *(Deprecated)*

:::caution
`bookworm login` has been removed. Use `bookworm auth` to manage OAuth credentials, `bookworm model` to select a provider, or `bookworm setup` for full interactive setup.
:::

## `bookworm auth`

Manage credential pools for same-provider key rotation. See [Credential Pools](/docs/user-guide/features/credential-pools) for full documentation.

```bash
bookworm auth                                              # Interactive wizard
bookworm auth list                                         # Show all pools
bookworm auth list openrouter                              # Show specific provider
bookworm auth add openrouter --api-key sk-or-v1-xxx        # Add API key
bookworm auth add anthropic --type oauth                   # Add OAuth credential
bookworm auth remove openrouter 2                          # Remove by index
bookworm auth reset openrouter                             # Clear cooldowns
```

Subcommands: `add`, `list`, `remove`, `reset`. When called with no subcommand, launches the interactive management wizard.

## `bookworm status`

```bash
bookworm status [--all] [--deep]
```

| Option | Description |
|--------|-------------|
| `--all` | Show all details in a shareable redacted format. |
| `--deep` | Run deeper checks that may take longer. |

## `bookworm cron`

```bash
bookworm cron <list|create|edit|pause|resume|run|remove|status|tick>
```

| Subcommand | Description |
|------------|-------------|
| `list` | Show scheduled jobs. |
| `create` / `add` | Create a scheduled job from a prompt, optionally attaching one or more skills via repeated `--skill`. |
| `edit` | Update a job's schedule, prompt, name, delivery, repeat count, or attached skills. Supports `--clear-skills`, `--add-skill`, and `--remove-skill`. |
| `pause` | Pause a job without deleting it. |
| `resume` | Resume a paused job and compute its next future run. |
| `run` | Trigger a job on the next scheduler tick. |
| `remove` | Delete a scheduled job. |
| `status` | Check whether the cron scheduler is running. |
| `tick` | Run due jobs once and exit. |

## `bookworm webhook`

```bash
bookworm webhook <subscribe|list|remove|test>
```

Manage dynamic webhook subscriptions for event-driven agent activation. Requires the webhook platform to be enabled in config — if not configured, prints setup instructions.

| Subcommand | Description |
|------------|-------------|
| `subscribe` / `add` | Create a webhook route. Returns the URL and HMAC secret to configure on your service. |
| `list` / `ls` | Show all agent-created subscriptions. |
| `remove` / `rm` | Delete a dynamic subscription. Static routes from config.yaml are not affected. |
| `test` | Send a test POST to verify a subscription is working. |

### `bookworm webhook subscribe`

```bash
bookworm webhook subscribe <name> [options]
```

| Option | Description |
|--------|-------------|
| `--prompt` | Prompt template with `{dot.notation}` payload references. |
| `--events` | Comma-separated event types to accept (e.g. `issues,pull_request`). Empty = all. |
| `--description` | Human-readable description. |
| `--skills` | Comma-separated skill names to load for the agent run. |
| `--deliver` | Delivery target: `log` (default), `telegram`, `discord`, `slack`, `github_comment`. |
| `--deliver-chat-id` | Target chat/channel ID for cross-platform delivery. |
| `--secret` | Custom HMAC secret. Auto-generated if omitted. |

Subscriptions persist to `~/.bookwormpro/webhook_subscriptions.json` and are hot-reloaded by the webhook adapter without a gateway restart.

## `bookworm doctor`

```bash
bookworm doctor [--fix]
```

| Option | Description |
|--------|-------------|
| `--fix` | Attempt automatic repairs where possible. |

## `bookworm dump`

```bash
bookworm dump [--show-keys]
```

Outputs a compact, plain-text summary of your entire BookwormPRO setup. Designed to be copy-pasted into Discord, GitHub issues, or Telegram when asking for support — no ANSI colors, no special formatting, just data.

| Option | Description |
|--------|-------------|
| `--show-keys` | Show redacted API key prefixes (first and last 4 characters) instead of just `set`/`not set`. |

### What it includes

| Section | Details |
|---------|---------|
| **Header** | BookwormPRO version, release date, git commit hash |
| **Environment** | OS, Python version, OpenAI SDK version |
| **Identity** | Active profile name, BOOKWORMPRO_HOME path |
| **Model** | Configured default model and provider |
| **Terminal** | Backend type (local, docker, ssh, etc.) |
| **API keys** | Presence check for all 22 provider/tool API keys |
| **Features** | Enabled toolsets, MCP server count, memory provider |
| **Services** | Gateway status, configured messaging platforms |
| **Workload** | Cron job counts, installed skill count |
| **Config overrides** | Any config values that differ from defaults |

### Example output

```
--- bookworm dump ---
version:          0.8.0 (2026.4.8) [af4abd2f]
os:               Linux 6.14.0-37-generic x86_64
python:           3.11.14
openai_sdk:       2.24.0
profile:          default
hermes_home:      ~/.bookwormpro
model:            anthropic/claude-opus-4.6
provider:         openrouter
terminal:         local

api_keys:
  openrouter           set
  openai               not set
  anthropic            set
  bookwormpro                 not set
  firecrawl            set
  ...

features:
  toolsets:           all
  mcp_servers:        0
  memory_provider:    built-in
  gateway:            running (systemd)
  platforms:          telegram, discord
  cron_jobs:          3 active / 5 total
  skills:             42

config_overrides:
  agent.max_turns: 250
  compression.threshold: 0.85
  display.streaming: True
--- end dump ---
```

### When to use

- Reporting a bug on GitHub — paste the dump into your issue
- Asking for help in Discord — share it in a code block
- Comparing your setup to someone else's
- Quick sanity check when something isn't working

:::tip
`bookworm dump` is specifically designed for sharing. For interactive diagnostics, use `bookworm doctor`. For a visual overview, use `bookworm status`.
:::

## `bookworm debug`

```bash
bookworm debug share [options]
```

Upload a debug report (system info + recent logs) to a paste service and get a shareable URL. Useful for quick support requests — includes everything a helper needs to diagnose your issue.

| Option | Description |
|--------|-------------|
| `--lines <N>` | Number of log lines to include per log file (default: 200). |
| `--expire <days>` | Paste expiry in days (default: 7). |
| `--local` | Print the report locally instead of uploading. |

The report includes system info (OS, Python version, BookwormPRO version), recent agent and gateway logs (512 KB limit per file), and redacted API key status. Keys are always redacted — no secrets are uploaded.

Paste services tried in order: paste.rs, dpaste.com.

### Examples

```bash
bookworm debug share              # Upload debug report, print URL
bookworm debug share --lines 500  # Include more log lines
bookworm debug share --expire 30  # Keep paste for 30 days
bookworm debug share --local      # Print report to terminal (no upload)
```

## `bookworm backup`

```bash
bookworm backup [options]
```

Create a zip archive of your BookwormPRO configuration, skills, sessions, and data. The backup excludes the bookwormpro codebase itself.

| Option | Description |
|--------|-------------|
| `-o`, `--output <path>` | Output path for the zip file (default: `~/bookworm-backup-<timestamp>.zip`). |
| `-q`, `--quick` | Quick snapshot: only critical state files (config.yaml, state.db, .env, auth, cron jobs). Much faster than a full backup. |
| `-l`, `--label <name>` | Label for the snapshot (only used with `--quick`). |

The backup uses SQLite's `backup()` API for safe copying, so it works correctly even when BookwormPRO is running (WAL-mode safe).

### Examples

```bash
bookworm backup                           # Full backup to ~/bookworm-backup-*.zip
bookworm backup -o /tmp/bookworm.zip        # Full backup to specific path
bookworm backup --quick                   # Quick state-only snapshot
bookworm backup --quick --label "pre-upgrade"  # Quick snapshot with label
```

## `bookworm import`

```bash
bookworm import <zipfile> [options]
```

Restore a previously created BookwormPRO backup into your BookwormPRO home directory.

| Option | Description |
|--------|-------------|
| `-f`, `--force` | Overwrite existing files without confirmation. |

## `bookworm logs`

```bash
bookworm logs [log_name] [options]
```

View, tail, and filter BookwormPRO log files. All logs are stored in `~/.bookwormpro/logs/` (or `<profile>/logs/` for non-default profiles).

### Log files

| Name | File | What it captures |
|------|------|-----------------|
| `agent` (default) | `agent.log` | All agent activity — API calls, tool dispatch, session lifecycle (INFO and above) |
| `errors` | `errors.log` | Warnings and errors only — a filtered subset of agent.log |
| `gateway` | `gateway.log` | Messaging gateway activity — platform connections, message dispatch, webhook events |

### Options

| Option | Description |
|--------|-------------|
| `log_name` | Which log to view: `agent` (default), `errors`, `gateway`, or `list` to show available files with sizes. |
| `-n`, `--lines <N>` | Number of lines to show (default: 50). |
| `-f`, `--follow` | Follow the log in real time, like `tail -f`. Press Ctrl+C to stop. |
| `--level <LEVEL>` | Minimum log level to show: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `--session <ID>` | Filter lines containing a session ID substring. |
| `--since <TIME>` | Show lines from a relative time ago: `30m`, `1h`, `2d`, etc. Supports `s` (seconds), `m` (minutes), `h` (hours), `d` (days). |
| `--component <NAME>` | Filter by component: `gateway`, `agent`, `tools`, `cli`, `cron`. |

### Examples

```bash
# View the last 50 lines of agent.log (default)
bookworm logs

# Follow agent.log in real time
bookworm logs -f

# View the last 100 lines of gateway.log
bookworm logs gateway -n 100

# Show only warnings and errors from the last hour
bookworm logs --level WARNING --since 1h

# Filter by a specific session
bookworm logs --session abc123

# Follow errors.log, starting from 30 minutes ago
bookworm logs errors --since 30m -f

# List all log files with their sizes
bookworm logs list
```

### Filtering

Filters can be combined. When multiple filters are active, a log line must pass **all** of them to be shown:

```bash
# WARNING+ lines from the last 2 hours containing session "tg-12345"
bookworm logs --level WARNING --since 2h --session tg-12345
```

Lines without a parseable timestamp are included when `--since` is active (they may be continuation lines from a multi-line log entry). Lines without a detectable level are included when `--level` is active.

### Log rotation

BookwormPRO uses Python's `RotatingFileHandler`. Old logs are rotated automatically — look for `agent.log.1`, `agent.log.2`, etc. The `bookworm logs list` subcommand shows all log files including rotated ones.

## `bookworm config`

```bash
bookworm config <subcommand>
```

Subcommands:

| Subcommand | Description |
|------------|-------------|
| `show` | Show current config values. |
| `edit` | Open `config.yaml` in your editor. |
| `set <key> <value>` | Set a config value. |
| `path` | Print the config file path. |
| `env-path` | Print the `.env` file path. |
| `check` | Check for missing or stale config. |
| `migrate` | Add newly introduced options interactively. |

## `bookworm pairing`

```bash
bookworm pairing <list|approve|revoke|clear-pending>
```

| Subcommand | Description |
|------------|-------------|
| `list` | Show pending and approved users. |
| `approve <platform> <code>` | Approve a pairing code. |
| `revoke <platform> <user-id>` | Revoke a user's access. |
| `clear-pending` | Clear pending pairing codes. |

## `bookworm skills`

```bash
bookworm skills <subcommand>
```

Subcommands:

| Subcommand | Description |
|------------|-------------|
| `browse` | Paginated browser for skill registries. |
| `search` | Search skill registries. |
| `install` | Install a skill. |
| `inspect` | Preview a skill without installing it. |
| `list` | List installed skills. |
| `check` | Check installed hub skills for upstream updates. |
| `update` | Reinstall hub skills with upstream changes when available. |
| `audit` | Re-scan installed hub skills. |
| `uninstall` | Remove a hub-installed skill. |
| `publish` | Publish a skill to a registry. |
| `snapshot` | Export/import skill configurations. |
| `tap` | Manage custom skill sources. |
| `config` | Interactive enable/disable configuration for skills by platform. |

Common examples:

```bash
bookworm skills browse
bookworm skills browse --source official
bookworm skills search react --source skills-sh
bookworm skills search https://mintlify.com/docs --source well-known
bookworm skills inspect official/security/1password
bookworm skills inspect skills-sh/vercel-labs/json-render/json-render-react
bookworm skills install official/migration/openclaw-migration
bookworm skills install skills-sh/anthropics/skills/pdf --force
bookworm skills check
bookworm skills update
bookworm skills config
```

Notes:
- `--force` can override non-dangerous policy blocks for third-party/community skills.
- `--force` does not override a `dangerous` scan verdict.
- `--source skills-sh` searches the public `skills.sh` directory.
- `--source well-known` lets you point BookwormPRO at a site exposing `/.well-known/skills/index.json`.

## `bookworm honcho`

```bash
bookworm honcho [--target-profile NAME] <subcommand>
```

Manage Honcho cross-session memory integration. This command is provided by the Honcho memory provider plugin and is only available when `memory.provider` is set to `honcho` in your config.

The `--target-profile` flag lets you manage another profile's Honcho config without switching to it.

Subcommands:

| Subcommand | Description |
|------------|-------------|
| `setup` | Redirects to `bookworm memory setup` (unified setup path). |
| `status [--all]` | Show current Honcho config and connection status. `--all` shows a cross-profile overview. |
| `peers` | Show peer identities across all profiles. |
| `sessions` | List known Honcho session mappings. |
| `map [name]` | Map the current directory to a Honcho session name. Omit `name` to list current mappings. |
| `peer` | Show or update peer names and dialectic reasoning level. Options: `--user NAME`, `--ai NAME`, `--reasoning LEVEL`. |
| `mode [mode]` | Show or set recall mode: `hybrid`, `context`, or `tools`. Omit to show current. |
| `tokens` | Show or set token budgets for context and dialectic. Options: `--context N`, `--dialectic N`. |
| `identity [file] [--show]` | Seed or show the AI peer identity representation. |
| `enable` | Enable Honcho for the active profile. |
| `disable` | Disable Honcho for the active profile. |
| `sync` | Sync Honcho config to all existing profiles (creates missing host blocks). |
| `migrate` | Step-by-step migration guide from openclaw-honcho to BookwormPRO Honcho. |

## `bookworm memory`

```bash
bookworm memory <subcommand>
```

Set up and manage external memory provider plugins. Available providers: honcho, openviking, mem0, hindsight, holographic, retaindb, byterover, supermemory. Only one external provider can be active at a time. Built-in memory (MEMORY.md/USER.md) is always active.

Subcommands:

| Subcommand | Description |
|------------|-------------|
| `setup` | Interactive provider selection and configuration. |
| `status` | Show current memory provider config. |
| `off` | Disable external provider (built-in only). |

## `bookworm acp`

```bash
bookworm acp
```

Starts BookwormPRO as an ACP (Agent Client Protocol) stdio server for editor integration.

Related entrypoints:

```bash
bookworm-acp
python -m acp_adapter
```

Install support first:

```bash
pip install -e '.[acp]'
```

See [ACP Editor Integration](../user-guide/features/acp.md) and [ACP Internals](../developer-guide/acp-internals.md).

## `bookworm mcp`

```bash
bookworm mcp <subcommand>
```

Manage MCP (Model Context Protocol) server configurations and run BookwormPRO as an MCP server.

| Subcommand | Description |
|------------|-------------|
| `serve [-v\|--verbose]` | Run BookwormPRO as an MCP server — expose conversations to other agents. |
| `add <name> [--url URL] [--command CMD] [--args ...] [--auth oauth\|header]` | Add an MCP server with automatic tool discovery. |
| `remove <name>` (alias: `rm`) | Remove an MCP server from config. |
| `list` (alias: `ls`) | List configured MCP servers. |
| `test <name>` | Test connection to an MCP server. |
| `configure <name>` (alias: `config`) | Toggle tool selection for a server. |

See [MCP Config Reference](./mcp-config-reference.md), [Use MCP with BookwormPRO](../guides/use-mcp-with-bookworm.md), and [MCP Server Mode](../user-guide/features/mcp.md#running-bookworm-as-an-mcp-server).

## `bookworm plugins`

```bash
bookworm plugins [subcommand]
```

Unified plugin management — general plugins, memory providers, and context engines in one place. Running `bookworm plugins` with no subcommand opens a composite interactive screen with two sections:

- **General Plugins** — multi-select checkboxes to enable/disable installed plugins
- **Provider Plugins** — single-select configuration for Memory Provider and Context Engine. Press ENTER on a category to open a radio picker.

| Subcommand | Description |
|------------|-------------|
| *(none)* | Composite interactive UI — general plugin toggles + provider plugin configuration. |
| `install <identifier> [--force]` | Install a plugin from a Git URL or `owner/repo`. |
| `update <name>` | Pull latest changes for an installed plugin. |
| `remove <name>` (aliases: `rm`, `uninstall`) | Remove an installed plugin. |
| `enable <name>` | Enable a disabled plugin. |
| `disable <name>` | Disable a plugin without removing it. |
| `list` (alias: `ls`) | List installed plugins with enabled/disabled status. |

Provider plugin selections are saved to `config.yaml`:
- `memory.provider` — active memory provider (empty = built-in only)
- `context.engine` — active context engine (`"compressor"` = built-in default)

General plugin disabled list is stored in `config.yaml` under `plugins.disabled`.

See [Plugins](../user-guide/features/plugins.md) and [Build a BookwormPRO Plugin](../guides/build-a-bookworm-plugin.md).

## `bookworm tools`

```bash
bookworm tools [--summary]
```

| Option | Description |
|--------|-------------|
| `--summary` | Print the current enabled-tools summary and exit. |

Without `--summary`, this launches the interactive per-platform tool configuration UI.

## `bookworm sessions`

```bash
bookworm sessions <subcommand>
```

Subcommands:

| Subcommand | Description |
|------------|-------------|
| `list` | List recent sessions. |
| `browse` | Interactive session picker with search and resume. |
| `export <output> [--session-id ID]` | Export sessions to JSONL. |
| `delete <session-id>` | Delete one session. |
| `prune` | Delete old sessions. |
| `stats` | Show session-store statistics. |
| `rename <session-id> <title>` | Set or change a session title. |

## `bookworm insights`

```bash
bookworm insights [--days N] [--source platform]
```

| Option | Description |
|--------|-------------|
| `--days <n>` | Analyze the last `n` days (default: 30). |
| `--source <platform>` | Filter by source such as `cli`, `telegram`, or `discord`. |

## `bookworm claw`

```bash
bookworm claw migrate [options]
```

Migrate your OpenClaw setup to BookwormPRO. Reads from `~/.openclaw` (or a custom path) and writes to `~/.bookwormpro`. Automatically detects legacy directory names (`~/.clawdbot`, `~/.moltbot`) and config filenames (`clawdbot.json`, `moltbot.json`).

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview what would be migrated without writing anything. |
| `--preset <name>` | Migration preset: `full` (default, includes secrets) or `user-data` (excludes API keys). |
| `--overwrite` | Overwrite existing BookwormPRO files on conflicts (default: skip). |
| `--migrate-secrets` | Include API keys in migration (enabled by default with `--preset full`). |
| `--source <path>` | Custom OpenClaw directory (default: `~/.openclaw`). |
| `--workspace-target <path>` | Target directory for workspace instructions (AGENTS.md). |
| `--skill-conflict <mode>` | Handle skill name collisions: `skip` (default), `overwrite`, or `rename`. |
| `--yes` | Skip the confirmation prompt. |

### What gets migrated

The migration covers 30+ categories across persona, memory, skills, model providers, messaging platforms, agent behavior, session policies, MCP servers, TTS, and more. Items are either **directly imported** into BookwormPRO equivalents or **archived** for manual review.

**Directly imported:** SOUL.md, MEMORY.md, USER.md, AGENTS.md, skills (4 source directories), default model, custom providers, MCP servers, messaging platform tokens and allowlists (Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Mattermost), agent defaults (reasoning effort, compression, human delay, timezone, sandbox), session reset policies, approval rules, TTS config, browser settings, tool settings, exec timeout, command allowlist, gateway config, and API keys from 3 sources.

**Archived for manual review:** Cron jobs, plugins, hooks/webhooks, memory backend (QMD), skills registry config, UI/identity, logging, multi-agent setup, channel bindings, IDENTITY.md, TOOLS.md, HEARTBEAT.md, BOOTSTRAP.md.

**API key resolution** checks three sources in priority order: config values → `~/.openclaw/.env` → `auth-profiles.json`. All token fields handle plain strings, env templates (`${VAR}`), and SecretRef objects.

For the complete config key mapping, SecretRef handling details, and post-migration checklist, see the **[full migration guide](../guides/migrate-from-openclaw.md)**.

### Examples

```bash
# Preview what would be migrated
bookworm claw migrate --dry-run

# Full migration including API keys
bookworm claw migrate --preset full

# Migrate user data only (no secrets), overwrite conflicts
bookworm claw migrate --preset user-data --overwrite

# Migrate from a custom OpenClaw path
bookworm claw migrate --source /home/user/old-openclaw
```

## `bookworm dashboard`

```bash
bookworm dashboard [options]
```

Launch the web dashboard — a browser-based UI for managing configuration, API keys, and monitoring sessions. Requires `pip install bookwormpro[web]` (FastAPI + Uvicorn). See [Web Dashboard](/docs/user-guide/features/web-dashboard) for full documentation.

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | `9119` | Port to run the web server on |
| `--host` | `127.0.0.1` | Bind address |
| `--no-open` | — | Don't auto-open the browser |

```bash
# Default — opens browser to http://127.0.0.1:9119
bookworm dashboard

# Custom port, no browser
bookworm dashboard --port 8080 --no-open
```

## `bookworm profile`

```bash
bookworm profile <subcommand>
```

Manage profiles — multiple isolated BookwormPRO instances, each with its own config, sessions, skills, and home directory.

| Subcommand | Description |
|------------|-------------|
| `list` | List all profiles. |
| `use <name>` | Set a sticky default profile. |
| `create <name> [--clone] [--clone-all] [--clone-from <source>] [--no-alias]` | Create a new profile. `--clone` copies config, `.env`, and `SOUL.md` from the active profile. `--clone-all` copies all state. `--clone-from` specifies a source profile. |
| `delete <name> [-y]` | Delete a profile. |
| `show <name>` | Show profile details (home directory, config, etc.). |
| `alias <name> [--remove] [--name NAME]` | Manage wrapper scripts for quick profile access. |
| `rename <old> <new>` | Rename a profile. |
| `export <name> [-o FILE]` | Export a profile to a `.tar.gz` archive. |
| `import <archive> [--name NAME]` | Import a profile from a `.tar.gz` archive. |

Examples:

```bash
bookworm profile list
bookworm profile create work --clone
bookworm profile use work
bookworm profile alias work --name h-work
bookworm profile export work -o work-backup.tar.gz
bookworm profile import work-backup.tar.gz --name restored
bookworm -p work chat -q "Hello from work profile"
```

## `bookworm completion`

```bash
bookworm completion [bash|zsh]
```

Print a shell completion script to stdout. Source the output in your shell profile for tab-completion of BookwormPRO commands, subcommands, and profile names.

Examples:

```bash
# Bash
bookworm completion bash >> ~/.bashrc

# Zsh
bookworm completion zsh >> ~/.zshrc
```

## Maintenance commands

| Command | Description |
|---------|-------------|
| `bookworm version` | Print version information. |
| `bookworm update` | Pull latest changes and reinstall dependencies. |
| `bookworm uninstall [--full] [--yes]` | Remove BookwormPRO, optionally deleting all config/data. |

## See also

- [Slash Commands Reference](./slash-commands.md)
- [CLI Interface](../user-guide/cli.md)
- [Sessions](../user-guide/sessions.md)
- [Skills System](../user-guide/features/skills.md)
- [Skins & Themes](../user-guide/features/skins.md)
