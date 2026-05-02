#!/usr/bin/env bash
# BookwormPRO 卸载脚本 (Mac/Linux)
set -e

R='\033[91m'; G='\033[92m'; Y='\033[93m'; C='\033[96m'; X='\033[0m'

echo ""
echo -e "${C}  ╔══════════════════════════════════════════════════════╗"
echo -e "  ║         BookwormPRO 卸载                              ║"
echo -e "  ╚══════════════════════════════════════════════════════╝${X}"
echo ""
echo "  将删除以下内容："
echo "    · ~/.bookwormpro/skills/  （所有技能文件）"
echo "    · ~/.bookwormpro/SOUL.md  （灵魂文件）"
echo "    · ~/.bookwormpro/CLAUDE.md"
echo ""
echo -e "  ${Y}⚠ 你的 .env (API Key) 和 config.yaml 不会被删除${X}"
echo ""

read -p "  确认卸载？输入 yes 继续: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "  已取消。"
    exit 0
fi

echo ""
echo "  正在卸载..."

if [ -d "$HOME/.bookwormpro/skills" ]; then
    rm -rf "$HOME/.bookwormpro/skills"
    echo -e "  ${G}✅${X} 技能文件已删除"
else
    echo "  ⚪ 技能目录不存在"
fi

for f in SOUL.md CLAUDE.md; do
    if [ -f "$HOME/.bookwormpro/$f" ]; then
        rm -f "$HOME/.bookwormpro/$f"
        echo -e "  ${G}✅${X} $f 已删除"
    fi
done

if [ -f "$HOME/.claude/SOUL.md" ]; then
    rm -f "$HOME/.claude/SOUL.md"
    echo -e "  ${G}✅${X} ~/.claude/SOUL.md 已删除"
fi

echo ""
echo -e "  ${G}🎉 卸载完成。${X}"
echo "  📝 .env 和 config.yaml 已保留，可手动删除："
echo "     $HOME/.bookwormpro/.env"
echo "     $HOME/.bookwormpro/config.yaml"
echo ""
