#!/usr/bin/env bash
# BookwormPRO Sale 仓一键发布脚本 (Linux/macOS)
#
# 用法:
#   ./scripts/publish-sale.sh --license-key <key>         # 构建并推送
#   ./scripts/publish-sale.sh --license-key <key> --dry-run  # 仅预览
#   BOOKWORMPRO_LICENSE_KEY=<key> ./scripts/publish-sale.sh  # 环境变量方式
#
# 前置依赖:
#   - Python 3.12+, pip install cython cryptography
#   - Linux:  gcc / build-essential
#   - macOS:  Xcode Command Line Tools (xcode-select --install)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── 参数解析 ────────────────────────────────────────────────────────────────

LICENSE_KEY="${BOOKWORMPRO_LICENSE_KEY:-}"
DRY_RUN=false
EXTRA_FLAGS="--push"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --license-key)
            LICENSE_KEY="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            EXTRA_FLAGS="--dry-run"
            shift
            ;;
        *)
            echo "[WARN] Unknown argument: $1"
            shift
            ;;
    esac
done

if [[ -z "$LICENSE_KEY" ]]; then
    echo ""
    echo "[FAIL] License key required:"
    echo "  --license-key <key>  or  export BOOKWORMPRO_LICENSE_KEY=<key>"
    exit 1
fi

# ── 环境检查 ────────────────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "  BookwormPRO Sale Publish Pipeline"
echo "  $(date '+%Y-%m-%d %H:%M:%S')  $(uname -s) $(uname -m)"
echo "========================================"
echo ""

if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[FAIL] Python not found"
    exit 1
fi
PYTHON=$(command -v python3 || command -v python)

if ! "$PYTHON" -c "import Cython" &>/dev/null; then
    echo "[FAIL] Cython not installed: pip install cython"
    exit 1
fi

if ! "$PYTHON" -c "import cryptography" &>/dev/null; then
    echo "[FAIL] cryptography not installed: pip install cryptography"
    exit 1
fi

# C compiler check
if ! command -v cc &>/dev/null && ! command -v gcc &>/dev/null && ! command -v clang &>/dev/null; then
    echo "[FAIL] No C compiler found"
    if [[ "$(uname -s)" == "Darwin" ]]; then
        echo "  macOS: xcode-select --install"
    else
        echo "  Linux: apt install build-essential  (or yum install gcc)"
    fi
    exit 1
fi

if [[ ! -f "$PROJECT_ROOT/scripts/build_sale.py" ]]; then
    echo "[FAIL] build_sale.py not found at $PROJECT_ROOT/scripts/"
    exit 1
fi

# ── 执行构建 ────────────────────────────────────────────────────────────────

echo "[1/1] Running build_sale.py $EXTRA_FLAGS"
echo ""

cd "$PROJECT_ROOT"
"$PYTHON" scripts/build_sale.py $EXTRA_FLAGS --license-key "$LICENSE_KEY"
EXIT_CODE=$?

echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "========================================"
    echo "  DONE"
    echo "========================================"
else
    echo "========================================"
    echo "  FAILED (exit $EXIT_CODE)"
    echo "========================================"
    exit $EXIT_CODE
fi
