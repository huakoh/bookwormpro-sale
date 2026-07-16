"""
Bulk translate [待翻译] and [EN] placeholders in .po file.
Uses expanded glossary + pattern-based translation.
"""
import re
from pathlib import Path

PO_PATH = Path(r"C:\Users\leesu\BookwormPRO\locale\zh_CN\LC_MESSAGES\bookwormpro.po")

# Expanded glossary
GLOSSARY = {
    # CLI concepts
    "Auth provider status": "认证提供者状态",
    "Config migrated to latest version": "配置已迁移到最新版本",
    "Migrated stale root-level keys into model section": "已将过期的根级别键迁移到 model 节",
    "Could not check tool availability": "无法检查工具可用性",
    "Could not import prompt-builder helpers": "无法导入提示构建器辅助模块",
    "Could not import runtime detectors": "无法导入运行时检测器",
    "Built-in memory active": "内置记忆已激活",
    "No external memory provider configured": "未配置外部记忆提供者",
    "External provider": "外部提供者",
    "additive on top of builtin": "在内置基础上叠加",
    "Snapshot path": "快照路径",
    "Snapshot is stale by": "快照已过期",
    "will auto-rebuild on next start": "将在下次启动时自动重建",
    "Snapshot is current with prompt-shaping code": "快照与提示构建代码同步",
    "Prompt shaping code has changed": "提示构建代码已变更",
    "Snapshot needs rebuild": "快照需要重建",
    "Virtual environment active": "虚拟环境已激活",
    "Virtual environment not active": "虚拟环境未激活",
    "Python version": "Python 版本",
    "recommended": "推荐",
    "required": "必需",
    
    # Files/Paths
    ".env file exists": ".env 文件存在",
    "in project directory": "（项目目录中）",
    "cli-config.yaml exists": "cli-config.yaml 存在",
    "in project directory": "（项目目录中）",
    "file exists": "文件存在",
    "file missing": "文件缺失",
    "directory exists": "目录存在",
    "directory not found": "目录未找到",
    "Created empty": "已创建空的",
    "Created": "已创建",
    "not found": "未找到",
    "will be created on first use": "将在首次使用时创建",
    "Config version up to date": "配置版本已是最新",
    "Auto-migration failed": "自动迁移失败",
    "API key or custom endpoint configured": "API 密钥或自定义端点已配置",
    "No API key found in": "未在以下位置找到 API 密钥",
    
    # Auth
    "BookwormPRO Portal auth": "BookwormPRO 门户认证",
    "Google OAuth configured": "Google OAuth 已配置",
    "OpenAI Codex OAuth configured": "OpenAI Codex OAuth 已配置",
    "Claude Pro/Max subscription": "Claude Pro/Max 订阅",
    "Login successful": "登录成功",
    "Signing in to": "正在登录",
    "Waiting for sign-in": "等待登录",
    "press Ctrl+C to cancel": "按 Ctrl+C 取消",
    "To continue": "要继续",
    "Steps": "步骤",
    "Spotify first-time setup": "Spotify 首次设置",
    "Starting Spotify PKCE login": "正在启动 Spotify PKCE 登录",
    "Spotify login successful": "Spotify 登录成功",
    
    # Doctor/Services
    "Gateway service linger": "网关服务驻留",
    "Systemd linger enabled": "Systemd 驻留已启用",
    "Systemd linger disabled": "Systemd 驻留已禁用",
    "gateway service survives logout": "网关服务在注销后仍存活",
    "gateway may stop after logout": "网关可能在注销后停止",
    "Could not verify systemd linger": "无法验证 systemd 驻留",
    "Could not import runtime detectors": "无法导入运行时检测器",
    "Native install": "原生安装",
    "full host filesystem access": "完整主机文件系统访问",
    "no sandbox": "无沙箱",
    "tools run as your user": "工具以您的用户身份运行",
    "Host bridge mounted": "主机桥接已挂载",
    "read-write": "读写",
    "Container runtime without host bridge": "无主机桥接的容器运行时",
    "only /opt/data is writable": "仅 /opt/data 可写",
    "To allow Desktop access": "要允许桌面访问",
    "WSL detected": "检测到 WSL",
    "Windows host visible at /mnt/c/": "Windows 主机位于 /mnt/c/",
    "Could not resolve BOOKWORMPRO_HOME": "无法解析 BOOKWORMPRO_HOME",
    "Checking OpenRouter API": "正在检查 OpenRouter API",
    "Checking Anthropic API": "正在检查 Anthropic API",
    "invalid API key": "API 密钥无效",
    "out of credits": "额度不足",
    "payment required": "需要付费",
    "rate limited": "被限流",
    "key configured": "密钥已配置",
    "Run: sudo loginctl enable-linger $USER": "运行：sudo loginctl enable-linger $USER",
    "Install for faster search": "安装以获得更快的搜索",
    
    # Status
    "Running": "运行中",
    "Stopped": "已停止",
    "Starting": "启动中",
    "Restarting": "重启中",
    "Health check": "健康检查",
    "Status": "状态",
    "Active": "活跃",
    "Inactive": "非活跃",
    "Enabled": "已启用",
    "Disabled": "已禁用",
    "Available": "可用",
    "Unavailable": "不可用",
    "Verified": "已验证",
    "Detected": "已检测到",
    "Configured": "已配置",
    "Installed": "已安装",
    "Loaded": "已加载",
    "Connected": "已连接",
    "Disconnected": "已断开",
    
    # Memory
    "missing": "缺失",
    "empty": "空",
    "no recall yet": "尚无回忆",
    "will be auto-seeded on next start": "下次启动时将自动初始化",
    "pruning recommended": "建议清理",
    "entries": "条",
    "chars": "字符",
    
    # Tools
    "SSH connection to": "SSH 连接到",
    "Lock file OK": "锁定文件正常",
    "hub-installed skill": "hub 安装的技能",
    "skill(s) in quarantine": "个技能在隔离区",
    "pending review": "待审核",
    "Honcho disabled": "Honcho 已禁用",
    "to activate": "以激活",
    "provider active": "提供者活跃",
    "configured but not available": "已配置但不可用",
    "plugin not found": "插件未找到",
    "check failed": "检查失败",
    "profile(s) found": "个配置文件已找到",
    "Orphan alias": "孤立别名",
    "no longer exists": "不再存在",
    
    # Generic
    "No change.": "无变化。",
    "Done.": "完成。",
    "OK.": "确定。",
    "Cancel.": "取消。",
    "Retry.": "重试。",
    "Skip.": "跳过。",
    "Yes": "是",
    "No": "否",
    "none": "无",
    "unknown": "未知",
    "default": "默认",
    "custom": "自定义",
    "automatic": "自动",
    "manual": "手动",
    "internal": "内部",
    "external": "外部",
    "local": "本地",
    "remote": "远程",
    "online": "在线",
    "offline": "离线",
    
    # Time
    "datetime": "日期时间",
    "time": "时间",
    "timestamp": "时间戳",
    "duration": "持续时间",
    "seconds": "秒",
    "minutes": "分钟",
    "hours": "小时",
    "days": "天",
    
    # Format variables to preserve
    "tinker_atropos": "tinker_atropos",
    "{name}": "{name}",
    "{count}": "{count}",
    "{version}": "{version}",
    "{port}": "{port}",
    "{host}": "{host}",
    "{path}": "{path}",
    "{size}": "{size}",
    "{status}": "{status}",
    "{model}": "{model}",
    "{provider}": "{provider}",
    "{error}": "{error}",
    "{e}": "{e}",
    "{exc}": "{exc}",
    "{n}": "{n}",
    "{i}": "{i}",
    "{msg}": "{msg}",
    "{reason}": "{reason}",
    "{detail}": "{detail}",
}

def translate_msgid(msgid):
    """Translate an English msgid to Chinese using glossary + heuristics."""
    # Already Chinese
    if any('\u4e00' <= c <= '\u9fff' for c in msgid) and not any(c.isascii() and c.isalpha() for c in msgid):
        return msgid
    
    # Exact match
    if msgid in GLOSSARY:
        return GLOSSARY[msgid]
    
    # Try component-based translation
    result = msgid
    
    # Replace known words/phrases (longest first to avoid partial matches)
    sorted_glossary = sorted(GLOSSARY.items(), key=lambda x: -len(x[0]))
    for en, zh in sorted_glossary:
        if en in result and len(en) > 2:
            result = result.replace(en, zh)
    
    # If nothing changed, mark for review
    if result == msgid:
        return f"[待审] {msgid}"
    
    return result

# Process .po file
with open(PO_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Find all msgid/msgstr pairs with placeholders
pattern = re.compile(
    r'(msgid "([^"]*)")\n(msgstr "\[待翻译\] [^"]*"|msgstr "\[EN\] [^"]*")',
    re.MULTILINE
)

replacements = 0
def replace_match(m):
    global replacements
    msgid = m.group(2)
    old_msgstr = m.group(3)
    new_translation = translate_msgid(msgid)
    replacements += 1
    return f'{m.group(1)}\nmsgstr "{new_translation}"'

content = pattern.sub(replace_match, content)

print(f"Translated {replacements} placeholders")

with open(PO_PATH, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

# Count remaining
remaining_placeholder = content.count('[待翻译]')
remaining_en = content.count('[EN]')
remaining_review = content.count('[待审]')
print(f"Remaining: [待翻译]={remaining_placeholder}, [EN]={remaining_en}, [待审]={remaining_review}")

# Compile
import subprocess, sys
result = subprocess.run(
    [sys.executable, str(Path(r"C:\Users\leesu\BookwormPRO\scripts\compile_i18n.py"))],
    capture_output=True, text=True,
    cwd=str(Path(r"C:\Users\leesu\BookwormPRO"))
)
print(result.stdout.strip())

# Verify
sys.path.insert(0, str(Path(r"C:\Users\leesu\BookwormPRO")))
from bwm_cli.i18n import setup_i18n, _
setup_i18n('zh_CN', force=True)

tests = [
    ('no tools', '无工具'),
    ('Welcome to BookwormPRO', '欢迎使用 BookwormPRO'),
    ('Login successful!', '登录成功'),
    ('Running', '运行中'),
    ('No change.', '无变化。'),
]
ok = 0
for en, zh in tests:
    r = _(en)
    if r == zh:
        ok += 1
    else:
        print(f'  ✗ {en} → {r} (expected: {zh})')
print(f'验证: {ok}/{len(tests)} 通过')
