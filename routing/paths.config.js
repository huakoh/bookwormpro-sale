#!/usr/bin/env node
/**
 * 路径配置中心 - 去硬编码化
 *
 * 所有脚本/钩子统一从此模块获取路径，不再各自硬编码。
 * 支持环境变量覆盖:
 *   CLAUDE_HOME   - .claude 根目录 (最高优先级)
 *   CLAUDE_ROOT   - 同 CLAUDE_HOME (兼容别名)
 *
 * 检测顺序:
 *   1. CLAUDE_HOME / CLAUDE_ROOT 环境变量
 *   2. 从调用者 __dirname 向上推断 (包含 .claude 的路径)
 *   3. WSL 默认: /mnt/c/Users/<USER>/.claude (从 os.homedir() 动态推断) [CLEANUP_PATHS_PORTABLE_2026_04_21]
 *   4. Windows 默认: <USER_HOME>/.claude (从 os.homedir() 动态推断)
 */

const fs = require('fs');
const path = require('path');

// ─── 根目录检测 ───────────────────────────────────────
const os = require('os');
const IS_WSL = process.platform === 'linux' && fs.existsSync('/mnt/c');
// 使用 os.homedir() 动态获取用户目录，不再硬编码用户名
const DEFAULT_ROOT_WSL = path.join('/mnt/c/Users', path.basename(os.homedir()), '.bookwormpro');
const DEFAULT_ROOT_WIN = path.join(os.homedir(), '.bookwormpro');

/**
 * 检测 .claude 根目录
 * @param {string} [callerDir] - 调用者的 __dirname，用于自动推断
 * @returns {string} 根目录绝对路径
 */
function detectRoot(callerDir) {
  // P0-4: 测试隔离 — CLAUDE_TEST_ROOT 最高优先级
  if (process.env.CLAUDE_TEST_ROOT) return process.env.CLAUDE_TEST_ROOT;

  // 1. 环境变量优先
  if (process.env.CLAUDE_HOME) return process.env.CLAUDE_HOME;
  if (process.env.CLAUDE_ROOT) return process.env.CLAUDE_ROOT;

  // 2. 从调用者路径推断
  if (callerDir && callerDir.includes('.bookwormpro')) {
    return callerDir.replace(/[/\\](scripts|hooks|hooks[/\\]__tests__|agents|skills).*$/, '');
  }

  // 3. 平台默认
  return IS_WSL ? DEFAULT_ROOT_WSL : DEFAULT_ROOT_WIN;
}

// 默认使用本文件所在目录推断
const ROOT = detectRoot(__dirname);

// ─── 派生路径 ─────────────────────────────────────────
const PATHS = {
  root: ROOT,

  // 核心配置
  claudeMd: path.join(ROOT, 'CLAUDE.md'),
  settingsJson: path.join(ROOT, 'settings.json'),
  settingsLocalJson: path.join(ROOT, 'settings.local.json'),
  skillsIndexJson: path.join(ROOT, 'skills-index.json'),
  skillRegistryMd: path.join(ROOT, 'SKILL-REGISTRY.md'),

  // 目录
  skillsDir: path.join(ROOT, 'skills'),
  agentsDir: path.join(ROOT, 'agents'),
  hooksDir: path.join(ROOT, 'hooks'),
  scriptsDir: path.join(ROOT, 'scripts'),
  debugDir: path.join(ROOT, 'debug'),
  backupsDir: path.join(ROOT, 'backups'),
  projectsDir: path.join(ROOT, 'projects'),
  docsDir: path.join(ROOT, 'docs'),

  // 钩子相关
  rulesDir: path.join(ROOT, 'hooks', 'rules'),
  rulesCompiledJson: path.join(ROOT, 'hooks', 'rules-compiled.json'),
  checksumsJson: path.join(ROOT, 'hooks', 'checksums.json'),

  // 调试 / 学习文件
  routeFeedbackJsonl: path.join(ROOT, 'debug', 'route-feedback.jsonl'),
  routeWeightsJson: path.join(ROOT, 'debug', 'route-weights.json'),
  abExperimentsJsonl: path.join(ROOT, 'debug', 'ab-experiments.jsonl'),
  healthWeightHistoryJson: path.join(ROOT, 'debug', 'health-weight-history.json'),

  // Phase 0: 基础设施路径
  routeWeightsLock:    path.join(ROOT, 'debug', 'route-weights.lock'),
  routeWeightsStaging: path.join(ROOT, 'debug', 'route-weights.json.staging'),
  weightsHistoryDir:   path.join(ROOT, 'debug', 'weights-history'),
  featureFlagsJson:    path.join(ROOT, 'feature-flags.json'),
  userOverridesJson:   path.join(ROOT, 'debug', 'user-overrides.json'),

  // Phase 3: 闭环智能路径
  detectionStatsJson:          path.join(ROOT, 'debug', 'detection-stats.json'),
  skillOutcomeCorrelationJson: path.join(ROOT, 'debug', 'skill-outcome-correlation.json'),
  sessionTraceJson:            path.join(ROOT, 'debug', 'session-trace.json'),
  remediationLogJsonl:         path.join(ROOT, 'debug', 'remediation-log.jsonl'),

  // 工具函数: 获取今日日期文件
  activityLog: (date) => path.join(ROOT, 'debug', `activity-${date || today()}.jsonl`),
  securityLog: (date) => path.join(ROOT, 'debug', `security-${date || today()}.jsonl`),
  complianceLog: (date) => path.join(ROOT, 'debug', `compliance-${date || today()}.jsonl`),
  routeLog: (date) => path.join(ROOT, 'debug', `route-${date || today()}.jsonl`),
  traceLog: (date) => path.join(ROOT, 'debug', `trace-${date || today()}.jsonl`),
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

// ─── 导出 ─────────────────────────────────────────────
if (typeof module !== 'undefined') {
  module.exports = { detectRoot, PATHS, IS_WSL, today };
}

// CLI: 直接运行时打印所有路径
if (require.main === module) {
  console.log('=== Bookworm Paths Config ===');
  console.log(`Root: ${PATHS.root}`);
  console.log(`WSL:  ${IS_WSL}`);
  console.log('');
  for (const [key, val] of Object.entries(PATHS)) {
    if (typeof val === 'function') {
      console.log(`  ${key}(): ${val()}`);
    } else {
      console.log(`  ${key}: ${val}`);
    }
  }
}
