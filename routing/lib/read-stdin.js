/**
 * 共享 stdin 读取模块 (M13)
 *
 * 替代 22 个 hook 中各自重复的 stdin 读取模板。
 * 统一: encoding、MAX_SIZE 保护、JSON.parse、错误处理。
 *
 * 用法:
 *   const readStdin = require('./lib/read-stdin.js');
 *   readStdin({ maxSize: 512 * 1024 }).then(input => { ... });
 */

/**
 * 从 stdin 读取 JSON 输入
 * @param {object} [opts]
 * @param {number} [opts.maxSize=512*1024] - 最大输入字节数
 * @returns {Promise<object>} 解析后的 JSON 对象
 */
function readStdin(opts = {}) {
  const maxSize = opts.maxSize || 512 * 1024;
  return new Promise((resolve, reject) => {
    let raw = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => {
      raw += chunk;
      if (raw.length > maxSize) {
        process.stdin.destroy();
        reject(new Error('stdin exceeds max size: ' + maxSize));
      }
    });
    process.stdin.on('end', () => {
      try {
        resolve(JSON.parse(raw));
      } catch (e) {
        reject(new Error('stdin JSON parse failed: ' + (e.message || '')));
      }
    });
    process.stdin.on('error', reject);
  });
}

module.exports = readStdin;
