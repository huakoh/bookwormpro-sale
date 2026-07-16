'use strict';
/**
 * BookwormPRO 运行时根目录检测
 * 返回 ~/.bookwormpro/ (runtime data: skills-index, route logs, debug)
 */
const path = require('path');
const os = require('os');

let _cached = null;
function detectRuntimeRoot() {
  if (_cached) return _cached;
  if (process.env.BOOKWORMPRO_HOME) { _cached = process.env.BOOKWORMPRO_HOME; return _cached; }
  const home = process.env.USERPROFILE || process.env.HOME || os.homedir();
  _cached = path.join(home, '.bookwormpro');
  return _cached;
}

module.exports = detectRuntimeRoot();
