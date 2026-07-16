#!/usr/bin/env python3
"""Fix 14 PO entries where \\n was double-escaped."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PO = ROOT / "locale" / "zh_CN" / "LC_MESSAGES" / "bookwormpro.po"

# These entries have \n in source code (real newline escape) that needs to be
# written as \n in the PO file (not \\n)
ENTRIES = [
    ("[角色] Personality cleared — using base agent behavior.\\n_(takes effect on next message)_",
     "[角色] 人格已清除 — 使用基础代理行为。\\n_（下条消息生效）_"),
    ("[角色] Personality set to **{args}**\\n_(takes effect on next message)_",
     "[角色] 人格已设为 **{args}**\\n_（下条消息生效）_"),
    ("Unknown personality: `{args}`\\n\\nAvailable: {available}",
     "未知人格：`{args}`\\n\\n可选：{available}"),
    ("[警告] Session too large for the model's context window.\\nUse /compact to compress the conversation, or /reset to start fresh.",
     "[警告] 会话超出模型上下文窗口。\\n使用 /compact 压缩对话，或 /reset 重新开始。"),
    ("The request failed: {error}\\nTry again or use /reset to start a fresh session.",
     "请求失败：{error}\\n请重试或使用 /reset 开始新会话。"),
    ("Hi~ I don't recognize you yet!\\n\\nHere's your pairing code: `{code}`\\n\\nAsk the bot owner to run:\\n`bookworm pairing approve {platform_name} {code}`",
     "嗨~ 我还不认识你！\\n\\n你的配对码是：`{code}`\\n\\n请让机器人管理员运行：\\n`bookworm pairing approve {platform_name} {code}`"),
    ('[调用] Background task started: \\"{preview}\\"\\nTask ID: {task_id}\\nYou can keep chatting — results will appear when done.',
     '[调用] 后台任务已启动：\\"{preview}\\"\\n任务 ID：{task_id}\\n你可以继续对话 — 结果完成后将自动显示。'),
    ('[对话] /btw: \\"{preview}\\"\\nReply will appear here shortly.',
     '[对话] /btw：\\"{preview}\\"\\n回复即将显示。'),
    ("📌 Session: `{session_id}`\\nTitle: **{title}**",
     "📌 会话：`{session_id}`\\n标题：**{title}**"),
    ("📌 Session: `{session_id}`\\nNo title set. Usage: `/title My Session Name`",
     "📌 会话：`{session_id}`\\n未设标题。用法：`/title 我的会话名`"),
    ("📬 No home channel is set for {platform}. A home channel is where BookwormPRO delivers cron job results and cross-platform messages.\\n\\nType /sethome to make this chat your home channel, or ignore to skip.",
     "📬 {platform} 尚未设置主频道。主频道用于接收 BookwormPRO 的定时任务结果和跨平台消息。\\n\\n输入 /sethome 将此对话设为主频道，或忽略跳过。"),
    ("{desc}\\n_(could not save to config: {e})_",
     "{desc}\\n_（保存配置失败：{e}）_"),
    ("🧠 [成功] Reasoning effort set to `{effort}` (saved to config)\\n_(takes effect on next message)_",
     "🧠 [成功] 推理强度设为 `{effort}`（已保存到配置）\\n_（下条消息生效）_"),
    ("* [成功] Priority Processing: **{label}** (saved to config)\\n_(takes effect on next message)_",
     "* [成功] 优先处理：**{label}**（已保存到配置）\\n_（下条消息生效）_"),
]


def main():
    lines = ["\n# ─── gateway/run.py (newline entries) ───"]
    for msgid, msgstr in ENTRIES:
        lines.append(f'msgid "{msgid}"')
        lines.append(f'msgstr "{msgstr}"')
        lines.append("")

    with open(PO, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Appended {len(ENTRIES)} newline-fix PO entries")


if __name__ == "__main__":
    main()
