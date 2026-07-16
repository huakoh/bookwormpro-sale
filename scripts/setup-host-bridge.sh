#!/usr/bin/env bash
# ============================================================================
# BookwormPRO — Host Bridge Setup (Linux / macOS / WSL)
# ============================================================================
# Generates a `.env` file in the repo root that maps your real host paths
# into the Docker container, so the agent can read/write/delete files on
# your actual Desktop and project workspace instead of being confined to
# the in-container sandbox.
#
# Run once after cloning:
#   ./scripts/setup-host-bridge.sh
#
# Flags:
#   --desktop <path>     skip prompt for HOST_DESKTOP
#   --workspace <path>   skip prompt for HOST_WORKSPACE
#   --force              overwrite existing .env values
#   --yes                non-interactive (use defaults)
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

DESKTOP=""
WORKSPACE=""
FORCE=0
YES=0

while [ $# -gt 0 ]; do
    case "$1" in
        --desktop)   DESKTOP="$2";   shift 2 ;;
        --workspace) WORKSPACE="$2"; shift 2 ;;
        --force)     FORCE=1;        shift   ;;
        --yes|-y)    YES=1;          shift   ;;
        -h|--help)
            sed -n '2,/^# ==.*$/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

# --- Auto-detect defaults ---
DEFAULT_DESKTOP="$HOME/Desktop"
DEFAULT_WORKSPACE="$(cd "$REPO_ROOT/.." && pwd)"

# --- Read existing .env if present ---
get_existing() {
    local key="$1"
    [ -f "$ENV_FILE" ] || return 0
    grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true
}

if [ -z "$DESKTOP" ]; then
    cur="$(get_existing HOST_DESKTOP)"
    if [ -n "$cur" ] && [ "$FORCE" -eq 0 ]; then
        DESKTOP="$cur"
    elif [ "$YES" -eq 1 ]; then
        DESKTOP="$DEFAULT_DESKTOP"
    else
        printf "Host Desktop path [%s]: " "$DEFAULT_DESKTOP"
        read -r ans
        DESKTOP="${ans:-$DEFAULT_DESKTOP}"
    fi
fi

if [ -z "$WORKSPACE" ]; then
    cur="$(get_existing HOST_WORKSPACE)"
    if [ -n "$cur" ] && [ "$FORCE" -eq 0 ]; then
        WORKSPACE="$cur"
    elif [ "$YES" -eq 1 ]; then
        WORKSPACE="$DEFAULT_WORKSPACE"
    else
        printf "Host workspace path [%s]: " "$DEFAULT_WORKSPACE"
        read -r ans
        WORKSPACE="${ans:-$DEFAULT_WORKSPACE}"
    fi
fi

# --- Validate ---
for pair in "HOST_DESKTOP=$DESKTOP" "HOST_WORKSPACE=$WORKSPACE"; do
    name="${pair%%=*}"
    val="${pair#*=}"
    if [ ! -e "$val" ]; then
        echo "[warn] $name path does not exist: $val" >&2
        echo "[warn] Docker will create it on first run, but verify it's correct." >&2
    fi
done

# --- Merge & write atomically ---
tmp="$(mktemp "${ENV_FILE}.XXXXXX")"
if [ -f "$ENV_FILE" ]; then
    grep -vE '^(HOST_DESKTOP|HOST_WORKSPACE)=' "$ENV_FILE" > "$tmp" || true
fi
{
    printf 'HOST_DESKTOP=%s\n'   "$DESKTOP"
    printf 'HOST_WORKSPACE=%s\n' "$WORKSPACE"
} >> "$tmp"
mv -f "$tmp" "$ENV_FILE"

echo
echo "[OK] Wrote host bridge config to $ENV_FILE"
echo "  HOST_DESKTOP   = $DESKTOP"
echo "  HOST_WORKSPACE = $WORKSPACE"
echo
echo "Next: docker compose up -d --build"
echo "Verify: docker exec bookworm ls /host/desktop"
