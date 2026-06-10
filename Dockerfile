FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:b3c543b6c4f23a5f2df22866bd7857e5d304b67a564f4feab6ac22044dde719b AS uv_source
FROM tianon/gosu:1.19-trixie@sha256:3b176695959c71e123eb390d427efc665eeb561b1540e82679c15e992006b8b9 AS gosu_source
FROM debian:13.4

# Disable Python stdout buffering to ensure logs are printed immediately
ENV PYTHONUNBUFFERED=1

# Store Playwright browsers outside the volume mount so the build-time
# install survives the /opt/data volume overlay at runtime.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/bookworm/.playwright

# Install system dependencies in one layer, clear APT cache
# tini reaps orphaned zombie processes (MCP stdio subprocesses, git, bun, etc.)
# that would otherwise accumulate when bookworm runs as PID 1. See #15012.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential nodejs npm python3 ripgrep ffmpeg gcc python3-dev libffi-dev procps git openssh-client docker-cli tini && \
    rm -rf /var/lib/apt/lists/*

# Non-root user for runtime; UID can be overridden via BOOKWORMPRO_UID at runtime
RUN useradd -u 10000 -m -d /opt/data bookworm

COPY --chmod=0755 --from=gosu_source /gosu /usr/local/bin/
COPY --chmod=0755 --from=uv_source /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/

WORKDIR /opt/bookworm

# ---------- Layer-cached dependency install ----------
# Copy only package manifests first so npm install + Playwright are cached
# unless the lockfiles themselves change.
COPY package.json package-lock.json ./
COPY web/package.json web/package-lock.json web/

RUN npm install --prefer-offline --no-audit && \
    npx playwright install --with-deps chromium --only-shell && \
    (cd web && npm install --prefer-offline --no-audit) && \
    npm cache clean --force

# ---------- Source code ----------
# .dockerignore excludes node_modules, so the installs above survive.
COPY --chown=bookworm:bookworm . .

# Build web dashboard (Vite outputs to bwm_cli/web_dist/)
RUN cd web && npm run build

# ---------- Permissions ----------
# Make install dir world-readable so any BOOKWORMPRO_UID can read it at runtime.
# The venv needs to be traversable too.
USER root
# 只对需要公开可读的子目录授权，而非整个 /opt/bookworm
RUN chmod -R a+rX /opt/bookworm/bwm_cli/web_dist /opt/bookworm/scripts
# Start as root so the entrypoint can usermod/groupmod + gosu.
# If BOOKWORMPRO_UID is unset, the entrypoint drops to the default bookworm user (10000).

# ---------- Python virtualenv ----------
RUN uv venv && \
    uv pip install --no-cache-dir -e ".[all]"

# ---------- Runtime ----------
ENV BOOKWORMPRO_WEB_DIST=/opt/bookworm/bwm_cli/web_dist
ENV BOOKWORMPRO_HOME=/opt/data
ENV PATH="/opt/data/.local/bin:${PATH}"
VOLUME [ "/opt/data" ]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; s=socket.create_connection(('localhost', 8765), 2); s.close()" || exit 1

ENTRYPOINT [ "/usr/bin/tini", "-g", "--", "/opt/bookworm/docker/entrypoint.sh" ]
