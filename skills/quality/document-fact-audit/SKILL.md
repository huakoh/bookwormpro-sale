---
name: document-fact-audit
description: Document fact audit — verify all claims against live system data, fix discrepancies, cite evidence
version: 1.0.0
maturity: stable
---

# 文档事实审计

对技术文档/HTML报告中的每一条数据主张进行逐条实测验证。

## 触发条件

- "去幻觉" / "事实核查" / "严谨性审查"
- 技术对比文档上线前
- HTML/PPT/报告包含量化数据

## 审计流程

### Phase 1: 提取主张
从文档中提取所有可验证的数值和事实主张：
- 数字 (N个/N%/N次)
- 文件名/目录名
- 版本号
- 功能描述

### Phase 2: 逐条实测
对每条主张，用终端命令直接验证：
```bash
# 计数类: 直接数
find ~/.bookwormpro/skills/ -name "SKILL.md" | wc -l

# 配置类: 读文件
grep "version" config.yaml

# 运行时: 跑命令
node accuracy.js

# Git类: 查log
git log --oneline --since="DATE" | wc -l
```

### Phase 3: 三级分类
- ✅ 可证实: 实测值与文档一致
- 🔴 需修正: 实测值与文档不一致 → 修改文档
- 🟡 待确认: 无法实测 → 标注来源

### Phase 4: 修正 + 验证
- 修正所有🔴项
- 重新核对全部主张
- 输出最终审计报告

## 常见陷阱
- Skills数包括/不包括_archived子目录
- Git push次数的时区边界
- BWR文件数包括.js/.json/.py但不包括子目录
- Cron数包括所有enabled jobs
