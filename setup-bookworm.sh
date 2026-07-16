#!/bin/bash
# ============================================================================
# BookwormPRO Setup Script
# ============================================================================
# Quick setup for developers who cloned the repo manually.
# Uses uv for desktop/server setup and Python's stdlib venv + pip on Termux.
#
# Usage:
#   ./setup-bookworm.sh
#
# This script:
# 1. Detects desktop/server vs Android/Termux setup path
# 2. Creates a Python 3.11 virtual environment
# 3. Installs the appropriate dependency set for the platform
# 4. Creates .env from template (if not exists)
# 5. Symlinks the 'bookworm' CLI command into a user-facing bin dir
# 6. Runs the setup wizard (optional)
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_VERSION="3.11"

is_termux() {
    [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *"com.termux/files/usr"* ]]
}

get_command_link_dir() {
    if is_termux && [ -n "${PREFIX:-}" ]; then
        echo "$PREFIX/bin"
    else
        echo "$HOME/.local/bin"
    fi
}

get_command_link_display_dir() {
    if is_termux && [ -n "${PREFIX:-}" ]; then
        echo '$PREFIX/bin'
    else
        echo '~/.local/bin'
    fi
}

echo ""
echo -e "${CYAN}[BWM] BookwormPRO Setup${NC}"
echo ""

# ============================================================================
# Install / locate uv
# ============================================================================

# 国内镜像自动检测 (对齐 install.ps1): 中文 locale / Asia 时区 / pypi.org 不可达 → 清华 PyPI + npmmirror.
# 覆盖 BOOKWORM_CHINA_MIRROR=1/0; 已设 PIP_INDEX_URL/UV_INDEX_URL 则尊重. 纯 env 导出, 后续 pip/uv/npm 继承.
if [ -z "${PIP_INDEX_URL:-}" ] && [ -z "${UV_INDEX_URL:-}" ]; then
    _bw_use_mirror=0
    case "${BOOKWORM_CHINA_MIRROR:-}" in
        1|true|yes|on) _bw_use_mirror=1 ;;
        0|false|no|off) _bw_use_mirror=0 ;;
        *)
            case "${LANG:-}${LC_ALL:-}${LC_MESSAGES:-}" in
                *zh_CN*|*zh_TW*|*zh_HK*|*zh_SG*) _bw_use_mirror=1 ;;
            esac
            if [ "$_bw_use_mirror" -eq 0 ] && { [ "${TZ:-}" = "Asia/Shanghai" ] || grep -qsE 'Asia/(Shanghai|Chongqing|Urumqi)' /etc/timezone 2>/dev/null; }; then
                _bw_use_mirror=1
            fi
            if [ "$_bw_use_mirror" -eq 0 ] && command -v curl >/dev/null 2>&1; then
                curl -fsS --max-time 3 -I "https://pypi.org/simple/" >/dev/null 2>&1 || _bw_use_mirror=1
            fi
            ;;
    esac
    if [ "$_bw_use_mirror" -eq 1 ]; then
        export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
        export PIP_TRUSTED_HOST="pypi.tuna.tsinghua.edu.cn"
        export UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
        export UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
        export npm_config_registry="https://registry.npmmirror.com"
        echo -e "${CYAN}→${NC} 国内镜像已启用 / China mirrors enabled"
    fi
fi

echo -e "${CYAN}→${NC} Checking for uv..."

UV_CMD=""
if is_termux; then
    echo -e "${CYAN}→${NC} Termux detected — using Python's stdlib venv + pip instead of uv"
else
    if command -v uv &> /dev/null; then
        UV_CMD="uv"
    elif [ -x "$HOME/.local/bin/uv" ]; then
        UV_CMD="$HOME/.local/bin/uv"
    elif [ -x "$HOME/.cargo/bin/uv" ]; then
        UV_CMD="$HOME/.cargo/bin/uv"
    fi

    if [ -n "$UV_CMD" ]; then
        UV_VERSION=$($UV_CMD --version 2>/dev/null)
        echo -e "${GREEN}[成功]${NC} uv found ($UV_VERSION)"
    else
        echo -e "${CYAN}→${NC} Installing uv..."
        if curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null; then
            if [ -x "$HOME/.local/bin/uv" ]; then
                UV_CMD="$HOME/.local/bin/uv"
            elif [ -x "$HOME/.cargo/bin/uv" ]; then
                UV_CMD="$HOME/.cargo/bin/uv"
            fi

            if [ -n "$UV_CMD" ]; then
                UV_VERSION=$($UV_CMD --version 2>/dev/null)
                echo -e "${GREEN}[成功]${NC} uv installed ($UV_VERSION)"
            else
                echo -e "${RED}[失败]${NC} uv installed but not found. Add ~/.local/bin to PATH and retry."
                exit 1
            fi
        else
            # astral.sh 常在国内被墙: 回退用 PyPI 镜像经 pip 安装 uv
            if command -v python3 >/dev/null 2>&1 && python3 -m pip --version >/dev/null 2>&1; then
                echo -e "${YELLOW}[警告]${NC} astral.sh 不可达, 改用 pip 镜像安装 uv..."
                if python3 -m pip install --user uv >/dev/null 2>&1; then
                    command -v uv &> /dev/null && UV_CMD="uv"
                    [ -z "$UV_CMD" ] && [ -x "$HOME/.local/bin/uv" ] && UV_CMD="$HOME/.local/bin/uv"
                fi
            fi
            if [ -n "$UV_CMD" ]; then
                UV_VERSION=$($UV_CMD --version 2>/dev/null)
                echo -e "${GREEN}[成功]${NC} uv installed via pip mirror ($UV_VERSION)"
            else
                echo -e "${RED}[失败]${NC} Failed to install uv. 国内可先 export BOOKWORM_CHINA_MIRROR=1 再重试, 或见 https://docs.astral.sh/uv/"
                exit 1
            fi
        fi
    fi
fi

# ============================================================================
# Python check (uv can provision it automatically)
# ============================================================================

echo -e "${CYAN}→${NC} Checking Python $PYTHON_VERSION..."

if is_termux; then
    if command -v python >/dev/null 2>&1; then
        PYTHON_PATH="$(command -v python)"
        if "$PYTHON_PATH" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            PYTHON_FOUND_VERSION=$($PYTHON_PATH --version 2>/dev/null)
            echo -e "${GREEN}[成功]${NC} $PYTHON_FOUND_VERSION found"
        else
            echo -e "${RED}[失败]${NC} Termux Python must be 3.11+"
            echo "    Run: pkg install python"
            exit 1
        fi
    else
        echo -e "${RED}[失败]${NC} Python not found in Termux"
        echo "    Run: pkg install python"
        exit 1
    fi
else
    if $UV_CMD python find "$PYTHON_VERSION" &> /dev/null; then
        PYTHON_PATH=$($UV_CMD python find "$PYTHON_VERSION")
        PYTHON_FOUND_VERSION=$($PYTHON_PATH --version 2>/dev/null)
        echo -e "${GREEN}[成功]${NC} $PYTHON_FOUND_VERSION found"
    else
        echo -e "${CYAN}→${NC} Python $PYTHON_VERSION not found, installing via uv..."
        $UV_CMD python install "$PYTHON_VERSION"
        PYTHON_PATH=$($UV_CMD python find "$PYTHON_VERSION")
        PYTHON_FOUND_VERSION=$($PYTHON_PATH --version 2>/dev/null)
        echo -e "${GREEN}[成功]${NC} $PYTHON_FOUND_VERSION installed"
    fi
fi

# ============================================================================
# Virtual environment
# ============================================================================

echo -e "${CYAN}→${NC} Setting up virtual environment..."

if [ -d "venv" ]; then
    echo -e "${CYAN}→${NC} Removing old venv..."
    rm -rf venv
fi

if is_termux; then
    "$PYTHON_PATH" -m venv venv
    echo -e "${GREEN}[成功]${NC} venv created with stdlib venv"
else
    $UV_CMD venv venv --python "$PYTHON_VERSION"
    echo -e "${GREEN}[成功]${NC} venv created (Python $PYTHON_VERSION)"
fi

export VIRTUAL_ENV="$SCRIPT_DIR/venv"
SETUP_PYTHON="$SCRIPT_DIR/venv/bin/python"

# ============================================================================
# Dependencies
# ============================================================================

echo -e "${CYAN}→${NC} Installing dependencies..."

if is_termux; then
    export ANDROID_API_LEVEL="$(getprop ro.build.version.sdk 2>/dev/null || printf '%s' "${ANDROID_API_LEVEL:-}")"
    echo -e "${CYAN}→${NC} Termux detected — installing the tested Android bundle"
    "$SETUP_PYTHON" -m pip install --upgrade pip setuptools wheel
    if [ -f "constraints-termux.txt" ]; then
        "$SETUP_PYTHON" -m pip install -e ".[termux]" -c constraints-termux.txt || {
            echo -e "${YELLOW}[警告]${NC} Termux bundle install failed, falling back to base install..."
            "$SETUP_PYTHON" -m pip install -e "." -c constraints-termux.txt
        }
    else
        "$SETUP_PYTHON" -m pip install -e ".[termux]" || "$SETUP_PYTHON" -m pip install -e "."
    fi
    echo -e "${GREEN}[成功]${NC} Dependencies installed"
else
    # Prefer uv sync with lockfile (hash-verified installs) when available,
    # fall back to pip install for compatibility or when lockfile is stale.
    if [ -f "uv.lock" ]; then
        echo -e "${CYAN}→${NC} Using uv.lock for hash-verified installation..."
        UV_PROJECT_ENVIRONMENT="$SCRIPT_DIR/venv" $UV_CMD sync --all-extras --locked 2>/dev/null && \
            echo -e "${GREEN}[成功]${NC} Dependencies installed (lockfile verified)" || {
            echo -e "${YELLOW}[警告]${NC} Lockfile install failed (may be outdated), falling back to pip install..."
            $UV_CMD pip install -e ".[all]" || $UV_CMD pip install -e "."
            echo -e "${GREEN}[成功]${NC} Dependencies installed"
        }
    else
        $UV_CMD pip install -e ".[all]" || $UV_CMD pip install -e "."
        echo -e "${GREEN}[成功]${NC} Dependencies installed"
    fi
fi

# ============================================================================
# Submodules (terminal backend + RL training)
# ============================================================================

echo -e "${CYAN}→${NC} Installing optional submodules..."

# tinker-atropos (RL training backend)
if is_termux; then
    echo -e "${CYAN}→${NC} Skipping tinker-atropos on Termux (not part of the tested Android path)"
elif [ -d "tinker-atropos" ] && [ -f "tinker-atropos/pyproject.toml" ]; then
    $UV_CMD pip install -e "./tinker-atropos" && \
        echo -e "${GREEN}[成功]${NC} tinker-atropos installed" || \
        echo -e "${YELLOW}[警告]${NC} tinker-atropos install failed (RL tools may not work)"
else
    echo -e "${YELLOW}[警告]${NC} tinker-atropos not found (run: git submodule update --init --recursive)"
fi

# ============================================================================
# Optional: ripgrep (for faster file search)
# ============================================================================

echo -e "${CYAN}→${NC} Checking ripgrep (optional, for faster search)..."

if command -v rg &> /dev/null; then
    echo -e "${GREEN}[成功]${NC} ripgrep found"
else
    echo -e "${YELLOW}[警告]${NC} ripgrep not found (file search will use grep fallback)"
    read -p "Install ripgrep for faster search? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        INSTALLED=false

        if is_termux; then
            pkg install -y ripgrep && INSTALLED=true
        else
            # Check if sudo is available
            if command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
                if command -v apt &> /dev/null; then
                    sudo apt install -y ripgrep && INSTALLED=true
                elif command -v dnf &> /dev/null; then
                    sudo dnf install -y ripgrep && INSTALLED=true
                fi
            fi

            # Try brew (no sudo needed)
            if [ "$INSTALLED" = false ] && command -v brew &> /dev/null; then
                brew install ripgrep && INSTALLED=true
            fi

            # Try cargo (no sudo needed)
            if [ "$INSTALLED" = false ] && command -v cargo &> /dev/null; then
                echo -e "${CYAN}→${NC} Trying cargo install (no sudo required)..."
                cargo install ripgrep && INSTALLED=true
            fi
        fi

        if [ "$INSTALLED" = true ]; then
            echo -e "${GREEN}[成功]${NC} ripgrep installed"
        else
            echo -e "${YELLOW}[警告]${NC} Auto-install failed. Install options:"
            if is_termux; then
                echo "    pkg install ripgrep          # Termux / Android"
            else
                echo "    sudo apt install ripgrep     # Debian/Ubuntu"
                echo "    brew install ripgrep         # macOS"
                echo "    cargo install ripgrep        # With Rust (no sudo)"
            fi
            echo "    https://github.com/BurntSushi/ripgrep#installation"
        fi
    fi
fi

# ============================================================================
# Environment file
# ============================================================================

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}[成功]${NC} Created .env from template"
    fi
else
    echo -e "${GREEN}[成功]${NC} .env exists"
fi

# ============================================================================
# PATH setup — symlink bookworm into a user-facing bin dir
# ============================================================================

echo -e "${CYAN}→${NC} Setting up bookworm command..."

BOOKWORMPRO_BIN="$SCRIPT_DIR/venv/bin/bookworm"
COMMAND_LINK_DIR="$(get_command_link_dir)"
COMMAND_LINK_DISPLAY_DIR="$(get_command_link_display_dir)"
mkdir -p "$COMMAND_LINK_DIR"
ln -sf "$BOOKWORMPRO_BIN" "$COMMAND_LINK_DIR/bookworm"
echo -e "${GREEN}[成功]${NC} Symlinked bookworm → $COMMAND_LINK_DISPLAY_DIR/bookworm"

if is_termux; then
    export PATH="$COMMAND_LINK_DIR:$PATH"
    echo -e "${GREEN}[成功]${NC} $COMMAND_LINK_DISPLAY_DIR is already on PATH in Termux"
else
    # Determine the appropriate shell config file
    SHELL_CONFIG=""
    if [[ "$SHELL" == *"zsh"* ]]; then
        SHELL_CONFIG="$HOME/.zshrc"
    elif [[ "$SHELL" == *"bash"* ]]; then
        SHELL_CONFIG="$HOME/.bashrc"
        [ ! -f "$SHELL_CONFIG" ] && SHELL_CONFIG="$HOME/.bash_profile"
    else
        # Fallback to checking existing files
        if [ -f "$HOME/.zshrc" ]; then
            SHELL_CONFIG="$HOME/.zshrc"
        elif [ -f "$HOME/.bashrc" ]; then
            SHELL_CONFIG="$HOME/.bashrc"
        elif [ -f "$HOME/.bash_profile" ]; then
            SHELL_CONFIG="$HOME/.bash_profile"
        fi
    fi

    if [ -n "$SHELL_CONFIG" ]; then
        # Touch the file just in case it doesn't exist yet but was selected
        touch "$SHELL_CONFIG" 2>/dev/null || true

        if ! echo "$PATH" | tr ':' '\n' | grep -q "^$HOME/.local/bin$"; then
            if ! grep -q '\.local/bin' "$SHELL_CONFIG" 2>/dev/null; then
                echo "" >> "$SHELL_CONFIG"
                echo "# BookwormPRO — ensure ~/.local/bin is on PATH" >> "$SHELL_CONFIG"
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_CONFIG"
                echo -e "${GREEN}[成功]${NC} Added ~/.local/bin to PATH in $SHELL_CONFIG"
            else
                echo -e "${GREEN}[成功]${NC} ~/.local/bin already in $SHELL_CONFIG"
            fi
        else
            echo -e "${GREEN}[成功]${NC} ~/.local/bin already on PATH"
        fi
    fi
fi

# ============================================================================
# Seed bundled skills into ~/.bookwormpro/skills/
# ============================================================================

BOOKWORMPRO_SKILLS_DIR="${BOOKWORMPRO_HOME:-$HOME/.bookwormpro}/skills"
mkdir -p "$BOOKWORMPRO_SKILLS_DIR"

echo ""
echo "Syncing bundled skills to ~/.bookwormpro/skills/ ..."
if "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/tools/skills_sync.py" 2>/dev/null; then
    echo -e "${GREEN}[成功]${NC} Skills synced"
else
    # Fallback: copy if sync script fails (missing deps, etc.)
    if [ -d "$SCRIPT_DIR/skills" ]; then
        cp -rn "$SCRIPT_DIR/skills/"* "$BOOKWORMPRO_SKILLS_DIR/" 2>/dev/null || true
        echo -e "${GREEN}[成功]${NC} Skills copied"
    fi
fi

# ============================================================================
# Done
# ============================================================================

echo ""
echo -e "${GREEN}[成功] Setup complete!${NC}"
echo ""
echo "Next steps:"
echo ""
if is_termux; then
    echo "  1. Run the setup wizard to configure API keys:"
    echo "     bookworm setup"
    echo ""
    echo "  2. Start chatting:"
    echo "     bookworm"
    echo ""
else
    echo "  1. Reload your shell:"
    echo "     source $SHELL_CONFIG"
    echo ""
    echo "  2. Run the setup wizard to configure API keys:"
    echo "     bookworm setup"
    echo ""
    echo "  3. Start chatting:"
    echo "     bookworm"
    echo ""
fi
echo "Other commands:"
echo "  bookworm status        # Check configuration"
if is_termux; then
    echo "  bookworm gateway       # Run gateway in foreground"
else
    echo "  bookworm gateway install # Install gateway service (messaging + cron)"
fi
echo "  bookworm cron list     # View scheduled jobs"
echo "  bookworm doctor        # Diagnose issues"
echo ""

# Ask if they want to run setup wizard now
read -p "Would you like to run the setup wizard now? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    echo ""
    # Run directly with venv Python (no activation needed)
    "$SCRIPT_DIR/venv/bin/python" -m bwm_cli.main setup
fi
