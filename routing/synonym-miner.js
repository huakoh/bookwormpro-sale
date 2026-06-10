#!/usr/bin/env node
/**
 * synonym-miner.js — 从 skills-index-lite.json 自动挖掘同义词候选组
 *
 * 算法:
 * 1. 加载所有技能的关键词
 * 2. 统计每个关键词出现在多少个技能中
 * 3. 出现在 2-4 个技能中的关键词为候选（太通用的排除，太独特的无同义价值）
 * 4. 对候选关键词，计算 Jaccard 相似度找到共现组
 * 5. 与现有 synonyms.json 对比，只输出尚未覆盖的新候选
 *
 * 用法: node synonym-miner.js [--min-skills 2] [--max-skills 4] [--threshold 0.3]
 */

const fs = require('fs');
const path = require('path');

// 配置
const args = process.argv.slice(2);
const getArg = (name, def) => {
  const idx = args.indexOf(`--${name}`);
  return idx >= 0 && args[idx + 1] ? Number(args[idx + 1]) : def;
};

const MIN_SKILLS = getArg('min-skills', 2);
const MAX_SKILLS = getArg('max-skills', 4);
const JACCARD_THRESHOLD = getArg('threshold', 0.25);

const BASE = path.resolve(__dirname, '..');
const skillsPath = path.join(BASE, 'skills-index-lite.json');
const synonymsPath = path.join(__dirname, 'synonyms.json');

// 加载数据
const skillsData = JSON.parse(fs.readFileSync(skillsPath, 'utf8'));
const synonymsData = JSON.parse(fs.readFileSync(synonymsPath, 'utf8'));

// 已有同义词词汇集合（小写化）
const existingWords = new Set();
synonymsData.groups.forEach(g => {
  g.words.forEach(w => existingWords.add(w.toLowerCase()));
});

// 过滤噪声关键词（太短、纯符号、通用词）
const NOISE = new Set([
  '测试', '架构', '性能', '配置', '日志', '组件', '认证', '安全',
  'test', 'architecture', 'performance', 'config', 'log', 'component',
  'auth', 'security', 'deploy', 'monitoring', 'database', 'template',
  'interface', 'routing', 'cache', 'microservice', 'cluster',
  'container', 'frontend', 'backend', 'api', 'queue',
  // 过短
  'pt', 'ts', 'ui', 'ux', 'ml', 'dl', 'db', 'ci', 'cd',
  // 通用中文
  '使用', '语言', '应用', '描述', '示例', '当用户需要', '专家', '技术栈',
  '流程', '策略', '场景', '优化', '设计', '管理', '系统', '工具',
]);

// 第1步: 统计关键词→技能映射
const kwToSkills = new Map();
const skillToKws = new Map();

skillsData.skills.forEach(skill => {
  const kws = new Set();
  skill.keywords.forEach(k => {
    const kw = (k.keyword || "").toLowerCase().trim();
    // 跳过太长（描述性）、太短（<2字符）或噪声词
    if (kw.length < 2 || kw.length > 20 || NOISE.has(kw)) return;
    // 跳过含有明显描述性文本的关键词
    if (kw.includes('当用户') || kw.includes('专家') || kw.includes('推荐') || kw.includes('适用')) return;

    kws.add(kw);
    if (!kwToSkills.has(kw)) kwToSkills.set(kw, new Set());
    kwToSkills.get(kw).add(skill.name);
  });
  skillToKws.set(skill.name, kws);
});

// 第2步: 筛选出现在 MIN_SKILLS~MAX_SKILLS 个技能中的关键词
const candidates = [];
for (const [kw, skills] of kwToSkills) {
  if (skills.size >= MIN_SKILLS && skills.size <= MAX_SKILLS) {
    // 排除已在 synonyms.json 中的
    if (!existingWords.has(kw)) {
      candidates.push({ keyword: kw, skills: [...skills], count: skills.size });
    }
  }
}

console.log(`=== Synonym Miner Report ===`);
console.log(`技能总数: ${skillsData.skills.length}`);
console.log(`关键词总数: ${kwToSkills.size}`);
console.log(`出现在 ${MIN_SKILLS}-${MAX_SKILLS} 个技能中的候选词: ${candidates.length}`);
console.log(`已有同义词覆盖的词数: ${existingWords.size}`);
console.log();

// 第3步: 用 Jaccard 相似度聚类候选词
// 对每对候选词，计算它们所属技能集合的 Jaccard 相似度
const groups = [];
const used = new Set();

candidates.sort((a, b) => b.count - a.count);

for (let i = 0; i < candidates.length; i++) {
  if (used.has(candidates[i].keyword)) continue;

  const group = [candidates[i]];
  const skillsA = new Set(candidates[i].skills);

  for (let j = i + 1; j < candidates.length; j++) {
    if (used.has(candidates[j].keyword)) continue;

    const skillsB = new Set(candidates[j].skills);

    // 计算 Jaccard
    const intersection = [...skillsA].filter(s => skillsB.has(s)).length;
    const union = new Set([...skillsA, ...skillsB]).size;
    const jaccard = intersection / union;

    if (jaccard >= JACCARD_THRESHOLD) {
      group.push(candidates[j]);
    }
  }

  // 只保留 >= 2 个词的组
  if (group.length >= 2) {
    group.forEach(g => used.add(g.keyword));
    groups.push({
      words: group.map(g => g.keyword),
      sharedSkills: [...new Set(group.flatMap(g => g.skills))],
      avgJaccard: 'computed',
    });
  }
}

// 第4步: 输出结果
console.log(`--- 建议新增同义词组 (${groups.length} 组) ---\n`);

groups.forEach((g, idx) => {
  console.log(`[组 ${idx + 1}] 词汇: ${g.words.join(', ')}`);
  console.log(`  关联技能: ${g.sharedSkills.join(', ')}`);
  console.log();
});

// 第5步: 输出未聚类的高频候选词
const unclustered = candidates.filter(c => !used.has(c.keyword));
if (unclustered.length > 0) {
  console.log(`--- 未聚类的候选词 (前 30) ---\n`);
  unclustered.slice(0, 30).forEach(c => {
    console.log(`  ${c.keyword} (${c.count} 技能): ${c.skills.join(', ')}`);
  });
}

// 第6步: 覆盖率统计
const allKws = [...kwToSkills.keys()];
const coveredBySynonyms = allKws.filter(kw => existingWords.has(kw)).length;
const coveredAfterMining = allKws.filter(kw => existingWords.has(kw) || used.has(kw)).length;

console.log(`\n--- 覆盖率统计 ---`);
console.log(`当前同义词覆盖率: ${(coveredBySynonyms / allKws.length * 100).toFixed(1)}% (${coveredBySynonyms}/${allKws.length})`);
console.log(`加入建议后覆盖率: ${(coveredAfterMining / allKws.length * 100).toFixed(1)}% (${coveredAfterMining}/${allKws.length})`);
console.log(`提升: +${(coveredAfterMining - coveredBySynonyms)} 个关键词`);
