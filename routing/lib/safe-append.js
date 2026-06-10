/**
 * 共享安全追加写入模块 (E-01/E-02 修复版)
 *
 * 修复:
 * - 锁获取失败时重试 3 次 (10ms 间隔)，而非静默降级
 * - 孤儿锁检测: 锁文件超过 10 秒自动清理
 * - fd 级操作减少 Windows NTFS 竞争窗口
 */

const fs = require('fs');
const path = require('path');

const LOCK_STALE_MS = 10000; // 10 秒锁超时
const LOCK_RETRIES = 3;
const LOCK_RETRY_MS = 10;

/**
 * 尝试获取 O_EXCL 锁，带孤儿锁检测和重试
 * @returns {number|null} 锁文件 fd 或 null
 */
function acquireAppendLock(lockFile) {
  for (let attempt = 0; attempt < LOCK_RETRIES; attempt++) {
    try {
      return fs.openSync(lockFile, 'wx');
    } catch (e) {
      // 锁已存在 — 检查是否为孤儿锁
      try {
        const stat = fs.statSync(lockFile);
        if (Date.now() - stat.mtimeMs > LOCK_STALE_MS) {
          // 孤儿锁: 删除后重试
          try { fs.unlinkSync(lockFile); } catch {}
          continue;
        }
      } catch {}
      // 锁被持有且未过期 — 无进程短 sleep (替代 execSync 子进程开销)
      if (attempt < LOCK_RETRIES - 1) {
        Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 10);
      }
    }
  }
  return null; // 重试耗尽
}

/**
 * 安全追加一行 JSONL 到文件
 * @param {string} filePath - 目标文件路径
 * @param {object} entry - 要序列化的 JSON 对象
 * @param {object} [opts]
 * @param {boolean} [opts.useLock=false] - 是否使用文件锁
 */
function safeAppendJsonl(filePath, entry, opts = {}) {
  const line = JSON.stringify(entry) + '\n';
  const dir = path.dirname(filePath);

  try {
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  } catch {}

  if (opts.useLock) {
    const lockFile = filePath + '.append.lock';
    const lockFd = acquireAppendLock(lockFile);

    if (lockFd !== null) {
      // 持锁写入
      try {
        fs.appendFileSync(filePath, line);
      } finally {
        try { fs.closeSync(lockFd); fs.unlinkSync(lockFile); } catch {}
      }
    } else {
      // H3 修复: 锁耗尽改 fail-close，写入 fallback 文件而非主日志，防止行交错
      const fallbackFile = filePath + '.lock-failed.jsonl';
      try {
        process.stderr.write('[safe-append] lock exhausted for ' + path.basename(filePath) + ', wrote to fallback\n');
      } catch {}
      try { fs.appendFileSync(fallbackFile, line); } catch {}
    }
  } else {
    // 无锁模式: fd 级操作
    let fd;
    try {
      fd = fs.openSync(filePath, 'a');
      fs.writeSync(fd, line);
    } catch {}
    finally {
      if (fd !== undefined) try { fs.closeSync(fd); } catch {}
    }
  }
}

module.exports = { safeAppendJsonl };
