#!/usr/bin/env node
/**
 * 规则预编译器
 *
 * 将 hooks/rules/*.json 合并为 hooks/rules/rules-compiled.json 单文件缓存。
 * Hook 优先加载编译缓存 (1 次 IO) 而非 4-6 个独立文件。
 *
 * 用法:
 *   node scripts/compile-rules.js          # 编译
 *   node scripts/compile-rules.js --verify # 编译 + 验证正则
 */

const fs = require('fs');
const path = require('path');

const detectClaudeRoot = () => require('./paths.config.js').PATHS.root;

const CLAUDE_ROOT = detectClaudeRoot();
const RULES_DIR = path.join(CLAUDE_ROOT, 'hooks', 'rules');
// P2 修复: 输出路径与 hooks 读取路径一致 (hooks/rules/rules-compiled.json)
const OUTPUT = path.join(CLAUDE_ROOT, 'hooks', 'rules', 'rules-compiled.json');
const VERIFY = process.argv.includes('--verify');

function main() {
  const ruleFiles = fs.readdirSync(RULES_DIR)
    .filter(f => f.endsWith('.json') && f !== 'rules-compiled.json')
    .sort();

  const compiled = {
    generated: new Date().toISOString(),
    sources: {},
    rules: {},
  };

  let totalPatterns = 0;
  let errors = 0;

  for (const file of ruleFiles) {
    const filePath = path.join(RULES_DIR, file);
    const stat = fs.statSync(filePath);
    const key = file.replace('.json', '');

    try {
      const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
      const patterns = data.patterns || [];

      // 记录源文件 mtime 用于缓存失效检查
      compiled.sources[file] = {
        mtime: stat.mtimeMs,
        size: stat.size,
        count: patterns.length,
      };

      // 验证每条正则
      const validPatterns = [];
      for (const p of patterns) {
        if (!p.regex) continue;
        try {
          new RegExp(p.regex, p.flags || '');
          validPatterns.push(p);
        } catch (e) {
          errors++;
          if (VERIFY) {
            console.log(`  ERROR: ${file} regex "${p.regex}" - ${e.message}`);
          }
        }
      }

      compiled.rules[key] = validPatterns;
      totalPatterns += validPatterns.length;
    } catch (e) {
      errors++;
      console.log(`  ERROR: ${file} - ${e.message}`);
    }
  }

  fs.writeFileSync(OUTPUT, JSON.stringify(compiled) + '\n');

  console.log('rules-compiled.json generated:');
  console.log(`  Sources: ${ruleFiles.length} files`);
  console.log(`  Patterns: ${totalPatterns} total`);
  console.log(`  Errors: ${errors}`);
  console.log(`  Output: ${OUTPUT}`);

  if (VERIFY) {
    console.log('\n验证:');
    for (const [key, patterns] of Object.entries(compiled.rules)) {
      console.log(`  ${key}: ${patterns.length} patterns OK`);
    }
  }
}

// 模块导出 (供测试使用)
if (typeof module !== 'undefined') {
  module.exports = { detectClaudeRoot, RULES_DIR, OUTPUT, main };
}

if (require.main === module) {
  main();
}
