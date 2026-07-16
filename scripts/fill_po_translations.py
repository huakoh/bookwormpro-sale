#!/usr/bin/env python3
"""
Fill empty PO msgstr entries with translations.

Strategy:
1. Pure Chinese msgids → msgstr = msgid (already Chinese, fallback is fine)
2. English/mixed msgids → apply translation table + heuristics
3. Proper nouns / brand names / code → keep as-is (msgstr = msgid)
4. Unknown → leave empty (fallback to msgid at runtime is OK)
"""
import re
from pathlib import Path

PO_PATH = Path("locale/zh_CN/LC_MESSAGES/bookwormpro.po")

# ── Translation table ──────────────────────────────────────────────────────────
# Key = msgid, Value = Chinese translation
# Format specifiers like {var} are preserved as-is
TRANSLATIONS = {
    # ── setup.py ──
    "[BWM] BookwormPRO Setup — Non-interactive mode": "[BWM] BookwormPRO 安装 — 非交互模式",
    "                          Set a specific value": "                          设置特定值",
    "   Or edit the files directly:": "   或直接编辑文件:",
    "[查询] To edit your configuration:": "[查询] 编辑配置:",
    "[启动] Ready to go!": "[启动] 准备就绪！",
    "  Would import:": "  将导入:",
    "  Would overwrite (conflicts with existing BookwormPRO config):": "  将覆盖 (与现有 BookwormPRO 配置冲突):",
    "  Would skip:": "  将跳过:",
    "  ── Warnings ──": "  ── 警告 ──",
    "  Note: OpenClaw config values may have different semantics in BookwormPRO.": "  注意: OpenClaw 配置值在 BookwormPRO 中可能具有不同语义。",
    "  Instruction files (.md) from OpenClaw may contain incompatible procedures.": "  来自 OpenClaw 的指令文件 (.md) 可能包含不兼容的操作步骤。",
    "│     [BWM] BookwormPRO Setup — {label:<34s} │": "│     [BWM] BookwormPRO 安装 — {label:<34s} │",

    # ── main.py sessions ──
    "No sessions found.": "未找到会话。",
    "\n  Browse sessions  (enter number to resume, q to cancel)\n": "\n  浏览会话 (输入编号恢复, q 取消)\n",
    "  Invalid input. Enter a number or q to cancel.": "  输入无效。请输入编号或 q 取消。",
    "  Invalid selection. Enter 1-{n} or q to cancel.": "  选择无效。请输入 1-{n} 或 q 取消。",
    "Resume this session with:": "使用以下命令恢复此会话:",
    "Session:        {target}": "会话:        {target}",
    "Title:          {title}": "标题:          {title}",
    "Messages:       {message_count}": "消息数:       {message_count}",
    "Use 'bookworm sessions list' to see available sessions.": "使用 'bookworm sessions list' 查看可用会话。",
    "  Run:  bookworm setup": "  运行:  bookworm setup",
    "You can run 'bookworm setup' at any time to configure.": "您可以随时运行 'bookworm setup' 进行配置。",
    "No session found matching '{continue_val}'.": "未找到匹配 '{continue_val}' 的会话。",
    "No previous {kind} session found to continue.": "未找到可继续的上一 {kind} 会话。",
    "Installing TUI dependencies…": "正在安装 TUI 依赖…",
    "npm install failed.": "npm install 失败。",
    "@bookworm/ink build failed.": "@bookworm/ink 构建失败。",
    "TUI build failed.": "TUI 构建失败。",
    "TUI build did not produce dist/entry.js": "TUI 构建未生成 dist/entry.js",
    "{bin} not found — install Node.js to use the TUI.": "未找到 {bin} — 安装 Node.js 以使用 TUI。",
    "Error: {exc}": "错误: {exc}",
    "Error: {e}": "错误: {e}",
    "Warning: {warning} Falling back to auto provider detection.": "警告: {warning} 回退到自动提供商检测。",
    "  Current model:    {current_model}": "  当前模型:    {current_model}",
    "  Active provider:  {active_label}": "  活动提供商:  {active_label}",
    "Could not detect authenticated providers: {exc}": "无法检测已认证提供商: {exc}",
    "  Configure {display_name} — current: {_format_aux_current}": "  配置 {display_name} — 当前: {_format_aux_current}",
    "Reset {n} auxiliary task(s) to auto.": "已将 {n} 个辅助任务重置为自动。",
    "No curated model list for {provider_slug}.": "{provider_slug} 无精选模型列表。",
    "{display_name}: reset to auto.": "{display_name}: 已重置为自动。",
    "{display_name}: {provider_slug} · {selected}": "{display_name}: {provider_slug} · {selected}",
    "{display_name}: {provider_slug} (provider default model)": "{display_name}: {provider_slug} (提供商默认模型)",
    "  Custom endpoint for {display_name}": "  {display_name} 的自定义端点",
    "{display_name}: custom ({short_url})": "{display_name}: 自定义 ({short_url})",
    "  [成功] Allowed users set: {phone}": "  [成功] 已设置允许用户: {phone}",
    "\n[失败] Bridge script not found at {bridge_script}": "\n[失败] 在 {bridge_script} 未找到桥接脚本",
    "\n[成功] Mode: {mode_label}": "\n[成功] 模式: {mode_label}",
    "[成功] Allowed users: {current_users}": "[成功] 允许用户: {current_users}",
    "  [成功] Updated to: {phone}": "  [成功] 已更新为: {phone}",
    "[成功] WhatsApp is already enabled": "[成功] WhatsApp 已启用",
    "[成功] WhatsApp enabled": "[成功] WhatsApp 已启用",
    "[BWM] WhatsApp Setup": "[BWM] WhatsApp 设置",
    "How will you use WhatsApp with BookwormPRO?": "您将如何将 WhatsApp 与 BookwormPRO 配合使用?",
    "  1. Separate bot number (recommended)": "  1. 独立机器人号码 (推荐)",
    "     People message the bot's number directly — cleanest experience.": "     用户直接向机器人号码发消息 — 体验最佳。",
    "  2. Personal number (self-chat)": "  2. 个人号码 (自发消息)",
    "     You message yourself to talk to the agent.": "     您向自己发消息与 Agent 对话。",
    "     Quick to set up, but the UX is less intuitive.": "     设置快速, 但用户体验不够直观。",
    "\nSetup cancelled.": "\n设置已取消。",
    "  [成功] Mode: separate bot number": "  [成功] 模式: 独立机器人号码",
    "  ┌─────────────────────────────────────────────────┐": "  ┌─────────────────────────────────────────────────┐",
    "  │  Getting a second number for the bot:           │": "  │  获取机器人第二个号码:                          │",
    "  │                                                 │": "  │                                                 │",
    "  │  Easiest: Install WhatsApp Business (free app)  │": "  │  最简单: 安装 WhatsApp Business (免费应用)      │",
    "  │  on your phone with a second number:            │": "  │  使用第二个号码:                                │",
    "  │    • Dual-SIM: use your 2nd SIM slot            │": "  │    • 双卡: 使用第二张 SIM 卡槽                  │",
    "  │    • Google Voice: free US number (voice.google) │": "  │    • Google Voice: 免费美国号码                  │",
    "  │    • Prepaid SIM: $3-10, verify once            │": "  │    • 预付费 SIM: $3-10, 一次性验证              │",

    # ── gateway.py ──
    "[等待] Service restart already pending — waiting for systemd relaunch...": "[等待] 服务重启已挂起 — 等待 systemd 重新启动…",
    "No legacy BookwormPRO gateway units found.": "未找到旧版 BookwormPRO gateway 单元。",
    "Legacy BookwormPRO gateway unit(s) found:": "找到旧版 BookwormPRO gateway 单元:",
    "(dry-run — nothing removed)": "(演习模式 — 未删除任何内容)",
    "Skipped. Run again with: bookworm gateway migrate-legacy": "已跳过。请使用以下命令重新运行: bookworm gateway migrate-legacy",
    "[成功] Systemd linger is enabled (service survives logout)": "[成功] Systemd linger 已启用 (服务在注销后继续运行)",
    "[警告] Systemd linger is disabled (gateway may stop when you log out)": "[警告] Systemd linger 未启用 (注销时 gateway 可能停止)",
    "  Run: sudo loginctl enable-linger $USER": "  运行: sudo loginctl enable-linger $USER",
    "  If you want the gateway user service to survive logout, run:": "  如需 gateway 用户服务在注销后继续运行, 请运行:",
    "  sudo loginctl enable-linger $USER": "  sudo loginctl enable-linger $USER",
    "[警告] Linger not enabled — gateway may stop when you close this terminal.": "[警告] Linger 未启用 — 关闭终端时 gateway 可能停止。",
    "  On headless servers (VPS, cloud instances) run:": "  在无头服务器 (VPS, 云实例) 上运行:",
    "  Then restart the gateway:": "  然后重启 gateway:",
    "Enabling linger so the gateway survives SSH logout...": "正在启用 linger 使 gateway 在 SSH 注销后继续运行…",
    "Use --force to reinstall": "使用 --force 重新安装",
    "Next steps:": "后续步骤:",
    "[失败] Gateway service is not installed": "[失败] Gateway 服务未安装",
    "[警告] Installed gateway service definition is outdated": "[警告] 已安装的 gateway 服务定义已过时",
    "Recent gateway health:": "近期 gateway 健康状态:",
    "  [等待] Restart pending: systemd is waiting to relaunch the gateway": "  [等待] 重启待处理: systemd 正在等待重新启动 gateway",
    "  [警告] Planned restart is stuck in systemd failed state (exit 75)": "  [警告] 计划重启卡在 systemd 失败状态 (退出码 75)",
    "[成功] System service starts at boot without requiring systemd linger": "[成功] 系统服务在启动时自动运行, 无需 systemd linger",
    "[警告] Gateway process is running for this profile, but the service is not active": "[警告] 此配置文件的 Gateway 进程正在运行, 但服务未激活",
    "  This is usually a manual foreground/tmux/nohup run, so `bookworm gateway`": "  这通常是手动前台/tmux/nohup 运行, 所以 `bookworm gateway`",
    "  can refuse to start another copy until this process stops.": "  可能拒绝启动另一个副本, 直到此进程停止。",
    "↻ Clearing failed state for pending {scope_label} service restart...": "↻ 正在清除待处理的 {scope_label} 服务重启的失败状态…",
    "[成功] {scope_label} service restarted (PID {new_pid})": "[成功] {scope_label} 服务已重启 (PID {new_pid})",
    "[成功] {scope_label} service restarted": "[成功] {scope_label} 服务已重启",
    "↻ Updated gateway {_service_scope_label} service definition to match the current BookwormPRO install": "↻ 已更新 gateway {_service_scope_label} 服务定义以匹配当前 BookwormPRO 安装",
    "    sudo loginctl enable-linger {username}": "    sudo loginctl enable-linger {username}",
    "    systemctl --user restart {get_service_name}.service": "    systemctl --user restart {get_service_name}.service",
    "↻ Repairing outdated {_service_scope_label} systemd service at: {unit_path}": "↻ 正在修复过时的 {_service_scope_label} systemd 服务: {unit_path}",
    "[成功] {_service_scope_label} service definition updated": "[成功] {_service_scope_label} 服务定义已更新",
    "Service already installed at: {unit_path}": "服务已安装于: {unit_path}",
    "Installing {_service_scope_label} systemd service to: {unit_path}": "正在安装 {_service_scope_label} systemd 服务到: {unit_path}",
    "[成功] {_service_scope_label} service installed and enabled!": "[成功] {_service_scope_label} 服务已安装并启用！",
    "Configured to run as: {configured_user}": "配置运行用户: {configured_user}",
    "[成功] Removed {unit_path}": "[成功] 已删除 {unit_path}",
    "[成功] {_service_scope_label} service uninstalled": "[成功] {_service_scope_label} 服务已卸载",
    "System gateway {action} requires root. Re-run with sudo.": "系统 gateway {action} 需要 root 权限。请使用 sudo 重新运行。",
    "[成功] Enabled linger for {username} — user D-Bus now available": "[成功] 已为 {username} 启用 linger — 用户 D-Bus 现已可用",
    "  {path}  ({scope} scope)": "  {path}  ({scope} 范围)",
    "  [成功] Removed {path}": "  [成功] 已删除 {path}",
    "  [警告] Could not remove {path}: {e}": "  [警告] 无法删除 {path}: {e}",
    "[警告] Permission denied to kill PID {pid}": "[警告] 无权终止 PID {pid}",
    "Failed to kill PID {pid}: {exc}": "终止 PID {pid} 失败: {exc}",
    "[警告] Could not verify systemd linger ({linger_detail})": "[警告] 无法验证 systemd linger ({linger_detail})",
    "[警告] Installed gateway service definition is outdated": "[警告] 已安装的 gateway 服务定义已过时",
    "Auto-enable failed: {detail}": "自动启用失败: {detail}",
    "[成功] Linger enabled — gateway will persist after logout": "[成功] Linger 已启用 — gateway 将在注销后继续运行",

    # ── memory_setup.py ──
    "  [警告] uv not found — cannot install dependencies": "  [警告] 未找到 uv — 无法安装依赖",
    "  [成功] Installed {joined_missing}": "  [成功] 已安装 {joined_missing}",
    "  [警告] '{dep_name}' not found. Install with:": "  [警告] 未找到 '{dep_name}'。请使用以下命令安装:",
    "  No memory entry mentions {needle}.": "  没有记忆条目提及 {needle}。",

    # ── backup.py ──
    "Backup complete.": "备份完成。",
    "Restore complete.": "还原完成。",
    "No backup found.": "未找到备份。",
    "Backup already exists.": "备份已存在。",
    "Overwrite existing backup? [y/N]: ": "覆盖现有备份? [y/N]: ",

    # ── auth.py ──
    "Authorization successful.": "授权成功。",
    "Authorization failed.": "授权失败。",
    "Login required.": "需要登录。",

    # ── claw.py ──
    "Usage: bookworm claw <command> [options]": "用法: bookworm claw <命令> [选项]",
    "Commands:": "命令:",

    # ── status.py ──
    "Checking status...": "正在检查状态…",

    # ── debug.py ──
    "Collecting debug report...": "正在收集调试报告…",

    # ── hooks.py ──
    "Unknown event: {event}": "未知事件: {event}",

    # ── profiles.py ──
    "\nProfile: {name}": "\n配置文件: {name}",

    # ── logs.py ──
    "No logs found.": "未找到日志。",

    # ── cli_output.py ──
    "成功": "成功",
    "警告": "警告",
    "失败": "失败",

    # ── Proper nouns / platform names (keep as-is) ──
    "modal": "modal",
    "daytona": "daytona",
    "mautrix": "mautrix",
    "  The ": "  ",
    "The ": "",

    # ── auth / login errors ──
    "Login failed: {exc}": "登录失败: {exc}",
    "  Login failed: {exc}": "  登录失败: {exc}",
    "Session expired: {msg}": "会话已过期: {msg}",
    "Re-login failed: {login_exc}": "重新登录失败: {login_exc}",
    "Could not verify credentials: {msg}": "无法验证凭证: {msg}",
    "OAuth login failed: {exc}": "OAuth 登录失败: {exc}",
    "Anthropic OAuth login did not return credentials.": "Anthropic OAuth 登录未返回凭证。",
    "Paste your API key: ": "请粘贴您的 API 密钥: ",
    "No API key provided.": "未提供 API 密钥。",
    "Label (optional, default: {default_label}): ": "标签 (可选, 默认: {default_label}): ",
    "Removed {provider} credential #{index} ({removed_label})": "已删除 {provider} 凭证 #{index} ({removed_label})",
    "Reset status on {count} {provider} credentials": "已重置 {count} 个 {provider} 凭证状态",
    "No credentials for {provider}.": "{provider} 无凭证。",
    "No auth state found for {provider_name}.": "未找到 {provider_name} 的认证状态。",
    "Logged out of {provider_name}.": "已退出 {provider_name}。",
    "Unknown provider: {provider_id}": "未知提供商: {provider_id}",
    "Unknown provider: {provider}": "未知提供商: {provider}",
    "Added {provider} credential #{n}: \"{label}\"": "已添加 {provider} 凭证 #{n}: \"{label}\"",
    "Added {provider} OAuth credential #{n}: \"{label}\"": "已添加 {provider} OAuth 凭证 #{n}: \"{label}\"",
    "Saved {provider} OAuth device-code credentials: \"{label}\"": "已保存 {provider} OAuth 设备码凭证: \"{label}\"",
    "`bookworm auth add {provider}` is not implemented for auth type {requested_type} yet.": "`bookworm auth add {provider}` 尚未支持认证类型 {requested_type}。",
    "\\n{provider} supports both API keys and OAuth login.": "\\n{provider} 同时支持 API 密钥和 OAuth 登录。",
    "\\nCurrent strategy for {provider}: {current}": "\\n{provider} 当前策略: {current}",
    "Set {provider} strategy to: {strategy}": "已将 {provider} 策略设置为: {strategy}",
    "  #{i}  {e_label:25s} {e_auth_type:10s} {e_source}{exhausted} [id:{e_id}]": "  #{i}  {e_label:25s} {e_auth_type:10s} {e_source}{exhausted} [id:{e_id}]",
    "bedrock (AWS SDK credential chain):": "bedrock (AWS SDK 凭证链):",
    "  Auth: {auth_source}": "  认证: {auth_source}",
    "  Region: {region}": "  区域: {region}",
    "  Identity: {arn}": "  身份: {arn}",
    "  Identity: (could not resolve — boto3 STS call failed)": "  身份: (无法解析 — boto3 STS 调用失败)",
    "\\nKnown providers: {', '.join(known)}": "\\n已知提供商: {join_known}",
    "Custom endpoints: {', '.join(custom_display)}": "自定义端点: {join_custom_display}",

    # ── model / provider config ──
    "Default model set to: {selected} (via OpenRouter)": "默认模型已设置为: {selected} (通过 OpenRouter)",
    "Default model set to: {selected} (via Vercel AI Gateway)": "默认模型已设置为: {selected} (通过 Vercel AI Gateway)",
    "Default model set to: {selected} (via BookwormPRO Portal)": "默认模型已设置为: {selected} (通过 BookwormPRO Portal)",
    "Default model set to: {selected} (via OpenAI Codex)": "默认模型已设置为: {selected} (通过 OpenAI Codex)",
    "Default model set to: {selected} (via Qwen OAuth)": "默认模型已设置为: {selected} (通过 Qwen OAuth)",
    "Default model set to: {selected} (via Anthropic)": "默认模型已设置为: {selected} (通过 Anthropic)",
    "Default model set to: {selected} (via {pconfig_name})": "默认模型已设置为: {selected} (通过 {pconfig_name})",
    "Default model set to: {selected} (via {endpoint_label})": "默认模型已设置为: {selected} (通过 {endpoint_label})",
    "Default model set to: {model_name} (via {effective_url})": "默认模型已设置为: {model_name} (通过 {effective_url})",
    "Default model set to: {selected_model}": "默认模型已设置为: {selected_model}",
    "  Default model set to: {selected} (via Bedrock API Key, {region})": "  默认模型已设置为: {selected} (通过 Bedrock API Key, {region})",
    "  Default model set to: {selected} (via AWS Bedrock, {region})": "  默认模型已设置为: {selected} (通过 AWS Bedrock, {region})",
    "Upgrade at {_url} to access paid models.": "在 {_url} 升级以访问付费模型。",
    "Expected credentials file: {auth_file}": "预期凭证文件: {auth_file}",
    "Error: {status}": "错误: {status}",
    "  Using GCP project: {project_id}": "  使用 GCP 项目: {project_id}",
    "Failed to resolve Gemini credentials: {exc}": "解析 Gemini 凭证失败: {exc}",
    "  Current URL: {current_url}": "  当前 URL: {current_url}",
    "  Current key: {current_key}...": "  当前密钥: {current_key}...",
    "Invalid URL: {effective_url} (must start with http:// or https://)": "无效 URL: {effective_url} (必须以 http:// 或 https:// 开头)",
    "  Hint: Did you mean to add /v1 at the end?": "  提示: 您是否需要在末尾添加 /v1？",
    "  Most local model servers (Ollama, vLLM, llama.cpp) require it.": "  大多数本地模型服务器 (Ollama, vLLM, llama.cpp) 需要它。",
    "  e.g. {effective_url}/v1": "  例如: {effective_url}/v1",
    "  Updated URL: {effective_url}": "  已更新 URL: {effective_url}",
    "  If /v1 should not be in the base URL, try: {suggested}": "  如果 /v1 不应在基础 URL 中，请尝试: {suggested}",
    "  Detected model: {detected_models}": "  检测到的模型: {detected_models}",
    "Invalid context length: {context_length_str} — will auto-detect.": "无效的上下文长度: {context_length_str} — 将自动检测。",
    "  Provider: {name}": "  提供商: {name}",
    "  URL:      {base_url}": "  URL:      {base_url}",
    "  Current:  {saved_model}": "  当前:  {saved_model}",
    "   Provider: {name} ({base_url})": "   提供商: {name} ({base_url})",
    "Please enter 1-{n}": "请输入 1-{n}",
    "  {selected} supports reasoning controls.": "  {selected} 支持推理控制。",
    "Reasoning effort set to: {selected_effort}": "推理力度已设置为: {selected_effort}",
    "  Command: {resolved_command}": "  命令: {resolved_command}",
    "  Backend marker: {effective_base}": "  后端标识: {effective_base}",
    "No {pconfig_name} API key configured.": "未配置 {pconfig_name} API 密钥。",
    "  Detected Kimi Coding Plan key → {effective_base}": "  检测到 Kimi Coding Plan 密钥 → {effective_base}",
    "  Using Moonshot endpoint → {effective_base}": "  使用 Moonshot 端点 → {effective_base}",
    "  Endpoint: {mantle_base_url}": "  端点: {mantle_base_url}",
    "  Bedrock will use boto3's default credential chain (IMDS, SSO, etc.)": "  Bedrock 将使用 boto3 的默认凭证链 (IMDS、SSO 等)",
    "  Discovering models in {region}...": "  正在探索 {region} 中的模型...",
    "  Running 'claude setup-token' — follow the prompts below.": "  正在运行 'claude setup-token' — 请按照以下提示操作。",
    "  The 'claude' CLI is required for OAuth login.": "  OAuth 登录需要 'claude' CLI。",
    "  Config updated: {config_path} (model.provider=openai-codex)": "  配置已更新: {config_path} (model.provider=openai-codex)",
    "  Config updated: {config_path} (model.provider=bookwormpro)": "  配置已更新: {config_path} (model.provider=bookwormpro)",
    "Starting BookwormPRO login via {pconfig_name}...": "正在通过 {pconfig_name} 登录 BookwormPRO...",
    "Portal: {portal_base_url}": "Portal: {portal_base_url}",
    "TLS verification: custom CA bundle ({ca_bundle})": "TLS 验证: 自定义 CA 捆绑包 ({ca_bundle})",
    "  1. Open: {verification_url}": "  1. 打开: {verification_url}",
    "  2. If prompted, enter code: {user_code}": "  2. 如有提示，请输入代码: {user_code}",
    "Waiting for approval (polling every {effective_interval}s)...": "等待批准 (每 {effective_interval}s 轮询)...",
    "Using portal-provided inference URL: {resolved_inference_url}": "使用 Portal 提供的推理 URL: {resolved_inference_url}",
    "  Subscribe here: {portal_url}/billing": "  在此订阅: {portal_url}/billing",
    "Login succeeded, but could not fetch available models. Reason: {message}": "登录成功，但无法获取可用模型。原因: {message}",
    "Unknown provider: {provider_id}": "未知提供商: {provider_id}",
    "  Open this URL in your browser: {verification_uri}": "  在浏览器中打开此 URL: {verification_uri}",
    "  Enter this code: {user_code}": "  输入此代码: {user_code}",
    "({auth_var}, {region}, {model_count} models)": "({auth_var}, {region}, {model_count} 个模型)",
    "(boto3 not installed — {exe} -m pip install boto3)": "(未安装 boto3 — {exe} -m pip install boto3)",
    "  Primary:   {primary}": "  主要:   {primary}",
    "  Fallback chain ({count} {noun}):": "  回退链 ({count} 个 {noun}):",
    "Unknown fallback subcommand: {sub}": "未知回退子命令: {sub}",
    "entry": "条目",
    "entries": "条目",
    "  {_DIM}── Unavailable models (requires paid tier — upgrade at {_upgrade_url}) ──{_RESET}": "  {_DIM}── 不可用模型 (需要付费版 — 在 {_upgrade_url} 升级) ──{_RESET}",
    "The 'bookworm login' command has been removed.": "'bookworm login' 命令已被移除。",
    "Use 'bookworm auth' to manage credentials,": "使用 'bookworm auth' 管理凭证，",
    "'bookworm model' to select a provider, or 'bookworm setup' for full setup.": "'bookworm model' 选择提供商，或 'bookworm setup' 进行完整设置。",

    # ── version / info ──
    "BookwormPRO v{__version__} ({__release_date__})": "BookwormPRO v{__version__} ({__release_date__})",
    "Project: {PROJECT_ROOT}": "项目: {PROJECT_ROOT}",
    "Python: {sys}": "Python: {sys}",
    "OpenAI SDK: {openai___version__}": "OpenAI SDK: {openai___version__}",
    "  Configure for: {platform_label}": "  配置平台: {platform_label}",
    "  Project:      {PROJECT_ROOT}": "  项目:      {PROJECT_ROOT}",
    "  Python:       {sys}": "  Python:       {sys}",

    # ── git / update ──
    "  Find the saved entry with: git stash list --format='%gd %H %s'": "  使用以下命令查找已保存条目: git stash list --format='%gd %H %s'",
    "  Remove it with: git stash drop {stash_selector}": "  使用以下命令删除: git stash drop {stash_selector}",
    "Restore manually with: git stash apply {stash_ref}": "手动恢复: git stash apply {stash_ref}",
    "  Stash ref: {stash_ref}": "  Stash 引用: {stash_ref}",
    "Restore your changes later with: git stash apply {stash_ref}": "稍后使用以下命令恢复更改: git stash apply {stash_ref}",
    "Add official repo as 'upstream' remote? [Y/n]: ": "将官方仓库添加为 'upstream' 远程? [Y/n]: ",
    "ℹ Your fork has {origin_ahead} commit(s) not on upstream.": "ℹ 您的 fork 有 {origin_ahead} 个提交未在 upstream 上。",
    "→ Fork is {upstream_ahead} commit(s) behind upstream": "→ Fork 落后 upstream {upstream_ahead} 个提交",
    "[BWM] Updating BookwormPRO...": "[BWM] 正在更新 BookwormPRO...",
    "→ Found {commit_count} new commit(s)": "→ 发现 {commit_count} 个新提交",
    "  Restore manually with: git stash apply": "  手动恢复: git stash apply",
    "Error: git init failed: {result_stderr}": "错误: git init 失败: {result_stderr}",
    "   Remote: {remote_url}": "   远程: {remote_url}",
    "        OR: git clone <remote> ~/.bookwormpro/": "        或: git clone <remote> ~/.bookwormpro/",

    # ── profile management ──
    "Switched to: {name}": "已切换至: {name}",
    "Switched to: default (~/.bookwormpro)": "已切换至: default (~/.bookwormpro)",
    "\\nProfile '{name}' created at {profile_dir}": "\\n配置文件 '{name}' 已创建于 {profile_dir}",
    "Full copy from {source_label}.": "从 {source_label} 完整复制。",
    "Cloned config, .env, SOUL.md from {source_label}.": "已从 {source_label} 克隆 config、.env、SOUL.md。",
    "Honcho config cloned (peer: {name})": "Honcho 配置已克隆 (peer: {name})",
    "  Or access via flag:     bookworm -p {name} chat": "  或通过参数访问:     bookworm -p {name} chat",
    "Wrapper created: {wrapper_path}": "包装器已创建: {wrapper_path}",
    "  Wrapper created: {wrapper_path}": "  包装器已创建: {wrapper_path}",
    "    export PATH=\"$HOME/.local/bin:$PATH\"": "    export PATH=\"$HOME/.local/bin:$PATH\"",
    "\\nNext steps:": "\\n后续步骤:",
    "  {name} setup              Configure API keys and model": "  {name} setup              配置 API 密钥和模型",
    "  {name} chat               Start chatting": "  {name} chat               开始聊天",
    "  {name} gateway start      Start the messaging gateway": "  {name} gateway start      启动消息网关",
    "\\n  Edit {profile_dir_display}/.env for different API keys": "\\n  编辑 {profile_dir_display}/.env 以使用不同的 API 密钥",
    "  Edit {profile_dir_display}/SOUL.md for different personality": "  编辑 {profile_dir_display}/SOUL.md 以自定义个性",
    "    or it will inherit keys from your shell environment.": "    否则将继承 shell 环境中的密钥。",
    "  Edit {profile_dir_display}/SOUL.md to customize personality": "  编辑 {profile_dir_display}/SOUL.md 以自定义个性",
    "Error: Profile '{name}' does not exist.": "错误: 配置文件 '{name}' 不存在。",
    "\\nProfile: {name}": "\\n配置文件: {name}",
    "Path:    {profile_dir}": "路径:    {profile_dir}",
    "Model:   {model}": "模型:   {model}",
    "Gateway: {'running' if gw else 'stopped'}": "Gateway: {gw_status}",
    "Skills:  {skills}": "技能:  {skills}",
    "Alias:   {wrapper}": "别名:   {wrapper}",
    "No alias '{alias_name}' found to remove.": "未找到别名 '{alias_name}'，无法删除。",
    "Error: {collision}": "错误: {collision}",
    "\\nProfile renamed: {args_old_name} → {args_new_name}": "\\n配置文件已重命名: {args_old_name} → {args_new_name}",
    "Path: {new_dir}\\n": "路径: {new_dir}\\n",
    "Import error: {e}": "导入错误: {e}",
    "Skills:  {skill_count}": "技能:  {skill_count}",
    "\\nThis will permanently delete:": "\\n这将永久删除:",
    "\\nProfile '{name}' deleted.": "\\n配置文件 '{name}' 已删除。",
    "\\nActive profile: {profile_name}": "\\n活动配置文件: {profile_name}",
    "Path:           {dhh}": "路径:           {dhh}",
    "Skills:         {p_skill_count} installed": "技能:         已安装 {p_skill_count} 个",
    "Alias:          {p_name} → bookworm -p {p_name}": "别名:          {p_name} → bookworm -p {p_name}",
    "  {p_name}: error ({pe})": "  {p_name}: 错误 ({pe})",
    "\\n-> Honcho: synced {synced} profile(s)": "\\n-> Honcho: 已同步 {synced} 个配置文件",
    "Would you like to configure them now? [Y/n]: ": "是否立即配置? [Y/n]: ",
    "Skipped. Run 'bookworm config migrate' later to configure.": "已跳过。稍后运行 'bookworm config migrate' 进行配置。",
    "    {path}  ({scope} scope)": "    {path}  ({scope} 范围)",

    # ── backup / import ──
    "Error: BookwormPRO home directory not found at {hermes_root}": "错误: 未找到 BookwormPRO 主目录 {hermes_root}",
    "Scanning {home} ...": "正在扫描 {home} ...",
    "Backing up {file_count} files ...": "正在备份 {file_count} 个文件 ...",
    "SQLite safe copy failed": "SQLite 安全复制失败",
    "  {i}/{file_count} files ...": "  {i}/{file_count} 个文件 ...",
    "Backup complete: {out_path}": "备份完成: {out_path}",
    "  Files:       {file_count}": "  文件:       {file_count}",
    "  Time:        {elapsed:.1f}s": "  耗时:        {elapsed:.1f}s",
    "\\n  Excluded directories:": "\\n  已排除目录:",
    "\\nRestore with: bookworm import {out_path_name}": "\\n使用以下命令恢复: bookworm import {out_path_name}",
    "Error: File not found: {zip_path}": "错误: 文件未找到: {zip_path}",
    "Error: Not a valid zip file: {zip_path}": "错误: 不是有效的 zip 文件: {zip_path}",
    "Error: {reason}": "错误: {reason}",
    "Backup contains {file_count} files": "备份包含 {file_count} 个文件",
    "\\nImporting {file_count} files ...": "\\n正在导入 {file_count} 个文件 ...",
    "  {restored}/{file_count} files ...": "  {restored}/{file_count} 个文件 ...",
    "Import complete: {restored} files restored in {elapsed:.1f}s": "导入完成: 已恢复 {restored} 个文件，耗时 {elapsed:.1f}s",
    "  Skipped alias '{profile_name}': {collision}": "  跳过别名 '{profile_name}': {collision}",
    "\\n  Profile aliases restored: {', '.join(created)}": "\\n  配置文件别名已恢复: {join_created}",
    "\\n  Profile aliases skipped:  {', '.join(skipped)}": "\\n  配置文件别名已跳过:  {join_skipped}",
    "\\n  Profiles detected but aliases could not be created.": "\\n  检测到配置文件，但无法创建别名。",
    "  Run: bookworm profile list  (after installing bookworm)": "  运行: bookworm profile list  (安装 bookworm 后)",
    "State snapshot created: {snap_id}": "状态快照已创建: {snap_id}",
    "  Restore with: /snapshot restore {snap_id}": "  使用以下命令恢复: /snapshot restore {snap_id}",

    # ── sessions ──
    "Level {args_learn}:": "级别 {args_learn}:",
    "Scenario: {r}": "场景: {r}",
    "Usage: bookworm navigate '<your intent>'": "用法: bookworm navigate '<您的意图>'",
    "\\n  This will permanently erase the following memory files:": "\\n  这将永久删除以下记忆文件:",
    "    ◆ {f} ({desc}) — {size:,} bytes": "    ◆ {f} ({desc}) — {size:,} 字节",
    "Error: Could not open session database: {e}": "错误: 无法打开会话数据库: {e}",
    "Session '{args_session_id}' not found.": "未找到会话 '{args_session_id}'。",
    "Exported 1 session to {args_output}": "已将 1 个会话导出到 {args_output}",
    "Deleted session '{resolved_session_id}'.": "已删除会话 '{resolved_session_id}'。",
    "Pruned {count} session(s).": "已清除 {count} 个会话。",
    "Session '{resolved_session_id}' renamed to: {title}": "会话 '{resolved_session_id}' 已重命名为: {title}",
    "Resuming session: {selected_id}": "正在恢复会话: {selected_id}",
    "Total sessions: {total}": "总会话数: {total}",
    "Total messages: {msgs}": "总消息数: {msgs}",
    "  {src}: {c} sessions": "  {src}: {c} 个会话",
    "Database size: {size_mb:.1f} MB": "数据库大小: {size_mb:.1f} MB",

    # ── cron ──
    "Create one with 'bookworm cron create ...' or the /cron command in chat.": "使用 'bookworm cron create ...' 或聊天中的 /cron 命令创建。",
    "[paused]": "[已暂停]",
    "[completed]": "[已完成]",
    "[active]": "[活动]",
    "[disabled]": "[已禁用]",
    "    Name:      {name}": "    名称:      {name}",
    "    Schedule:  {schedule}": "    计划:  {schedule}",
    "    Repeat:    {repeat_str}": "    重复:    {repeat_str}",
    "    Next run:  {next_run}": "    下次运行:  {next_run}",
    "    Deliver:   {deliver_str}": "    投递:   {deliver_str}",
    "    Skills:    {skills}": "    技能:    {skills}",
    "    Script:    {script}": "    脚本:    {script}",
    "    Workdir:   {workdir}": "    工作目录:   {workdir}",
    "    Last run:  {last_run}  {status_display}": "    上次运行:  {last_run}  {status_display}",
    "  PID: {pids}": "  PID: {pids}",
    "Failed to create job: {result}": "创建任务失败: {result}",
    "Created job: {result}": "已创建任务: {result}",
    "  Name: {result}": "  名称: {result}",
    "  Schedule: {result}": "  计划: {result}",
    "  Script: {job_data}": "  脚本: {job_data}",
    "  Workdir: {job_data}": "  工作目录: {job_data}",
    "  Next run: {result}": "  下次运行: {result}",
    "Job not found: {args_job_id}": "未找到任务: {args_job_id}",
    "Failed to update job: {result}": "更新任务失败: {result}",
    "Updated job: {updated}": "已更新任务: {updated}",
    "  Name: {updated}": "  名称: {updated}",
    "  Schedule: {updated}": "  计划: {updated}",
    "  Script: {updated}": "  脚本: {updated}",
    "  Workdir: {updated}": "  工作目录: {updated}",
    "Failed to {action} job: {result}": "{action} 任务失败: {result}",
    "Unknown cron command: {subcmd}": "未知 cron 命令: {subcmd}",

    # ── debug / upload ──
    "\\nUpload failed: {exc}": "\\n上传失败: {exc}",
    "\\nDebug report uploaded:": "\\n调试报告已上传:",
    "\\n  (failed to upload: {', '.join(failures)})": "\\n  (上传失败: {join_failures})",
    "To delete now:  bookworm debug delete <url>": "立即删除:  bookworm debug delete <url>",
    "\\nShare these links with the BookwormPRO team for support.": "\\n将这些链接分享给 BookwormPRO 团队以获取支持。",
    "  Deletes paste.rs pastes uploaded by 'bookworm debug share'.": "  删除由 'bookworm debug share' 上传的 paste.rs 粘贴内容。",

    # ── hooks ──
    "Run 'bookworm hooks --help' for details.": "运行 'bookworm hooks --help' 查看详细信息。",
    "Unknown hooks subcommand: {sub}": "未知 hooks 子命令: {sub}",
    "      approved_at: {entry}": "      approved_at: {entry}",
    "Valid events: {', '.join(sorted(VALID_HOOKS))}": "有效事件: {join_valid_hooks}",
    "Warning: {args_payload_file} is not a JSON object; ignoring": "警告: {args_payload_file} 不是 JSON 对象；已忽略",
    "Error reading payload file: {exc}": "读取 payload 文件出错: {exc}",
    "No shell hooks configured for event: {event}": "未为事件 {event} 配置 shell hook",
    "(with matcher filter --for-tool={args_for_tool})": "(使用匹配器过滤 --for-tool={args_for_tool})",
    "      exit={rc}  elapsed={elapsed}s": "      退出码={rc}  耗时={elapsed}s",
    "      parsed (BookwormPRO wire shape): {json}": "      已解析 (BookwormPRO 线格式): {json}",
    "No allowlist entry found for command: {args_command}": "未找到命令 {args_command} 的允许列表条目",
    "Removed {removed} allowlist entry/entries for: {args_command}": "已删除 {args_command} 的 {removed} 个允许列表条目",

    # ── logs ──
    "Log file not found: {log_path}": "日志文件未找到: {log_path}",
    "(Logs are created when BookwormPRO runs — try 'bookworm chat' first)": "(日志在 BookwormPRO 运行时创建 — 先试试 'bookworm chat')",
    "Permission denied: {log_path}": "权限拒绝: {log_path}",
    "  (no log files yet — run 'bookworm chat' to generate logs)": "  (尚无日志文件 — 运行 'bookworm chat' 生成日志)",

    # ── mcp ──
    "  Connecting to '{name}'...": "  正在连接 '{name}'...",
    "  Testing '{name}'...": "  正在测试 '{name}'...",
    "Error: 'bookworm mcp configure' requires an interactive terminal.": "错误: 'bookworm mcp configure' 需要交互式终端。",
    "  Connecting to '{name}' to discover tools...": "  正在连接 '{name}' 以发现工具...",
    "\\n  Installing dependencies: {', '.join(missing)}": "\\n  正在安装依赖: {join_missing}",
    "  Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh": "  安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh",
    "  Then re-run: bookworm memory setup": "  然后重新运行: bookworm memory setup",
    "  Run manually: uv pip install --python {sys_executable} {' '.join(missing)}": "  手动运行: uv pip install --python {sys_executable} {join_missing}",

    # ── memory ──
    "\\n  Memory provider '{provider_name}' not found.": "\\n  未找到记忆提供商 '{provider_name}'。",
    "  Run 'bookworm memory setup' to see available providers.\\n": "  运行 'bookworm memory setup' 查看可用提供商。\\n",
    "\\n  Memory provider: {name}": "\\n  记忆提供商: {name}",
    "  Activation saved to config.yaml\\n": "  激活已保存到 config.yaml\\n",
    "\\n  No memory provider plugins detected.": "\\n  未检测到记忆提供商插件。",
    "  Install a plugin to ~/.bookwormpro/plugins/ and try again.\\n": "  安装插件到 ~/.bookwormpro/plugins/ 后重试。\\n",
    "\\n  Configuring {name}:\\n": "\\n  正在配置 {name}:\\n",
    "  Failed to write provider config: {e}": "  写入提供商配置失败: {e}",
    "  Activation saved to config.yaml": "  激活已保存到 config.yaml",
    "  Provider config saved": "  提供商配置已保存",
    "  API keys saved to .env": "  API 密钥已保存到 .env",
    "\\n  Start a new session to activate.\\n": "\\n  启动新会话以激活。\\n",
    "\\nMemory status\\n": "\\n记忆状态\\n",
    "  Built-in:  always active": "  内置:  始终活动",
    "  Provider:  {provider_name}": "  提供商:  {provider_name}",
    "\\n  {provider_name} config:": "\\n  {provider_name} 配置:",
    "  Missing:": "  缺失:",
    "  Install the '{provider_name}' memory plugin to ~/.bookwormpro/plugins/": "  安装 '{provider_name}' 记忆插件到 ~/.bookwormpro/plugins/",
    "\\n  Installed plugins:": "\\n  已安装插件:",
    "\\n  No matching memory store.\\n": "\\n  无匹配的记忆存储。\\n",
    "  (not present — nothing remembered yet)\\n": "  (不存在 — 尚未记忆任何内容)\\n",
    "  (read failed: {exc})\\n": "  (读取失败: {exc})\\n",
    "  (empty)\\n": "  (空)\\n",
    "\\n  [{idx}]": "\\n  [{idx}]",
    "\\n  Usage: bookworm memory why <substring>\\n": "\\n  用法: bookworm memory why <子字符串>\\n",
    "  The agent has no recorded reason — it may be inferring from": "  Agent 没有记录的原因 — 可能正在从",
    "  current context, project files, or skill defaults instead.\\n": "  当前上下文、项目文件或技能默认值中推断。\\n",
    "\\n  ━━ {label} entry [{idx}] ━━": "\\n  ━━ {label} 条目 [{idx}] ━━",
    "  source: {path}": "  来源: {path}",

    # ── pairing ──
    "Usage: bookworm pairing {list|approve|revoke|clear-pending}": "用法: bookworm pairing {list|approve|revoke|clear-pending}",
    "Run 'bookworm pairing --help' for details.": "运行 'bookworm pairing --help' 查看详细信息。",
    "No pairing data found. No one has tried to pair yet~": "未找到配对数据。尚无人尝试配对~",
    "\\n  No pending pairing requests.": "\\n  无待处理的配对请求。",
    "\\n  No approved users.": "\\n  无已批准的用户。",
    "\\n  Approved! User {display} on {platform} can now use the bot~": "\\n  已批准！用户 {display} 在 {platform} 上现在可以使用机器人~",
    "  They'll be recognized automatically on their next message.\\n": "  他们的下一条消息将被自动识别。\\n",
    "\\n  Code '{code}' not found or expired for platform '{platform}'.": "\\n  平台 '{platform}' 的代码 '{code}' 未找到或已过期。",
    "  Run 'bookworm pairing list' to see pending codes.\\n": "  运行 'bookworm pairing list' 查看待处理代码。\\n",
    "\\n  Revoked access for user {user_id} on {platform}.\\n": "\\n  已撤销用户 {user_id} 在 {platform} 上的访问权限。\\n",
    "\\n  User {user_id} not found in approved list for {platform}.\\n": "\\n  在 {platform} 的批准列表中未找到用户 {user_id}。\\n",
    "\\n  Cleared {count} pending pairing request(s).\\n": "\\n  已清除 {count} 个待处理配对请求。\\n",
    "\\n  No pending requests to clear.\\n": "\\n  无待处理请求可清除。\\n",

    # ── status / doctor ──
    "logged in": "已登录",
    "not logged in (run: bookworm auth add bookwormpro --type oauth)": "未登录 (运行: bookworm auth add bookwormpro --type oauth)",
    "    Portal URL: {portal_url}": "    Portal URL: {portal_url}",
    "    Access exp: {access_exp}": "    访问过期: {access_exp}",
    "    Key exp:    {key_exp}": "    密钥过期:    {key_exp}",
    "    Refresh:    {refresh_label}": "    刷新:    {refresh_label}",
    "    Error:      {nous_error}": "    错误:      {nous_error}",
    "    Auth file:  {codex_auth_file}": "    认证文件:  {codex_auth_file}",
    "    Refreshed:  {codex_last_refresh}": "    已刷新:  {codex_last_refresh}",
    "    Error:      {codex_status}": "    错误:      {codex_status}",
    "    Auth file:  {qwen_auth_file}": "    认证文件:  {qwen_auth_file}",
    "    Access exp: {datetime}": "    访问过期: {datetime}",
    "    Error:      {qwen_status}": "    错误:      {qwen_status}",
    "not logged in": "未登录",
    "managed tools available": "托管工具可用",
    "active via BookwormPRO subscription": "通过 BookwormPRO 订阅激活",
    "configured provider": "已配置提供商",
    "active via {current}": "通过 {current} 激活",
    "included by subscription, not currently selected": "订阅包含，当前未选择",
    "available via subscription (optional)": "可通过订阅使用 (可选)",
    "  Upgrade: {portal_url}": "  升级: {portal_url}",
    "  Backend:      {terminal_env}": "  后端:      {terminal_env}",
    "  SSH Host:     {ssh_host}": "  SSH 主机:     {ssh_host}",
    "  SSH User:     {ssh_user}": "  SSH 用户:     {ssh_user}",
    "  Docker Image: {docker_image}": "  Docker 镜像: {docker_image}",
    "  Daytona Image: {daytona_image}": "  Daytona 镜像: {daytona_image}",
    "  Manager:      {snapshot_manager}": "  管理器:      {snapshot_manager}",
    "  Port 18789:   {'in use' if port_in_use else 'available'}": "  端口 18789:   {port_status}",
    "  Run 'bookworm doctor' for detailed diagnostics": "  运行 'bookworm doctor' 进行详细诊断",
    "  Run 'bookworm setup' to configure": "  运行 'bookworm setup' 进行配置",
    "exists": "存在",
    "not found": "未找到",
    "not logged in (run: bookworm model)": "未登录 (运行: bookworm model)",
    "not logged in (run: qwen auth qwen-oauth)": "未登录 (运行: qwen auth qwen-oauth)",
    "  {ts_label} requires configuration:": "  {ts_label} 需要配置:",
    "  --- {icon} {name} - Choose a provider ---": "  --- {icon} {name} - 选择提供商 ---",
    "[BWM] Tool Summary": "[BWM] 工具摘要",
    "[BWM] BookwormPRO Tool Configuration": "[BWM] BookwormPRO 工具配置",
    "  You can skip any tool you don't need right now.": "  您可以跳过当前不需要的任何工具。",
    "  No changes to {pinfo}": "  {pinfo} 无变更",
    "  Changes take effect on next 'bookworm' or gateway restart.": "  更改在下次 'bookworm' 或 gateway 重启后生效。",
    "Built-in toolsets ({platform}):": "内置工具集 ({platform}):",
    "Plugin toolsets ({platform}):": "插件工具集 ({platform}):",

    # ── webhook ──
    "Run 'bookworm webhook --help' for details.": "运行 'bookworm webhook --help' 查看详细信息。",
    "Error: Invalid name '{name}'. Use lowercase alphanumeric with hyphens/underscores.": "错误: 无效名称 '{name}'。请使用小写字母数字及连字符/下划线。",
    "\\n  {status} webhook subscription: {name}": "\\n  {status} webhook 订阅: {name}",
    "  URL:    {base_url}/webhooks/{name}": "  URL:    {base_url}/webhooks/{name}",
    "  Secret: {secret}": "  密钥: {secret}",
    "  Events: {', '.join(events)}": "  事件: {join_events}",
    "  Deliver: {route}": "  投递: {route}",
    "\\n  Configure your service to POST to the URL above.": "\\n  配置您的服务以 POST 到上述 URL。",
    "  Use the secret for HMAC-SHA256 signature validation.": "  使用密钥进行 HMAC-SHA256 签名验证。",
    "  The gateway must be running to receive events (bookworm gateway run).\\n": "  必须运行 gateway 才能接收事件 (bookworm gateway run)。\\n",
    "    URL:     {base_url}/webhooks/{name}": "    URL:     {base_url}/webhooks/{name}",
    "    Events:  {events}": "    事件:  {events}",
    "    Deliver: {deliver}": "    投递: {deliver}",
    "  No subscription named '{name}'.": "  未找到名为 '{name}' 的订阅。",
    "  Removed webhook subscription: {name}": "  已删除 webhook 订阅: {name}",
    "  Sending test POST to {url}": "  正在发送测试 POST 到 {url}",
    "  Response ({resp_status}): {body}": "  响应 ({resp_status}): {body}",
    "  Error: {e}": "  错误: {e}",
    "  BookwormPRO Web UI → http://{host}:{port}": "  BookwormPRO Web UI → http://{host}:{port}",

    # ── voice ──
    "[voice] {msg}": "[语音] {msg}",

    # ── gateway / service ──
    "  ─── {emoji} {label} Setup ───": "  ─── {emoji} {label} 设置 ───",
    "To enable systemd: add systemd=true to /etc/wsl.conf and run 'wsl --shutdown' from PowerShell": "启用 systemd: 在 /etc/wsl.conf 中添加 systemd=true 并在 PowerShell 中运行 'wsl --shutdown'",
    "The gateway runs as the container's main process.": "gateway 作为容器的主进程运行。",
    "  Run:  sudo loginctl enable-linger {_username}": "  运行:  sudo loginctl enable-linger {_username}",
    "Full guide: {SPOTIFY_DOCS_URL}": "完整指南: {SPOTIFY_DOCS_URL}",
    "  1. Opening {SPOTIFY_DASHBOARD_URL} in your browser...": "  1. 正在浏览器中打开 {SPOTIFY_DASHBOARD_URL}...",
    "  2. Click 'Create app' and fill in:": "  2. 点击 '创建应用' 并填写:",
    "       Redirect URI: {redirect_uri_hint}": "       重定向 URI: {redirect_uri_hint}",
    "  4. Open the app's Settings page and copy the Client ID.": "  4. 打开应用的设置页面并复制 Client ID。",
    "No Client ID entered. See {SPOTIFY_DOCS_URL} for the full guide.": "未输入 Client ID。请参阅 {SPOTIFY_DOCS_URL} 查看完整指南。",
    "Client ID: {client_id}": "Client ID: {client_id}",
    "Redirect URI: {redirect_uri}": "重定向 URI: {redirect_uri}",
    "Full setup guide: {SPOTIFY_DOCS_URL}": "完整设置指南: {SPOTIFY_DOCS_URL}",
    "  Auth state: {saved_to}": "  认证状态: {saved_to}",
    "  Docs: {SPOTIFY_DOCS_URL}": "  文档: {SPOTIFY_DOCS_URL}",
    "↻ Repairing outdated launchd service at: {plist_path}": "↻ 正在修复过时的 launchd 服务: {plist_path}",
    "Service already installed at: {plist_path}": "服务已安装于: {plist_path}",
    "Installing launchd service to: {plist_path}": "正在安装 launchd 服务到: {plist_path}",
    "Launchd plist: {plist_path}": "Launchd plist: {plist_path}",
    "  Auto-enable failed: {detail}": "  自动启用失败: {detail}",
    "  Run: {'sudo ' if system else ''}bookworm gateway install{scope_flag}": "  运行: bookworm gateway install{scope_flag}",
    "  Run: {'sudo ' if system else ''}bookworm gateway restart{scope_flag}  # auto-refreshes the service definition": "  运行: bookworm gateway restart{scope_flag}  # 自动刷新服务定义",
    "  Run: {'sudo ' if system else ''}bookworm gateway start{scope_flag}": "  运行: bookworm gateway start{scope_flag}",

    # ── WhatsApp setup ──
    "   phone with the BOT's number, then scan:": "   手机输入机器人号码，然后扫描:",
    "    2. Send a message to the bot's WhatsApp number": "    2. 向机器人的 WhatsApp 号码发送一条消息",
    "  Tip: Agent responses are prefixed with '[BWM] BookwormPRO'": "  提示: Agent 回复以 '[BWM] BookwormPRO' 开头",
    "Install them with:  pip install -e '.[acp]'": "使用以下命令安装:  pip install -e '.[acp]'",
    "Run 'bookworm claw <command> --help' for options.": "运行 'bookworm claw <命令> --help' 查看选项。",
    "(auto)": "(自动)",
    "Unknown fallback subcommand: {sub}": "未知回退子命令: {sub}",

    # ── plugins_cmd (Rich markup) ──
    "[dim]  Created {real_name} from {example_file.name}[/dim]": "[dim]  已从 {example_file} 创建 {real_name}[/dim]",
    "[yellow]Warning:[/yellow] Failed to copy {example_file.name}: {e}": "[yellow]警告:[/yellow] 复制 {example_file} 失败: {e}",
    "\\n[bold]{plugin_name}[/bold] requires the following environment variables:\\n": "\\n[bold]{plugin_name}[/bold] 需要以下环境变量:\\n",
    "  [dim]Get yours at: {url}[/dim]": "  [dim]在此获取: {url}[/dim]",
    "\\n[dim]  Skipped (you can set these later in {display_hermes_home}/.env)[/dim]": "\\n[dim]  已跳过 (您可以稍后在 {display_hermes_home}/.env 中设置)[/dim]",
    "  [dim]  Skipped (set {name} in {display_hermes_home}/.env later)[/dim]": "  [dim]  已跳过 (稍后在 {display_hermes_home}/.env 中设置 {name})[/dim]",
    "[red]Error:[/red] {e}": "[red]错误:[/red] {e}",
    "[yellow]Warning:[/yellow] Using insecure/local URL scheme. Consider using https:// or git@": "[yellow]警告:[/yellow] 使用了不安全/本地 URL 方案。建议使用 https:// 或 git@",
    "[dim]Cloning {git_url}...[/dim]": "[dim]正在克隆 {git_url}...[/dim]",
    "[red]Error:[/red] git is not installed or not in PATH.": "[red]错误:[/red] git 未安装或不在 PATH 中。",
    "[red]Error:[/red] Git clone timed out after 60 seconds.": "[red]错误:[/red] Git 克隆超时（60 秒）。",
    "[red]Error:[/red] Git pull timed out after 60 seconds.": "[red]错误:[/red] Git pull 超时（60 秒）。",
    "[dim]  Removing existing {plugin_name}...[/dim]": "[dim]  正在删除现有 {plugin_name}...[/dim]",
    "[dim]Plugin installed but not enabled. Run `bookworm plugins enable {installed_name}` to activate.": "[dim]插件已安装但未启用。运行 `bookworm plugins enable {installed_name}` 激活。",
    "[dim]Restart the gateway for the plugin to take effect:[/dim]": "[dim]重启 gateway 使插件生效:[/dim]",
    "[dim]  bookworm gateway restart[/dim]": "[dim]  bookworm gateway restart[/dim]",
    "[dim]Updating {name}...[/dim]": "[dim]正在更新 {name}...[/dim]",
    "[dim]{output}[/dim]": "[dim]{output}[/dim]",
    "[dim]No plugins installed.[/dim]": "[dim]未安装插件。[/dim]",
    "[dim]Install with:[/dim] bookworm plugins install owner/repo": "[dim]安装命令:[/dim] bookworm plugins install owner/repo",
    "[dim]Interactive toggle:[/dim] bookworm plugins": "[dim]交互式切换:[/dim] bookworm plugins",
    "[dim]Enable/disable:[/dim] bookworm plugins enable/disable <name>": "[dim]启用/禁用:[/dim] bookworm plugins enable/disable <name>",
    "[dim]Plugins are opt-in by default — only 'enabled' plugins load.[/dim]": "[dim]插件默认需手动启用 — 只有 'enabled' 插件会加载。[/dim]",
    "[dim]No plugins installed and no provider categories available.[/dim]": "[dim]未安装插件且无提供商类别。[/dim]",
    "[dim]Interactive mode requires a terminal.[/dim]": "[dim]交互模式需要终端。[/dim]",
    "[dim]Changes take effect on next session.[/dim]": "[dim]更改在下次会话时生效。[/dim]",

    # ── skills_hub (Rich markup) ──
    "[dim]Resolving '{name}'...[/]": "[dim]正在解析 '{name}'...[/]",
    "[dim]Resolved to: {exact_0_identifier}[/]": "[dim]已解析为: {exact_0_identifier}[/]",
    "\\n[yellow]Multiple skills named '{name}' found:[/]": "\\n[yellow]找到多个名为 '{name}' 的技能:[/]",
    "[bold]Use the full identifier to install a specific one.[/]\\n": "[bold]使用完整标识符安装特定技能。[/]\\n",
    "[yellow]No exact match for '{name}'. Did you mean one of these?[/]": "[yellow]未找到 '{name}' 的精确匹配。您是否想要以下之一?[/]",
    "  [cyan]{r.name}[/] — {r.identifier}": "  [cyan]{r.name}[/] — {r.identifier}",
    "[bold red]Error:[/] No skill named '{name}' found in any source.\\n": "[bold red]错误:[/] 在任何来源中均未找到名为 '{name}' 的技能。\\n",
    "\\n[bold]Searching for:[/] {query}": "\\n[bold]正在搜索:[/] {query}",
    "[dim]No skills found matching your query.[/]\\n": "[dim]未找到匹配您查询的技能。[/]\\n",
    "[dim]No skills found in the Skills Hub.[/]\\n": "[dim]技能中心未找到技能。[/]\\n",
    "[bright_cyan]★ {official_count} official optional skill(s) from BookwormPRO Project[/]": "[bright_cyan]★ {official_count} 个来自 BookwormPRO 项目的官方可选技能[/]",
    "[dim]Tip: 'bookworm skills search <query>' searches deeper across all registries[/]\\n": "[dim]提示: 'bookworm skills search <query>' 可在所有注册表中深度搜索[/]\\n",
    "\\n[bold]Fetching:[/] {identifier}": "\\n[bold]正在获取:[/] {identifier}",
    "[bold red]Error:[/] Could not fetch '{identifier}' from any source.": "[bold red]错误:[/] 无法从任何来源获取 '{identifier}'。",
    "Use --force to reinstall.\\n": "使用 --force 重新安装。\\n",
    "[bold]Running security scan...[/]": "[bold]正在运行安全扫描...[/]",
    "[dim]Installation cancelled.[/]\\n": "[dim]安装已取消。[/]\\n",
    "[dim]Skill will be available in your next session.[/]": "[dim]技能将在您的下一个会话中可用。[/]",
    "[bold red]Error:[/] Could not find '{identifier}' in any source.\\n": "[bold red]错误:[/] 在任何来源中均未找到 '{identifier}'。\\n",
    "[dim]No hub-installed skills to check.[/]\\n": "[dim]没有通过 Hub 安装的技能可供检查。[/]\\n",
    "[dim]No updates available.[/]\\n": "[dim]没有可用更新。[/]\\n",
    "[dim]No hub-installed skills to audit.[/]\\n": "[dim]没有通过 Hub 安装的技能可供审计。[/]\\n",
    "[dim]Cancelled.[/]\\n": "[dim]已取消。[/]\\n",
    "[dim]Change will take effect in your next session.[/]": "[dim]更改将在您的下一个会话中生效。[/]",
    "[dim]No custom taps configured. Using default sources only.[/]\\n": "[dim]未配置自定义 tap。仅使用默认来源。[/]\\n",
    "[bold red]Cannot publish a skill with DANGEROUS verdict.[/]\\n": "[bold red]无法发布具有 DANGEROUS 判定的技能。[/]\\n",
    "[bold green]Snapshot import complete.[/]\\n": "[bold green]快照导入完成。[/]\\n",
    "[dim]No skills in snapshot to install.[/]\\n": "[dim]快照中没有可安装的技能。[/]\\n",
    "[bold red]Unknown action:[/] {action}": "[bold red]未知操作:[/] {action}",

    # ── feishu / wecom / platform ──
    "\\n  Scan the QR code above, or open this URL directly:\\n  {qr_url}": "\\n  扫描上方二维码，或直接打开此 URL:\\n  {qr_url}",
    "  Open this URL in Feishu / Lark on your phone:\\n\\n  {qr_url}\\n": "  在手机上的飞书/Lark 中打开此 URL:\\n\\n  {qr_url}\\n",
    " failed: {exc}": " 失败: {exc}",
    "\\n  Scan the QR code above, or open this URL directly:\\n  {page_url}": "\\n  扫描上方二维码，或直接打开此 URL:\\n  {page_url}",
    "  Open this URL in WeCom on your phone:\\n\\n  {page_url}\\n": "  在手机上的企业微信中打开此 URL:\\n\\n  {page_url}\\n",
    "  QR scan timed out ({timeout_seconds} minutes). Please try again.": "  二维码扫描超时 ({timeout_seconds} 分钟)。请重试。",

    # ── feishu_comment_rules ──
    "Rules file: {RULES_FILE}": "规则文件: {RULES_FILE}",
    "  exists: {RULES_FILE}": "  存在: {RULES_FILE}",
    "Pairing file: {PAIRING_FILE}": "配对文件: {PAIRING_FILE}",
    "  exists: {PAIRING_FILE}": "  存在: {PAIRING_FILE}",
    "Top-level:": "顶层:",
    "  enabled:    {cfg_enabled}": "  已启用:    {cfg_enabled}",
    "  policy:     {cfg_policy}": "  策略:     {cfg_policy}",
    "  {uid}  (approved_at={ts})": "  {uid}  (批准时间={ts})",
    "Document:     {doc_key}": "文档:     {doc_key}",
    "User:         {user_open_id}": "用户:         {user_open_id}",
    "Resolved rule:": "已解析规则:",
    "  enabled:      {rule_enabled}": "  已启用:      {rule_enabled}",
    "  policy:       {rule_policy}": "  策略:       {rule_policy}",
    "  match_source: {rule_match_source}": "  匹配来源: {rule_match_source}",
    "Added: {args}": "已添加: {args}",
    "Already approved: {args}": "已批准: {args}",
    "Removed: {args}": "已删除: {args}",
    "Not in approved list: {args}": "不在批准列表中: {args}",
    "  {uid}  approved_at={meta}": "  {uid}  批准时间={meta}",
    "Unknown pairing subcommand: {sub}": "未知配对子命令: {sub}",

    # ── main.py selections / prompts ──
    "\\n  Select [1-{len}]: ": "\n  选择 [1-{len}]: ",
    "  Invalid selection. Enter 1-{len} or q to cancel.": "  无效选择，请输入 1-{len} 或 q 取消。",
    "{bin} not found — install Node.js to use the TUI.": "{bin} 未找到 — 请安装 Node.js 以使用 TUI。",
    "Run setup now? [Y/n] ": "现在运行设置？[Y/n] ",
    "  Choose [1/2]: ": "  选择 [1/2]: ",
    "\\n  Update allowed users? [y/N] ": "\n  更新允许用户？[y/N] ",
    "  Your phone number (e.g. 15551234567): ": "  您的手机号 (例如 15551234567): ",
    "  Configure {display_name} — current: {_format_aux_current}": "  配置 {display_name} — 当前: {_format_aux_current}",
    "{display_name}: reset to auto.": "{display_name}: 已重置为自动。",
    "Model: ": "模型: ",
    "{display_name}: {provider_slug} (provider default model)": "{display_name}: {provider_slug} (服务商默认模型)",
    "{display_name}: custom ({short_url})": "{display_name}: 自定义 ({short_url})",
    "Choice [1-{len}] ({default}): ": "选择 [1-{len}] ({default}): ",
    "Please enter 1-{len}": "请输入 1-{len}",
    "  Choice [1/2/3]: ": "  选择 [1/2/3]: ",
    "Continue with OAuth login? [y/N]: ": "继续 OAuth 登录？[y/N]: ",
    "  Add /v1? [Y/n]: ": "  添加 /v1？[Y/n]: ",
    "  Use this model? [Y/n]: ": "  使用此模型？[Y/n]: ",
    "Model name (e.g. gpt-4, llama-3-70b): ": "模型名称 (例如 gpt-4, llama-3-70b): ",
    "Choice [1-{len}]: ": "选择 [1-{len}]: ",
    "Found {len} model(s):\\n": "找到 {len} 个模型:\n",
    "  {len}. Cancel": "  {len}. 取消",
    "Model name: ": "模型名称: ",
    "Choice [1-{n}] (default: keep current): ": "选择 [1-{n}] (默认: 保持当前): ",
    "  Choice [1-3]: ": "  选择 [1-3]: ",
    "  Found {len} model(s) from GitHub Copilot": "  从 GitHub Copilot 找到 {len} 个模型",
    "Enter model name: ": "输入模型名称: ",
    "  Found {len} model(s) from {pconfig_name} API": "  从 {pconfig_name} API 找到 {len} 个模型",
    "  Showing {len} curated models": "  显示 {len} 个精选模型",
    "  Model ID: ": "  模型 ID: ",
    "  AWS Region [{current_region}]: ": "  AWS 区域 [{current_region}]: ",
    "  Choice [1]: ": "  选择 [1]: ",
    "Base URL [{effective_base}]: ": "基础 URL [{effective_base}]: ",
    "  Found {len} model(s) from Ollama Cloud": "  从 Ollama Cloud 找到 {len} 个模型",
    "  Found {len} model(s) from models.dev registry": "  从 models.dev 仓库找到 {len} 个模型",
    "Model name (e.g., claude-sonnet-4-20250514): ": "模型名称 (例如 claude-sonnet-4-20250514): ",
    "  + {len} new: {', '.join(result['copied'])}": "  + {len} 个新增: {', '.join(result['copied'])}",
    "  ~ {len} user-modified (kept)": "  ~ {len} 个用户修改 (已保留)",
    "  − {len} removed from manifest": "  − {len} 个已从清单移除",
    "  ℹ️  {len} new config option(s) available": "  ℹ️  {len} 个新配置项可用",
    "  → Stopped {len} manual gateway process(es)": "  → 已停止 {len} 个手动网关进程",
    "{copied} bundled skills synced.": "{copied} 个内置技能已同步。",
    "\\n[警告] {_get_wrapper_dir} is not in your PATH.": "\n[警告] {_get_wrapper_dir} 不在 PATH 中。",
    "[警告] {_get_wrapper_dir} is not in your PATH.": "[警告] {_get_wrapper_dir} 不在 PATH 中。",
    "Skills ({len}):": "技能 ({len}):",
    "{args_skill}: Level={r_level} Findings={len}": "{args_skill}: 等级={r_level} 发现={len}",
    "\\n  Type 'yes' to confirm: ": "\n  输入 'yes' 确认: ",
    "  Files were in: {display_hermes_home}/memories/\\n": "  文件位于: {display_hermes_home}/memories/\n",
    "Exported {len} sessions to {args_output}": "已导出 {len} 个会话到 {args_output}",

    # ── auth.py ──
    "Spotify Client ID: ": "Spotify 客户端 ID: ",
    "Use existing credentials? [Y/n]: ": "使用现有凭证？[Y/n]: ",
    "Import these credentials? (a separate login is recommended) [y/N]: ": "导入这些凭证？(建议单独登录) [y/N]: ",
    "  Auth state: {_dhh}/auth.json": "  认证状态: {_dhh}/auth.json",
    "{provider} ({len} credentials):": "{provider} ({len} 个凭证):",
    "{provider}: logged out ({reason})": "{provider}: 已退出登录 ({reason})",
    "{provider}: logged out": "{provider}: 已退出登录",
    "{provider}: logged in": "{provider}: 已登录",
    "\\nChoice: ": "\n选择: ",
    "Type [1/2]: ": "类型 [1/2]: ",
    "Label / account name (optional): ": "标签 / 账户名称 (可选): ",
    "Remove #, id, or label (blank to cancel): ": "删除 #、ID 或标签 (空白取消): ",
    "\\nStrategy [1-4]: ": "\n策略 [1-4]: ",
    "  Account number{f' [{default_account}]' if default_account else ''}: ": "  账户编号: ",

    # ── backup.py ──
    "  Original:    {_format_size}": "  原始大小:    {_format_size}",
    "  Compressed:  {_format_size}": "  压缩后:  {_format_size}",
    "\\n  Warnings ({len} files skipped):": "\n  警告 ({len} 个文件已跳过):",
    "  ... and {len} more": "  ... 还有 {len} 个",
    "      ... and {len} more": "      ... 还有 {len} 个",
    "Target: {display_hermes_home}": "目标: {display_hermes_home}",
    "Continue? [y/N] ": "继续？[y/N] ",
    "  Target: {display_hermes_home}": "  目标: {display_hermes_home}",

    # ── memory_setup.py ──
    "\\n  Note: {_get_wrapper_dir} is not in your PATH.": "\n  注意: {_get_wrapper_dir} 不在 PATH 中。",
    "  {len} snapshot(s) stored in {display_hermes_home}/state-snapshots/": "  {len} 个快照存储于 {display_hermes_home}/state-snapshots/",
    "  {len} state file(s) found:": "  找到 {len} 个状态文件:",
    "    • {var} — {var_1} (from skill: {skill_name})": "    • {var} — {var_1} (来自技能: {skill_name})",
    "📁 All your files are in {_dhh}/:": "📁 您的所有文件位于 {_dhh}/:",

    # ── cron.py ──
    "  {len} active job(s)": "  {len} 个活跃任务",
    "  Next run: {min}": "  下次运行: {min}",
    "{success_verb} job: {job} ({job_id})": "{success_verb} 任务: {job} ({job_id})",

    # ── hooks.py ──
    "  Choice [1-{len}]: ": "  选择 [1-{len}]: ",
    "Configured shell hooks ({len} total):\\n": "已配置 shell 钩子 ({len} 个):\n",
    "Firing {len} hook(s) for event '{event}':\\n": "触发 {len} 个钩子事件 '{event}':\n",
    "      stdout: {_truncate}": "      标准输出: {_truncate}",
    "      stderr: {_truncate}": "      标准错误: {_truncate}",
    "Checking {len} configured shell hook(s)...\\n": "检查 {len} 个已配置的 shell 钩子...\n",
    "{problems} issue(s) found.  Fix before relying on these hooks.": "{problems} 个问题。请在依赖这些钩子之前修复。",

    # ── logs.py ──
    "--- {display_hermes_home}/logs/{filename}{filter_desc} (Ctrl+C to stop) ---": "--- {display_hermes_home}/logs/{filename}{filter_desc} (Ctrl+C 停止) ---",
    "--- {display_hermes_home}/logs/{filename}{filter_desc} (last {num_lines}) ---": "--- {display_hermes_home}/logs/{filename}{filter_desc} (最后 {num_lines} 条) ---",
    "No logs directory at {display_hermes_home}/logs/": "日志目录不存在: {display_hermes_home}/logs/",
    "Log files in {display_hermes_home}/logs/:\\n": "日志文件位于 {display_hermes_home}/logs/:\n",

    # ── pairing.py ──
    "  {len} entries · {size:,} bytes": "  {len} 条记录 · {size:,} 字节",
    "\\n  Pending Pairing Requests ({len}):": "\n  待处理配对请求 ({len}):",
    "\\n  Approved Users ({len}):": "\n  已批准用户 ({len}):",
    "Type '{name}' to confirm: ": "输入 '{name}' 确认: ",

    # ── setup.py wizard ──
    "   {color}          Re-run the full wizard": "   {color}          重新运行完整向导",
    "   {color}    Change model/provider": "   {color}    更改模型/服务商",
    "   {color} Change terminal backend": "   {color} 更改终端后端",
    "   {color}  Configure messaging": "   {color}  配置消息",
    "   {color}    Configure tool providers": "   {color}    配置工具提供商",
    "   {color}         View current settings": "   {color}         查看当前设置",
    "   {color}              Start chatting": "   {color}              开始聊天",
    "   {color}      Start messaging gateway": "   {color}      启动消息网关",
    "   {color}       Check for issues": "   {color}       检查问题",
    "Confirm [y/N]: ": "确认 [y/N]: ",

    # ── status.py ──
    "  Model:        {_configured_model_label}": "  模型:        {_configured_model_label}",
    "  Provider:     {_effective_provider_label}": "  服务商:     {_effective_provider_label}",
    "  Sudo:         {check_mark} {'enabled' if sudo_password else 'disabled'}": "  Sudo:         {check_mark} {'已启用' if sudo_password else '已禁用'}",
    "  Status:       {check_mark} {'running' if is_running else 'stopped'}": "  状态:       {check_mark} {'运行中' if is_running else '已停止'}",
    "  PID(s):       {_format_gateway_pids}": "  PID:       {_format_gateway_pids}",
    "  Status:       {color}": "  状态:       {color}",
    "  Jobs:         {len} active, {len_1} total": "  任务:         {len} 活跃, {len_1} 总计",
    "  Active:       {len} session(s)": "  活跃:       {len} 个会话",
    "  OpenRouter:   {check_mark} {'reachable' if ok else f'error ({response_status_code})'}": "  OpenRouter:   {check_mark} {'可访问' if ok else f'错误 ({response_status_code})'}",
    "  OpenRouter:   {check_mark} error: {e}": "  OpenRouter:   {check_mark} 错误: {e}",
    "  Configuring {len} tool(s):": "  配置 {len} 个工具:",
    "  Tool configuration saved to {display_hermes_home}/config.yaml": "  工具配置已保存至 {display_hermes_home}/config.yaml",
    "  Connecting to {len} server(s): {', '.join(enabled_names)}": "  连接到 {len} 个服务器: {', '.join(enabled_names)}",
    "  Found {total_tools} tool(s) across {len} server(s)": "  在 {len} 个服务器中找到 {total_tools} 个工具",
    "\\n  {len} webhook subscription(s):\\n": "\n  {len} 个 webhook 订阅:\n",
    "[成功] Saved: {enabled_count} enabled, {len} disabled ({platform_label}).": "[成功] 已保存: {enabled_count} 个启用, {len} 个禁用 ({platform_label})。",

    # ── gateway / systemd ──
    "  PID(s): {_format_gateway_pids}": "  PID: {_format_gateway_pids}",
    "↻ Updated gateway {_service_scope_label} service definition to match the current BookwormPRO install": "↻ 已更新网关 {_service_scope_label} 服务定义以匹配当前 BookwormPRO 安装",
    "↻ Repairing outdated {_service_scope_label} systemd service at: {unit_path}": "↻ 正在修复过时的 {_service_scope_label} systemd 服务: {unit_path}",
    "[成功] {_service_scope_label} service definition updated": "[成功] {_service_scope_label} 服务定义已更新",
    "Installing {_service_scope_label} systemd service to: {unit_path}": "正在安装 {_service_scope_label} systemd 服务到: {unit_path}",
    "[成功] {_service_scope_label} service installed and enabled!": "[成功] {_service_scope_label} 服务已安装并启用！",
    "[成功] {_service_scope_label} service uninstalled": "[成功] {_service_scope_label} 服务已卸载",
    "[成功] {_service_scope_label} service started": "[成功] {_service_scope_label} 服务已启动",
    "[成功] {_service_scope_label} service stopped": "[成功] {_service_scope_label} 服务已停止",
    "[成功] {_service_scope_label} service restarted": "[成功] {_service_scope_label} 服务已重启",
    "[成功] {_service_scope_label} gateway service is running": "[成功] {_service_scope_label} 网关服务运行中",
    "[失败] {_service_scope_label} gateway service is stopped": "[失败] {_service_scope_label} 网关服务已停止",
    "[成功] Stopped {get_service_name} service": "[成功] 已停止 {get_service_name} 服务",
}


def fill_translations(po_text: str) -> tuple[str, int, int]:
    """Fill empty msgstr entries using translation table + heuristics."""
    lines = po_text.splitlines()
    result = []
    filled = 0
    skipped = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        # Look for msgid + empty msgstr pairs
        msgid_m = re.match(r'^msgid "(.+)"$', line)
        if msgid_m and i + 1 < len(lines):
            next_line = lines[i + 1]
            msgstr_m = re.match(r'^msgstr ""$', next_line)
            if msgstr_m:
                msgid = msgid_m.group(1)

                # Determine translation
                translation = get_translation(msgid)

                if translation is not None:
                    result.append(line)
                    result.append(f'msgstr "{translation}"')
                    filled += 1
                    i += 2
                    continue
                else:
                    skipped += 1

        result.append(line)
        i += 1

    return "\n".join(result), filled, skipped


def get_translation(msgid: str) -> str | None:
    """Return Chinese translation for a msgid, or None to leave empty."""
    # 1. Direct table lookup
    if msgid in TRANSLATIONS:
        return TRANSLATIONS[msgid]

    # 2. Strings starting with Chinese status bracket like [成功]/[警告]/[失败]/[等待]
    if re.match(r"^[\\n]*\[[一-鿿]+\]", msgid):
        return msgid

    # 3. Pure Chinese msgid (no long English word sequences) → use as-is
    if re.search(r"[一-鿿]", msgid) and not re.search(r"[A-Za-z]{5,}", msgid):
        return msgid

    # 4. Strip {placeholders} and analyze the remaining text
    stripped = re.sub(r"\{[^}]*\}", "", msgid).strip()
    stripped = re.sub(r"\\[ntr]", "", stripped).strip()  # strip PO escape sequences

    if not stripped or len(stripped) < 2:
        return msgid  # Mostly formatting/placeholders

    # 5. Chinese dominant in non-placeholder content (>40% CJK)
    cjk_count = len(re.findall(r"[一-鿿]", stripped))
    total_alpha = len(re.findall(r"[A-Za-z一-鿿]", stripped))
    if total_alpha > 0 and cjk_count / total_alpha > 0.4:
        return msgid  # Sufficiently Chinese

    # 6. Strings that are CLI commands or technical strings (keep as-is)
    if re.match(r"^[\s]*(bookworm|sudo|systemctl|journalctl|loginctl)", stripped):
        return msgid

    # 7. Leave English-heavy strings empty (runtime fallback to msgid is fine)
    return None


if __name__ == "__main__":
    po_text = PO_PATH.read_text(encoding="utf-8")
    new_text, filled, skipped = fill_translations(po_text)
    PO_PATH.write_text(new_text, encoding="utf-8")
    print(f"Filled: {filled} entries")
    print(f"Skipped (left empty): {skipped} entries")
    print(f"(Runtime fallback to msgid for skipped entries)")
