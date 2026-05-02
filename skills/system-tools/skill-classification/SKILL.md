---
name: skill-classification
category: 系统工具
description: >
  技能系统归类方法论。当需要对大量无类别技能进行系统分类、设计分类体系、
  验证分类合理性、或修正归属偏差时使用。覆盖四阶段流程：收集分析 →
  体系设计 → 逐一分配 → 场景验证。触发词：技能归类、技能分类、
  skill classification、系统归类、分类验证。
---

# 技能系统归类

对 BookwormPRO 技能库中无类别技能进行系统化分类的方法论。

## 四阶段流程

### Phase 1: 收集与分析
1. `skills_list` 获取全部技能，过滤 `category: null` 的项
2. 对名称模糊的技能调用 `skill_view(name)` 读取全文确认属性
3. 标注技能的 composable/related_skills 链，防止割裂相关技能

### Phase 2: 体系设计
- 类别数量控制在 10-15 个，过多失去聚合意义
- 优先中文命名，与系统现有类别风格一致
- 允许双类归属（如 devsecops-expert ∈ 安全 ∩ 云基础设施）
- 类别之间有清晰边界，避免"杂项"兜底类

### Phase 3: 逐一分配
- 每个技能基于其 SKILL.md 中 `description`、触发关键词、`allowed-tools`、`composable` 判定
- 优先匹配核心功能而非边缘场景
- 本地技能（~/.bookwormpro/skills/ 下存在 SKILL.md）可直接 patch category
- 捆绑/Hub 技能（不在本地目录）标记为需上游 PR

### Phase 4: 场景驱动验证
最关键步骤。设计 3-4 个覆盖不同领域的典型任务场景，模拟技能调用链：

| 验证维度 | 方法 |
|----------|------|
| 同类聚合 | 一个场景是否自然触发同类别多个技能？ |
| 跨类隔离 | 是否需要同时加载多个类别完成同一任务？（允许，但应合理） |
| 边界清晰 | 是否有技能在不同场景中反复跨类？（检测归属偏差信号） |
| 遗漏检查 | 是否有技能从未被任何场景触发？（可能类别设计有盲区） |

每个场景记录调用链验证表：
```
场景: "从零搭建 SaaS 项目"
| 阶段 | 调用技能 | 分类 | 判定 |
| Phase 0 | product-manager-expert | 项目管理 | ✅/❌ |
```

## 常见陷阱

### patch 工具 CRLF 问题 (Windows)
在 Windows + Git Bash 环境，`patch` 对任何文件都会因 CRLF/LF 不匹配导致写入验证失败（"wrote X chars, read back Y chars"，差额 ~80-100）。此时：
```bash
sed -i 's/old_pattern/new_text/' file   # 简单替换首选
```
复杂编辑：先用 `read_file`（**不带 offset/limit**，读取全文取得精确 CRLF 格式），再用 `write_file` 重写整个文件。千万不能分页读取后 patch——必定失败。

### 捆绑技能 vs 本地技能
- `skills_list` 返回的技能 ≠ 全部可编辑
- 验证方法：`search_files(pattern="skill-name", path="~/.bookwormpro/skills")`
- 返回 0 结果 = 捆绑/Hub 技能，不可本地修改
- 本地技能 `category` 写入后立即生效

### 包名路径映射
`skills_list` 中的 skill name 到文件路径的映射不是简单拼接：
- Hub 捆绑技能在 `.bundled_manifest` 中用 hash 映射
- 本地技能在 `~/.bookwormpro/skills/<name>/SKILL.md`
- 某些技能的 name（如 `bookwormpro`）映射到不同的文件名（如 `hermes-agent/SKILL.md`）

## Phase 5: 批量打标与发布（上游贡献 · 实战验证）

如技能来自外部注册表（skills.sh Hub，Vercel托管服务，不接受PR），采用 Skills Tap 方案。

### 实战工作流
1. **确认技能来源**: `search_files(pattern="skill-name", path="~/.bookwormpro/skills")` 返回 0 = Hub捆绑，但 `ls -d ~/.bookwormpro/skills/<name>` 可能仍存在目录（search_files 有路径解析差异，以终端 ls 为准）
2. **批量读取**: 遍历 CATEGORY_MAP，从 `~/.bookwormpro/skills/<name>/SKILL.md` 复制并注入 category
3. **YAML 注入**: 在 YAML frontmatter 的 `name:` 行后插入 `category: <中文类别>`
4. **目录重组**: 输出为 `类别名/技能名/SKILL.md`，同步复制 references/scripts/assets 等支持文件
5. **生成 README**: 含分类统计和使用说明
6. **推送到 GitHub**: `git init && git commit && gh repo create --public --push`
7. **加载为 Tap**: `bookworm skills tap add https://github.com/<user>/<repo>`

### 实战 Python 脚本
```python
CATEGORY_MAP = {"ai-ml-expert": "AI与机器学习", ...}  # 79个条目

def add_category_to_frontmatter(content, category):
    """在 YAML name: 行后插入 category 行"""
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == '---' and i > 0: break  # end of frontmatter
        if line.startswith('name:'):
            lines.insert(i+1, f'category: {category}')
            break
    return '\n'.join(lines)

for name, cat in CATEGORY_MAP.items():
    src = SKILLS_DIR / name / "SKILL.md"
    dst = OUTPUT_DIR / cat / name / "SKILL.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(add_category_to_frontmatter(src.read_text('utf-8'), cat), 'utf-8')
```

### GitHub 网络（China 环境）
- `web_search`/`web_extract` GitHub URL 可能返回 "Blocked: private network address"
- **但 `git clone`、`git push`、`gh` CLI 正常工作** —— 先用 `git ls-remote` 验证
- `gh auth status` 确认登录态后再操作
- 浅克隆提速: `git clone --depth 1 <url>`

### 仪表盘生成
分类完成后生成交互式 HTML 仪表盘（纯 HTML/CSS/JS，零依赖）：
- 侧栏 31 类分类导航（彩色圆点 + 技能计数）
- 实时搜索（`Ctrl+K` 聚焦，支持名称/描述/类别搜索）
- 技能卡片网格（自适应布局，点击展开详情弹窗，`Esc` 关闭）
- 数据以 JS 数组 `{n, c, d}` 格式嵌入
- 每个类别分配独立颜色（CATEGORY_COLORS 字典）

## 输出规范

1. 汇总表：14 类对照表，含中英文名和技能数
2. 详细分配：每类列出所有技能 + 说明
3. 修订记录：逐项说明修正原因
4. 双类技能用注释标注（如 `devsecops-expert` 双类：安全+云基础设施）
5. 本地已更新的技能单独列出文件路径
6. 验证报告单独保存（`_Validation.md`），含场景调用链

## 禁止事项

- 不基于技能名称猜测归属，必须读描述或全文
- 不在未验证的情况下宣称分类完成
- 不将相关技能拆分到不同类别（检查 composable 链）
- 不超过 15 个类别（碎片化失去意义）
- 不假设所有技能都在本地可编辑（先验证文件存在）

## 已验证的 14 类体系 (138 技能分类实战)

以下分类体系经过 6 专家（AI/CTO/架构师/算法/哲学/红队）交叉验证，适用于 BookwormPRO + skills.sh 混合生态：

1. 开发与编程 (11): python-pro, typescript-pro, golang-pro, rust-engineer, debugger-expert...
2. 前端与移动 (16): frontend-design, vue-expert, vercel-react-*, miniprogram-expert...
3. 后端与API (6): backend-builder, api-designer, graphql-architect, websocket-engineer...
4. AI与数据 (9): ai-ml-expert, mlops, data-science, prompt-optimizer, codex...
5. 云与基础设施 (6): cloud-architect, kubernetes, terraform, edge-computing...
6. 架构与系统设计 (4): architect-expert, tech-lead-mentor, performance-expert...
7. 安全 (6): security-expert, devsecops, guardian, red-teaming, skill-guardian...
8. DevOps与质量 (15): devops, sre-expert, benchmark, qa, tester-expert...
9. 项目管理 (7): project-coordinator, genesis-engine, evolution-tracker...
10. 产品与商业 (9): product-manager, business-plan, pricing-strategist...
11. 内容与营销 (10): copywriter-expert, tech-writer, seo, i18n...
12. 设计与体验 (6): designer-expert, ui-ux-pro-max, ux-researcher...
13. 集成与平台 (15): mcp, github, email, browser-automation, media...
14. 元能力与思维 (16): brainstorming, structured-thinking, skill-navigator, find-skills...

类别选择原则：每类 4-16 个技能，无杂项兜底类，skills.sh 技能与 BookwormPRO 技能混归同类别。
