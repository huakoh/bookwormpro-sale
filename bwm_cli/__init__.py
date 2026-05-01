"""
BookwormPRO CLI - Unified command-line interface for BookwormPRO.

Provides subcommands for:
- bookworm chat          - Interactive chat (same as ./bookworm)
- bookworm gateway       - Run gateway in foreground
- bookworm gateway start - Start gateway service
- bookworm gateway stop  - Stop gateway service  
- bookworm setup         - Interactive setup wizard
- bookworm status        - Show status of all components
- bookworm cron          - Manage cron jobs
"""

__version__ = "7.0.0"
__soul_version__ = "7.0.0-soul"  # 与 soul.md 版本同步
__soul_path__ = "~/.bookwormpro/SOUL.md"  # 系统提示词槽位 #1，唯一运行时路径
__release_date__ = "2026.4.30"
