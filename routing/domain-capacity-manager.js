#!/usr/bin/env node
/**
 * 域容量管理器 (v6.0 Phase 3)
 *
 * 当域内技能超过容量上限时，提供拆域建议。
 * 为未来技能数量增长到 100+ 时的组织结构提前做好规划。
 *
 * 设计约束:
 *   - 每域建议上限 DOMAIN_CAPACITY = 12
 *   - fail-open: 所有分析失败不影响主路由流程
 *   - 只读分析，不修改任何配置文件
 *
 * 用法:
 *   node domain-capacity-manager.js           # 打印分析报告
 *   node domain-capacity-manager.js --json    # JSON 输出
 *   node domain-capacity-manager.js --suggest # 仅显示拆域建议
 */

'use strict';

const fs = require('fs');
const path = require('path');

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const ROOT = detectClaudeRoot();
const INDEX_FILE = path.join(ROOT, 'skills-index.json');

// 每域建议上限
const DOMAIN_CAPACITY = 12;

// =====================================================
// 内部: 辅助函数
// =====================================================

/**
 * 从技能名称和关键词中提取聚类标签
 * 用于拆域建议时的子域聚类
 *
 * @param {string} skillName - 技能名称
 * @param {Array} keywords - 技能关键词列表
 * @returns {string[]} 标签列表
 */
function extractClusterTags(skillName, keywords) {
  const tags = [];
  const nameLower = skillName.toLowerCase();

  // 基于名称推断子域标签
  const tagPatterns = [
    { pattern: /frontend|react|vue|angular|next|css|tailwind|svelte/, tag: 'web-frontend' },
    { pattern: /backend|api|rest|graphql|node|fastapi|django|gin|express/, tag: 'backend-services' },
    { pattern: /mobile|flutter|swift|kotlin|react.native|expo|android|ios/, tag: 'mobile' },
    { pattern: /database|sql|redis|mongo|postgres|mysql|orm|query/, tag: 'data-storage' },
    { pattern: /devops|docker|k8s|kubernetes|ci.cd|pipeline|deploy/, tag: 'infrastructure' },
    { pattern: /security|auth|jwt|oauth|encrypt|pentest|owasp/, tag: 'security' },
    { pattern: /ai|ml|llm|rag|torch|tensorflow|embedding|model/, tag: 'ai-ml' },
    { pattern: /data|analyst|pandas|spark|etl|dbt|warehouse/, tag: 'data-engineering' },
    { pattern: /test|spec|jest|vitest|pytest|coverage|e2e/, tag: 'quality-testing' },
    { pattern: /architect|design|pattern|ddd|microservice|system/, tag: 'architecture' },
    { pattern: /automation|workflow|browser|playwright|selenium|scrape/, tag: 'automation' },
    { pattern: /cloud|aws|gcp|azure|vercel|edge|cdn|terraform/, tag: 'cloud' },
    { pattern: /typescript|python|golang|rust|java|swift/, tag: 'language-specific' },
    { pattern: /git|version|branch|merge|rebase|commit/, tag: 'vcs' },
    { pattern: /monitor|sre|slo|sli|alert|grafana|prometheus/, tag: 'observability' },
    { pattern: /product|prd|roadmap|sprint|agile|scrum/, tag: 'product-management' },
    { pattern: /design|ux|ui|figma|wcag|accessibility/, tag: 'design-ux' },
    { pattern: /content|write|doc|readme|seo|copy/, tag: 'content' },
    { pattern: /business|finance|sales|legal|marketing/, tag: 'business' },
    { pattern: /notification|push|sms|email|webhook/, tag: 'messaging' },
  ];

  for (const { pattern, tag } of tagPatterns) {
    if (pattern.test(nameLower)) {
      tags.push(tag);
    }
  }

  // 从关键词中补充标签（取前 10 个关键词）
  const kwText = (keywords || []).slice(0, 10).map(k => k.keyword || '').join(' ').toLowerCase();
  for (const { pattern, tag } of tagPatterns) {
    if (!tags.includes(tag) && pattern.test(kwText)) {
      tags.push(tag);
    }
  }

  // 没有匹配则打 general 标签
  if (tags.length === 0) tags.push('general');

  return tags;
}

/**
 * 基于技能的聚类标签，对超容量域内的技能进行简单分组
 *
 * @param {string[]} skillNames - 技能名称列表
 * @param {Object} skillsMap - { skillName → skill对象 } 映射
 * @returns {Object} { subDomain → skillNames[] }
 */
function clusterSkills(skillNames, skillsMap) {
  const clusters = {}; // subDomain → skillNames[]
  const assigned = new Set();

  for (const name of skillNames) {
    const skill = skillsMap[name];
    if (!skill) continue;
    const tags = extractClusterTags(name, skill.keywords || []);
    // 取第一个标签作为主要子域
    const primaryTag = tags[0] || 'general';
    if (!clusters[primaryTag]) clusters[primaryTag] = [];
    clusters[primaryTag].push(name);
    assigned.add(name);
  }

  // 未分配的技能归入 general
  for (const name of skillNames) {
    if (!assigned.has(name)) {
      if (!clusters['general']) clusters['general'] = [];
      clusters['general'].push(name);
    }
  }

  return clusters;
}

// =====================================================
// 公共 API
// =====================================================

/**
 * 分析各域的技能容量
 *
 * @param {Object} [skillsIndex] - skills-index.json 内容（可选，不传则自动加载）
 * @param {Object} [domainClassifier] - domain-classifier 模块（可选，不传则自动加载）
 * @returns {Object} 分析结果
 *   {
 *     domains: {
 *       domainName: {
 *         skillCount: number,
 *         capacity: number,
 *         overCapacity: boolean,
 *         skills: string[],
 *         utilization: number  // 0~1+
 *       }
 *     },
 *     overCapacityDomains: string[],
 *     totalSkills: number,
 *     totalDomains: number,
 *     suggestions: Object[]   // 拆域建议列表
 *   }
 */
function analyze(skillsIndex, domainClassifier) {
  try {
    // 加载 skills-index
    let index = skillsIndex;
    if (!index) {
      if (!fs.existsSync(INDEX_FILE)) {
        return { error: 'skills-index.json 不存在', domains: {}, totalSkills: 0 };
      }
      index = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf8'));
    }

    // 加载 domain-classifier
    let classifier = domainClassifier;
    if (!classifier) {
      try {
        classifier = require('./domain-classifier.js');
      } catch {
        return { error: 'domain-classifier.js 不可用', domains: {}, totalSkills: 0 };
      }
    }

    const skills = index.skills || [];
    const totalSkills = skills.length;

    // 构建 skillName → skill 对象 的快速查找
    const skillsMap = {};
    for (const s of skills) {
      skillsMap[s.name] = s;
    }

    // 使用 DOMAIN_SKILLS 映射统计各域技能数
    const DOMAIN_SKILLS = classifier.DOMAIN_SKILLS || {};
    const domains = {};

    for (const [domain, domainSkills] of Object.entries(DOMAIN_SKILLS)) {
      // 过滤只统计 index 中实际存在的技能
      const existingSkills = domainSkills.filter(name => skillsMap[name]);
      const skillCount = existingSkills.length;

      domains[domain] = {
        skillCount,
        capacity: DOMAIN_CAPACITY,
        overCapacity: skillCount > DOMAIN_CAPACITY,
        skills: existingSkills,
        utilization: Math.round(skillCount / DOMAIN_CAPACITY * 100) / 100,
      };
    }

    // 检测未归类的技能（不在任何域 DOMAIN_SKILLS 中）
    const allMappedSkills = new Set(
      Object.values(DOMAIN_SKILLS).flat()
    );
    const unmapped = skills.filter(s => !allMappedSkills.has(s.name)).map(s => s.name);
    if (unmapped.length > 0) {
      domains['_unmapped'] = {
        skillCount: unmapped.length,
        capacity: DOMAIN_CAPACITY,
        overCapacity: unmapped.length > DOMAIN_CAPACITY,
        skills: unmapped,
        utilization: Math.round(unmapped.length / DOMAIN_CAPACITY * 100) / 100,
      };
    }

    // 标记超容量域
    const overCapacityDomains = Object.keys(domains)
      .filter(d => domains[d].overCapacity)
      .sort((a, b) => domains[b].skillCount - domains[a].skillCount);

    // 生成拆域建议
    const suggestions = [];
    for (const domain of overCapacityDomains) {
      const suggestion = suggestSplit(domain, domains[domain].skills, skillsMap);
      if (suggestion) suggestions.push(suggestion);
    }

    return {
      domains,
      overCapacityDomains,
      totalSkills,
      totalDomains: Object.keys(domains).length,
      suggestions,
      capacity: DOMAIN_CAPACITY,
    };
  } catch (err) {
    // fail-open
    return {
      error: err.message,
      domains: {},
      overCapacityDomains: [],
      totalSkills: 0,
      totalDomains: 0,
      suggestions: [],
    };
  }
}

/**
 * 为超容量域生成拆域建议
 *
 * @param {string} domain - 域名称
 * @param {string[]} skills - 域内技能名称列表
 * @param {Object} [skillsMap] - { skillName → skill对象 } 映射（可选）
 * @returns {Object|null} 拆域建议
 *   {
 *     domain: string,
 *     currentCount: number,
 *     proposedSubDomains: {
 *       name: string,
 *       skills: string[],
 *       rationale: string
 *     }[]
 *   }
 */
function suggestSplit(domain, skills, skillsMap) {
  try {
    if (!domain || !Array.isArray(skills) || skills.length <= DOMAIN_CAPACITY) {
      return null;
    }

    // 如果没有提供 skillsMap，尝试从文件加载
    let sMap = skillsMap;
    if (!sMap) {
      try {
        const index = JSON.parse(fs.readFileSync(INDEX_FILE, 'utf8'));
        sMap = {};
        for (const s of (index.skills || [])) sMap[s.name] = s;
      } catch {
        sMap = {};
      }
    }

    // 聚类
    const clusters = clusterSkills(skills, sMap);

    // 合并过小的子域（< 2 个技能）到 general
    const merged = {};
    let generalSkills = clusters['general'] || [];

    for (const [subDomain, subSkills] of Object.entries(clusters)) {
      if (subDomain === 'general') continue;
      if (subSkills.length < 2) {
        generalSkills = generalSkills.concat(subSkills);
      } else {
        merged[subDomain] = subSkills;
      }
    }

    if (generalSkills.length > 0) {
      merged['general'] = generalSkills;
    }

    // 生成建议
    const proposedSubDomains = [];
    for (const [subName, subSkills] of Object.entries(merged)) {
      if (subSkills.length === 0) continue;

      // 生成子域命名建议
      const fullName = `${domain}-${subName}`;
      const rationale = subSkills.length > DOMAIN_CAPACITY
        ? `${subSkills.length} 个技能，仍超容量，建议进一步拆分`
        : `${subSkills.length} 个技能，在容量范围内`;

      proposedSubDomains.push({
        name: fullName,
        skills: subSkills,
        skillCount: subSkills.length,
        rationale,
      });
    }

    // 按技能数量降序排列
    proposedSubDomains.sort((a, b) => b.skillCount - a.skillCount);

    return {
      domain,
      currentCount: skills.length,
      capacityLimit: DOMAIN_CAPACITY,
      overBy: skills.length - DOMAIN_CAPACITY,
      proposedSubDomains,
      totalProposedDomains: proposedSubDomains.length,
    };
  } catch {
    return null;
  }
}

/**
 * 打印域容量分析报告（人类可读格式）
 *
 * @param {Object} [skillsIndex] - 可选，直接传入 index
 * @param {Object} [domainClassifier] - 可选，直接传入 classifier
 */
function report(skillsIndex, domainClassifier) {
  const result = analyze(skillsIndex, domainClassifier);

  if (result.error) {
    console.error(`[domain-capacity] 错误: ${result.error}`);
    return result;
  }

  console.log(`\n=== 域容量分析报告 ===`);
  console.log(`总技能数: ${result.totalSkills} | 域数: ${result.totalDomains} | 容量上限: ${result.capacity}/域\n`);

  // 按技能数降序排列域
  const sortedDomains = Object.entries(result.domains)
    .sort(([, a], [, b]) => b.skillCount - a.skillCount);

  for (const [domain, info] of sortedDomains) {
    const bar = Math.round(info.utilization * 10);
    const barStr = '█'.repeat(Math.min(bar, 12)) + '░'.repeat(Math.max(0, 12 - bar));
    const overMark = info.overCapacity ? ' ← 超容量!' : '';
    const pct = Math.round(info.utilization * 100);
    console.log(`  ${domain.padEnd(15)} ${barStr} ${String(info.skillCount).padStart(3)}/${result.capacity} (${pct}%)${overMark}`);
  }

  // 拆域建议
  if (result.suggestions.length > 0) {
    console.log(`\n--- 拆域建议 ---`);
    for (const sug of result.suggestions) {
      console.log(`\n[${sug.domain}] ${sug.currentCount} 个技能，超出 ${sug.overBy} 个`);
      console.log(`  建议拆分为 ${sug.totalProposedDomains} 个子域:`);
      for (const sub of sug.proposedSubDomains) {
        console.log(`    → ${sub.name} (${sub.skillCount} 技能): ${sub.skills.slice(0, 4).join(', ')}${sub.skills.length > 4 ? '...' : ''}`);
        console.log(`      ${sub.rationale}`);
      }
    }
  } else {
    console.log(`\n所有域均在容量范围内，无需拆分。`);
  }

  console.log();
  return result;
}

// =====================================================
// 模块导出
// =====================================================
if (typeof module !== 'undefined') {
  module.exports = {
    analyze,
    suggestSplit,
    report,
    DOMAIN_CAPACITY,
  };
}

// CLI 入口
if (require.main === module) {
  const args = process.argv.slice(2);
  const jsonMode = args.includes('--json');
  const suggestOnly = args.includes('--suggest');

  if (jsonMode) {
    const result = analyze();
    console.log(JSON.stringify(result, null, 2));
  } else if (suggestOnly) {
    const result = analyze();
    if (result.suggestions.length === 0) {
      console.log('所有域均在容量范围内，无拆域建议。');
    } else {
      console.log(JSON.stringify(result.suggestions, null, 2));
    }
  } else {
    report();
  }
}
