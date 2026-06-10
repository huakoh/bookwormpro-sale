#!/usr/bin/env node
/**
 * 分层路由 L1: 域分类器 (v5.9)
 *
 * 将用户查询分类到 8 个技能域之一，缩小 L2 精排的候选集。
 *
 * 域划分 (与 SKILL-REGISTRY.md 一致):
 *   ai-data      — AI/机器学习/数据分析/数据工程
 *   development  — 前后端/移动/小程序/通用开发/浏览器/工作流
 *   architecture — 系统架构/数据库/云原生/性能/图表
 *   devops       — CI/CD/Docker/K8s/Git/SRE
 *   security     — 安全/渗透/加密/DevSecOps
 *   quality      — 测试/审查/审计
 *   product      — 产品/设计/UX/项目管理
 *   business     — 商业/财务/营销/法务/研究
 *   content      — 技术写作/文案/邮件/SEO/社媒
 *   meta         — 编排/提示词/元技能
 *
 * 模块导出:
 *   classifyDomain(queryText, intents, entities) → { domain, confidence, candidates }
 *   DOMAIN_SKILLS — 域→技能名映射
 *   DOMAIN_KEYWORDS — 域→关键词映射
 */

// === 域→技能名映射 ===
const DOMAIN_SKILLS = {
  'ai-data': [
    'ai-ml-expert', 'data-analyst-expert', 'data-engineer-expert',
  ],
  'development': [
    'frontend-expert', 'backend-builder', 'mobile-expert', 'miniprogram-expert',
    'developer-expert', 'debugger-expert', 'api-integration-specialist',
    'regex-shell-wizard', 'ultimate-code-expert', 'browser-automation-expert',
    'workflow-automation-expert', 'notification-system-expert',
    'typescript-pro', 'python-pro', 'golang-pro', 'rust-engineer',
    'angular-architect', 'vue-expert', 'nextjs-developer', 'flutter-expert',
    'swift-expert', 'websocket-engineer',
  ],
  'architecture': [
    'architect-expert', 'database-tuning-expert', 'cloud-native-expert',
    'edge-computing-expert', 'performance-expert', 'impact-analyst',
    'diagram-as-code-expert', 'zero-defect-guardian',
    'api-designer', 'graphql-architect', 'cloud-architect',
  ],
  'devops': [
    'devops-expert', 'devsecops-expert', 'git-operation-master', 'sre-expert',
    'kubernetes-specialist', 'terraform-engineer',
  ],
  'security': [
    'security-expert',
  ],
  'quality': [
    'tester-expert', 'reviewer-expert', 'project-audit-expert',
  ],
  'product': [
    'product-manager-expert', 'designer-expert', 'ux-researcher', 'project-coordinator',
  ],
  'business': [
    'business-plan-skill', 'finance-advisor', 'sales-consultant',
    'pricing-strategist', 'customer-success-expert', 'growth-hacker',
    'investor-review-guide', 'industry-research-cn', 'legal-review-skill',
  ],
  'content': [
    'tech-writer-expert', 'copywriter-expert', 'email-communicator',
    'social-media-manager', 'technical-seo-expert',
  ],
  'meta': [
    'genesis-engine', 'prompt-optimizer', 'tech-lead-mentor', 'planning-with-files',
  ],
};

// === 域关键词 (用于 L1 快速匹配) ===
const DOMAIN_KEYWORDS = {
  'ai-data': [
    'ai', 'ml', '机器学习', '深度学习', 'pytorch', 'tensorflow', 'nlp', 'cv',
    'llm', 'rag', '模型', '训练', '微调', 'fine-tune', 'embedding', 'transformer',
    'pandas', 'numpy', '数据分析', '数据工程', 'etl', 'spark', 'kafka', 'dbt',
    '大语言模型', 'langchain', 'huggingface', 'agent', 'prompt',
  ],
  'development': [
    'react', 'vue', 'angular', 'next', 'nuxt', 'svelte', 'tailwind', 'css',
    'node', 'express', 'fastapi', 'django', 'flask', 'go', 'gin', 'fiber',
    'flutter', 'swift', 'kotlin', 'react native', 'expo',
    '小程序', 'taro', 'uni-app', '微信',
    'api', 'rest', 'graphql', 'websocket', 'socket',
    '正则', 'shell', 'bash', 'awk', 'sed',
    '浏览器自动化', '爬虫', 'playwright', 'selenium', 'puppeteer',
    'zapier', 'n8n', '工作流', '自动化',
    '通知', '推送', 'fcm', 'sms', '站内信',
    'typescript', 'python', 'golang', 'rust', 'wasm',
    '写代码', '实现', '开发', '编程', '函数', '接口',
  ],
  'architecture': [
    '架构', '设计模式', 'ddd', 'adr', '技术选型', '微服务',
    '数据库', 'sql', '索引', '慢查询', 'mysql', 'postgresql', 'mongodb',
    'istio', 'gitops', '云原生',  // V17 修复: k8s/kubernetes/helm 移至 devops，消除跨域冲突
    'edge', 'workers', 'vercel edge', 'deno deploy', 'cdn',
    '性能', '优化', 'cwv', '首屏', '内存', '调优', '瓶颈',
    '影响范围', '依赖分析', '爆炸半径',
    'mermaid', 'plantuml', 'graphviz', '画图', '图表', '可视化',
    '零缺陷', 'pinning test',
  ],
  'devops': [
    'docker', 'ci', 'cd', 'ci/cd', 'pipeline', 'jenkins', 'github actions',
    'nginx', '部署', 'deploy', '运维',
    'git', 'rebase', 'cherry-pick', '分支', 'merge', 'conflict',
    'sli', 'slo', '监控', 'prometheus', 'grafana', '告警', 'postmortem',
    'terraform', 'iac', 'helm', 'rbac', 'k8s', 'kubernetes',  // V17: 统一归 devops
    'ssh', '服务器', 'linux',
  ],
  'security': [
    '安全', 'owasp', 'xss', 'csrf', 'sql注入', 'jwt', '加密', '渗透',
    'sast', 'dast', 'sbom', '漏洞', '权限', '认证', '鉴权',
  ],
  'quality': [
    '测试', 'test', 'jest', 'vitest', 'pytest', 'tdd', 'bdd',
    'code review', '代码审查', '审查', '重构', '技术债',
    '审计', '上线前', '质量',
  ],
  'product': [
    '产品', 'prd', '需求', '用户故事', '路线图', 'rice', 'kano',
    'ui', 'ux', '设计', '交互', 'figma', 'wcag', '无障碍',
    '用户研究', '访谈', 'persona', '可用性',
    '项目管理', '甘特图', 'sprint', '里程碑', '排期',
  ],
  'business': [
    '商业', 'bp', '融资', '商业计划', '商业模式',
    '记账', '财务', '税务', '现金流', '报税', '报价',
    '销售', 'crm', '谈判', '客户开发',
    '定价', '收费', 'saas', '免费增值',
    '客户成功', 'sla', 'onboarding', '续费', '流失',
    '增长', 'aarrr', '转化率', '裂变', '私域',
    '投资', '估值', '尽调', 'dd',
    '行业研究', '市场调研', '竞品', '市场规模',
    '合同', '法务', '合规', '知识产权', '劳动法',
  ],
  'content': [
    '文档', 'readme', 'api文档', '用户手册',
    '文案', '广告', '营销', '落地页', 'cta',
    '邮件', '商务邮件', '冷邮件', '催款',
    '社交媒体', '新媒体', '公众号', '小红书', '抖音', 'kol',
    'seo', 'sitemap', 'robots', 'json-ld', 'meta',
  ],
  'meta': [
    '从零', '全流程', '端到端', '全生命周期',
    '提示词', '优化提示',
    '团队管理', '晋升', '招聘', '1on1',
    '规划文档',
  ],
};

// 预编译: 域关键词 → 小写 Set
const DOMAIN_KEYWORD_SETS = {};
for (const [domain, keywords] of Object.entries(DOMAIN_KEYWORDS)) {
  DOMAIN_KEYWORD_SETS[domain] = new Set(keywords.map(k => k.toLowerCase()));
}

/**
 * L1 域分类: 基于关键词命中率 + 意图映射
 * @param {string} queryText - 用户查询文本
 * @param {string[]} intents - 已检测到的意图 (来自 intent-classifier)
 * @param {string[]} entities - 已检测到的实体 (来自 intent-classifier)
 * @returns {{ domain: string, confidence: number, candidates: string[] }}
 */
function classifyDomain(queryText, intents, entities) {
  const queryLower = (queryText || '').toLowerCase();
  const scores = {};

  // Phase 1: 关键词匹配评分
  for (const [domain, kwSet] of Object.entries(DOMAIN_KEYWORD_SETS)) {
    let hits = 0;
    for (const kw of kwSet) {
      // P1-4: 短英文关键词 (<=3字符) 使用 word boundary 防止子串误匹配
      if (kw.length <= 3 && /^[a-z]+$/i.test(kw)) {
        if (new RegExp('\\b' + kw + '\\b', 'i').test(queryLower)) hits++;
      } else {
        if (queryLower.includes(kw)) hits++;
      }
    }
    if (hits > 0) {
      // P2-15 修复: 二次方公式 — hits^2/size 减少大关键词集的噪声加分偏差
      // 小域少量精确命中 > 大域多量模糊命中
      scores[domain] = (scores[domain] || 0) + (hits * hits) / kwSet.size * 2.0;
    }
  }

  // Phase 2: 实体匹配 (框架/工具名)
  for (const entity of (entities || [])) {
    const entityLower = entity.toLowerCase();
    for (const [domain, kwSet] of Object.entries(DOMAIN_KEYWORD_SETS)) {
      if (kwSet.has(entityLower)) {
        scores[domain] = (scores[domain] || 0) + 0.5;
      }
    }
  }

  // Phase 3: 意图映射加成
  const intentDomainMap = {
    'debug': 'development', 'create': 'development', 'explain': 'development',
    'performance': 'architecture', 'architecture': 'architecture',
    'deploy': 'devops', 'security': 'security',
    'test': 'quality', 'review': 'quality',
    'data': 'ai-data',
  };
  for (const intent of (intents || [])) {
    const mapped = intentDomainMap[intent];
    if (mapped) {
      scores[mapped] = (scores[mapped] || 0) + 0.3;
    }
  }

  // 排序取 top
  const sorted = Object.entries(scores).sort((a, b) => b[1] - a[1]);

  if (sorted.length === 0) {
    return {
      domain: 'development',
      confidence: 0.1,
      candidates: DOMAIN_SKILLS['development'],
    };
  }

  const topDomain = sorted[0][0];
  const topScore = sorted[0][1];

  // V09 修复: 归一化置信度 = topScore / sum(allScores)，消除域大小偏差
  const totalScore = sorted.reduce((s, [, v]) => s + v, 0);
  const normalizedConfidence = totalScore > 0
    ? Math.min(1.0, Math.round((topScore / totalScore) * 100) / 100)
    : 0.1;

  // 如果 top-2 分数接近，合并候选集
  let candidates = [...DOMAIN_SKILLS[topDomain]];
  if (sorted.length >= 2 && sorted[1][1] / topScore > 0.6) {
    const secondDomain = sorted[1][0];
    candidates = candidates.concat(DOMAIN_SKILLS[secondDomain]);
  }

  // 始终包含 developer-expert 作为通用回退
  if (!candidates.includes('developer-expert')) {
    candidates.push('developer-expert');
  }

  return {
    domain: topDomain,
    confidence: normalizedConfidence,
    candidates,
    _scores: sorted.slice(0, 3).map(([d, s]) => ({ domain: d, score: Math.round(s * 100) / 100 })),
  };
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = {
    classifyDomain,
    DOMAIN_SKILLS,
    DOMAIN_KEYWORDS,
    DOMAIN_KEYWORD_SETS,
  };
}

// CLI 入口
if (require.main === module) {
  const query = process.argv.slice(2).join(' ') || '帮我写一个 React 组件';
  const result = classifyDomain(query, [], []);
  console.log(`查询: "${query}"`);
  console.log(`域:   ${result.domain} (${result.confidence})`);
  console.log(`候选: ${result.candidates.length} 个技能`);
  if (result._scores) {
    console.log(`评分: ${result._scores.map(s => `${s.domain}=${s.score}`).join(', ')}`);
  }
}
