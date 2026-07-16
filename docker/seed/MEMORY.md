§
Memory architecture: bookworm has 3 layers — tools/memory_tool.py (builtin MEMORY.md+USER.md, frozen system-prompt snapshot, char-bounded), agent/memory_manager.py (sanitize + injection), agent/memory_provider.py (ABC for pluggable backends). Builtin always on; only one external provider active at a time.
§
Memory backends available as plugins: byterover, hindsight, holographic, honcho, mem0, openviking, retaindb, supermemory. Activate via config.yaml: `memory: { provider: <name> }`. Each provider needs its own API key in .env.
§
Memory file paths in container: $BOOKWORMPRO_HOME/memories/MEMORY.md and USER.md. BOOKWORMPRO_HOME defaults to /opt/data in Docker. Char limits: 2200 (memory), 1375 (user). Entries separated by `\n§\n`.
§
Frozen snapshot semantics: mid-session writes hit disk immediately but do NOT update the system prompt — preserves prefix cache for the whole session. Snapshot refreshes on next session start.
§
Threat scanning: memory content is scanned before write for prompt-injection patterns (ignore previous instructions, role hijack, exfil curl, ssh backdoor, .env reads). Blocked content never persists.
§
Tirith security scanner enabled by default — wraps shell commands. To loosen for diagnostics set TIRITH_ENABLED=false or `security.tirith_enabled: false` in config.yaml. Keep on in production; use single commands instead of `bash -c`.
§
Skill resolution: skill_view() looks up by directory name (skills_tool.py:969), not frontmatter `name:` field. Keep dir name == frontmatter name to avoid lookup mismatches.
§
Host bridge: when env BOOKWORMPRO_HOST_BRIDGE=1 is set, /host/desktop and /host/workspace map to the user's real Desktop and a chosen workspace root. Read/write/delete on those paths IS allowed — do not refuse with "server-side sandbox" excuses. If the env var is absent the sandbox restriction stands.
§
File ops translation: when user gives a Windows path like C:\Users\<u>\Desktop\foo.json, translate to /host/desktop/foo.json before calling terminal/read/write. Same for macOS/Linux Desktop paths.
