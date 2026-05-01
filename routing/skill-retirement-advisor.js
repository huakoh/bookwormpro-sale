#!/usr/bin/env node
/**
 * Skill Retirement Advisor — 技能退役顾问 (v6.0 F2-3)
 *
 * 功能:
 *   1. 读取 debug/route-stats.json 获取每个技能的命中次数
 *   2. 扫描 debug/route-YYYY-MM-DD.jsonl 获取每个技能最后命中时间
 *   3. 标记连续 30 天零命中的技能为 retired-candidate
 *   4. 输出人类可读报告到 stdout
 *   5. --apply: 在 skills-index.json 中对 retired 技能降低关键词权重 (×0.3)
 *   6. --restore <skill-name>: 恢复指定技能的关键词权重
 *
 * CLI 用法:
 *   node scripts/skill-retirement-advisor.js                    → 输出报告
 *   node scripts/skill-retirement-advisor.js --apply            → 应用降权
 *   node scripts/skill-retirement-advisor.js --restore devops   → 恢复权重
 *   node scripts/skill-retirement-advisor.js --json             → JSON 格式报告
 *
 * 安全约束:
 *   - 不删除任何技能文件
 *   - 不修改 .claude/hooks/ 目录
 *   - 降权因子 × 0.3，原始权重保存在 _originalWeight 字段
 *   - 恢复时从 _originalWeight 还原
 */

'use strict';

const fs = require('fs');
const path = require('path');

// ─── 路径检测 ──────────────────────────────────────────
const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const CLAUDE_ROOT = detectClaudeRoot();
const DEBUG_DIR = path.join(CLAUDE_ROOT, 'debug');
const ROUTE_STATS_FILE = path.join(DEBUG_DIR, 'route-stats.json');
const SKILLS_INDEX_FILE = path.join(CLAUDE_ROOT, 'skills-index.json');

// 退役阈值: 连续 N 天零命中
const RETIREMENT_DAYS = 30;
// 降权因子: retired 技能的关键词权重乘以此值
const RETIREMENT_WEIGHT_FACTOR = 0.3;
// 保留字段名 (原始权重)
const ORIGINAL_WEIGHT_FIELD = '_originalWeight';

// ─── 数据加载 ──────────────────────────────────────────

/**
 * 从 route-stats.json 加载技能命中次数统计
 * @returns {Map<string, number>} skillName → totalHits
 */
function loadRouteStats() {
  try {
    if (!fs.existsSync(ROUTE_STATS_FILE)) return new Map();
    const data = JSON.parse(fs.readFileSync(ROUTE_STATS_FILE, 'utf8'));
    const stats = data.stats || {};
    return new Map(Object.entries(stats));
  } catch {
    return new Map();
  }
}

/**
 * 从每日路由日志中提取每个技能最后一次命中的时间
 * 扫描最近 RETIREMENT_DAYS 天的日志文件
 * @returns {Map<string, Date>} skillName → lastSeenDate
 */
function loadLastSeenDates() {
  const lastSeen = new Map();

  try {
    const now = new Date();
    // 扫描 RETIREMENT_DAYS + 5 天的日志 (多扫几天确保覆盖)
    for (let i = 0; i <= RETIREMENT_DAYS + 5; i++) {
      const d = new Date(now.getTime() - i * 86400000);
      const dateStr = d.toISOString().slice(0, 10);
      const logFile = path.join(DEBUG_DIR, `route-${dateStr}.jsonl`);

      if (!fs.existsSync(logFile)) continue;

      const lines = fs.readFileSync(logFile, 'utf8').split('\n').filter(l => l.trim());
      for (const line of lines) {
        try {
          const entry = JSON.parse(line);
          const skill = entry.topResult || entry.selectedSkill;
          if (!skill || skill === 'none') continue;

          const ts = entry.ts ? new Date(entry.ts) : d;
          // 更新: 只保留最新的命中时间
          if (!lastSeen.has(skill) || ts > lastSeen.get(skill)) {
            lastSeen.set(skill, ts);
          }

          // 也处理 candidates 数组 (次优候选也算"被考虑")
          for (const candidate of (entry.candidates || [])) {
            const cName = typeof candidate === 'string' ? candidate : candidate.name;
            if (cName && cName !== 'none') {
              if (!lastSeen.has(cName) || ts > lastSeen.get(cName)) {
                lastSeen.set(cName, ts);
              }
            }
          }
        } catch {}
      }
    }
  } catch {}

  return lastSeen;
}

/**
 * 从 skills-index.json 加载所有技能名称
 */
function loadAllSkillNames() {
  try {
    if (!fs.existsSync(SKILLS_INDEX_FILE)) return [];
    const index = JSON.parse(fs.readFileSync(SKILLS_INDEX_FILE, 'utf8'));
    return (index.skills || []).map(s => s.name);
  } catch {
    return [];
  }
}

// ─── 退役分析 ──────────────────────────────────────────

/**
 * 分析每个技能的退役状态
 * @returns {Array<SkillStatus>} 技能状态列表
 *
 * SkillStatus {
 *   name: string,
 *   totalHits: number,
 *   lastSeenDate: Date|null,
 *   daysSinceLastSeen: number|null,  // null = 从未被命中
 *   status: 'active' | 'idle' | 'retired-candidate',
 *   reason: string
 * }
 */
function analyzeRetirement() {
  const routeStats = loadRouteStats();
  const lastSeenDates = loadLastSeenDates();
  const allSkills = loadAllSkillNames();

  if (allSkills.length === 0) {
    return { error: 'skills-index.json 不存在或为空', skills: [] };
  }

  const now = new Date();
  const results = [];

  for (const skillName of allSkills) {
    const totalHits = routeStats.get(skillName) || 0;
    const lastSeenDate = lastSeenDates.get(skillName) || null;
    const daysSinceLastSeen = lastSeenDate
      ? Math.floor((now - lastSeenDate) / 86400000)
      : null;

    let status, reason;

    if (totalHits === 0 && lastSeenDate === null) {
      // 从未被命中
      status = 'retired-candidate';
      reason = '从未被路由命中 (零历史记录)';
    } else if (daysSinceLastSeen !== null && daysSinceLastSeen >= RETIREMENT_DAYS) {
      // 超过 30 天没有命中
      status = 'retired-candidate';
      reason = `连续 ${daysSinceLastSeen} 天零命中 (最后命中: ${lastSeenDate.toISOString().slice(0, 10)})`;
    } else if (daysSinceLastSeen !== null && daysSinceLastSeen >= 14) {
      // 14-29 天: 空闲观察期
      status = 'idle';
      reason = `${daysSinceLastSeen} 天未命中 (观察期，未达退役阈值 ${RETIREMENT_DAYS} 天)`;
    } else {
      status = 'active';
      reason = lastSeenDate
        ? `${daysSinceLastSeen} 天前命中，共 ${totalHits} 次`
        : `命中 ${totalHits} 次`;
    }

    results.push({
      name: skillName,
      totalHits,
      lastSeenDate,
      daysSinceLastSeen,
      status,
      reason,
    });
  }

  // 按状态+最后命中排序
  results.sort((a, b) => {
    const order = { 'retired-candidate': 0, 'idle': 1, 'active': 2 };
    const oa = order[a.status] ?? 3;
    const ob = order[b.status] ?? 3;
    if (oa !== ob) return oa - ob;
    // 同状态: 按最后命中时间升序 (越久没用排越前)
    const da = a.lastSeenDate ? a.lastSeenDate.getTime() : 0;
    const db = b.lastSeenDate ? b.lastSeenDate.getTime() : 0;
    return da - db;
  });

  return { skills: results };
}

// ─── 降权应用 ──────────────────────────────────────────

/**
 * 对 retired-candidate 技能在 skills-index.json 中降低关键词权重
 * 原始权重保存在 _originalWeight 字段以便恢复
 * @param {string[]} retiredSkills - 要降权的技能名称列表
 * @returns {{ modified: string[], skipped: string[], errors: string[] }}
 */
function applyRetirementPenalty(retiredSkills) {
  const modified = [], skipped = [], errors = [];

  try {
    if (!fs.existsSync(SKILLS_INDEX_FILE)) {
      return { modified, skipped, errors: ['skills-index.json 不存在'] };
    }

    const index = JSON.parse(fs.readFileSync(SKILLS_INDEX_FILE, 'utf8'));
    const skills = index.skills || [];
    let changed = false;

    for (const skill of skills) {
      if (!retiredSkills.includes(skill.name)) continue;

      // 检查是否已经降权过
      const alreadyRetired = (skill.keywords || []).some(kw => kw[ORIGINAL_WEIGHT_FIELD] !== undefined);
      if (alreadyRetired) {
        skipped.push(`${skill.name} (已降权，跳过)`);
        continue;
      }

      // 对每个关键词保存原始权重并降权
      let anyModified = false;
      for (const kw of (skill.keywords || [])) {
        const originalWeight = kw.weight;
        if (typeof originalWeight === 'number' && originalWeight > 0) {
          kw[ORIGINAL_WEIGHT_FIELD] = originalWeight;
          kw.weight = Math.round(originalWeight * RETIREMENT_WEIGHT_FACTOR * 1000) / 1000;
          anyModified = true;
        }
        // tfidfWeight 同样降权
        if (typeof kw.tfidfWeight === 'number' && kw.tfidfWeight > 0) {
          kw._originalTfidfWeight = kw.tfidfWeight;
          kw.tfidfWeight = Math.round(kw.tfidfWeight * RETIREMENT_WEIGHT_FACTOR * 1000) / 1000;
        }
      }

      if (anyModified) {
        // 标记技能为退役候选
        skill._retiredAt = new Date().toISOString();
        skill._retirementReason = `${RETIREMENT_DAYS}天零命中自动降权`;
        modified.push(skill.name);
        changed = true;
      } else {
        skipped.push(`${skill.name} (无关键词可降权)`);
      }
    }

    if (changed) {
      fs.writeFileSync(SKILLS_INDEX_FILE, JSON.stringify(index, null, 2) + '\n');
    }
  } catch (e) {
    errors.push(e.message);
  }

  return { modified, skipped, errors };
}

/**
 * 恢复指定技能的关键词权重
 * @param {string} skillName - 要恢复的技能名称
 * @returns {{ success: boolean, message: string }}
 */
function restoreSkillWeight(skillName) {
  try {
    if (!fs.existsSync(SKILLS_INDEX_FILE)) {
      return { success: false, message: 'skills-index.json 不存在' };
    }

    const index = JSON.parse(fs.readFileSync(SKILLS_INDEX_FILE, 'utf8'));
    const skill = (index.skills || []).find(s => s.name === skillName);

    if (!skill) {
      return { success: false, message: `技能 ${skillName} 不存在于索引中` };
    }

    let restoredCount = 0;
    for (const kw of (skill.keywords || [])) {
      if (kw[ORIGINAL_WEIGHT_FIELD] !== undefined) {
        kw.weight = kw[ORIGINAL_WEIGHT_FIELD];
        delete kw[ORIGINAL_WEIGHT_FIELD];
        restoredCount++;
      }
      if (kw._originalTfidfWeight !== undefined) {
        kw.tfidfWeight = kw._originalTfidfWeight;
        delete kw._originalTfidfWeight;
      }
    }

    if (restoredCount === 0) {
      return { success: false, message: `${skillName} 没有被降权的关键词，无需恢复` };
    }

    // 清除退役标记
    delete skill._retiredAt;
    delete skill._retirementReason;
    skill._restoredAt = new Date().toISOString();

    fs.writeFileSync(SKILLS_INDEX_FILE, JSON.stringify(index, null, 2) + '\n');
    return { success: true, message: `${skillName} 已恢复 ${restoredCount} 个关键词权重` };
  } catch (e) {
    return { success: false, message: e.message };
  }
}

// ─── 报告生成 ──────────────────────────────────────────

function printReport(analysis) {
  const { skills, error } = analysis;

  if (error) {
    console.error(`[ERROR] ${error}`);
    return;
  }

  const retired = skills.filter(s => s.status === 'retired-candidate');
  const idle = skills.filter(s => s.status === 'idle');
  const active = skills.filter(s => s.status === 'active');

  console.log('\n=== Skill Retirement Advisor Report ===');
  console.log(`生成时间: ${new Date().toISOString().slice(0, 19).replace('T', ' ')}`);
  console.log(`技能总数: ${skills.length} | 活跃: ${active.length} | 空闲: ${idle.length} | 退役候选: ${retired.length}`);
  console.log(`退役阈值: 连续 ${RETIREMENT_DAYS} 天零命中`);
  console.log(`降权因子: ×${RETIREMENT_WEIGHT_FACTOR}\n`);

  if (retired.length > 0) {
    console.log('--- 退役候选 (RETIRED-CANDIDATE) ---');
    for (const s of retired) {
      const hitsStr = s.totalHits > 0 ? ` [历史 ${s.totalHits} 次]` : ' [从未命中]';
      console.log(`  ✗ ${s.name.padEnd(35)} ${hitsStr}`);
      console.log(`    原因: ${s.reason}`);
    }
    console.log();
  }

  if (idle.length > 0) {
    console.log('--- 空闲观察 (IDLE, 14-29天) ---');
    for (const s of idle) {
      console.log(`  ~ ${s.name.padEnd(35)} [${s.totalHits} 次] ${s.reason}`);
    }
    console.log();
  }

  if (active.length > 0) {
    console.log('--- 活跃技能 (ACTIVE) ---');
    for (const s of active) {
      const lastStr = s.lastSeenDate ? s.lastSeenDate.toISOString().slice(0, 10) : '-';
      console.log(`  ✓ ${s.name.padEnd(35)} [${s.totalHits} 次] 最后: ${lastStr}`);
    }
    console.log();
  }

  if (retired.length > 0) {
    console.log('--- 操作建议 ---');
    console.log(`  运行以下命令对退役候选技能降权:`);
    console.log(`    node scripts/skill-retirement-advisor.js --apply\n`);
    console.log(`  恢复指定技能权重:`);
    console.log(`    node scripts/skill-retirement-advisor.js --restore <skill-name>\n`);
    console.log(`  注意: 降权不删除技能文件，仅降低路由优先级 (×${RETIREMENT_WEIGHT_FACTOR})`);
  } else {
    console.log('  所有技能均处于活跃或观察状态，无需退役操作。');
  }

  console.log('\n=======================================\n');
}

// ─── CLI 入口 ──────────────────────────────────────────
if (require.main === module) {
  const args = process.argv.slice(2);
  const jsonMode = args.includes('--json');
  const applyMode = args.includes('--apply');
  const restoreIdx = args.indexOf('--restore');
  const restoreSkill = restoreIdx >= 0 ? args[restoreIdx + 1] : null;

  if (restoreSkill) {
    // 恢复模式
    const result = restoreSkillWeight(restoreSkill);
    if (jsonMode) {
      console.log(JSON.stringify(result, null, 2));
    } else {
      console.log(result.success
        ? `[OK] ${result.message}`
        : `[ERROR] ${result.message}`);
    }
    process.exit(result.success ? 0 : 1);
  }

  // 分析退役状态
  const analysis = analyzeRetirement();

  if (applyMode) {
    // 应用降权
    const retiredNames = (analysis.skills || [])
      .filter(s => s.status === 'retired-candidate')
      .map(s => s.name);

    if (retiredNames.length === 0) {
      console.log('[OK] 无退役候选技能，无需降权');
      process.exit(0);
    }

    const applyResult = applyRetirementPenalty(retiredNames);

    if (jsonMode) {
      console.log(JSON.stringify({ analysis, applyResult }, null, 2));
    } else {
      printReport(analysis);
      console.log('--- 降权执行结果 ---');
      if (applyResult.modified.length > 0) {
        console.log(`  已降权: ${applyResult.modified.join(', ')}`);
      }
      if (applyResult.skipped.length > 0) {
        console.log(`  已跳过: ${applyResult.skipped.join(', ')}`);
      }
      if (applyResult.errors.length > 0) {
        console.error(`  错误: ${applyResult.errors.join(', ')}`);
      }
    }
    process.exit(applyResult.errors.length > 0 ? 1 : 0);
  }

  // 仅报告模式
  if (jsonMode) {
    console.log(JSON.stringify(analysis, null, 2));
  } else {
    printReport(analysis);
  }

  process.exit(0);
}

// ─── 模块导出 ──────────────────────────────────────────
if (typeof module !== 'undefined') {
  module.exports = {
    analyzeRetirement,
    applyRetirementPenalty,
    restoreSkillWeight,
    loadRouteStats,
    loadLastSeenDates,
    loadAllSkillNames,
    RETIREMENT_DAYS,
    RETIREMENT_WEIGHT_FACTOR,
  };
}
