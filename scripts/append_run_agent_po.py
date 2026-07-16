#!/usr/bin/env python3
"""Append run_agent.py PO entries with Chinese translations."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PO = ROOT / "locale" / "zh_CN" / "LC_MESSAGES" / "bookwormpro.po"

TRANSLATIONS = {
    # ─── Model initialization ───
    "[模型] AI Agent initialized with model: {model}":
        "[模型] AI 代理已初始化，模型：{model}",
    "[模型] AI Agent initialized with model: {model} (AWS Bedrock + AnthropicBedrock SDK, {region})":
        "[模型] AI 代理已初始化，模型：{model}（AWS Bedrock + AnthropicBedrock SDK，{region}）",
    "[模型] AI Agent initialized with model: {model} (AWS Bedrock, {region}{gr_label})":
        "[模型] AI 代理已初始化，模型：{model}（AWS Bedrock，{region}{gr_label}）",
    "[模型] AI Agent initialized with model: {model} (Anthropic native)":
        "[模型] AI 代理已初始化，模型：{model}（Anthropic 原生）",
    "[模型] AI Agent with Tool Calling":
        "[模型] AI 代理（支持工具调用）",

    # ─── Key / token ───
    "[密钥] Using token: {prefix}...{suffix}":
        "[密钥] 使用令牌：{prefix}...{suffix}",
    "[密钥] Using API key: {prefix}...{suffix}":
        "[密钥] 使用 API 密钥：{prefix}...{suffix}",

    # ─── Endpoint ───
    "[端点] Using custom base URL: {base_url}":
        "[端点] 使用自定义端点：{base_url}",

    # ─── API key warning ───
    "[警告]  Warning: API key appears invalid or missing (got: '{key}...')":
        "[警告] API 密钥似乎无效或缺失（获取到：'{key}...'）",

    # ─── Fallback ───
    "[调用] Fallback model: {model} ({provider})":
        "[调用] 备用模型：{model}（{provider}）",
    "[调用] Fallback chain ({count} providers): {chain}":
        "[调用] 备用链（{count} 个提供商）：{chain}",

    # ─── Tools loaded ───
    "[工具]  Loaded {count} tools: {names}":
        "[工具] 已加载 {count} 个工具：{names}",
    "   [成功] Enabled toolsets: {toolsets}":
        "   [成功] 已启用工具集：{toolsets}",
    "   [失败] Disabled toolsets: {toolsets}":
        "   [失败] 已禁用工具集：{toolsets}",
    "[工具]  No tools loaded (all tools filtered out or unavailable)":
        "[工具] 未加载任何工具（全部被过滤或不可用）",
    "[警告]  Some tools may not work due to missing requirements: {reqs}":
        "[警告] 部分工具可能因缺少依赖而无法使用：{reqs}",

    # ─── Trajectory / cache ───
    "[查询] Trajectory saving enabled":
        "[查询] 轨迹保存已启用",
    "[加锁] Ephemeral system prompt: '{preview}' (not saved to trajectories)":
        "[加锁] 临时系统提示：'{preview}'（不保存到轨迹）",
    "[保存] Prompt caching: ENABLED ({source}, {ttl} TTL)":
        "[保存] 提示词缓存：已启用（{source}，TTL {ttl}）",

    # ─── Context limit ───
    "[状态] Context limit: {limit:,} tokens (compress at {pct}% = {threshold:,})":
        "[状态] 上下文限制：{limit:,} tokens（在 {pct}% = {threshold:,} 时压缩）",
    "[状态] Context limit: {limit:,} tokens (auto-compression disabled)":
        "[状态] 上下文限制：{limit:,} tokens（自动压缩已禁用）",

    # ─── Interrupt ───
    "* Interrupt requested: '{msg}...'":
        "* 中断请求：'{msg}...'",
    "* Interrupt requested: '{msg}'":
        "* 中断请求：'{msg}'",
    "* Interrupt requested":
        "* 中断请求",
    "* Interrupt: skipping {count} tool call(s)":
        "* 中断：跳过 {count} 个工具调用",

    # ─── Connection ───
    "[调用] Reconnected — resuming…":
        "[调用] 已重连 — 恢复中…",
    "[失败] Connection to provider failed after {count} attempts. "
    "The provider may be experiencing issues — "
    "try again in a moment.":
        "[失败] 连接提供商失败，已尝试 {count} 次。提供商可能正在维护 — 请稍后重试。",

    # ─── Memory ───
    "  🧠 Memory flush: saved to {target}":
        "  🧠 记忆刷新：已保存到 {target}",

    # ─── Concurrent tool calls ───
    "  * Concurrent: {count} tool calls — {names}":
        "  * 并发：{count} 个工具调用 — {names}",
    "  [调用] Tool {i}: {name}({keys})":
        "  [调用] 工具 {i}：{name}({keys})",
    "  [调用] Tool {i}: {name}({keys}) - {preview}":
        "  [调用] 工具 {i}：{name}({keys}) - {preview}",
    "  [成功] Tool {i} completed in {dur:.2f}s":
        "  [成功] 工具 {i} 完成，耗时 {dur:.2f}s",
    "  [成功] Tool {i} completed in {dur:.2f}s - {preview}":
        "  [成功] 工具 {i} 完成，耗时 {dur:.2f}s - {preview}",

    # ─── Max iterations ───
    "[警告]  Reached maximum iterations ({max_iter}). Requesting summary...":
        "[警告] 已达最大迭代次数（{max_iter}）。请求摘要中...",

    # ─── Conversation ───
    "[对话] Starting conversation: '{preview}'":
        "[对话] 开始对话：'{preview}'",
    "[对话] Messages: {count}":
        "[对话] 消息数：{count}",

    # ─── Wait / retry ───
    "[等待] {msg}":
        "[等待] {msg}",
    "[等待] Retrying in {wait:.1f}s (attempt {attempt}/{max_retries})...":
        "[等待] {wait:.1f}s 后重试（第 {attempt}/{max_retries} 次）...",

    # ─── Fallback switching ───
    "[警告] Empty/malformed response — switching to fallback...":
        "[警告] 响应为空或格式错误 — 切换到备用...",
    "[警告] Max retries ({max_retries}) for invalid responses — trying fallback...":
        "[警告] 无效响应已达最大重试次数（{max_retries}）— 尝试备用...",
    "[失败] Max retries ({max_retries}) exceeded for invalid responses. Giving up.":
        "[失败] 无效响应超过最大重试次数（{max_retries}）。放弃。",

    # ─── BookwormPRO 401 ───
    "🔐 BookwormPRO agent key refreshed after 401. Retrying request...":
        "🔐 BookwormPRO 代理密钥在 401 后已刷新。正在重试...",
    "🔐 BookwormPRO 401 — Portal authentication failed.":
        "🔐 BookwormPRO 401 — 门户认证失败。",
    "   Response: {body}":
        "   响应：{body}",
    "   Most likely: Portal OAuth expired, account out of credits, or agent key revoked.":
        "   最可能原因：门户 OAuth 过期、额度用尽或代理密钥已撤销。",
    "   Troubleshooting:":
        "   排查步骤：",
    "     • Re-authenticate: bookworm login --provider bookwormpro":
        "     • 重新认证：bookworm login --provider bookwormpro",
    "     • Check credits / billing: ":
        "     • 检查额度/账单：",
    "     • Verify stored credentials: {path}/auth.json":
        "     • 验证存储的凭证：{path}/auth.json",
    "     • Switch providers temporarily: /model <model> --provider openrouter":
        "     • 临时切换提供商：/model <model> --provider openrouter",

    # ─── Anthropic 401 ───
    "🔐 Anthropic credentials refreshed after 401. Retrying request...":
        "🔐 Anthropic 凭证在 401 后已刷新。正在重试...",
    "🔐 Anthropic 401 — authentication failed.":
        "🔐 Anthropic 401 — 认证失败。",
    "   Auth method: {method}":
        "   认证方式：{method}",
    "   Token prefix: {prefix}...":
        "   令牌前缀：{prefix}...",
    "   Token: (empty or short)":
        "   令牌：（为空或过短）",
    "     • Check ANTHROPIC_TOKEN in {path}/.env for BookwormPRO-managed OAuth/setup tokens":
        "     • 检查 {path}/.env 中的 ANTHROPIC_TOKEN（BookwormPRO 管理的 OAuth/安装令牌）",
    "     • Check ANTHROPIC_API_KEY in {path}/.env for API keys or legacy token values":
        "     • 检查 {path}/.env 中的 ANTHROPIC_API_KEY（API 密钥或旧令牌值）",
    "     • For API keys: verify at https://platform.claude.com/settings/keys":
        "     • API 密钥：在 https://platform.claude.com/settings/keys 验证",
    "     • For Claude Code: run 'claude /login' to refresh, then retry":
        "     • Claude Code：运行 'claude /login' 刷新后重试",
    '     • Legacy cleanup: bookworm config set ANTHROPIC_TOKEN ""':
        '     • 清理旧令牌：bookworm config set ANTHROPIC_TOKEN ""',
    '     • Clear stale keys: bookworm config set ANTHROPIC_API_KEY ""':
        '     • 清除过期密钥：bookworm config set ANTHROPIC_API_KEY ""',

    # ─── Rate limit ───
    "[警告] Rate limited — switching to fallback provider...":
        "[警告] 触发速率限制 — 切换到备用提供商...",
    "[耗时] Rate limited. Waiting {wait:.1f}s (attempt {attempt}/{max_retries})...":
        "[耗时] 触发速率限制。等待 {wait:.1f}s（第 {attempt}/{max_retries} 次）...",

    # ─── 413 payload ───
    "[警告]  Request payload too large (413) — compression attempt {attempt}/{max_attempt}...":
        "[警告] 请求体过大 (413) — 压缩尝试 {attempt}/{max_attempt}...",
    "🗜️ Compressed {orig} → {new} messages, retrying...":
        "🗜️ 已压缩 {orig} → {new} 条消息，重试中...",
    "🗜️ Context too large (~{tokens:,} tokens) — compressing ({attempt}/{max_attempt})...":
        "🗜️ 上下文过大（~{tokens:,} tokens）— 压缩中（{attempt}/{max_attempt}）...",

    # ─── Non-retryable ───
    "[警告] Non-retryable error (HTTP {code}) — trying fallback...":
        "[警告] 不可重试错误 (HTTP {code}) — 尝试备用...",
    "[失败] Non-retryable error (HTTP {code}): {summary}":
        "[失败] 不可重试错误 (HTTP {code})：{summary}",

    # ─── Max retries exhausted ───
    "[警告] Max retries ({max_retries}) exhausted — trying fallback...":
        "[警告] 最大重试次数（{max_retries}）已用尽 — 尝试备用...",
    "[失败] Rate limited after {max_retries} retries — {summary}":
        "[失败] {max_retries} 次重试后仍被限速 — {summary}",
    "[失败] API failed after {max_retries} retries — {summary}":
        "[失败] API 在 {max_retries} 次重试后失败 — {summary}",
    "[失败] All API retries exhausted with no successful response.":
        "[失败] 所有 API 重试均已用尽，无成功响应。",

    # ─── Tool repair ───
    "[工具] Auto-repaired tool name: '{old}' -> '{new}'":
        "[工具] 自动修复工具名：'{old}' -> '{new}'",

    # ─── Completion ───
    "[完成] Conversation completed after {count} OpenAI-compatible API call(s)":
        "[完成] 对话完成，共 {count} 次 OpenAI 兼容 API 调用",
    "[失败] {msg}":
        "[失败] {msg}",

    # ─── Tool listing (main) ───
    "[汇总] Available Tools & Toolsets:":
        "[汇总] 可用工具和工具集：",
    "[最终] Predefined Toolsets (New System):":
        "[最终] 预定义工具集（新系统）：",
    "    Tools: {tools}":
        "    工具：{tools}",
    "[目录] Composite Toolsets (built from other toolsets):":
        "[目录] 组合工具集（由其他工具集组成）：",
    "    Includes: {includes}":
        "    包含：{includes}",
    "    Total tools: {count}":
        "    工具总数：{count}",
    "[角色] Scenario-Specific Toolsets:":
        "[角色] 场景专用工具集：",
    "[包] Legacy Toolsets (for backward compatibility):":
        "[包] 旧版工具集（向后兼容）：",
    "[成功]": "[成功]",
    "[失败]": "[失败]",
    "    Requirements: {reqs}":
        "    依赖项：{reqs}",
    "[工具] Individual Tools ({count} available):":
        "[工具] 单个工具（{count} 个可用）：",
    "[提示] Usage Examples:":
        "[提示] 使用示例：",

    # ─── Enabled / disabled toolsets ───
    "[最终] Enabled toolsets: {toolsets}":
        "[最终] 已启用工具集：{toolsets}",
    "🚫 Disabled toolsets: {toolsets}":
        "🚫 已禁用工具集：{toolsets}",

    # ─── Trajectory saving ───
    "[保存] Trajectory saving: ENABLED":
        "[保存] 轨迹保存：已启用",
    "   - Successful conversations → trajectory_samples.jsonl":
        "   - 成功对话 → trajectory_samples.jsonl",
    "   - Failed conversations → failed_trajectories.jsonl":
        "   - 失败对话 → failed_trajectories.jsonl",

    # ─── Agent result ───
    "[失败] Failed to initialize agent: {err}":
        "[失败] 代理初始化失败：{err}",
    "[查询] User Query: {query}":
        "[查询] 用户查询：{query}",
    "[汇总] CONVERSATION SUMMARY":
        "[汇总] 对话摘要",
    "[成功] Completed: {completed}":
        "[成功] 已完成：{completed}",
    "[调用] API Calls: {calls}":
        "[调用] API 调用次数：{calls}",
    "[最终] 回复:":
        "[最终] 回复：",
    "[保存] Sample trajectory saved to: {filename}":
        "[保存] 示例轨迹已保存到：{filename}",
    "[警告] Failed to save sample: {err}":
        "[警告] 保存示例失败：{err}",
    "[结束] Agent execution completed!":
        "[结束] 代理执行完成！",
}


def escape_po(s: str) -> str:
    return s.replace('\\', '\\\\').replace('"', '\\"')


def main():
    lines = ["\n# ─── run_agent.py (Agent 运行引擎) ───"]
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
