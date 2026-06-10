"""
Shared platform registry for BookwormPRO.

Single source of truth for platform metadata consumed by both
skills_config (label display) and tools_config (default toolset
resolution).  Import ``PLATFORMS`` from here instead of maintaining
duplicate dicts in each module.
"""

from collections import OrderedDict
from typing import NamedTuple


class PlatformInfo(NamedTuple):
    """Metadata for a single platform entry."""
    label: str
    default_toolset: str


# Ordered so that TUI menus are deterministic.
PLATFORMS: OrderedDict[str, PlatformInfo] = OrderedDict([
    ("cli",            PlatformInfo(label="[系统]  CLI",            default_toolset="bookworm-cli")),
    ("telegram",       PlatformInfo(label="📱 Telegram",        default_toolset="bookworm-telegram")),
    ("discord",        PlatformInfo(label="[对话] Discord",         default_toolset="bookworm-discord")),
    ("slack",          PlatformInfo(label="💼 Slack",           default_toolset="bookworm-slack")),
    ("whatsapp",       PlatformInfo(label="📱 WhatsApp",        default_toolset="bookworm-whatsapp")),
    ("signal",         PlatformInfo(label="📡 Signal",          default_toolset="bookworm-signal")),
    ("bluebubbles",    PlatformInfo(label="💙 BlueBubbles",     default_toolset="bookworm-bluebubbles")),
    ("email",          PlatformInfo(label="📧 Email",           default_toolset="bookworm-email")),
    ("homeassistant",  PlatformInfo(label="🏠 Home Assistant",  default_toolset="bookworm-homeassistant")),
    ("mattermost",     PlatformInfo(label="[对话] Mattermost",      default_toolset="bookworm-mattermost")),
    ("matrix",         PlatformInfo(label="[对话] Matrix",          default_toolset="bookworm-matrix")),
    ("dingtalk",       PlatformInfo(label="[对话] DingTalk",        default_toolset="bookworm-dingtalk")),
    ("feishu",         PlatformInfo(label="🪽 Feishu",          default_toolset="bookworm-feishu")),
    ("wecom",          PlatformInfo(label="[对话] WeCom",           default_toolset="bookworm-wecom")),
    ("wecom_callback", PlatformInfo(label="[对话] WeCom Callback",  default_toolset="bookworm-wecom-callback")),
    ("weixin",         PlatformInfo(label="[对话] Weixin",          default_toolset="bookworm-weixin")),
    ("qqbot",          PlatformInfo(label="[对话] QQBot",           default_toolset="bookworm-qqbot")),
    ("webhook",        PlatformInfo(label="[端点] Webhook",         default_toolset="bookworm-webhook")),
    ("api_server",     PlatformInfo(label="[网页] API Server",      default_toolset="bookworm-api-server")),
    ("cron",           PlatformInfo(label="⏰ Cron",            default_toolset="bookworm-cron")),
])


def platform_label(key: str, default: str = "") -> str:
    """Return the display label for a platform key, or *default*."""
    info = PLATFORMS.get(key)
    return info.label if info is not None else default
