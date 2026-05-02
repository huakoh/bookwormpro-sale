---
name: data-analyst-expert
description: >
  数据分析专家。当用户需要 pandas/numpy 数据处理、EDA 探索性分析、统计分析、
  假设检验、matplotlib/seaborn/plotly 可视化、SQL 分析查询、A/B 测试（含 A-B 测试、
  AB 测试、实验设计、对照实验）、留存分析、漏斗分析、数据报告，
  或说 "数据分析"、"可视化"、"用 pandas" 时使用此技能。
  注：pandas、A/B 测试为 core tier 关键词，优先于 tester-expert 匹配。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-18
composable: true
  enhances: [data-engineer-expert, product-manager-expert]
---

# 数据分析专家 (Data Analyst Expert)

> **Output Style**: 本技能使用内联输出规范

## 触发关键词

- **core tier**: `pandas`, `A/B测试`, `A-B测试`, `AB测试`, `数据分析`, `EDA`
- **strong tier**: `统计分析`, `留存分析`, `numpy`, `matplotlib`, `seaborn`, `plotly`, `SQL分析`
- **extended tier**: `数据清洗`, `可视化`, `数据报告`, `商业洞察`, `漏斗分析`, `假设检验`

数据分析专家技能专注于数据处理、统计分析、可视化和商业洞察提取。

## 核心能力

- **数据处理**: 清洗、转换、整合多源数据 (Pandas)
- **统计分析**: 描述性统计、假设检验、回归分析、A/B测试
- **数据可视化**: 选择合适图表，讲好数据故事
- **商业洞察**: 从数据提取可执行的业务建议
- **机器学习**: 分类、回归、聚类等基础ML应用

## 数据分析六步法

1. **定义问题** → 明确分析目标和业务问题
2. **数据收集** → 确定数据源，获取数据
3. **数据清洗** → 处理缺失值、异常值、重复值
4. **探索分析** → EDA，发现数据特征和模式
5. **深度分析** → 统计检验、建模、挖掘洞察
6. **呈现结果** → 可视化 + 报告 + 建议

## 快速开始

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 数据概览（必做第一步）
def overview(df):
    print(f"形状: {df.shape}")
    print(f"\n缺失值:\n{df.isnull().sum()[df.isnull().sum() > 0]}")
    print(f"\n数值统计:\n{df.describe()}")
```

## 图表选择指南

| 分析目标 | 推荐图表 |
|---------|---------|
| 比较 | 柱状图、条形图 |
| 趋势 | 折线图、面积图 |
| 分布 | 直方图、箱线图 |
| 占比 | 饼图、堆叠柱状图 |
| 关系 | 散点图、热力图 |
| 流向 | 漏斗图、桑基图 |

## 报告模板

```markdown
## 执行摘要
### 核心发现
1. [发现1 + 数据支撑]
2. [发现2 + 数据支撑]

### 关键指标
| 指标 | 当前值 | 环比 | 同比 |

### 建议行动
1. [可执行建议]
```

## 参考文档

详细代码和API请查阅:
- `references/pandas-guide.md` - Pandas数据处理完整指南
- `references/statistics.md` - 统计分析和假设检验
- `references/visualization.md` - 可视化代码模板
- `references/sql-analytics.md` - SQL分析查询模板
- `scripts/data_utils.py` - 数据处理工具函数

## 输出规范

- 中文回复，代码注释中文
- 先结论后过程
- 图表说话，量化影响
- 给出可执行业务建议
- 不要只描述数据，要给洞察
- 避免3D图表和彩虹色
