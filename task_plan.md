# BookwormPRO i18n 汉化方案 C — 任务计划

## 目标
引入完整 i18n 框架（Python gettext），支持 `config.yaml` 中 `language: zh_CN` 切换，
默认 zh_CN。全部用户可见文本中文化。

## 架构设计

```
bwm_cli/i18n.py              ← i18n 核心模块 (_() 函数 + gettext 封装)
locale/
  zh_CN/LC_MESSAGES/
    bookwormpro.po            ← 中文字符串翻译
    bookwormpro.mo            ← 编译后的二进制
  bookwormpro.pot             ← 字符串模板（用于翻译）
scripts/extract_strings.py   ← 自动提取字符串工具
```

### 设计原则
- 零侵入：`from bwm_cli.i18n import _` 一行即可使用
- 回退：gettext 不可用时退回原始英文字符串
- 语言检测顺序：config.yaml language → LANG 环境变量 → zh_CN 默认
- 不改变函数签名，只包裹输出字符串

## 阶段划分

### Phase 1: i18n 核心基础设施
- [ ] 创建 `bwm_cli/i18n.py` 模块
- [ ] 创建 locale 目录结构
- [ ] 生成 bookwormpro.pot 模板
- [ ] 创建 zh_CN 翻译文件 (.po → .mo)
- [ ] 创建 `scripts/extract_strings.py` 提取工具
- [ ] 添加 config 选项 `language: zh_CN`
- [ ] 验证：基本 i18n 函数可用

### Phase 2: 核心 CLI 汉化
- [ ] bwm_cli/banner.py — 横幅完全汉化
- [ ] bwm_cli/commands.py — 命令描述汉化
- [ ] bwm_cli/cli.py (或主 cli.py) — 交互消息

### Phase 3: Gateway + 工具汉化
- [ ] bwm_cli/gateway.py — 状态消息
- [ ] bwm_cli/config.py — 配置提示
- [ ] bwm_cli/models.py — 模型相关
- [ ] agent/ — 错误/状态消息

### Phase 4: 测试 + 文档
- [ ] 添加 i18n 单元测试
- [ ] 更新 user-manual.html
- [ ] 发布说明

## 进度
- 当前阶段：Phase 1
- 状态：进行中

## 错误记录
（暂无）
