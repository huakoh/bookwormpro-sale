# Host Bridge — Letting BookwormPRO Touch Your Real Files

By default the BookwormPRO container is a closed sandbox: it can read and write
inside `/opt/data` (mapped to `~/.bookwormpro` on the host) but nothing else. If
you ask it to delete a file on your Desktop, it will refuse with:

> Agent runs in a server-side sandbox — cannot access user's local filesystem
> or Desktop.

The host bridge is the supported way to lift that restriction for specific
host directories you choose.

## How It Works

`docker-compose.yml` mounts two host paths into the container:

| Container path     | Host path env var | Default                                  |
| ------------------ | ----------------- | ---------------------------------------- |
| `/host/desktop`    | `HOST_DESKTOP`    | `~/Desktop`                              |
| `/host/workspace`  | `HOST_WORKSPACE`  | `~/workspace` (parent of repo on setup)  |

Plus an env var `BOOKWORMPRO_HOST_BRIDGE=1` so the agent's seeded memory
knows the bridge is up and stops giving the "sandbox" excuse.

The seeded `MEMORY.md` (see `docker/seed/MEMORY.md`) instructs the agent to
translate Windows / macOS / Linux Desktop paths to `/host/desktop/<name>`
before calling read / write / terminal tools — so users don't have to know
the container path.

## Setup (one-time, per machine)

### Windows

```powershell
git clone https://github.com/huakoh/BookwormPRO.git
cd BookwormPRO
.\scripts\setup-host-bridge.ps1
docker compose up -d --build
```

The script auto-detects `%USERPROFILE%\Desktop` and the parent of the repo as
the workspace, asks you to confirm, and writes a `.env` file in the repo
root. Re-run any time to change the paths.

Non-interactive: `.\scripts\setup-host-bridge.ps1 -NonInteractive` (uses
detected defaults silently).

### macOS / Linux / WSL

```bash
git clone https://github.com/huakoh/BookwormPRO.git
cd BookwormPRO
./scripts/setup-host-bridge.sh
docker compose up -d --build
```

Non-interactive: `./scripts/setup-host-bridge.sh --yes`.

## Verification

```bash
docker exec bookworm ls /host/desktop | head
docker exec bookworm env | grep BOOKWORMPRO_HOST_BRIDGE
# expected: BOOKWORMPRO_HOST_BRIDGE=1
```

Then in chat:

> 列出我桌面上的所有 .json 文件
>
> 删除 `~/Desktop/old-audit.json`

The agent should now perform the operation rather than refusing.

## Security & Permissions

- Mounts are **read-write** by default. To make read-only, change the volume
  line in `docker-compose.yml` to `${HOST_DESKTOP:-~/Desktop}:/host/desktop:ro`.
- The agent runs as UID `BOOKWORMPRO_UID` (defaults to your host UID via
  `docker compose` when you set `BOOKWORMPRO_UID=$(id -u)`). Files it creates
  on the host are owned by that user.
- To **disable** the bridge, comment out the two volume lines and the
  `BOOKWORMPRO_HOST_BRIDGE` env var in `docker-compose.yml`. The agent
  reverts to refusing host access.
- Tirith content scanner (see `tools/tirith_security.py`) still inspects
  every shell command — the bridge does not bypass that layer.

## Scope Customization

To restrict the bridge to a sub-directory of Desktop instead of the entire
Desktop, set `HOST_DESKTOP` to that sub-path:

```bash
./scripts/setup-host-bridge.sh --desktop ~/Desktop/AgentSandbox --yes
```

Or edit `.env` directly:

```
HOST_DESKTOP=/Users/me/Desktop/AgentSandbox
HOST_WORKSPACE=/Users/me/repos
```

## Why Not Auto-Mount Everything?

Mounting the entire home directory would expose `~/.ssh`, `~/.aws`,
`~/.bookwormpro/.env` (which holds API keys), browser profiles, and other
secret-bearing paths to a tool-using agent. The bridge is intentionally
**opt-in and scoped** so each user picks exactly which directories the
agent can touch.
