#!/usr/bin/env node
/**
 * 意图分类引擎 (v5.2 Neural Gateway)
 *
 * 轻量级正则规则引擎，对用户输入做三级分流:
 *   simple  — 简单问答，跳过路由
 *   medium  — 标准路由 (BM25 + 上下文融合)
 *   complex — 编排路由 (orchestrator / 多技能协作)
 *
 * 模块导出:
 *   classifyIntent(text) → { intents, modifiers, entities, complexity }
 *   extractEntities(text) → string[]
 *   scoreComplexity(intents, modifiers, entities) → 'simple'|'medium'|'complex'
 *
 * 性能预算: < 30ms
 */

const path = require('path');

// === 12 种意图标签 (正则规则) ===
const INTENT_RULES = [
  {
    label: 'debug',
    patterns: [
      /(?:调试|debug|报错|bug|异常|错误|error|crash|崩溃|修复|fix|排查|trace|stacktrace|故障)/i,
    ],
  },
  {
    label: 'performance',
    patterns: [
      /(?:性能|performance|优化|optimize|慢|卡顿|内存泄漏|memory\s*leak|profil|benchmark|瓶颈|bottleneck|缓存|cache|加速|提速)/i,
    ],
  },
  {
    label: 'security',
    patterns: [
      /(?:安全|security|漏洞|vulnerab|XSS|CSRF|注入|inject|认证|auth|鉴权|加密|encrypt|权限|permission|OWASP|渗透|pentest)/i,
    ],
  },
  {
    label: 'architecture',
    patterns: [
      /(?:架构|architect|设计模式|design\s*pattern|微服务|microservice|重构|refactor|解耦|decouple|分层|layer|模块化|modular|系统设计)/i,
    ],
  },
  {
    label: 'review',
    patterns: [
      /(?:代码审查|code\s*review|PR\s*review|评审|会审|review|审计|audit|检查代码|代码质量|lint|规范|专家组)/i,
    ],
  },
  {
    label: 'create',
    patterns: [
      /(?:从零|从头|新建|创建|搭建|初始化|init|scaffold|bootstrap|generate|新项目|starter|template|脚手架|生成)/i,
    ],
  },
  {
    label: 'deploy',
    patterns: [
      /(?:部署|deploy|上线|发布|release|CI\/?CD|pipeline|构建|build|打包|bundle|Docker|容器|K8s|Kubernetes)/i,
    ],
  },
  {
    label: 'test',
    patterns: [
      /(?:测试|test|单元测试|unit\s*test|集成测试|integration|E2E|端到端|覆盖率|coverage|mock|stub|TDD|BDD|vitest|jest|playwright)/i,
    ],
  },
  {
    label: 'data',
    patterns: [
      /(?:数据库|database|SQL|查询|query|表|table|索引|index|迁移|migration|ORM|Redis|MongoDB|PostgreSQL|MySQL|数据模型)/i,
    ],
  },
  {
    label: 'research',
    patterns: [
      /(?:调研|research|对比|compare|选型|evaluate|评估|分析|analyz|竞品|技术方案|方案设计|可行性)/i,
    ],
  },
  {
    label: 'explain',
    patterns: [
      /(?:解释|explain|什么是|what\s*is|怎么理解|区别|difference|原理|principle|概念|concept|为什么|why|how\s*does)/i,
    ],
  },
  {
    label: 'continue',
    patterns: [
      /^(?:继续|接着|下一步|往下|go\s+on|proceed)/i,
    ],
  },
  {
    label: 'select',
    patterns: [
      /^(?:选[第1-9一二三四五六七八九十]|方案[A-Za-z]|用这个|就这个|[1-9]号$)/i,
    ],
  },
  {
    label: 'confirm',
    patterns: [
      /^(?:好的|可以|行|确认|ok|yes|是的|对|没问题|同意)/i,
    ],
  },
  {
    label: 'general',
    patterns: [
      /(?:你好|hello|hi|帮我|请问|麻烦|谢谢|thanks|嗯)/i,
    ],
  },
];

// === 3 种修饰符 ===
const MODIFIER_RULES = [
  {
    label: 'urgent',
    patterns: [/(?:紧急|urgent|马上|立刻|赶紧|ASAP|immediately|尽快)/i],
  },
  {
    label: 'complex',
    patterns: [/(?:全面|comprehensive|完整|complete|端到端|end.to.end|全链路|full.stack|整个|entire|深入|deep|详细|detail)/i],
  },
  {
    label: 'simple',
    patterns: [/(?:简单|simple|快速|quick|直接|直|高效|efficient|简要|brief)/i],
  },
];

// === 实体提取 (框架/工具/语言) ===
const ENTITY_PATTERNS = {
  // 框架
  frameworks: [
    /\b(?:React|Vue(?:\.js)?|Angular|Next\.?js|Nuxt(?:\.js)?|Svelte|Solid(?:JS)?|Remix|Gatsby|Astro)\b/gi,
    /\b(?:FastAPI|Django|Flask|Express(?:\.js)?|Nest(?:JS|\.js)?|Spring\s*Boot|Laravel|Rails|Gin|Echo|Fiber)\b/gi,
    /\b(?:Electron|React\s*Native|Flutter|SwiftUI|Jetpack\s*Compose|Tauri|Expo)\b/gi,
  ],
  // 工具
  tools: [
    /\b(?:Docker|Kubernetes|K8s|Webpack|Vite|Rollup|esbuild|SWC|Turbopack|Bun)\b/gi,
    /\b(?:Git(?:Hub)?|GitLab|Terraform|Ansible|Prometheus|Grafana|Nginx|Caddy)\b/gi,
    /\b(?:PostgreSQL|MySQL|Redis|MongoDB|ElasticSearch|Milvus|Qdrant|SQLite|Prisma|Drizzle)\b/gi,
    /\b(?:pnpm|npm|yarn|pip|cargo|go\s+mod)\b/gi,
  ],
  // 语言
  languages: [
    /\b(?:TypeScript|JavaScript|Python|Go(?:lang)?|Rust|Java|C\+\+|C#|Swift|Kotlin|Ruby|PHP|Dart|Elixir|Zig)\b/gi,
  ],
};

// === 编排触发词 (标记为 complex) ===
const ORCHESTRATOR_TRIGGERS = /(?:从零开发|全面优化|端到端实现|帮我搭建|整个链路|全生命周期|多步骤|全栈项目|完整项目|多技能协作)/i;

// === 预编译联合正则 (模块加载时一次性构建，用于快速预筛选) ===
// 将 12 条意图 + 3 条修饰符的核心关键词合并为单一正则
// 无匹配时直接短路为 general/simple，避免逐条遍历
// continue/select/confirm 用 ^ 锚定只匹配开头，不需要参与联合预筛选
const _SKIP_PRESCREEN = new Set(['general', 'continue', 'select', 'confirm']);
const _intentKeywords = INTENT_RULES
  .filter(r => !_SKIP_PRESCREEN.has(r.label))
  .flatMap(r => r.patterns.map(p => p.source.replace(/^\(\?:/, '').replace(/\)$/, '').replace(/^\^/, '')));
const _modifierKeywords = MODIFIER_RULES
  .flatMap(r => r.patterns.map(p => p.source.replace(/^\(\?:/, '').replace(/\)$/, '')));
const FAST_INTENT_CHECK = new RegExp(`(?:${_intentKeywords.join('|')})`, 'i');
const FAST_MODIFIER_CHECK = new RegExp(`(?:${_modifierKeywords.join('|')})`, 'i');

/**
 * 提取实体 (框架/工具/语言名)
 * @param {string} text - 用户输入
 * @returns {string[]} 去重后的实体列表
 */
function extractEntities(text) {
  const entities = new Set();

  for (const category of Object.values(ENTITY_PATTERNS)) {
    for (const pattern of category) {
      const matches = text.match(pattern) || [];
      for (const m of matches) {
        entities.add(m.trim());
      }
    }
  }

  return Array.from(entities);
}

/**
 * 评估复杂度
 * @param {string[]} intents - 意图标签列表
 * @param {string[]} modifiers - 修饰符列表
 * @param {string[]} entities - 实体列表
 * @returns {'simple'|'medium'|'complex'}
 */
// v5.9: 相邻意图对 — 这些 2-意图组合不应升级为 complex，用 medium 处理即可
const ADJACENT_INTENT_PAIRS = new Set([
  'data:test', 'debug:performance', 'deploy:test',
  'create:deploy', 'review:test', 'data:deploy',
  'debug:data', 'debug:security', 'performance:test',
  'architecture:data', 'create:test', 'review:security',
  // v5.9: explain 与其他意图组合天然相邻 (如"解释一下这个 bug")
  'debug:explain', 'explain:performance', 'architecture:explain',
  'deploy:explain', 'explain:security', 'create:explain',
]);

function scoreComplexity(intents, modifiers, entities) {
  // complex: 有 complex 修饰符 或 匹配编排触发词
  if (modifiers.includes('complex')) return 'complex';

  // V-01: confirm/continue 后有实质内容 → 强制 medium
  if (modifiers.includes('_force_medium')) return 'medium';

  // v5.9: simple 修饰符优先于多意图判定 (如"简单说一下性能问题")
  if (modifiers.includes('simple')) return 'simple';

  // v5.9: 2 意图时检查是否为相邻意图对 (medium 而非 complex)
  if (intents.length === 2 && !intents.includes('general')) {
    const pair = intents.slice().sort().join(':');
    if (!ADJACENT_INTENT_PAIRS.has(pair)) return 'complex';
    // 相邻意图对 → 继续往下判定为 medium
  }
  // 3+ 意图 → complex
  if (intents.length >= 3 && !intents.includes('general')) return 'complex';

  // simple: 仅 explain/general/continue/select/confirm 且无框架实体
  const simpleIntents = new Set(['explain', 'general', 'continue', 'select', 'confirm']);
  const allSimple = intents.every(i => simpleIntents.has(i));
  if (allSimple && entities.length === 0) {
    return 'simple';
  }

  // medium: 其余
  return 'medium';
}

/**
 * 意图分类主函数
 * @param {string} text - 用户输入文本
 * @returns {{ intents: string[], modifiers: string[], entities: string[], complexity: 'simple'|'medium'|'complex' }}
 */
function classifyIntent(text) {
  if (!text || typeof text !== 'string') {
    return { intents: ['general'], modifiers: [], entities: [], complexity: 'simple' };
  }

  // 截断超长输入，防止正则性能退化 (2000 字符覆盖 99.9% 正常 prompt)
  const input = text.slice(0, 2000);

  // 快速预筛选: 联合正则一次判定是否有任何意图/修饰符匹配
  const hasIntent = FAST_INTENT_CHECK.test(input);
  const hasModifier = FAST_MODIFIER_CHECK.test(input);

  // 匹配意图 (仅在预筛选命中时逐条匹配)
  const intents = [];
  if (hasIntent) {
    for (const rule of INTENT_RULES) {
      if (_SKIP_PRESCREEN.has(rule.label)) continue; // 跳过锚定规则，下面单独检查
      for (const pattern of rule.patterns) {
        if (pattern.test(input)) {
          intents.push(rule.label);
          break;
        }
      }
    }
  }

  // 单独检查 ^ 锚定意图 (continue/select/confirm)，不依赖预筛选
  for (const rule of INTENT_RULES) {
    if (!_SKIP_PRESCREEN.has(rule.label) || rule.label === 'general') continue;
    for (const pattern of rule.patterns) {
      if (pattern.test(input)) {
        intents.push(rule.label);
        break;
      }
    }
  }

  // 无匹配时回退 general
  if (intents.length === 0) {
    for (const pattern of INTENT_RULES[INTENT_RULES.length - 1].patterns) {
      if (pattern.test(input)) { intents.push('general'); break; }
    }
    if (intents.length === 0) intents.push('general');
  }

  // 匹配修饰符 (仅在预筛选命中时逐条匹配)
  const modifiers = [];
  if (hasModifier) {
    for (const rule of MODIFIER_RULES) {
      for (const pattern of rule.patterns) {
        if (pattern.test(input)) {
          modifiers.push(rule.label);
          break;
        }
      }
    }
  }

  // 编排触发词检测
  if (ORCHESTRATOR_TRIGGERS.test(input) && !modifiers.includes('complex')) {
    modifiers.push('complex');
  }

  // 实体提取
  const entities = extractEntities(input);

  // V-01 修复: confirm/continue/select 前缀后若有实质性后续内容，移除该标签走全分类
  // 防止 "好的，帮我写支付接口" 被 confirm 吞没
  const _PREFIX_INTENTS = ['confirm', 'continue', 'select'];
  const _TRANSITION_WORDS = /[，,。.、！!？?]\s*|但是|不过|but|however|换成|改为|另外|还有/i;
  for (const pi of _PREFIX_INTENTS) {
    if (intents.includes(pi) && intents.length === 1) {
      // 提取前缀匹配后的剩余文本
      const rule = INTENT_RULES.find(r => r.label === pi);
      if (rule) {
        const match = rule.patterns[0].exec(input);
        if (match) {
          const remaining = input.slice(match[0].length).replace(/^[\s，,。.、]+/, '');
          // 剩余文本 > 8 字符或含转折词 → 移除前缀标签，重新分类剩余文本
          if (remaining.length > 8 || _TRANSITION_WORDS.test(remaining)) {
            intents.length = 0;
            // 重新检测剩余文本中的实质性意图
            for (const r of INTENT_RULES) {
              if (_SKIP_PRESCREEN.has(r.label)) continue;
              for (const p of r.patterns) {
                if (p.test(remaining)) { intents.push(r.label); break; }
              }
            }
            // 未命中任何专业意图但剩余文本有实质内容 → 标记 general 并强制 medium
            // 原理: "好的，帮我写支付接口" 中 "帮我写支付接口" 是新任务不应继承
            if (intents.length === 0) {
              intents.push('general');
              modifiers.push('_force_medium');
            }
          }
        }
      }
    }
  }

  // 复杂度评分
  const complexity = scoreComplexity(intents, modifiers, entities);

  return { intents, modifiers, entities, complexity };
}

// 模块导出
if (typeof module !== 'undefined') {
  module.exports = {
    classifyIntent,
    extractEntities,
    scoreComplexity,
    // 导出规则供测试
    INTENT_RULES,
    MODIFIER_RULES,
    ENTITY_PATTERNS,
    FAST_INTENT_CHECK,
    FAST_MODIFIER_CHECK,
    ADJACENT_INTENT_PAIRS,
  };
}

// CLI 入口
if (require.main === module) {
  const query = process.argv.slice(2).join(' ');
  if (!query) {
    console.log('Usage: node intent-classifier.js "<query>"');
    process.exit(0);
  }
  const result = classifyIntent(query);
  console.log(JSON.stringify(result, null, 2));
}
