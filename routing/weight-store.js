#!/usr/bin/env node
/**
 * WeightStore — 并发安全的权重文件读写 (Phase 0)
 *
 * 解决 route-feedback.js / route-ab-test.js 并发写入 route-weights.json 无锁问题。
 *
 * 写入流程: acquireLock → snapshot → write .staging → validate JSON → rename → releaseLock
 * 读取流程: 直接 readFileSync（无锁，安全）
 *
 * 锁机制: O_EXCL lockfile（Windows NTFS 兼容，无需 flock）
 * - 锁文件: debug/route-weights.lock
 * - 超时: 30 秒自动清除过期锁
 * - 重试: 50ms 间隔，最多 100 次（5 秒）
 *
 * Staging: 写入 .staging → JSON.parse 验证 → fs.renameSync（NTFS 同卷原子）
 */

const fs = require('fs');
const path = require('path');

// 路径解析
let weightsPath, lockPath, stagingPath, historyDir;
try {
  const { PATHS } = require('./paths.config.js');
  weightsPath = PATHS.routeWeightsJson;
  lockPath = PATHS.routeWeightsLock;
  stagingPath = PATHS.routeWeightsStaging;
  historyDir = PATHS.weightsHistoryDir;
} catch {
  const root = path.resolve(__dirname, '..');
  const debugDir = path.join(root, 'debug');
  weightsPath = path.join(debugDir, 'route-weights.json');
  lockPath = path.join(debugDir, 'route-weights.lock');
  stagingPath = path.join(debugDir, 'route-weights.json.staging');
  historyDir = path.join(debugDir, 'weights-history');
}

const LOCK_EXPIRE_MS = 30 * 1000;  // 30 秒过期
const RETRY_INTERVAL = 50;          // 50ms 重试间隔
const MAX_RETRIES = 100;            // 最多 100 次 (5 秒)

// ─── 锁机制 ──────────────────────────────────────────

function ensureDir(dirPath) {
  try {
    if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
  } catch {}
}

/**
 * 尝试获取锁（非阻塞）
 * @returns {boolean} 是否成功获取
 */
function tryAcquireLock() {
  ensureDir(path.dirname(lockPath));

  // 检查过期锁
  try {
    if (fs.existsSync(lockPath)) {
      const stat = fs.statSync(lockPath);
      const age = Date.now() - stat.mtimeMs;
      if (age > LOCK_EXPIRE_MS) {
        // 过期锁 → 强制清除
        try { fs.unlinkSync(lockPath); } catch {}
      }
    }
  } catch {}

  // O_EXCL 创建锁文件（原子操作）
  try {
    const fd = fs.openSync(lockPath, fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL);
    const lockData = JSON.stringify({ pid: process.pid, ts: new Date().toISOString() });
    fs.writeSync(fd, lockData);
    fs.closeSync(fd);
    return true;
  } catch {
    return false;
  }
}

/**
 * 获取锁（阻塞，带重试）
 * @returns {Promise<void>}
 */
async function acquireLock() {
  for (let i = 0; i < MAX_RETRIES; i++) {
    if (tryAcquireLock()) return;
    await new Promise(resolve => setTimeout(resolve, RETRY_INTERVAL));
  }
  throw new Error('WeightStore: failed to acquire lock after 5 seconds');
}

/**
 * 释放锁
 */
function releaseLock() {
  try {
    if (fs.existsSync(lockPath)) fs.unlinkSync(lockPath);
  } catch {}
}

// ─── 核心操作 ─────────────────────────────────────────

/**
 * 读取权重（无锁，安全）
 * @returns {Object|null}
 */
function readWeights() {
  try {
    const raw = fs.readFileSync(weightsPath, 'utf8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

/**
 * 安全写入权重（lock + stage + validate + rename）
 * @param {Object} data - 权重数据
 * @returns {Promise<void>}
 */
async function writeWeights(data) {
  await acquireLock();
  try {
    ensureDir(path.dirname(stagingPath));

    // 序列化
    const json = JSON.stringify(data, null, 2) + '\n';

    // 写入 staging
    fs.writeFileSync(stagingPath, json, 'utf8');

    // 验证 staging 文件可被正确解析
    const verify = fs.readFileSync(stagingPath, 'utf8');
    JSON.parse(verify);

    // 原子重命名（NTFS 同卷原子）
    fs.renameSync(stagingPath, weightsPath);
  } finally {
    releaseLock();
  }
}

/**
 * 创建快照
 * @returns {Promise<string|null>} 快照文件路径
 */
async function snapshot() {
  const data = readWeights();
  if (!data) return null;

  ensureDir(historyDir);
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const snapshotPath = path.join(historyDir, `weights-${ts}.json`);
  fs.writeFileSync(snapshotPath, JSON.stringify(data, null, 2) + '\n');
  // V13 修复: 限制快照数量，保留最近 20 个
  try {
    const files = fs.readdirSync(historyDir).filter(f => f.startsWith('weights-') && f.endsWith('.json')).sort();
    const MAX_SNAPSHOTS = 20;
    if (files.length > MAX_SNAPSHOTS) {
      for (const old of files.slice(0, files.length - MAX_SNAPSHOTS)) {
        fs.unlinkSync(path.join(historyDir, old));
      }
    }
  } catch {}
  return snapshotPath;
}

/**
 * 从快照回滚
 * @param {string} snapshotPath - 快照文件路径
 * @returns {Promise<void>}
 */
async function rollbackToSnapshot(snapshotPath) {
  const raw = fs.readFileSync(snapshotPath, 'utf8');
  const data = JSON.parse(raw); // 验证
  await writeWeights(data);
}

/**
 * 列出所有快照
 * @returns {string[]} 快照文件路径列表
 */
function listSnapshots() {
  ensureDir(historyDir);
  try {
    return fs.readdirSync(historyDir)
      .filter(f => f.startsWith('weights-') && f.endsWith('.json'))
      .sort()
      .map(f => path.join(historyDir, f));
  } catch {
    return [];
  }
}

// ─── 通用安全写入 ─────────────────────────────────────

/**
 * 通用安全写入 JSON 文件（lock + stage + validate + rename）
 * 与 writeWeights 相同的安全写入流程，但可指定任意文件路径。
 * @param {string} filePath - 目标 JSON 文件路径
 * @param {Object} data - 要写入的数据
 * @returns {Promise<void>}
 */
async function safeWriteJson(filePath, data) {
  await acquireLock();
  try {
    ensureDir(path.dirname(filePath));
    const stg = filePath + '.staging';
    const json = JSON.stringify(data, null, 2) + '\n';
    fs.writeFileSync(stg, json, 'utf8');
    // 验证 staging 文件可被正确解析
    const verify = fs.readFileSync(stg, 'utf8');
    JSON.parse(verify);
    // 原子重命名（NTFS 同卷原子）
    fs.renameSync(stg, filePath);
  } finally {
    releaseLock();
  }
}

// ─── 导出 ─────────────────────────────────────────────
module.exports = {
  readWeights,
  writeWeights,
  safeWriteJson,
  snapshot,
  rollbackToSnapshot,
  listSnapshots,
};

// CLI: 直接运行时打印状态
if (require.main === module) {
  console.log('=== WeightStore ===');
  console.log(`Weights: ${weightsPath}`);
  console.log(`Lock: ${lockPath}`);
  console.log(`Staging: ${stagingPath}`);
  console.log(`History: ${historyDir}`);
  console.log('');

  const data = readWeights();
  if (data) {
    console.log(`Feedback count: ${data.feedbackCount || 0}`);
    console.log(`Correction count: ${data.correctionCount || 0}`);
    console.log(`Delta skills: ${Object.keys(data.deltas || {}).length}`);
  } else {
    console.log('No weights file found');
  }

  const snapshots = listSnapshots();
  console.log(`Snapshots: ${snapshots.length}`);
}
