#!/bin/bash
# Docker/Podman entrypoint: bootstrap config files into the mounted volume, then run bookworm.
set -e

BOOKWORMPRO_HOME="${BOOKWORMPRO_HOME:-/opt/data}"
INSTALL_DIR="/opt/bookworm"

# --- Privilege dropping via gosu ---
# When started as root (the default for Docker, or fakeroot in rootless Podman),
# optionally remap the bookworm user/group to match host-side ownership, fix volume
# permissions, then re-exec as bookworm.
if [ "$(id -u)" = "0" ]; then
    if [ -n "$BOOKWORMPRO_UID" ] && [ "$BOOKWORMPRO_UID" != "$(id -u bookworm)" ]; then
        echo "Changing bookworm UID to $BOOKWORMPRO_UID"
        usermod -u "$BOOKWORMPRO_UID" bookworm
    fi

    if [ -n "$BOOKWORMPRO_GID" ] && [ "$BOOKWORMPRO_GID" != "$(id -g bookworm)" ]; then
        echo "Changing bookworm GID to $BOOKWORMPRO_GID"
        # -o allows non-unique GID (e.g. macOS GID 20 "staff" may already exist
        # as "dialout" in the Debian-based container image)
        groupmod -o -g "$BOOKWORMPRO_GID" bookworm 2>/dev/null || true
    fi

    # Fix ownership of the data volume. When BOOKWORMPRO_UID remaps the bookworm user,
    # files created by previous runs (under the old UID) become inaccessible.
    # Always chown -R when UID was remapped; otherwise only if top-level is wrong.
    actual_hermes_uid=$(id -u bookworm)
    needs_chown=false
    if [ -n "$BOOKWORMPRO_UID" ] && [ "$BOOKWORMPRO_UID" != "10000" ]; then
        needs_chown=true
    elif [ "$(stat -c %u "$BOOKWORMPRO_HOME" 2>/dev/null)" != "$actual_hermes_uid" ]; then
        needs_chown=true
    fi
    if [ "$needs_chown" = true ]; then
        echo "Fixing ownership of $BOOKWORMPRO_HOME to bookworm ($actual_hermes_uid)"
        # In rootless Podman the container's "root" is mapped to an unprivileged
        # host UID — chown will fail.  That's fine: the volume is already owned
        # by the mapped user on the host side.
        chown -R bookworm:bookworm "$BOOKWORMPRO_HOME" 2>/dev/null || \
            echo "Warning: chown failed (rootless container?) — continuing anyway"
    fi

    echo "Dropping root privileges"
    exec gosu bookworm "$0" "$@"
fi

# --- Running as bookworm from here ---
source "${INSTALL_DIR}/.venv/bin/activate"

# Create essential directory structure.  Cache and platform directories
# (cache/images, cache/audio, platforms/whatsapp, etc.) are created on
# demand by the application — don't pre-create them here so new installs
# get the consolidated layout from get_hermes_dir().
# The "home/" subdirectory is a per-profile HOME for subprocesses (git,
# ssh, gh, npm …).  Without it those tools write to /root which is
# ephemeral and shared across profiles.  See issue #4426.
mkdir -p "$BOOKWORMPRO_HOME"/{cron,sessions,logs,hooks,memories,skills,skins,plans,workspace,home}

# .env
if [ ! -f "$BOOKWORMPRO_HOME/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$BOOKWORMPRO_HOME/.env"
fi

# config.yaml
if [ ! -f "$BOOKWORMPRO_HOME/config.yaml" ]; then
    cp "$INSTALL_DIR/cli-config.yaml.example" "$BOOKWORMPRO_HOME/config.yaml"
fi

# Ensure the main config file remains accessible to the bookworm runtime user
# even if it was edited on the host after initial ownership setup.
if [ -f "$BOOKWORMPRO_HOME/config.yaml" ]; then
    chown bookworm:bookworm "$BOOKWORMPRO_HOME/config.yaml"
    chmod 640 "$BOOKWORMPRO_HOME/config.yaml"
fi

# SOUL.md
if [ ! -f "$BOOKWORMPRO_HOME/SOUL.md" ]; then
    cp "$INSTALL_DIR/docker/SOUL.md" "$BOOKWORMPRO_HOME/SOUL.md"
fi

# .gitignore seed — protects against accidental secret commit if container
# operator runs `git init` inside the home volume for backup purposes.
# Idempotent: only seeds when missing, never overwrites user edits.
if [ ! -f "$BOOKWORMPRO_HOME/.gitignore" ] && [ -f "$INSTALL_DIR/docker/seed/.gitignore" ]; then
    cp "$INSTALL_DIR/docker/seed/.gitignore" "$BOOKWORMPRO_HOME/.gitignore"
    chown bookworm:bookworm "$BOOKWORMPRO_HOME/.gitignore" 2>/dev/null || true
    chmod 640 "$BOOKWORMPRO_HOME/.gitignore" 2>/dev/null || true
fi

# Memory seed: bootstrap MEMORY.md / USER.md from templates on first run.
# Builtin memory (tools/memory_tool.py) reads $BOOKWORMPRO_HOME/memories/{MEMORY,USER}.md
# and freezes a snapshot into the system prompt at session start. Empty files
# mean "no recall" — seed templates give the agent useful baseline context.
# Idempotent: only seeds when file is missing, never overwrites user edits.
for seed_file in MEMORY.md USER.md; do
    src="$INSTALL_DIR/docker/seed/$seed_file"
    dst="$BOOKWORMPRO_HOME/memories/$seed_file"
    if [ -f "$src" ] && [ ! -f "$dst" ]; then
        cp "$src" "$dst"
        chown bookworm:bookworm "$dst" 2>/dev/null || true
        chmod 640 "$dst" 2>/dev/null || true
    fi
done

# Sync bundled skills (manifest-based so user edits are preserved)
if [ -d "$INSTALL_DIR/skills" ]; then
    python3 "$INSTALL_DIR/tools/skills_sync.py"
fi

# Final exec: two supported invocation patterns.
#
#   docker run <image>                 -> exec `bookworm` with no args (legacy default)
#   docker run <image> chat -q "..."   -> exec `bookworm chat -q "..."` (legacy wrap)
#   docker run <image> sleep infinity  -> exec `sleep infinity` directly
#   docker run <image> bash            -> exec `bash` directly
#
# If the first positional arg resolves to an executable on PATH, we assume the
# caller wants to run it directly (needed by the launcher which runs long-lived
# `sleep infinity` sandbox containers — see tools/environments/docker.py).
# Otherwise we treat the args as a bookworm subcommand and wrap with `bookworm`,
# preserving the documented `docker run <image> <subcommand>` behavior.
if [ $# -gt 0 ] && command -v "$1" >/dev/null 2>&1; then
    exec "$@"
fi
exec bookworm "$@"
