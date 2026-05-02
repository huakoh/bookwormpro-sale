#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  BookwormPRO — AI 智能助手技能包 安装程序 (Mac/Linux)
#  用法: chmod +x install.sh && ./install.sh
# ═══════════════════════════════════════════════════════════

set -e

# ── 色彩 ──
if [ -t 1 ]; then
  R='\033[91m'; G='\033[92m'; Y='\033[93m'; B='\033[94m'
  C='\033[96m'; W='\033[97m'; D='\033[2m'; X='\033[0m'
else
  R=''; G=''; Y=''; B=''; C=''; W=''; D=''; X=''
fi

echo ""
echo -e "${C}  ╔══════════════════════════════════════════════════════╗"
echo -e "  ║    ____              _                                ║"
echo -e "  ║   | __ )  ___   ___ | | _____      _____  _ __       ║"
echo -e "  ║   |  _ \\ / _ \\ / _ \\| |/ / \\ \\ /\\ / / _ \\| '__|      ║"
echo -e "  ║   | |_) | (_) | (_) |   <  \\ V  V / (_) | |         ║"
echo -e "  ║   |____/ \\___/ \\___/|_|\\_\\  \\_/\\_/ \\___/|_|         ║"
echo -e "  ║                                                      ║"
echo -e "  ║         ${W}AI 智能助手技能包 · 安装向导${C}                ║"
echo -e "  ╚══════════════════════════════════════════════════════╝${X}"
echo ""

# ── 步骤 1: 检查 Python ──
echo -e "${B}  [1/3] 检查运行环境...${X}"

PYTHON=""
for cmd in python3 python; do
  if command -v $cmd &> /dev/null; then
    VER=$($cmd --version 2>&1)
    MAJOR=$(echo $VER | grep -oP '\d+' | head -1)
    if [ "$MAJOR" -ge 3 ]; then
      PYTHON=$cmd
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo ""
  echo -e "  ${R}❌ 未检测到 Python 3！${X}"
  echo ""
  echo "  macOS: brew install python3"
  echo "  Ubuntu/Debian: sudo apt install python3"
  echo "  CentOS/RHEL: sudo yum install python3"
  echo ""
  exit 1
fi

echo -e "  ${G}✅${X} $($PYTHON --version) 已就绪"

# ── 步骤 2: 运行安装向导 ──
echo ""
echo -e "${B}  [2/3] 启动安装向导...${X}"
echo ""

cd "$(dirname "$0")"
$PYTHON scripts/setup_wizard.py "$@"

if [ $? -ne 0 ]; then
  echo ""
  echo -e "  ${R}❌ 安装过程出错${X}"
  exit 1
fi

# ── 步骤 3: 验证 ──
echo ""
echo -e "${B}  [3/3] 验证安装...${X}"

$PYTHON scripts/check.py

echo ""
echo -e "${C}  ╔══════════════════════════════════════════════════════╗"
echo -e "  ║                                                      ║"
echo -e "  ║   🎉 安装完成！                                      ║"
echo -e "  ║                                                      ║"
echo -e "  ║   下一步:                                            ║"
echo -e "  ║   1. 打开 docs/快速开始.html 查看教程                ║"
echo -e "  ║   2. 重启你的 AI 助手                                ║"
echo -e "  ║   3. 试试输入: bookworm自检                          ║"
echo -e "  ║                                                      ║"
echo -e "  ║   善读者，必善造。                                   ║"
echo -e "  ║                                                      ║"
echo -e "  ╚══════════════════════════════════════════════════════╝${X}"
echo ""
