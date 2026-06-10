// Golden Set Expansion v2 — extract queries from skill descriptions
const fs = require('fs');

const existing = require('./golden-set.json');
const existingSet = new Set(existing.entries.map(e => e.query.substring(0, 40).toLowerCase()));

const skillsIndex = JSON.parse(fs.readFileSync(
  require('./lib/root.js') + '/skills-index-lite.json', 'utf8'));

// Manual corrections
const fixes = [
  { query: "REST API 接口设计 OpenAPI", skill: "api-designer" },
  { query: "Swagger API 文档规范设计", skill: "api-designer" },
  { query: "Golang 接口 struct 编程", skill: "golang-pro" },
  { query: "Next.js SSR App Router 服务端渲染", skill: "nextjs-developer" },
  { query: "Python pytest 类型提示测试", skill: "python-pro" },
  { query: "TypeScript 类型泛型 interface 编程", skill: "typescript-pro" },
  { query: "法律合规审查隐私政策", skill: "legal-review-skill" },
  { query: "SQL 数据查询分析报表生成", skill: "data-analyst-expert" },
  { query: "项目规划文件进度管理跟踪", skill: "planning-with-files" },
  { query: "终极代码审查双重审查机制", skill: "ultimate-code-expert" },
  { query: "clash verge 静态住宅IP 翻墙上网配置", skill: "devops-expert" },
  { query: "terminator mcp 是什么功能", skill: "mcp-probe" },
  { query: "MCP 服务器全量体检", skill: "mcp-probe" },
  { query: "mcp prune 剪枝分析工具", skill: "mcp-prune" },
  { query: "React 组件状态管理", skill: "frontend-expert" },
  { query: "Vue3 组合式 API 怎么写", skill: "vue-expert" },
  { query: "Flutter 列表性能优化", skill: "flutter-expert" },
  { query: "Kubernetes 部署配置", skill: "kubernetes-specialist" },
  { query: "Terraform 管理阿里云资源", skill: "terraform-engineer" },
  { query: "Git 冲突 rebase 报错解决", skill: "git-operation-master" },
  { query: "Rust 异步编程 tokio", skill: "rust-engineer" },
  { query: "Swift iOS App SwiftUI", skill: "swift-expert" },
  { query: "小程序微信支付集成", skill: "miniprogram-expert" },
  { query: "React Native 跨平台开发", skill: "mobile-expert" },
  { query: "WebSocket 实时通信", skill: "websocket-engineer" },
  { query: "通知系统推送设计", skill: "notification-system-expert" },
  { query: "Cloudflare Workers 部署", skill: "edge-computing-expert" },
  { query: "GraphQL schema 设计", skill: "graphql-architect" },
  { query: "Angular 17 Signals 使用", skill: "angular-architect" },
  { query: "CSS Grid Flexbox 布局", skill: "designer-expert" },
  { query: "正则表达式匹配邮箱格式", skill: "regex-shell-wizard" },
  { query: "Shell 脚本批量处理文件", skill: "regex-shell-wizard" },
  { query: "PPT 制作演示文稿", skill: "powerpoint" },
  { query: "PDF 文档编辑修改", skill: "nano-pdf" },
  { query: "Google Calendar 日历管理", skill: "google-workspace" },
  { query: "Notion 数据库页面管理", skill: "notion" },
  { query: "邮件商务沟通客户跟进", skill: "email-communicator" },
  { query: "SaaS 定价模型设计", skill: "pricing-strategist" },
  { query: "商业计划书融资 BP", skill: "business-plan-skill" },
  { query: "销售策略 CRM 客户管理", skill: "sales-consultant" },
  { query: "社交媒体运营内容策略", skill: "social-media-manager" },
  { query: "财务记账税务筹划", skill: "finance-advisor" },
  { query: "用户增长 AARRR 漏斗", skill: "growth-hacker" },
  { query: "用户体验研究可用性测试", skill: "ux-researcher" },
  { query: "Docker 容器化部署", skill: "devops-expert" },
  { query: "GitHub Actions CI/CD 流水线", skill: "devops-expert" },
  { query: "Prometheus Grafana 监控配置", skill: "sre-expert" },
  { query: "数据库索引优化慢查询", skill: "database-tuning-expert" },
  { query: "数据仓库 ETL 管道设计", skill: "data-engineer-expert" },
  { query: "PyTorch 神经网络训练", skill: "ai-ml-expert" },
  { query: "LLM 微调 LoRA 训练", skill: "ai-ml-expert" },
  { query: "RAG 检索增强生成系统", skill: "ai-ml-expert" },
  { query: "AI 伦理偏见对齐审计", skill: "ai-philosophy-expert" },
  { query: "SEO 百度优化收录", skill: "technical-seo-expert" },
  { query: "JWT OAuth 2.0 认证实现", skill: "security-expert" },
  { query: "XSS SQL 注入防护", skill: "security-expert" },
  { query: "代码审计漏洞扫描", skill: "devsecops-expert" },
  { query: "容器安全镜像扫描 Trivy", skill: "devsecops-expert" },
  { query: "供应链安全 SBOM 生成", skill: "devsecops-expert" },
  { query: "AWS 云架构设计", skill: "cloud-architect" },
  { query: "K8s 编排微服务", skill: "cloud-native-expert" },
  { query: "DDD 领域驱动设计", skill: "architect-expert" },
  { query: "Mermaid 流程图架构图", skill: "diagram-as-code-expert" },
  { query: "行业研究市场调研 TAM SAM SOM", skill: "industry-research-cn" },
  { query: "投资分析项目估值", skill: "investor-review-guide" },
  { query: "客户成功 SLA 设计", skill: "customer-success-expert" },
  { query: "暗色主题 SVG 架构图", skill: "architecture-diagram" },
  { query: "ASCII art 文字艺术", skill: "ascii-art" },
  { query: "Spotify 音乐控制播放", skill: "spotify" },
  { query: "YouTube 视频字幕提取", skill: "youtube-content" },
  { query: "Hugging Face 模型下载", skill: "huggingface-hub" },
  { query: "llama.cpp 本地 GGUF 推理", skill: "llama-cpp" },
  { query: "Jupyter 交互式数据分析", skill: "jupyter-live-kernel" },
  { query: "Windows 桌面自动化 RPA", skill: "windows-mcp" },
  { query: "浏览器自动化 Playwright 测试", skill: "browser-automation-expert" },
  { query: "Minecraft 模组服务器搭建", skill: "minecraft-modpack-server" },
  { query: "Obsidian 笔记管理搜索", skill: "obsidian" },
  { query: "GIF 动图搜索下载", skill: "gif-search" },
  { query: "学术论文 arXiv 检索", skill: "arxiv" },
  { query: "Polymarket 预测市场数据", skill: "polymarket" },
  { query: "Philips Hue 智能灯控制", skill: "openhue" },
  { query: "Linear 项目管理事务跟踪", skill: "linear" },
  { query: "Slack 消息频道操作", skill: "developer-expert" },
  { query: "Atlassian Jira 项目管理", skill: "developer-expert" },
  { query: "Supabase 数据库实时订阅", skill: "developer-expert" },
  { query: "Figma 设计文件操作", skill: "developer-expert" },
];

// Add all corrections
for (const f of fixes) {
  if (!existingSet.has(f.query.toLowerCase().substring(0, 40))) {
    existing.entries.push({ query: f.query, expectedSkill: f.skill, source: 'manual-fix' });
    existingSet.add(f.query.toLowerCase().substring(0, 40));
  }
}

existing.version = 'v7.0';
existing.generated = new Date().toISOString();

fs.writeFileSync('./golden-set.json', JSON.stringify(existing, null, 2));
console.log('Original: 170');
console.log('Added:   ', existing.entries.length - 170);
console.log('New total:', existing.entries.length);
