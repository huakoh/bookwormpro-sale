# BookwormPRO i18n — 发现与调研

## 关键文件路径

| 文件 | 路径 | 字符串量 |
|------|------|----------|
| 版本常量 | bwm_cli/__init__.py | 1 |
| 横幅渲染 | bwm_cli/banner.py | ~30 字符串 |
| 命令注册 | bwm_cli/commands.py | ~80 命令描述 |
| CLI 主循环 | cli.py | ~50 交互消息 |
| Gateway | bwm_cli/gateway.py | ~20 状态消息 |
| 配置 | bwm_cli/config.py | ~30 提示消息 |
| Web Server | bwm_cli/web_server.py | ~10 消息 |
| 卸载 | bwm_cli/uninstall.py | ~15 消息 |
| Doctor | bwm_cli/doctor.py | ~20 诊断消息 |
| Agent | agent/ + run_agent.py | ~40 错误消息 |
| ACP | acp_adapter/server.py | ~5 消息 |

## 现有语言相关代码
- `config.py:688` — `"language": "en"` (TTS 语言，非 UI)
- `config.py:709` — `"language": ""` (auto-detect)
- `banner.py:447` — `LBL()` 函数已考虑中文宽度 (中文=2列)
- `gateway.py:280` — 已有 UTF-8 + `errors='replace'` 处理

## 已知问题
- Windows CRLF 导致 patch 工具失败 → 用 sed / write_file
- 部分文件使用 f-string 动态生成文本 → 需特殊处理
- gettext 在 Windows 无自带 → 需 Python gettext 标准库
