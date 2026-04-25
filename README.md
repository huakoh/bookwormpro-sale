<p align="center">
  <img src="assets/banner.png" alt="BookwormPRO" width="100%">
</p>

# BookwormPRO ☤

<p align="center">
  <a href="https://bookwormpro.local/docs/"><img src="https://img.shields.io/badge/Docs-bookworm--agent.bookwormpro.local-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/BookwormPRO"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/huakoh/BookwormPRO/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://bookwormpro.local"><img src="https://img.shields.io/badge/Built%20by-BookwormPRO%20Research-blueviolet?style=for-the-badge" alt="Built by BookwormPRO Project"></a>
</p>

**The self-improving AI agent built by [BookwormPRO Project](https://bookwormpro.local).** It's the only agent with a built-in learning loop — it creates skills from experience, improves them during use, nudges itself to persist knowledge, searches its own past conversations, and builds a deepening model of who you are across sessions. Run it on a $5 VPS, a GPU cluster, or serverless infrastructure that costs nearly nothing when idle. It's not tied to your laptop — talk to it from Telegram while it works on a cloud VM.

Use any model you want — [BookwormPRO Portal](), [OpenRouter](https://openrouter.ai) (200+ models), [NVIDIA NIM](https://build.nvidia.com) (Nemotron), [Xiaomi MiMo](https://platform.xiaomimimo.com), [z.ai/GLM](https://z.ai), [Kimi/Moonshot](https://platform.moonshot.ai), [MiniMax](https://www.minimax.io), [Hugging Face](https://huggingface.co), OpenAI, or your own endpoint. Switch with `bookworm model` — no code changes, no lock-in.

<table>
<tr><td><b>A real terminal interface</b></td><td>Full TUI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output.</td></tr>
<tr><td><b>Lives where you do</b></td><td>Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process. Voice memo transcription, cross-platform conversation continuity.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall. <a href="https://github.com/plastic-labs/honcho">Honcho</a> dialectic user modeling. Compatible with the <a href="https://agentskills.io">agentskills.io</a> open standard.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with delivery to any platform. Daily reports, nightly backups, weekly audits — all in natural language, running unattended.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Six terminal backends — local, Docker, SSH, Daytona, Singularity, and Modal. Daytona and Modal offer serverless persistence — your agent's environment hibernates when idle and wakes on demand, costing nearly nothing between sessions. Run it on a $5 VPS or a GPU cluster.</td></tr>
<tr><td><b>Research-ready</b></td><td>Batch trajectory generation, Atropos RL environments, trajectory compression for training the next generation of tool-calling models.</td></tr>
</table>

---

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/huakoh/BookwormPRO/main/scripts/install.sh | bash
```

Works on Linux, macOS, WSL2, and Android via Termux. The installer handles the platform-specific setup for you.

> **Android / Termux:** The tested manual path is documented in the [Termux guide](https://bookwormpro.local/docs/getting-started/termux). On Termux, BookwormPRO installs a curated `.[termux]` extra because the full `.[all]` extra currently pulls Android-incompatible voice dependencies.
>
> **Windows:** Native Windows is not supported. Please install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) and run the command above.

After installation:

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
bookworm              # start chatting!
```

---

## Docker Compose (with host bridge)

Run BookwormPRO in Docker and let it operate on your real Desktop and
project files instead of an isolated sandbox.

**Linux / macOS / WSL:**

```bash
git clone https://github.com/huakoh/BookwormPRO.git
cd BookwormPRO
./scripts/setup-host-bridge.sh    # writes .env with detected host paths
docker compose up -d --build
```

**Windows (Docker Desktop):**

```powershell
git clone https://github.com/huakoh/BookwormPRO.git
cd BookwormPRO
.\scripts\setup-host-bridge.ps1
docker compose up -d --build
```

The setup scripts auto-detect your Desktop and a workspace root and write
them into a repo-root `.env`. The container then mounts them at
`/host/desktop` and `/host/workspace` and exports
`BOOKWORMPRO_HOST_BRIDGE=1` so the agent knows it can read, write, and
delete real local files. Full background, security model, and scope-
restriction options: [docs/host-bridge.md](docs/host-bridge.md).

To disable the bridge entirely, comment the two `/host/*` volume lines
and the `BOOKWORMPRO_HOST_BRIDGE` env var in `docker-compose.yml` — the
agent reverts to closed-sandbox behavior.

---

## Getting Started

```bash
bookworm              # Interactive CLI — start a conversation
bookworm model        # Choose your LLM provider and model
bookworm tools        # Configure which tools are enabled
bookworm config set   # Set individual config values
bookworm gateway      # Start the messaging gateway (Telegram, Discord, etc.)
bookworm setup        # Run the full setup wizard (configures everything at once)
bookworm claw migrate # Migrate from OpenClaw (if coming from OpenClaw)
bookworm update       # Update to the latest version
bookworm doctor       # Diagnose any issues
```

📖 **[Full documentation →](https://bookwormpro.local/docs/)**

## CLI vs Messaging Quick Reference

BookwormPRO has two entry points: start the terminal UI with `bookworm`, or run the gateway and talk to it from Telegram, Discord, Slack, WhatsApp, Signal, or Email. Once you're in a conversation, many slash commands are shared across both interfaces.

| Action | CLI | Messaging platforms |
|---------|-----|---------------------|
| Start chatting | `bookworm` | Run `bookworm gateway setup` + `bookworm gateway start`, then send the bot a message |
| Start fresh conversation | `/new` or `/reset` | `/new` or `/reset` |
| Change model | `/model [provider:model]` | `/model [provider:model]` |
| Set a personality | `/personality [name]` | `/personality [name]` |
| Retry or undo the last turn | `/retry`, `/undo` | `/retry`, `/undo` |
| Compress context / check usage | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]` |
| Browse skills | `/skills` or `/<skill-name>` | `/<skill-name>` |
| Interrupt current work | `Ctrl+C` or send a new message | `/stop` or send a new message |
| Platform-specific status | `/platforms` | `/status`, `/sethome` |

For the full command lists, see the [CLI guide](https://bookwormpro.local/docs/user-guide/cli) and the [Messaging Gateway guide](https://bookwormpro.local/docs/user-guide/messaging).

---

## Documentation

All documentation lives at **[bookwormpro.local/docs](https://bookwormpro.local/docs/)**:

| Section | What's Covered |
|---------|---------------|
| [Quickstart](https://bookwormpro.local/docs/getting-started/quickstart) | Install → setup → first conversation in 2 minutes |
| [CLI Usage](https://bookwormpro.local/docs/user-guide/cli) | Commands, keybindings, personalities, sessions |
| [Configuration](https://bookwormpro.local/docs/user-guide/configuration) | Config file, providers, models, all options |
| [Messaging Gateway](https://bookwormpro.local/docs/user-guide/messaging) | Telegram, Discord, Slack, WhatsApp, Signal, Home Assistant |
| [Security](https://bookwormpro.local/docs/user-guide/security) | Command approval, DM pairing, container isolation |
| [Tools & Toolsets](https://bookwormpro.local/docs/user-guide/features/tools) | 40+ tools, toolset system, terminal backends |
| [Skills System](https://bookwormpro.local/docs/user-guide/features/skills) | Procedural memory, Skills Hub, creating skills |
| [Memory](https://bookwormpro.local/docs/user-guide/features/memory) | Persistent memory, user profiles, best practices |
| [MCP Integration](https://bookwormpro.local/docs/user-guide/features/mcp) | Connect any MCP server for extended capabilities |
| [Cron Scheduling](https://bookwormpro.local/docs/user-guide/features/cron) | Scheduled tasks with platform delivery |
| [Context Files](https://bookwormpro.local/docs/user-guide/features/context-files) | Project context that shapes every conversation |
| [Architecture](https://bookwormpro.local/docs/developer-guide/architecture) | Project structure, agent loop, key classes |
| [Contributing](https://bookwormpro.local/docs/developer-guide/contributing) | Development setup, PR process, code style |
| [CLI Reference](https://bookwormpro.local/docs/reference/cli-commands) | All commands and flags |
| [Environment Variables](https://bookwormpro.local/docs/reference/environment-variables) | Complete env var reference |

---

## Migrating from OpenClaw

If you're coming from OpenClaw, BookwormPRO can automatically import your settings, memories, skills, and API keys.

**During first-time setup:** The setup wizard (`bookworm setup`) automatically detects `~/.openclaw` and offers to migrate before configuration begins.

**Anytime after install:**

```bash
bookworm claw migrate              # Interactive migration (full preset)
bookworm claw migrate --dry-run    # Preview what would be migrated
bookworm claw migrate --preset user-data   # Migrate without secrets
bookworm claw migrate --overwrite  # Overwrite existing conflicts
```

What gets imported:
- **SOUL.md** — persona file
- **Memories** — MEMORY.md and USER.md entries
- **Skills** — user-created skills → `~/.bookwormpro/skills/openclaw-imports/`
- **Command allowlist** — approval patterns
- **Messaging settings** — platform configs, allowed users, working directory
- **API keys** — allowlisted secrets (Telegram, OpenRouter, OpenAI, Anthropic, ElevenLabs)
- **TTS assets** — workspace audio files
- **Workspace instructions** — AGENTS.md (with `--workspace-target`)

See `bookworm claw migrate --help` for all options, or use the `openclaw-migration` skill for an interactive agent-guided migration with dry-run previews.

---

## Contributing

We welcome contributions! See the [Contributing Guide](https://bookwormpro.local/docs/developer-guide/contributing) for development setup, code style, and PR process.

Quick start for contributors — clone and go with `setup-bookworm.sh`:

```bash
git clone https://github.com/huakoh/BookwormPRO.git
cd bookwormpro
./setup-bookworm.sh     # installs uv, creates venv, installs .[all], symlinks ~/.local/bin/bookworm
./bookworm              # auto-detects the venv, no need to `source` first
```

Manual path (equivalent to the above):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv venv --python 3.11
source venv/bin/activate
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

> **RL Training (optional):** The RL/Atropos integration (`environments/`) ships via the `atroposlib` and `tinker` dependencies pulled in by `.[all,dev]` — no submodule setup required.

---

## Community

- [对话] [Discord](https://discord.gg/BookwormPRO)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/huakoh/BookwormPRO/issues)
- [网络] [HermesClaw](https://github.com/AaronWong1999/hermesclaw) — Community WeChat bridge: Run BookwormPRO and OpenClaw on the same WeChat account.

---

## License

MIT — see [LICENSE](LICENSE).

Built by [BookwormPRO Project](https://bookwormpro.local).
