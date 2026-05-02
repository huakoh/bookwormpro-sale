# BookwormPRO — AI 智能助手技能包

## 这是什么

BookwormPRO 是一套为 AI 编程助手（Claude Code / Cursor / Windsurf 等）设计的**技能生态系统**。包含 300+ 专业领域技能、多 AI 协作架构、神经网关路由引擎和"见山大叔"人格系统。

它不是另一个 AI 工具——它是**让你的 AI 助手从"能用"变成"专业"**的升级包。

## 核心组成

| 组件 | 数量 | 说明 |
|------|------|------|
| **专业技能** | 305 | 覆盖开发/设计/安全/运维/数据/产品/营销等 |
| **人格系统** | 1 | "见山大叔"——20年经验老派工程师风格 |
| **灵魂文件** | 2 | SOUL.md + CLAUDE.md（行为宪法） |
| **配置模板** | 3 | config.yaml + .env + auth.json 开箱即用 |

## 快速开始

### 前置条件

- 已安装支持 Skills 的 AI 编程助手（Claude Code / Bookworm Agent 等）
- 一个 API Key（DeepSeek / OpenAI / Anthropic 任选其一）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/huakoh/bookwormpro-sale.git ~/.bookwormpro

# 2. 运行安装脚本
cd ~/.bookwormpro && python scripts/setup.py

# 3. 按提示填入你的 API Key
# 4. 重启 AI 助手
```

### 最少配置（5 分钟上手）

在 `~/.bookwormpro/.env` 中填入：

```bash
# 必选：至少配一个
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 可选：解锁更多能力
DASHSCOPE_API_KEY=sk-your-key    # 通义千问 + 视觉
GOOGLE_API_KEY=your-key          # Gemini
```

## 使用方式

安装后，你的 AI 助手会自动加载所有技能。直接对话即可：

```
用户: 帮我审查这个项目的安全性
→ AI 自动调用 security-expert 技能

用户: 设计一个 SaaS 定价方案
→ AI 自动调用 pricing-strategist 技能

用户: bookworm自检
→ AI 运行 6 环节系统自检管线
```

## 技能分类

| 领域 | 技能数 | 代表技能 |
|------|--------|----------|
| 软件开发 | 40+ | developer-expert, debugger-expert, architect-expert |
| DevOps | 30+ | docker-rebuild-safe, gateway-hardening, ssl-behind-proxy |
| 创意设计 | 20+ | frontend-design, seedream-generation, ascii-art |
| 数据科学 | 15+ | data-analyst-expert, jupyter-live-kernel |
| 安全审计 | 10+ | security-expert, guardian, red-teaming |
| 产品运营 | 15+ | pricing-strategist, growth-hacker, social-media-manager |
| 中文特色 | 20+ | 微信/企微/飞书/钉钉集成, 中国服务器部署, ICP备案 |
| 系统工具 | 10+ | bookworm自检, 五柱体检, 凭证管理 |

## 人格风格

默认激活"**见山大叔**"人格——敲过二十年代码的老派工程师：

- 中文回复，技术名词保留英文
- 先分析后动手，给方案列编号
- 改代码必附 diff——改了什么、为什么、影响什么
- 不留 TODO，不交半成品，质量过四关才出手
- 专业但不端着，务实但有温度

可通过 `config.yaml` 自定义或禁用。

## 更新

```bash
cd ~/.bookwormpro && git pull && python scripts/upgrade.py
```

## 许可

MIT License. 技能和配置文件可自由使用、修改、分发。

## 联系

- Issues: https://github.com/huakoh/bookwormpro-sale/issues
- 文档: 见 INSTALL.md
