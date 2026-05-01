#!/usr/bin/env node
/**
 * Feature Flags 加载器 (Phase 0)
 *
 * 提供统一的 feature flag 读取接口，所有 hook/script 统一调用。
 *
 * 特性:
 *   - 5 秒进程内缓存
 *   - 文件缺失/损坏 → 返回空 features（所有功能视为关闭）
 *   - Mode 语义: off=完全关闭 | warn=仅记录不阻断 | enforce=完全生效
 *   - T3 (2026-04-17): warn 模式到达 promoteToEnforceAfter 日期后自动升 enforce
 */

const fs = require('fs');
const path = require('path');

// 路径解析
let flagsPath;
try {
  const { PATHS } = require('./paths.config.js');
  flagsPath = PATHS.featureFlagsJson;
} catch {
  const root = path.resolve(__dirname, '..');
  flagsPath = path.join(root, 'feature-flags.json');
}

// ─── 缓存 ────────────────────────────────────────────
const CACHE_TTL = 5000; // 5 秒
let _cache = null;
let _cacheTs = 0;

/**
 * 加载 feature-flags.json（带缓存）
 * @returns {Object} features 对象，失败时返回空对象
 */
function loadFlags() {
  const now = Date.now();
  if (_cache && (now - _cacheTs) < CACHE_TTL) {
    return _cache;
  }

  try {
    const raw = fs.readFileSync(flagsPath, 'utf8');
    const parsed = JSON.parse(raw);
    _cache = parsed.features || {};
    _cacheTs = now;
    return _cache;
  } catch {
    // H8: 文件缺失/损坏 → 保持旧缓存（如果存在），而非清空
    // 避免安全 flag 被暂时性 I/O 错误关闭
    if (!_cache) _cache = {};
    // 不更新 _cacheTs，下次调用会重试加载
    return _cache;
  }
}

/**
 * 检查功能是否启用
 * @param {string} name - feature flag 名称
 * @returns {boolean}
 */
function isEnabled(name) {
  const flags = loadFlags();
  const flag = flags[name];
  if (!flag) return false;
  return flag.enabled === true;
}

/**
 * 获取功能模式
 * @param {string} name - feature flag 名称
 * @returns {'off'|'warn'|'enforce'}
 *
 * T3 自动提升规则: mode=warn 且当前日期 >= promoteToEnforceAfter → 返回 'enforce'
 * 字段缺失/格式错误时向后兼容返回原 mode.
 */
function getMode(name) {
  const flags = loadFlags();
  const flag = flags[name];
  if (!flag) return 'off';
  let mode = flag.mode || 'off';

  // T3: 到期自动提升 warn → enforce (2026-04-17)
  if (mode === 'warn' && flag.promoteToEnforceAfter) {
    const promoteDate = new Date(flag.promoteToEnforceAfter);
    if (!isNaN(promoteDate.getTime()) && Date.now() >= promoteDate.getTime()) {
      mode = 'enforce';
    }
  }

  return mode;
}

/**
 * 获取完整 flag 对象
 * @param {string} name - feature flag 名称
 * @returns {Object|null}
 */
function getFlag(name) {
  const flags = loadFlags();
  return flags[name] || null;
}

/**
 * 列出所有 flags
 * @returns {Object} { name: { enabled, mode, phase }, ... }
 */
function listFlags() {
  return loadFlags();
}

/**
 * 清除缓存（测试用）
 */
function clearCache() {
  _cache = null;
  _cacheTs = 0;
}

// ─── 导出 ─────────────────────────────────────────────
module.exports = { isEnabled, getMode, getFlag, listFlags, clearCache };

// CLI: 直接运行时打印所有 flags (附效度模式提示)
if (require.main === module) {
  const flags = listFlags();
  console.log('=== Bookworm Feature Flags ===');
  console.log(`Path: ${flagsPath}`);
  console.log(`Today: ${new Date().toISOString().slice(0, 10)}`);
  console.log(`Flags: ${Object.keys(flags).length}`);
  console.log('');
  for (const [name, flag] of Object.entries(flags)) {
    const status = flag.enabled ? '✓ ON' : '✗ OFF';
    const effective = getMode(name);
    const hint = flag.mode !== effective ? ` [T3 auto→${effective}]` : '';
    console.log(`  ${status}  ${name}  (mode: ${flag.mode}${hint}, phase: ${flag.phase})`);
  }
}
