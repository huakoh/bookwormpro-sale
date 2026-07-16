"""Add missing PO entries for config.py, uninstall.py, doctor.py"""
import re

po_path = r"C:\Users\leesu\BookwormPRO\locale\zh_CN\LC_MESSAGES\bookwormpro.po"

# Read existing msgids
with open(po_path, 'r', encoding='utf-8') as f:
    po_content = f.read()

existing_ids = set()
for m in re.finditer(r'^msgid "(.*?)"$', po_content, re.MULTILINE):
    existing_ids.add(m.group(1))

# All translations: msgid -> msgstr
translations = {
    # ─── config.py: managed installation warnings ───
    "Cannot {action}: this BookwormPRO installation is managed by NixOS ":
        "无法 {action}：此 BookwormPRO 安装由 NixOS 管理 ",
    "Edit services.bookwormpro.settings in your configuration.nix and run:":
        "编辑 configuration.nix 中的 services.bookwormpro.settings 并运行：",
    "Cannot {action}: this BookwormPRO installation is managed by Homebrew ":
        "无法 {action}：此 BookwormPRO 安装由 Homebrew 管理 ",
    "Use:": "使用：",
    "Cannot {action}: this BookwormPRO installation is managed by {managed_system}.":
        "无法 {action}：此 BookwormPRO 安装由 {managed_system} 管理。",
    "Use your package manager to upgrade or reinstall BookwormPRO.":
        "请使用包管理器升级或重新安装 BookwormPRO。",

    # ─── config.py: migration success messages ───
    "  [成功] Repaired .env file ({fixes} corrupted entries fixed)":
        "  [成功] 已修复 .env 文件（修正了 {fixes} 个损坏条目）",
    "  [成功] Migrated tool progress to config.yaml: {tool_progress}":
        "  [成功] 已迁移工具进度到 config.yaml：{tool_progress}",
    "  [成功] Added timezone to config.yaml: {tz_display}":
        "  [成功] 已添加时区到 config.yaml：{tz_display}",
    "  [成功] Cleared ANTHROPIC_TOKEN from .env (no longer used)":
        "  [成功] 已从 .env 清除 ANTHROPIC_TOKEN（不再使用）",
    "  [成功] Migrated {migrated_count} custom provider(s) to providers: section":
        "  [成功] 已迁移 {migrated_count} 个自定义提供商到 providers: 段",
    "  [成功] Cleared {dead_var} from .env (no longer used — config.yaml is source of truth)":
        "  [成功] 已从 .env 清除 {dead_var}（不再使用 — config.yaml 为唯一配置源）",
    "  [成功] Migrated legacy stt.model to provider-specific config":
        "  [成功] 已迁移旧版 stt.model 到提供商专属配置",
    "  [成功] Added display.interim_assistant_messages=true":
        "  [成功] 已添加 display.interim_assistant_messages=true",
    "  [成功] Migrated tool_progress_overrides → display.platforms: {migrated}":
        "  [成功] 已迁移 tool_progress_overrides → display.platforms：{migrated}",
    "  [成功] Migrated compression.summary_* → auxiliary.compression: {keys}":
        "  [成功] 已迁移 compression.summary_* → auxiliary.compression：{keys}",
    "  [成功] Removed unused compression.summary_* keys":
        "  [成功] 已移除废弃的 compression.summary_* 键",
    "  [成功] Plugins now opt-in: grandfathered ":
        "  [成功] 插件已改为主动启用：已祖父化 ",
    "  [成功] Plugins now opt-in: no existing plugins to grandfather. ":
        "  [成功] 插件已改为主动启用：无需祖父化的现有插件。 ",
    "Config version: {current_ver} → {latest_ver}":
        "配置版本：{current_ver} → {latest_ver}",

    # ─── config.py: env var prompts ───
    "[警告]  Missing required environment variables:":
        "[警告]  缺少必需的环境变量：",
    "Let's configure them now:":
        "现在来配置它们：",
    "  Get your key at: {url}":
        "  获取密钥：{url}",
    "  {prompt}: ":
        "  {prompt}：",
    "  {prompt} (Enter to skip): ":
        "  {prompt}（回车跳过）：",
    "  [成功] Saved {name}":
        "  [成功] 已保存 {name}",
    "Skipped {name} - some features may not work":
        "已跳过 {name} - 部分功能可能不可用",
    "{count} new optional key(s) in this update:":
        "本次更新有 {count} 个新的可选密钥：",
    "  Configure new keys? [y/N]: ":
        "  配置新密钥？[y/N]：",
    "  [成功] Saved {key} = {value}":
        "  [成功] 已保存 {key} = {value}",
    "  Set later with: bookworm config set <key> <value>":
        "  稍后设置：bookworm config set <key> <value>",
    "  [成功] Added {key} = {default}":
        "  [成功] 已添加 {key} = {default}",
    "{count} skill setting(s) not configured:":
        "{count} 个技能设置未配置：",
    "  Configure skill settings? [y/N]: ":
        "  配置技能设置？[y/N]：",
    "Skipped {key} — skill '{skill}' may ask for it later":
        "已跳过 {key} — 技能 '{skill}' 稍后可能会询问",

    # ─── config.py: non-ASCII warning ───
    "Warning: {key} contains non-ASCII characters that will break API requests.":
        "警告：{key} 包含会导致 API 请求失败的非 ASCII 字符。",
    "This usually happens when copy-pasting from a PDF, rich-text editor,":
        "这通常发生在从 PDF、富文本编辑器",
    "or web page that substitutes lookalike Unicode glyphs for ASCII letters.":
        "或网页复制粘贴时，用了外观相似的 Unicode 字符替代 ASCII 字母。",
    "... and more": "... 及更多",
    "The non-ASCII characters have been stripped automatically.":
        "非 ASCII 字符已被自动清除。",
    "If authentication fails, re-copy the key from the provider's dashboard.":
        "如果认证失败，请从提供商后台重新复制密钥。",

    # ─── config.py: show config ───
    "◆ Paths": "◆ 路径",
    "  Config:       {path}": "  配置：       {path}",
    "  Secrets:      {path}": "  密钥：       {path}",
    "  Install:      {path}": "  安装：       {path}",
    "◆ API Keys": "◆ API 密钥",
    "◆ Model": "◆ 模型",
    "  Model:        {model}": "  模型：        {model}",
    "not set": "未设置",
    "  Max turns:    {max_turns}": "  最大轮数：    {max_turns}",
    "◆ Display": "◆ 显示",
    "  Personality:  {personality}": "  个性：        {personality}",
    "  Reasoning:    {state}": "  推理：        {state}",
    "on": "开",
    "off": "关",
    "  Bell:         {state}": "  响铃：        {state}",
    "  User preview: first {first} line(s), last {last} line(s)":
        "  用户预览：前 {first} 行，后 {last} 行",
    "◆ Terminal": "◆ 终端",
    "  Backend:      {backend}": "  后端：        {backend}",
    "  Working dir:  {cwd}": "  工作目录：    {cwd}",
    "  Timeout:      {timeout}s": "  超时：        {timeout}s",
    "  Docker image: {image}": "  Docker 镜像： {image}",
    "  Image:        {image}": "  镜像：        {image}",
    "  Modal image:  {image}": "  Modal 镜像：  {image}",
    "  Modal token:  {status}": "  Modal 令牌：  {status}",
    "configured": "已配置",
    "(not set)": "（未设置）",
    "  Daytona image: {image}": "  Daytona 镜像：{image}",
    "  API key:      {status}": "  API 密钥：    {status}",
    "  SSH host:     {host}": "  SSH 主机：    {host}",
    "  SSH user:     {user}": "  SSH 用户：    {user}",
    "◆ Timezone": "◆ 时区",
    "  Timezone:     {tz}": "  时区：        {tz}",
    "(server-local)": "（服务器本地）",
    "◆ Context Compression": "◆ 上下文压缩",
    "  Enabled:      {enabled}": "  启用：        {enabled}",
    "yes": "是",
    "no": "否",
    "  Threshold:    {threshold}%": "  阈值：        {threshold}%",
    "  Target ratio: {ratio}% of threshold preserved":
        "  目标比率：    保留阈值的 {ratio}%",
    "  Protect last: {count} messages":
        "  保护最后：    {count} 条消息",
    "  Provider:     {provider}": "  提供商：      {provider}",
    "◆ Auxiliary Models (overrides)": "◆ 辅助模型（覆盖）",
    "◆ Messaging Platforms": "◆ 消息平台",
    "  Telegram:     {status}": "  Telegram：    {status}",
    "not configured": "未配置",
    "  Discord:      {status}": "  Discord：     {status}",
    "◆ Skill Settings": "◆ 技能设置",
    "  bookworm config edit     # Edit config file":
        "  bookworm config edit     # 编辑配置文件",
    "  bookworm config set <key> <value>":
        "  bookworm config set <key> <value>",
    "  bookworm setup           # Run setup wizard":
        "  bookworm setup           # 运行设置向导",

    # ─── config.py: edit/set/check/migrate commands ───
    "Created {path}": "已创建 {path}",
    "No editor found. Config file is at:": "未找到编辑器。配置文件位于：",
    "Opening {path} in {editor}...": "正在用 {editor} 打开 {path}...",
    "[成功] Set {key} in {path}": "[成功] 已在 {path} 中设置 {key}",
    "[成功] Set {key} = {value} in {path}": "[成功] 已在 {path} 中设置 {key} = {value}",
    "Usage: bookworm config set <key> <value>": "用法：bookworm config set <key> <value>",
    "Examples:": "示例：",
    "[调用] Checking configuration for updates...":
        "[调用] 正在检查配置更新...",
    "[成功] Configuration is up to date!":
        "[成功] 配置已是最新！",
    "  Config version: {current_ver} → {latest_ver}":
        "  配置版本：{current_ver} → {latest_ver}",
    "{count} new config option(s) will be added with defaults":
        "将添加 {count} 个新配置选项（使用默认值）",
    "[警告]  {count} required API key(s) missing:":
        "[警告]  缺少 {count} 个必需的 API 密钥：",
    "{count} optional API key(s) not configured:":
        "{count} 个可选 API 密钥未配置：",
    " (enables: {tools})": " （启用：{tools}）",
    "[成功] Configuration updated!": "[成功] 配置已更新！",
    "[汇总] Configuration Status": "[汇总] 配置状态",
    "  Config version: {ver} [成功]": "  配置版本：{ver} [成功]",
    "  Config version: {current_ver} → {latest_ver} (update available)":
        "  配置版本：{current_ver} → {latest_ver}（有更新）",
    "  Required:": "  必需：",
    "    [失败] {var_name} (missing)": "    [失败] {var_name}（缺失）",
    "  Optional:": "  可选：",
    "  {count} new config option(s) available":
        "  {count} 个新配置选项可用",
    "    Run 'bookworm config migrate' to add them":
        "    运行 'bookworm config migrate' 添加",
    "Unknown config command: {subcmd}": "未知配置命令：{subcmd}",
    "Available commands:": "可用命令：",
    "  bookworm config           Show current configuration":
        "  bookworm config           显示当前配置",
    "  bookworm config edit      Open config in editor":
        "  bookworm config edit      在编辑器中打开配置",
    "  bookworm config set <key> <value>   Set a config value":
        "  bookworm config set <key> <value>   设置配置值",
    "  bookworm config check     Check for missing/outdated config":
        "  bookworm config check     检查缺失/过时的配置",
    "  bookworm config migrate   Update config with new options":
        "  bookworm config migrate   用新选项更新配置",
    "  bookworm config path      Show config file path":
        "  bookworm config path      显示配置文件路径",
    "  bookworm config env-path  Show .env file path":
        "  bookworm config env-path  显示 .env 文件路径",
    "Warning: Failed to load config: {error}":
        "警告：加载配置失败：{error}",
    "  Model:        {model}": "  模型：        {model}",

    # ─── uninstall.py: log messages ───
    "Could not update {config_path}: {e}":
        "无法更新 {config_path}：{e}",
    "Could not remove {wrapper}: {e}":
        "无法移除 {wrapper}：{e}",
    "Killed {killed} running gateway process(es)":
        "已终止 {killed} 个运行中的网关进程",
    "Could not check for gateway processes: {e}":
        "无法检查网关进程：{e}",
    "System gateway service exists at {unit_path} ":
        "系统网关服务存在于 {unit_path} ",
    "Removed {scope} gateway service ({unit_path})":
        "已移除 {scope} 网关服务（{unit_path}）",
    "Could not remove {scope} gateway service: {e}":
        "无法移除 {scope} 网关服务：{e}",
    "Could not check systemd gateway services: {e}":
        "无法检查 systemd 网关服务：{e}",
    "Removed macOS gateway service ({plist_path})":
        "已移除 macOS 网关服务（{plist_path}）",
    "Could not remove launchd gateway service: {e}":
        "无法移除 launchd 网关服务：{e}",
    "Could not enumerate profiles: {e}":
        "无法枚举配置文件：{e}",
    "Uninstalling profile '{name}'...":
        "正在卸载配置 '{name}'...",
    "  Gateway {subcmd} timed out for '{name}'":
        "  网关 {subcmd} 对 '{name}' 超时",
    "  Could not run gateway {subcmd} for '{name}': {e}":
        "  无法为 '{name}' 运行网关 {subcmd}：{e}",
    "  Removed alias {alias_path}":
        "  已移除别名 {alias_path}",
    "  Could not remove alias {alias_path}: {e}":
        "  无法移除别名 {alias_path}：{e}",
    "  Removed {profile_home}":
        "  已移除 {profile_home}",
    "  Could not remove {profile_home}: {e}":
        "  无法移除 {profile_home}：{e}",

    # ─── uninstall.py: UI messages ───
    "Current Installation:": "当前安装：",
    "  Code:    {project_root}": "  代码：    {project_root}",
    "  Config:  {config_path}": "  配置：    {config_path}",
    "  Secrets: {secrets_path}": "  密钥：    {secrets_path}",
    "  Data:    {cron}, {sessions}, {logs}":
        "  数据：    {cron}、{sessions}、{logs}",
    "Other profiles detected:": "检测到其他配置：",
    " (gateway running)": "（网关运行中）",
    "  • {name}{running}: {path}":
        "  • {name}{running}：{path}",
    "Uninstall Options:": "卸载选项：",
    "Keep data": "保留数据",
    " - Remove code only, keep configs/sessions/logs":
        " - 仅移除代码，保留配置/会话/日志",
    "(Recommended - you can reinstall later with your settings intact)":
        "（推荐 - 稍后可使用现有设置重新安装）",
    "Full uninstall": "完全卸载",
    " - Remove everything including all data":
        " - 移除所有内容包括全部数据",
    "(Warning: This deletes all configs, sessions, and logs permanently)":
        "（警告：这将永久删除所有配置、会话和日志）",
    "Cancel": "取消",
    " - Don't uninstall": " - 不卸载",
    "Select option [1/2/3]: ": "选择选项 [1/2/3]：",
    "Cancelled.": "已取消。",
    "Uninstall cancelled.": "卸载已取消。",
    "Other profiles will NOT be removed by default.":
        "默认情况下不会移除其他配置。",
    "Found {count} named profile(s): ":
        "发现 {count} 个命名配置：",
    "Also stop and remove these {count} profile(s)? [y/N]: ":
        "同时停止并移除这 {count} 个配置？[y/N]：",
    "[WARNING]  WARNING: This will permanently delete ALL BookwormPRO data!":
        "[警告]  警告：这将永久删除所有 BookwormPRO 数据！",
    "   Including: configs, API keys, sessions, scheduled jobs, logs":
        "   包括：配置、API 密钥、会话、定时任务、日志",
    "   Plus {count} profile(s): ":
        "   以及 {count} 个配置：",
    "This will remove the BookwormPRO code but keep your configuration and data.":
        "这将移除 BookwormPRO 代码但保留配置和数据。",
    "Type '{yes_word}' to confirm: ":
        "输入 '{yes_word}' 确认：",
    "Uninstalling...": "正在卸载...",
    "Checking for running gateway...": "正在检查运行中的网关...",
    "No gateway service or processes found":
        "未发现网关服务或进程",
    "Removing PATH entries from shell configs...":
        "正在从 shell 配置中移除 PATH 条目...",
    "Updated {config}": "已更新 {config}",
    "No PATH entries found to remove":
        "未发现需要移除的 PATH 条目",
    "Removing bookworm command...": "正在移除 bookworm 命令...",
    "Removed {wrapper}": "已移除 {wrapper}",
    "No wrapper script found": "未发现包装脚本",
    "Removing installation directory...": "正在移除安装目录...",
    "Removed {project_root}": "已移除 {project_root}",
    "Could not fully remove {project_root}: {e}":
        "无法完全移除 {project_root}：{e}",
    "You may need to manually remove it":
        "可能需要手动移除",
    "Removing configuration and data...":
        "正在移除配置和数据...",
    "Removed {hermes_home}": "已移除 {hermes_home}",
    "Could not fully remove {hermes_home}: {e}":
        "无法完全移除 {hermes_home}：{e}",
    "Keeping configuration and data in {hermes_home}":
        "保留配置和数据在 {hermes_home}",
    "Your configuration and data have been preserved:":
        "您的配置和数据已保留：",
    "  {hermes_home}/": "  {hermes_home}/",
    "To reinstall later with your existing settings:":
        "稍后使用现有设置重新安装：",
    "Reload your shell to complete the process:":
        "重新加载 shell 以完成操作：",
    "  source ~/.bashrc  # or ~/.zshrc":
        "  source ~/.bashrc  # 或 ~/.zshrc",
    "Thank you for using BookwormPRO! [BWM]":
        "感谢使用 BookwormPRO！[BWM]",

    # ─── doctor.py: section headers ───
    "◆ Gateway Service": "◆ 网关服务",
    "◆ Runtime Filesystem Capability": "◆ 运行时文件系统能力",
    "◆ Persistent Memory": "◆ 持久记忆",
    "◆ Prompt Cache Freshness": "◆ 提示缓存新鲜度",
    "│                 [体检] BookwormPRO Doctor                        │":
        "│                 [体检] BookwormPRO 健康检查                      │",
    "◆ Python Environment": "◆ Python 环境",
    "◆ Required Packages": "◆ 必需依赖包",
    "◆ Configuration Files": "◆ 配置文件",
    "◆ Config Structure": "◆ 配置结构",
    "◆ Auth Providers": "◆ 认证提供商",
    "◆ Directory Structure": "◆ 目录结构",
    "◆ Command Installation": "◆ 命令安装",
    "◆ External Tools": "◆ 外部工具",
    "◆ API Connectivity": "◆ API 连通性",
    "◆ Submodules": "◆ 子模块",
    "◆ Tool Availability": "◆ 工具可用性",
    "◆ Skills Hub": "◆ 技能中心",
    "◆ Memory Provider": "◆ 记忆提供商",
    "◆ Profiles": "◆ 配置文件",

    # ─── doctor.py: gateway service ───
    "Enable linger for the gateway user service: sudo loginctl enable-linger $USER":
        "为网关用户服务启用 linger：sudo loginctl enable-linger $USER",

    # ─── doctor.py: persistent memory ───
    "Mount host paths via docker-compose host bridge ":
        "通过 docker-compose 主机桥接挂载主机路径 ",
    "Memory files missing under {mem_dir}. They auto-seed from ":
        "{mem_dir} 下缺少记忆文件。它们会自动从 ",
    "External provider: {provider} (additive on top of builtin)":
        "外部提供商：{provider}（在内置之上叠加）",

    # ─── doctor.py: prompt cache ───
    "Snapshot is stale by {diff_s:.1f}s":
        "快照已过期 {diff_s:.1f}s",
    "Snapshot path: {snap_path}":
        "快照路径：{snap_path}",

    # ─── doctor.py: python environment ───
    "Python {major}.{minor}.{micro}":
        "Python {major}.{minor}.{micro}",
    "Upgrade Python to 3.10+":
        "请升级 Python 到 3.10+",

    # ─── doctor.py: required packages ───
    "Install {name}: {cmd} {module}":
        "安装 {name}：{cmd} {module}",

    # ─── doctor.py: configuration files ───
    "{dhh}/.env file exists": "{dhh}/.env 文件存在",
    "No API key found in {dhh}/.env":
        "{dhh}/.env 中未找到 API 密钥",
    "Run 'bookworm setup' to configure API keys":
        "运行 'bookworm setup' 配置 API 密钥",
    "{dhh}/.env file missing": "{dhh}/.env 文件缺失",
    "Created empty {dhh}/.env": "已创建空的 {dhh}/.env",
    "Run 'bookworm setup' to create .env":
        "运行 'bookworm setup' 创建 .env",
    "{dhh}/config.yaml exists": "{dhh}/config.yaml 存在",
    "model.provider '{provider_raw}' is not a recognised provider":
        "model.provider '{provider_raw}' 不是已知的提供商",
    "(known: {known_list})": "（已知：{known_list}）",
    "model.provider '{provider_raw}' is unknown. ":
        "model.provider '{provider_raw}' 未知。 ",
    "model.default '{default_model}' uses a vendor/model slug but provider is '{provider_raw}'":
        "model.default '{default_model}' 使用了厂商/模型格式但 provider 是 '{provider_raw}'",
    "model.default '{default_model}' is vendor-prefixed but model.provider is '{provider_raw}'. ":
        "model.default '{default_model}' 带厂商前缀但 model.provider 是 '{provider_raw}'。 ",
    "model.provider '{canonical_provider}' is set but no API key is configured":
        "model.provider '{canonical_provider}' 已设置但未配置 API 密钥",
    "No credentials found for provider '{canonical_provider}'. ":
        "未找到提供商 '{canonical_provider}' 的凭证。 ",
    "Created {dhh}/config.yaml from cli-config.yaml.example":
        "已从 cli-config.yaml.example 创建 {dhh}/config.yaml",
    "Create {dhh}/config.yaml manually":
        "手动创建 {dhh}/config.yaml",
    "Config version outdated (v{current_ver} → v{latest_ver})":
        "配置版本过时（v{current_ver} → v{latest_ver}）",
    "Auto-migration failed: {mig_err}":
        "自动迁移失败：{mig_err}",
    "Run 'bookworm setup' to migrate config":
        "运行 'bookworm setup' 迁移配置",
    "Run 'bookworm doctor --fix' or 'bookworm setup' to migrate config":
        "运行 'bookworm doctor --fix' 或 'bookworm setup' 迁移配置",
    "Config version up to date (v{current_ver})":
        "配置版本已是最新（v{current_ver}）",
    "Stale root-level config keys: {keys}":
        "过时的根级配置键：{keys}",
    "Stale root-level provider/base_url in config.yaml — run 'bookworm doctor --fix'":
        "config.yaml 中有过时的根级 provider/base_url — 运行 'bookworm doctor --fix'",

    # ─── doctor.py: directory structure ───
    "{dhh} directory exists": "{dhh} 目录存在",
    "Created {dhh} directory": "已创建 {dhh} 目录",
    "{dhh} not found": "{dhh} 未找到",
    "{dhh}/{subdir_name}/ exists": "{dhh}/{subdir_name}/ 存在",
    "Created {dhh}/{subdir_name}/": "已创建 {dhh}/{subdir_name}/",
    "{dhh}/{subdir_name}/ not found": "{dhh}/{subdir_name}/ 未找到",
    "{dhh}/SOUL.md exists (persona configured)":
        "{dhh}/SOUL.md 存在（角色已配置）",
    "{dhh}/SOUL.md exists but is empty — edit it to customize personality":
        "{dhh}/SOUL.md 存在但为空 — 编辑它来自定义个性",
    "{dhh}/SOUL.md not found":
        "{dhh}/SOUL.md 未找到",
    "Created {dhh}/SOUL.md with basic template":
        "已创建 {dhh}/SOUL.md（基础模板）",
    "{dhh}/memories/ directory exists":
        "{dhh}/memories/ 目录存在",
    "MEMORY.md exists ({size} chars)":
        "MEMORY.md 存在（{size} 字符）",
    "USER.md exists ({size} chars)":
        "USER.md 存在（{size} 字符）",
    "{dhh}/memories/ not found":
        "{dhh}/memories/ 未找到",
    "Created {dhh}/memories/":
        "已创建 {dhh}/memories/",
    "{dhh}/state.db exists ({count} sessions)":
        "{dhh}/state.db 存在（{count} 个会话）",
    "{dhh}/state.db exists but has issues: {e}":
        "{dhh}/state.db 存在但有问题：{e}",
    "{dhh}/state.db not created yet (will be created on first session)":
        "{dhh}/state.db 尚未创建（将在首次会话时创建）",
    "WAL file is large ({size} MB)":
        "WAL 文件过大（{size} MB）",
    "WAL checkpoint performed ({old}K → {new}K)":
        "WAL 检查点已完成（{old}K → {new}K）",
    "Large WAL file — run 'bookworm doctor --fix' to checkpoint":
        "WAL 文件过大 — 运行 'bookworm doctor --fix' 执行检查点",
    "WAL file is {size} MB (normal for active sessions)":
        "WAL 文件 {size} MB（活跃会话属正常）",

    # ─── doctor.py: command installation ───
    "Reinstall entry point: cd {project_root} && source venv/bin/activate && pip install -e '.[all]'":
        "重新安装入口点：cd {project_root} && source venv/bin/activate && pip install -e '.[all]'",
    "Venv entry point exists ({venv_bin})":
        "Venv 入口点存在（{venv_bin}）",
    "{cmd_link_display}/bookworm → correct target":
        "{cmd_link_display}/bookworm → 目标正确",
    "{cmd_link_display}/bookworm points to wrong target":
        "{cmd_link_display}/bookworm 指向错误目标",
    "(→ {target}, expected → {expected})":
        "（→ {target}，应为 → {expected}）",
    "Fixed symlink: {cmd_link_display}/bookworm → {venv_bin}":
        "已修复符号链接：{cmd_link_display}/bookworm → {venv_bin}",
    "Broken symlink at {cmd_link_display}/bookworm — run 'bookworm doctor --fix'":
        "{cmd_link_display}/bookworm 符号链接损坏 — 运行 'bookworm doctor --fix'",
    "{cmd_link_display}/bookworm exists (non-symlink)":
        "{cmd_link_display}/bookworm 存在（非符号链接）",
    "{cmd_link_display}/bookworm not found":
        "{cmd_link_display}/bookworm 未找到",
    "Created symlink: {cmd_link_display}/bookworm → {venv_bin}":
        "已创建符号链接：{cmd_link_display}/bookworm → {venv_bin}",
    "{cmd_link_display} is not on your PATH":
        "{cmd_link_display} 不在 PATH 中",
    "Add {cmd_link_display} to your PATH":
        "将 {cmd_link_display} 添加到 PATH",
    "Missing {cmd_link_display}/bookworm symlink — run 'bookworm doctor --fix'":
        "缺少 {cmd_link_display}/bookworm 符号链接 — 运行 'bookworm doctor --fix'",

    # ─── doctor.py: external tools ───
    "Install for faster search: {cmd}":
        "安装以加速搜索：{cmd}",
    "Start Docker daemon": "启动 Docker 守护进程",
    "Install Docker or change TERMINAL_ENV":
        "安装 Docker 或更改 TERMINAL_ENV",
    "SSH connection to {ssh_host}":
        "SSH 连接到 {ssh_host}",
    "Check SSH configuration for {ssh_host}":
        "检查 {ssh_host} 的 SSH 配置",
    "Set TERMINAL_SSH_HOST in .env":
        "在 .env 中设置 TERMINAL_SSH_HOST",
    "Set DAYTONA_API_KEY environment variable":
        "设置 DAYTONA_API_KEY 环境变量",
    "Install daytona SDK: pip install daytona":
        "安装 Daytona SDK：pip install daytona",
    "{label} deps": "{label} 依赖",
    "({critical} critical, {high} high, {moderate} moderate — run: cd {npm_dir} && npm audit fix)":
        "（{critical} 严重、{high} 高危、{moderate} 中等 — 运行：cd {npm_dir} && npm audit fix）",
    "{label} has {total} npm vulnerability(ies)":
        "{label} 有 {total} 个 npm 漏洞",
    "({moderate} moderate vulnerability(ies))":
        "（{moderate} 个中等漏洞）",

    # ─── doctor.py: API connectivity ───
    "Checking OpenRouter API...": "正在检查 OpenRouter API...",
    "OpenRouter API": "OpenRouter API",
    "(invalid API key)": "（API 密钥无效）",
    "(out of credits — payment required)": "（额度不足 — 需要付款）",
    "OpenRouter account has insufficient credits. ":
        "OpenRouter 账户额度不足。 ",
    "(rate limited)": "（被限流）",
    "(HTTP {status_code})": "（HTTP {status_code}）",
    "Check network connectivity": "检查网络连接",
    "Check OPENROUTER_API_KEY in .env":
        "检查 .env 中的 OPENROUTER_API_KEY",
    "OpenRouter rate limit hit — consider switching to a different provider or waiting":
        "OpenRouter 触发限流 — 考虑切换提供商或等待",
    "Checking Anthropic API...": "正在检查 Anthropic API...",
    "Anthropic API": "Anthropic API",
    "(couldn't verify)": "（无法验证）",
    "Checking {pname} API...": "正在检查 {pname} API...",
    "Check {env_var} in .env": "检查 .env 中的 {env_var}",
    "Checking AWS Bedrock...": "正在检查 AWS Bedrock...",
    "Install boto3 for Bedrock: {exe} -m pip install boto3":
        "安装 Bedrock 所需的 boto3：{exe} -m pip install boto3",
    "AWS Bedrock: {err_name} — check IAM permissions for bedrock:ListFoundationModels":
        "AWS Bedrock：{err_name} — 检查 bedrock:ListFoundationModels 的 IAM 权限",

    # ─── doctor.py: submodules ───
    "(run: {install_cmd})": "（运行：{install_cmd}）",
    "Install tinker-atropos: {install_cmd}":
        "安装 tinker-atropos：{install_cmd}",
    "(current: {major}.{minor})": "（当前：{major}.{minor}）",

    # ─── doctor.py: tool availability ───
    "(missing {vars_str})": "（缺少 {vars_str}）",
    "Run 'bookworm setup' to configure missing API keys for full tool access":
        "运行 'bookworm setup' 配置缺失的 API 密钥以获取完整工具访问",

    # ─── doctor.py: skills hub ───
    "Lock file OK ({count} hub-installed skill(s))":
        "锁定文件正常（{count} 个中心安装的技能）",
    "{q_count} skill(s) in quarantine":
        "{q_count} 个技能在隔离区",
    "(60 req/hr rate limit — set in {dhh}/.env for better rates)":
        "（60 次/小时限流 — 在 {dhh}/.env 中设置以获取更高限额）",

    # ─── doctor.py: memory provider ───
    "Honcho disabled (set enabled: true in {honcho_cfg_path} to activate)":
        "Honcho 已禁用（在 {honcho_cfg_path} 中设置 enabled: true 以激活）",
    "No Honcho API key — run 'bookworm memory setup'":
        "无 Honcho API 密钥 — 运行 'bookworm memory setup'",
    "Honcho unreachable: {e}": "Honcho 不可达：{e}",
    "Honcho is set as memory provider but honcho-ai is not installed":
        "Honcho 被设为记忆提供商但 honcho-ai 未安装",
    "Mem0 is set as memory provider but API key is missing":
        "Mem0 被设为记忆提供商但 API 密钥缺失",
    "Mem0 is set as memory provider but mem0ai is not installed":
        "Mem0 被设为记忆提供商但 mem0ai 未安装",
    "{provider} provider active": "{provider} 提供商已激活",
    "{provider} configured but not available":
        "{provider} 已配置但不可用",
    "{provider} plugin not found":
        "{provider} 插件未找到",
    "{provider} check failed": "{provider} 检查失败",

    # ─── doctor.py: profiles ───
    "{count} profile(s) found": "发现 {count} 个配置",
    "gateway running": "网关运行中",
    "[警告] missing config": "[警告] 缺少配置",
    "no .env": "无 .env",
    "no alias": "无别名",
    "Orphan alias: {wrapper_name} → profile '{profile}' no longer exists":
        "孤立别名：{wrapper_name} → 配置 '{profile}' 已不存在",

    # ─── doctor.py: summary ───
    "  Fixed {fixed_count} issue(s).":
        "  已修复 {fixed_count} 个问题。",
    " {count} issue(s) require manual intervention.":
        " {count} 个问题需要手动处理。",
    "  Found {count} issue(s) to address:":
        "  发现 {count} 个待解决问题：",
    "  Tip: run 'bookworm doctor --fix' to auto-fix what's possible.":
        "  提示：运行 'bookworm doctor --fix' 自动修复可修复的问题。",
    "  All checks passed! [完成]":
        "  所有检查通过！[完成]",

    # ─── doctor.py: auth providers ───
    "(logged in{suffix})": "（已登录{suffix}）",
    "(could not check: {e})": "（无法检查：{e}）",

    # ─── doctor.py: npm audit ───
    "(no known vulnerabilities)": "（无已知漏洞）",
}

# Filter to only those actually missing
added = 0
skipped = 0
new_entries = []

for msgid, msgstr in sorted(translations.items()):
    if msgid not in existing_ids:
        new_entries.append((msgid, msgstr))
        added += 1
    else:
        skipped += 1

print(f"Translations defined: {len(translations)}")
print(f"Already in PO (skipped): {skipped}")
print(f"New entries to add: {added}")

# Write new entries
if new_entries:
    sections = {
        'config.py': [],
        'uninstall.py': [],
        'doctor.py': [],
    }

    # We'll just write all as one section since we have proper translations
    with open(po_path, 'a', encoding='utf-8', newline='') as f:
        f.write("\n# ─── config.py + uninstall.py + doctor.py (会话4 批量补全) ───\n\n")
        for msgid, msgstr in new_entries:
            # Escape any quotes in msgid/msgstr
            safe_id = msgid.replace('"', '\\"')
            safe_str = msgstr.replace('"', '\\"')
            f.write(f'msgid "{safe_id}"\n')
            f.write(f'msgstr "{safe_str}"\n\n')

    print(f"\nSuccessfully added {added} entries to PO file")

# Final count
with open(po_path, 'r', encoding='utf-8') as f:
    final_content = f.read()
final_count = len(re.findall(r'^msgid "(.*?)"$', final_content, re.MULTILINE))
print(f"Final msgid count: {final_count}")
