#!/usr/bin/env node
/**
 * 共享日志脱敏模块 (v6.0) — SANITIZE-V6-17PATTERNS
 *
 * 17 条 pattern 对齐 OpenClaw redact.ts。
 * 提供 maskToken 部分可见输出（前6后4位）+ 全量 [REDACTED] fallback。
 */

const REDACT_MIN_LEN = 18;
const KEEP_START = 6;
const KEEP_END = 4;

const PATTERNS = [
  // 1. ENV 键值对  KEY=value  KEY: value (含引号)
  { re: /\b[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|APIKEY)\b\s*[=:]\s*(["']?)([^\s"'\\]{8,})\1/gi, type: 'kv' },
  // 2. JSON 字段
  { re: /"(?:apiKey|api_key|token|secret|password|passwd|accessToken|refreshToken|credential)"\s*:\s*"([^"]{8,})"/gi, type: 'json' },
  // 3. CLI flags
  { re: /--(?:api[-_]?key|hook[-_]?token|token|secret|password|credential)\s+(["']?)([^\s"']{8,})\1/gi, type: 'cli' },
  // 4. Bearer header
  { re: /Authorization\s*[:=]\s*Bearer\s+([A-Za-z0-9._\-+=]{18,})/gi, type: 'bearer' },
  { re: /\bBearer\s+([A-Za-z0-9._\-+=]{18,})\b/g, type: 'bearer' },
  // 5. PEM block (多行)
  { re: /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----/g, type: 'pem' },
  // 6-15. 已知 token 前缀
  { re: /\b(sk-[A-Za-z0-9_-]{8,})\b/g, type: 'token' },         // OpenAI/Anthropic
  { re: /\b(sk-ant-[A-Za-z0-9_-]{8,})\b/g, type: 'token' },     // Anthropic 显式
  { re: /\b(ghp_[A-Za-z0-9]{20,})\b/g, type: 'token' },         // GitHub PAT
  { re: /\b(gho_[A-Za-z0-9]{20,})\b/g, type: 'token' },         // GitHub OAuth
  { re: /\b(github_pat_[A-Za-z0-9_]{20,})\b/g, type: 'token' },// GitHub Fine-grained PAT
  { re: /\b(xox[baprs]-[A-Za-z0-9-]{10,})\b/g, type: 'token' }, // Slack
  { re: /\b(gsk_[A-Za-z0-9_-]{10,})\b/g, type: 'token' },       // Groq
  { re: /\b(AIza[0-9A-Za-z\-_]{20,})\b/g, type: 'token' },     // Google API
  { re: /\b(npm_[A-Za-z0-9]{10,})\b/g, type: 'token' },         // npm
  { re: /\b(pplx-[A-Za-z0-9_-]{10,})\b/g, type: 'token' },      // Perplexity
  { re: /\bAKIA[A-Z0-9]{16}\b/g, type: 'token' },               // AWS Access Key
  // 16. JWT (eyJ 开头三段)
  { re: /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g, type: 'jwt' },
  // 17. Telegram bot token
  { re: /\b(\d{6,}:[A-Za-z0-9_-]{20,})\b/g, type: 'telegram' },
];

function maskToken(token) {
  if (!token || token.length < REDACT_MIN_LEN) return '***';
  return token.slice(0, KEEP_START) + '\u2026' + token.slice(-KEEP_END);
}

function sanitize(text, opts) {
  if (!text || typeof text !== 'string') return text || '';
  if (opts && opts.mode === 'off') return text;
  let result = text;
  for (let i = 0; i < PATTERNS.length; i++) {
    const { re, type } = PATTERNS[i];
    re.lastIndex = 0;
    if (type === 'pem') {
      result = result.replace(re, (m) => {
        const lines = m.split(/\r?\n/).filter(Boolean);
        return lines.length < 2 ? '***' : lines[0] + '\n[REDACTED_PEM]\n' + lines[lines.length - 1];
      });
    } else if (type === 'kv' || type === 'json' || type === 'cli') {
      // SANITIZE-V6-FIX-REPLACE: 过滤非字符串参数 (offset:number / namedGroups:object)
      result = result.replace(re, function() {
        const args = Array.from(arguments);
        const m = args[0];
        const strs = args.slice(1).filter(function(a){ return typeof a === 'string' && a.length > 0; });
        const token = strs[strs.length - 1];
        if (!token || typeof token !== 'string') return m;
        return m.split(token).join(maskToken(token));
      });
    } else if (type === 'jwt' || type === 'token' || type === 'bearer' || type === 'telegram') {
      result = result.replace(re, function(m, g1) {
        var token = (typeof g1 === 'string' && g1.length > 0) ? g1 : m;
        if (typeof token !== 'string') return m;
        return m.split(token).join(maskToken(token));
      });
    }
  }
  return result;
}

// 兼容旧调用: safeAppendLog 保持不变
const fs = require('fs');
function safeAppendLog(filePath, jsonData) {
  try {
    const dir = require('path').dirname(filePath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(filePath, JSON.stringify(jsonData) + '\n');
  } catch (e) {
    try { process.stderr.write('[LOG-FALLBACK] ' + JSON.stringify(jsonData) + '\n'); } catch {}
  }
}

if (typeof module !== 'undefined') {
  module.exports = { sanitize, safeAppendLog, maskToken };
}
