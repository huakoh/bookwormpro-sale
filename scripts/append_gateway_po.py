#!/usr/bin/env python3
"""Append gateway/run.py PO entries with Chinese translations."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PO = ROOT / "locale" / "zh_CN" / "LC_MESSAGES" / "bookwormpro.po"

TRANSLATIONS = {
    # ─── Command responses: stop/queue/steer ───
    "* Stopped. You can continue this session.":
        "* 已停止。你可以继续��前会话。",
    "* Stopped. The agent hadn't started yet — you can continue this session.":
        "* 已停止。代理尚未启动 — 你可以继续当前会话。",
    "* Force-stopped. The agent was still starting — session unlocked.":
        "* 已强制停止。代理仍在启动中 — 会话已解锁。",
    "No active task to stop.":
        "没有正在运行的任务���停止。",
    "Usage: /queue <prompt>":
        "用法：/queue <提示词>",
    "Queued for the next turn.":
        "已排队，下一轮��理。",
    "Usage: /steer <prompt>":
        "用法：/steer <提示词>",
    "Agent still starting — /steer queued for the next turn.":
        "代理正在启动 — /steer 已排队等待下一轮。",
    "[警告] Steer failed: {exc}":
        "[警告] Steer 失败：{exc}",
    "⏩ Steer queued — arrives after the next tool call: '{preview}'":
        "⏩ Steer 已排队 — 将在下一次工具调用后送达：'{preview}'",
    "Steer rejected (empty payload).":
        "Steer 被拒绝（空内容）。",
    "No active agent — /steer queued for the next turn.":
        "无活跃代理 — /steer 已排队等待下一轮。",
    "Agent is running — wait or /stop first, then switch models.":
        "代理运行中 — 请��待或先 /stop，再切换模型。",
    "Usage: /steer <prompt>  (no agent is running; sending as a normal message)":
        "用法：/steer <提示词>（无运行中代理；将作为普通消息发送）",

    # ─── Running agent guard ───
    "[等待] Agent is running — `/{name}` can't run mid-turn. Wait for the current response or `/stop` first.":
        "[等待] 代理运行中 — `/{name}` 无法在轮次中执行。请等待当���响应或先 `/stop`。",
    "[等待] Gateway is {action} and is not accepting new work right now.":
        "[等待] 网关正在{action}，暂不接受新任务。",
    "Command `/{command}` was blocked by a hook.":
        "命令 `/{command}` 被钩子拦截。",

    # ─── Quick commands ───
    "Quick command timed out (30s).":
        "快捷命令超时（30秒）。",
    "Quick command error: {e}":
        "快捷命令错误：{e}",
    "Quick command '/{command}' has no command defined.":
        "快捷命令 '/{command}' 未定义命令。",
    "Quick command '/{command}' has no target defined.":
        "快捷命令 '/{command}' 未定义目标。",
    "Quick command '/{command}' has unsupported type (supported: 'exec', 'alias').":
        "快捷命令 '/{command}' 类型不支持（支持：'exec'、'alias'）。",

    # ─── Pairing ───
    "Hi~ I don't recognize you yet!\\n\\nHere's your pairing code: `{code}`\\n\\nAsk the bot owner to run:\\n`bookworm pairing approve {platform_name} {code}`":
        "嗨~ 我还不认识你！\\n\\n你的配对码是：`{code}`\\n\\n请让机器人管理���运行：\\n`bookworm pairing approve {platform_name} {code}`",
    "Too many pairing requests right now~ Please try again later!":
        "配对请求太多了~ 请稍后再试！",

    # ─── Restart / drain ───
    "[等待] Draining {count} active agent(s) before restart...":
        "[等待] 等待 {count} 个活跃代理完成后重启...",
    "[等待] Gateway restart already in progress...":
        "[等待] 网关重启已在进行中...",
    "[等待] Draining {active_agents} active agent(s) before restart...":
        "[等待] 等待 {active_agents} 个活跃代理完成后重启...",
    "♻ Restarting gateway. If you aren't notified within 60 seconds, restart from the console with `bookworm gateway restart`.":
        "♻ 正在重启网关。如果 60 秒内没有收��通知，请在终端运行 `bookworm gateway restart`。",
    "♻ Gateway restarted successfully. Your session continues.":
        "♻ 网关重启成功。你的会话将继续。",

    # ─── Commands listing ───
    "No commands available.":
        "没有可用的命令。",
    "Usage: `/commands [page]`":
        "用法��`/commands [页码]`",

    # ─── Model ───
    "Error: {msg}":
        "错误：{msg}",

    # ─── Personality ───
    "No personalities configured in `{home}/config.yaml`":
        "`{home}/config.yaml` 中未配置人格",
    "[角色] Personality cleared — using base agent behavior.\\n_(takes effect on next message)_":
        "[角色] 人格已清除 — 使用基础代理行为。\\n_（下条消息生效）_",
    "[角色] Personality set to **{args}**\\n_(takes effect on next message)_":
        "[角色] 人格已设��� **{args}**\\n_（下条消息生效）_",
    "[警告] Failed to save personality change: {e}":
        "[警告] 保存人格变更失败：{e}",
    "Unknown personality: `{args}`\\n\\nAvailable: {available}":
        "未知人格：`{args}`\\n\\n可选：{available}",

    # ─── Retry / Undo ───
    "No previous message to retry.":
        "没有可重试的上一条消息。",
    "Nothing to undo.":
        "没有可撤销的内容。",

    # ─── Sethome ───
    "Failed to save home channel: {e}":
        "保存主频道失败：{e}",

    # ─── Voice ───
    "Voice mode disabled. Text-only replies.":
        "语音模式已关闭。仅文字回复。",
    "Voice mode enabled.":
        "语音模式已开启。",
    "Voice mode disabled.":
        "语音模式已关闭。",
    "Voice mode: {labels}":
        "语音模式：{labels}",
    "Voice channels are not supported on this platform.":
        "此平台不支持语音频道。",
    "This command only works in a Discord server.":
        "此命令仅在 Discord 服务器中可用。",
    "You need to be in a voice channel first.":
        "你需要先加入一个语音频道。",
    "Failed to join voice channel: {e}":
        "加入语音频道失败：{e}",
    "Failed to join voice channel. Check bot permissions (Connect + Speak).":
        "加入语音频道失败。请检查机器人权限（连接 + 说话）。",
    "Not in a voice channel.":
        "当前不在语音频道中。",
    "Left voice channel.":
        "已离开语音频道。",

    # ─── Checkpoints ───
    "No checkpoints found for {cwd}":
        "未找到 {cwd} 的检查点",
    "Invalid checkpoint number. Use 1-{len}.":
        "无效的检查点编号。请使用 1-{len}。",

    # ─── Background tasks ───
    '[调用] Background task started: \\"{preview}\\"\\nTask ID: {task_id}\\nYou can keep chatting — results will appear when done.':
        '[调用] 后台任务已启动：\\"{preview}\\"\\n任务 ID：{task_id}\\n你可以继续对话 — 结果完成后将自动显示。',

    # ─── /btw ───
    "A /btw is already running for this chat. Wait for it to finish.":
        "此对���已有 /btw 在运行。请等待完成。",
    '[对话] /btw: \\"{preview}\\"\\nReply will appear here shortly.':
        '[对话] /btw：\\"{preview}\\"\\n回复即将显示。',

    # ─── Reasoning / Fast ───
    "🧠 [成功] Reasoning display: **OFF** for **{platform_key}**":
        "🧠 [成功] 推理显示：**关闭**，平台 **{platform_key}**",
    "🧠 [成功] Reasoning effort set to `{effort}` (saved to config)\\n_(takes effect on next message)_":
        "🧠 [成功] 推理强度设为 `{effort}`（已保存到配置）\\n_（下条消息生效）_",
    "🧠 [成功] Reasoning effort set to `{effort}` (this session only)":
        "🧠 [成功] 推理强度设为 `{effort}`（仅本会话）",
    "* /fast is only available for OpenAI models that support Priority Processing.":
        "* /fast ��适用于支持优先处理的 OpenAI 模型。",
    "* [成功] Priority Processing: **{label}** (saved to config)\\n_(takes effect on next message)_":
        "* [成功] 优先处理：**{label}**（已保存到配置）\\n_（下条消息生效）_",
    "* [成功] Priority Processing: **{label}** (this session only)":
        "* [成功] 优先处理：**{label}**（仅本会话）",

    # ─── YOLO ───
    "[警告] YOLO mode **OFF** for this session — dangerous commands will require approval.":
        "[警告] YOLO 模式本会话已**关闭** — 危险命令将需要审批。",
    "* YOLO mode **ON** for this session — all commands auto-approved. Use with caution.":
        "* YOLO 模式本会话已**开启** — 所有命令自动批准。请谨慎使用。",

    # ─── Verbose / Compress ───
    "{desc}\\n_(could not save to config: {e})_":
        "{desc}\\n_（保存配置失败：{e}）_",
    "Not enough conversation to compress (need at least 4 messages).":
        "对话不够长，无法压缩（需要至少 4 条消息）。",
    "No provider configured -- cannot compress.":
        "未配置提供商 — 无法压缩。",
    "Nothing to compress yet (the transcript is still all protected context).":
        "暂无可压缩内容（记录全部为受保护上下文）。",
    "Compression failed: {e}":
        "压缩失败：{e}",

    # ─── Title / Resume / Branch ───
    "Session database not available.":
        "会话数据库不可用。",
    "[编辑] Session title set: **{sanitized}**":
        "[编辑] 会话标题已设置：**{sanitized}**",
    "[警告] Title is empty after cleanup. Please use printable characters.":
        "[警告] 清理后标题为空。请使用可打印字符。",
    "[警告] {e}":
        "[警告] {e}",
    "Session not found in database.":
        "数据库中未找到会话。",
    "📌 Session: `{session_id}`\\nTitle: **{title}**":
        "📌 会话：`{session_id}`\\n标题：**{title}**",
    "📌 Session: `{session_id}`\\nNo title set. Usage: `/title My Session Name`":
        "📌 会话：`{session_id}`\\n���设标题。用法：`/title 我的会话名`",
    "Could not list sessions: {e}":
        "无法列出会话：{e}",
    "📌 Already on session **{name}**.":
        "📌 已在会话 **{name}** 中。",
    "Failed to switch session.":
        "切换会话失败。",
    "↻ Resumed session **{title}**{msg_part}. Conversation restored.":
        "↻ 已恢复会话 **{title}**{msg_part}。对话已还原。",
    "No conversation to branch — send a message first.":
        "无对话可分支 — 请先发送一条消息。",
    "Failed to create branch: {e}":
        "创建分支失败：{e}",
    "Branch created but failed to switch to it.":
        "分支已创建但切换失败。",

    # ─── Usage / Insights ───
    "No usage data available for this session.":
        "本会话无可用的用量数据。",
    "Invalid --days value: {parts}":
        "无效的 --days 值：{parts}",
    "Error generating insights: {e}":
        "生成洞察失败：{e}",

    # ─── MCP ───
    "[失败] MCP reload failed: {e}":
        "[失败] MCP 重新加载失败：{e}",

    # ─── Approve / Deny ───
    "[警告] Approval expired (agent is no longer waiting). Ask the agent to try again.":
        "[警告] 审批已过期（代理不再等待）。请让代理重试。",
    "No pending command to approve.":
        "没有待审批的命令。",
    "No pending command to deny.":
        "没有待拒绝的命令。",
    "[成功] Command{s} approved{scope_msg}{count_msg}. The agent is resuming...":
        "[成功] 命令{s}已批准{scope_msg}{count_msg}。代理正在恢复...",
    "[失败] Command denied (approval was stale).":
        "[失败] 命令被拒绝（审批已过期）。",
    "[失败] Command{s} denied{count_msg}.":
        "[失败] 命令{s}已拒绝{count_msg}。",

    # ─── Debug ───
    "[失败] Failed to upload debug report: {exc}":
        "[失败] 上传调试报告失败：{exc}",

    # ─── Update ───
    "[失败] /update is only available from messaging platforms. Run `bookworm update` from the terminal.":
        "[失败] /update 仅可从消息平台使用。请在终端运行 `bookworm update`。",
    "[失败] {msg}":
        "[失败] {msg}",
    "[失败] Not a git repository — cannot update.":
        "[失败] 不是 Git 仓库 — 无法更新。",
    "[失败] Failed to start update: {e}":
        "[失败] 启动更新失败：{e}",
    "[BWM] Starting BookwormPRO update… I'll stream progress here.":
        "[BWM] 正在启动 BookwormPRO 更新… 进度将在此显示。",
    "[成功] BookwormPRO update finished.":
        "[成功] BookwormPRO 更新完成。",
    "[失败] BookwormPRO update failed (exit code {exit_code}).":
        "[失败] BookwormPRO 更新失败（退出码 {exit_code}）。",
    "[失败] BookwormPRO update timed out after 30 minutes.":
        "[失败] BookwormPRO 更新超时（30 分钟）。",
    "[失败] Failed to send response to update process: {e}":
        "[失败] 向更新进程发送响应失败：{e}",
    "[成功] Sent `{label}` to the update process.":
        "[成功] 已向更新进程发送 `{label}`。",

    # ─── Home channel ───
    "📬 No home channel is set for {platform}. A home channel is where BookwormPRO delivers cron job results and cross-platform messages.\\n\\nType /sethome to make this chat your home channel, or ignore to skip.":
        "📬 {platform} 尚未设置主频道。主频道用于接收 BookwormPRO 的定时任务结果和跨平台消息。\\n\\n输入 /sethome 将此对话设为主频道，或忽略跳过。",

    # ─── Error responses ───
    "[警告] The model returned no response after processing tool results. This can happen with some models — try again or rephrase your question.":
        "[警告] 模型在处理工具结果后未返回响���。某些模型可能出现此情况 — 请重试或换一种提问方式。",
    "[警告] Session too large for the model's context window.\\nUse /compact to compress the conversation, or /reset to start fresh.":
        "[警告] 会话超出模型上下文窗口。\\n使用 /compact 压缩对话，或 /reset 重新开始。",
    "The request failed: {error}\\nTry again or use /reset to start a fresh session.":
        "请求失败：{error}\\n请重试或使用 /reset 开始新会话。",

    # ─── System ───
    "[SYSTEM: {msg}]":
        "[系统：{msg}]",
    "[失败] {result}":
        "[失败] {result}",
}


def escape_po(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')


def main():
    lines = ["\n# ─── gateway/run.py (网关引擎) ───"]
    for msgid, msgstr in TRANSLATIONS.items():
        lines.append(f'msgid "{escape_po(msgid)}"')
        lines.append(f'msgstr "{escape_po(msgstr)}"')
        lines.append("")

    block = "\n".join(lines)
    with open(PO, "a", encoding="utf-8") as f:
        f.write(block)

    print(f"Appended {len(TRANSLATIONS)} PO entries to {PO.name}")


if __name__ == "__main__":
    main()
