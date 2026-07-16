# BookwormPRO Changelog

## v7.0.0 (2026-04-30)

### 新增

- **soul.md — 系统灵魂文件**: 16章宪法+12条反自负的浓缩精华（233行）。当上下文耗尽、宪法记不全时，soul.md 为 AI 提供退化行为指南
- **退化安全网**: 5条不可违反底线内联至 CLAUDE.md，任何模式下均生效——不可逆操作确认、禁止代码执行、禁止凭证暴露、安全操作需宪法确认、所有修改显式声明
- **soul 命令**: `/soul [audit|drift]` — 运行闭环度自审和宪法漂移检测
- **漂移检测**: `soul-drift.py` 每周一 cron 自动运行，检测 soul.md 与宪法章节覆盖漂移
- **soul-design-rationale.md**: 设计哲学文档，记录压缩策略、内联决策、版本同步机制等 tradeoff
- **soul-ab-verification.md**: 效能 A/B 验证方案，定义安全行为度量指标
- **Portable NDA 适配**: dist-portable 版 soul.md 和 CLAUDE.md 已完成内部变量名脱敏

### 变更

- CLAUDE.md: 新增退化安全网节（L75-85），增强 soul.md 引用
- bwm_cli/__init__.py: 新增 `__soul_version__` 和 `__soul_path__`
- commands.py: 注册 `/soul` 命令
- cli.py: 新增 `_handle_soul_command` 处理器

### 审查

- soul.md 经安全/质量/架构/红队四路专家并行审查，修复 4 CRITICAL + 5 HIGH 项
- 闭环度自审: 25/32 (78.1%)，通用核心章全覆盖 PASS
