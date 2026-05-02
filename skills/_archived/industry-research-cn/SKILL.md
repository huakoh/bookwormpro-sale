---
name: industry-research-cn
description: >
  中国行业深度研究与市场分析技能。当用户需要进行行业调研、市场规模测算、
  竞争格局分析、投资可行性研究、竞品分析、PESTLE 分析时使用此技能。
  触发词：行业研究、市场调研、竞争格局、TAM/SAM/SOM、竞品分析、
  industry research、market analysis。优先引用权威资料。

allowed-tools: Read, Glob, Grep, WebFetch, WebSearch
maturity: stable
last-reviewed: 2026-02-18
---

# 中国行业深度研究技能

> **Output Style**: 本技能使用内联输出规范

为中国市场的行业研究提供系统化方法论，确保研究结论权威可信、数据可追溯。

## 核心能力

- **权威数据检索**：7级16类数据来源分级体系，优先引用法规、标准、官方统计
- **系统化分析框架**：九大模块覆盖行业研究全维度
- **专业引用规范**：标准化引用格式，数据交叉验证机制
- **决策导向输出**：兼顾投资、创业、战略咨询多场景需求

## 工作流程

### Step 1: 明确研究范围

收集以下信息（必要时询问用户）：

```yaml
必填项:
  - 目标行业: [行业名称]
  - 研究目的: [投资评估|创业调研|竞争分析|战略规划|商业计划书支撑]

选填项:
  - 重点细分领域: [细分市场]
  - 目标区域: [默认全国]
  - 时间范围: [默认近3年+未来3-5年预测]
  - 特别关注的政策/标准: [具体政策或标准]
```

### Step 2: 执行分层检索

按权威性从高到低依次搜索，详见 [references/data-source-hierarchy.md](references/data-source-hierarchy.md)：

**第一梯队（必须搜索）**：
1. 法律法规：`"{{行业}} 法律 site:gov.cn"` `"{{行业}} 管理条例"`
2. 国家标准：`"GB {{行业关键词}} 标准"` 
3. 产业政策：`"{{行业}} 十四五 规划"` `"{{行业}} 产业政策 发改委"`
4. 官方统计：`"{{行业}} 统计 国家统计局"`

**第二梯队（补充搜索）**：
5. 行业标准/团体标准
6. 行业协会报告
7. 上市公司披露（年报、招股书）
8. 第三方研究机构报告

完整搜索模板见 [references/search-strategy.md](references/search-strategy.md)

### Step 3: 数据验证

关键数据必须交叉验证：
- 市场规模、增长率、市占率等核心数据至少2个独立来源
- 验证结果标注：`✓已验证` `△存疑` `✗不可用`
- 详见 [references/citation-standards.md](references/citation-standards.md)

### Step 4: 按框架撰写报告

九大模块分析框架，每个模块标注数据来源级别：

| 模块 | 核心内容 | 来源要求 |
|------|----------|----------|
| 1. 政策法规与监管环境 | 法律法规、产业政策、标准体系 | **L1-L6必须** |
| 2. 行业概况与发展现状 | 定义、历程、产业链 | L3-L6优先 |
| 3. 市场规模与增长分析 | TAM/SAM/SOM、增长趋势 | **需交叉验证** |
| 4. 服务/产品类型分析 | 分类、特征、演进 | L7-L12 |
| 5. 用户画像与需求洞察 | 画像、KANO需求分层 | L10-L12 |
| 6. 市场痛点与未满足需求 | 供需痛点、监管挑战 | L10-L12 |
| 7. 市场特征与竞争格局 | CR5/HHI、波特五力 | **L11优先** |
| 8. 市场机会识别 | 增量/存量机会、RICE评估 | 综合 |
| 9. 盈利模式与战略建议 | 单位经济、风险矩阵 | 综合 |

详细框架见 [references/research-framework.md](references/research-framework.md)

### Step 5: 输出报告

使用标准模板输出，包含：
- 执行摘要（核心结论+关键数据+Top3机会/风险）
- 九大模块正文
- 附录（来源分级汇总、验证表、法规索引、参考列表）

输出模板见 [references/output-template.md](references/output-template.md)

## 数据来源分级速查

| 级别 | 来源类型 | 权威性 |
|------|----------|--------|
| **L1-L3** | 法律法规、国标、官方统计 | 最高 |
| **L4-L6** | 产业政策、政府报告、技术白皮书 | 高 |
| **L7-L9** | 行业标准、团体标准、专家共识 | 中高 |
| **L10-L12** | 行业协会、上市公司、研究机构 | 中 |
| **L13-L16** | 国际机构、学术论文、媒体报道 | 辅助 |

完整分级体系见 [references/data-source-hierarchy.md](references/data-source-hierarchy.md)

## 禁止引用来源

- ❌ 百度百科、知乎等UGC内容
- ❌ 来源不明的"业内人士透露"
- ❌ 自媒体文章（除非追溯原始来源）
- ❌ 已失效的法规或标准

## 质量控制红线

- L1-L6级来源占比 ≥ 40%
- 推算/估计数据占比 ≤ 20%
- 所有数据100%标注来源
- 市场规模数据必须交叉验证

## 引用格式速查

```
法律法规: 《法律名称》(年份) 第X条
国家标准: GB/T XXXXX-YYYY《标准名称》
政策文件: 《文件名称》(发文字号)
统计数据: 机构《报告名称》(时间)，第X页
行业报告: 机构《报告名称》(时间)，第X页
上市公司: 公司名《文件类型》(报告期)，第X页
```

完整引用规范见 [references/citation-standards.md](references/citation-standards.md)

## 参考文档

- [references/data-source-hierarchy.md](references/data-source-hierarchy.md) — 7级16类数据来源分级详解
- [references/search-strategy.md](references/search-strategy.md) — 6类数据搜索关键词模板
- [references/citation-standards.md](references/citation-standards.md) — 引用格式与交叉验证规范
- [references/authoritative-sources.md](references/authoritative-sources.md) — 中国权威数据来源清单
- [references/research-framework.md](references/research-framework.md) — 九大模块详细分析框架
- [references/output-template.md](references/output-template.md) — 报告输出格式模板

## 输出规范

- 中文撰写，专业术语保留英文缩写
- 先结论后论据，数据说话
- 每个核心观点配套至少1个数据支撑
- 明确区分"事实"与"观点"
- 报告篇幅：6000-10000字（不含附录）
