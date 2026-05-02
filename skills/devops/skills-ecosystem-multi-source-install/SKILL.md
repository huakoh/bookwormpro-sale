---
name: skills-ecosystem-multi-source-install
description: Install skills from the skills.sh ecosystem (npx skills) and hybrid approach with BookwormPRO skills. Use when BookwormPRO skills hub times out or when skills exist on skills.sh but not in BookwormPRO format.
version: 1.0.0
author: BookwormPRO
tags: [skills, npm, skills-sh, claude-code, multi-agent]
---

# Multi-Source Skill Installation (skills.sh + BookwormPRO Hybrid)

当需要安装来自 skills.sh 生态的技能时（截图识别、用户指定技能名），
使用 `npx skills` CLI 作为主通道，GitHub API 作为备用通道。

## 触发条件

- 用户要求安装 skills.sh 上看到的技能
- BookwormPRO `skills hub` 搜索/安装超时（代理网络慢）
- 需要对比截图技能 vs BookwormPRO 已有技能

## 核心发现

1. **skills.sh 注册表技能格式**：`owner/repo@skill-name`（如 `obra/superpowers@brainstorming`）
2. **安装位置**：`~/.agents/skills/` 和 `~/.claude/skills/`（非 BookwormPRO 的 `~/.bookwormpro/skills/`）
3. **官方 Anthropic 技能**：`anthropics/skills` repo 含 17 个官方技能（skill-creator, mcp-builder, frontend-design 等）
4. **BookwormPRO 等价技能**：许多 skills.sh 技能在 BookwormPRO 中有 `-expert` 后缀的等价物

## 工作流

### 1. 搜索技能

```bash
npx skills find "<keyword>"
```

输出格式：
```
owner/repo@skill-name  XXK installs
└ https://skills.sh/owner/repo/skill-name
```

选安装量最高的。

### 2. 安装技能

```bash
npx skills add <owner/repo@skill-name> --yes
```

批量安装多个：
```bash
npx skills add anthropics/skills@skill-creator --yes
npx skills add anthropics/skills@mcp-builder --yes
```

### 3. 验证安装

```bash
npx skills list
```

### 4. GitHub API 备用通道（当 npx skills 不可用时）

```python
import urllib.request, json

url = 'https://api.github.com/repos/<owner>/<repo>/git/trees/main?recursive=1'
req = urllib.request.Request(url)
req.add_header('Accept', 'application/vnd.github+json')
req.add_header('User-Agent', 'BookwormPRO')

resp = urllib.request.urlopen(req, timeout=30)
data = json.loads(resp.read().decode())
skills = set()
for item in data.get('tree', []):
    path = item['path']
    if path.startswith('skills/') and item['type'] == 'tree':
        parts = path.split('/')
        if len(parts) == 2:
            skills.add(parts[1])
```

### 5. 直接下载 SKILL.md（GitHub Raw）

```python
url = f'https://raw.githubusercontent.com/vercel-labs/skills/main/skills/{name}/SKILL.md'
```

## 已安装的 skills.sh 技能清单（本次会话）

| 技能 | 来源 | 安装量 |
|------|------|--------|
| brainstorming | obra/superpowers | 130K |
| skill-creator | anthropics/skills | 177K |
| mcp-builder | anthropics/skills | 46K |
| programmatic-seo | coreyhaines31/marketingskills | 55K |
| find-skills | vercel-labs/skills (GitHub direct) | - |
| vercel-react-native-skills | vercel-labs/agent-skills | - |

## BookwormPRO vs skills.sh 等价技能映射

| skills.sh 技能 | BookwormPRO 等价 |
|---------------|-----------------|
| copywriting | copywriter-expert |
| technical-writing | tech-writer-expert |
| seo-audit | technical-seo-expert |
| social-content | social-media-manager |
| pricing-strategy | pricing-strategist |
| audit-website | project-audit-expert |
| webapp-testing | qa / tester-expert |
| marketing-psychology | growth-hacker |
| guidelines | ui-ux-pro-max (包含设计规范) |
| agent-browser / browser-use | 浏览器工具已内置 (browser_navigate/click等) |

## 技能发现流程：截图→OCR→安装

当用户分享 skills.sh 截图时：

```bash
# 1. 批量压缩截图
python -c "
from PIL import Image
for f in screenshots:
    img = Image.open(f); img.thumbnail((1200,1200))
    img.convert('RGB').save(out, 'JPEG', quality=75)
"

# 2. 批量 OCR（OCR.space 免费 API）
python -c "
import base64, json, urllib.request
for img in compressed:
    b64 = base64.b64encode(open(img,'rb').read()).decode()
    data = urllib.parse.urlencode({
        'apikey': 'helloworld',
        'base64Image': f'data:image/jpeg;base64,{b64}',
        'language': 'chs',  # chs=中英混合
    }).encode()
    result = json.loads(urllib.request.urlopen(
        urllib.request.Request('https://api.ocr.space/parse/image', data=data)
    ).read())
    print(result['ParsedResults'][0]['ParsedText'])
"
```

## 自创替代技能（当 registry 找不到时）

当技能在所有 registry 均不可用时，直接创建 BookwormPRO 兼容版本：

1. 基于技能名推断功能（从截图描述/类似技能推断）
2. 写 SKILL.md 到 `~/.bookwormpro/skills/<name>/SKILL.md`
3. 遵循 YAML frontmatter + Markdown 格式
4. 标注 `version: 1.0.0` 和 `author: BookwormPRO (adapted)`

示例：`structured-thinking` 未被任何 registry 收录，自创含 8 种框架（第一性原理/MECE/议题树/六顶思考帽/决策矩阵/5Whys/ICE/Pre-mortem）。

## 多源安装汇总（本次会话实战）

| 技能 | 方式 | 来源 |
|------|------|------|
| brainstorming | npx skills | obra/superpowers (130K) |
| skill-creator | npx skills | anthropics/skills (177K) |
| mcp-builder | npx skills | anthropics/skills (46K) |
| programmatic-seo | npx skills | coreyhaines31/marketingskills (55K) |
| proactive-agent | npx skills | halthelobster/proactive-agent (13.6K) |
| find-skills | GitHub raw | vercel-labs/skills (251K, 唯一在repo中的) |
| vercel-react-native | npx skills | vercel-labs/agent-skills (bundled, 原名 vercel-react-native-skills) |
| structured-thinking | 自创 | 无registry收录 |

## 注意事项

- skills.sh 技能格式与 BookwormPRO 不兼容，需通过 `npx skills` 安装
- 安装后技能位于 `~/.agents/skills/`，对 Claude Code/Codex/Cursor 等代理可用
- `~/.bookwormpro/skills/` 是 BookwormPRO 原生技能路径
- `npx skills` 首次运行会安装 npm 包 `skills`（约 1.5MB）
- 代理/VPN 环境下 `npx skills` 通常比 BookwormPRO skills hub 快（走 npm/git 协议）
- **命名陷阱**：截图中的 `vercel-react-native-mobile` 实际叫 `vercel-react-native-skills`
- **Anthropic 官方技能**：`anthropics/skills` repo 含 17 个官方技能 (skill-creator, mcp-builder, frontend-design, algorithmic-art, brand-guidelines, canvas-design, claude-api, doc-coauthoring, docx, internal-comms, pdf, pptx, slack-gif-creator, theme-factory, web-artifacts-builder, webapp-testing, xlsx)
- **结构化思维缺位**：`structured-thinking` 在所有 registry 均未找到（14.8K截图可能来自已下架源）
- **Bundle 技能**：`vercel-labs/agent-skills` 是一个包含 7 个子技能的 mono-repo，`npx skills add vercel-labs/agent-skills` 会一次性安装全部
- 下载的 SKILL.md 放入 `~/.bookwormpro/skills/from-hub/` 隔离管理
- **完全映射表已扩展至 13 对**：见上方 BookwormPRO vs skills.sh 等价映射

## 跨生态分类方法论

skills.sh 技能与 BookwormPRO 技能分别管理，但统一归入同一 14 类体系：

```
类别                    skills.sh 技能          BookwormPRO 技能
─────────────────────────────────────────────────────────────
前端与移动              vercel-react-* (6个)     frontend-design, vue-expert...
AI与数据                —                        ai-ml-expert, mlops...
元能力与思维            brainstorming            structured-thinking, skill-navigator...
内容与营销              —                        programmatic-seo, copywriter...
集成与平台              mcp-builder              mcp, github...
```

分类原则：skills.sh 技能与 BookwormPRO 同类别技能并列，互补不互斥。

## 全部已安装 skills.sh 技能 (8个)

| 技能 | 方式 | 来源 | 安装量 |
|------|------|------|--------|
| brainstorming | npx skills | obra/superpowers | 130K |
| skill-creator | npx skills | anthropics/skills | 177K |
| mcp-builder | npx skills | anthropics/skills | 46K |
| programmatic-seo | npx skills | coreyhaines31/marketingskills | 55K |
| proactive-agent | npx skills | halthelobster/proactive-agent | 13.6K |
| find-skills | GitHub raw | vercel-labs/skills | 251K |
| vercel-react-native-skills | npx skills | vercel-labs/agent-skills | bundled |
| structured-thinking | 自创 | BookwormPRO 格式 | — |
