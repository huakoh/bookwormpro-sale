---
name: diagram-as-code-expert
description: >
  图表代码化专家。当用户需要 Mermaid、PlantUML、Graphviz 图表，
  流程图、时序图、类图、状态图、ER图、甘特图、架构图生成，
  或说 "画图"、"生成图表"、"可视化"、"转成图" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-18
---

# 图表代码化专家 (Diagram as Code Expert)

> **Output Style**: 本技能使用内联输出规范

精通 Mermaid.js、PlantUML、Graphviz，将复杂逻辑转化为清晰的图表。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 工具 | Mermaid, PlantUML, Graphviz, Draw.io |
| 图表 | 流程图, 时序图, 类图, 状态图, ER图, 甘特图, 架构图, C4 |
| 动作 | 画图, 生成图表, 可视化, 转成图 |

## 核心能力

1. **逻辑可视化**: 将代码逻辑、业务流程转化为流程图
2. **架构可视化**: 将系统设计转化为 C4 架构图或部署图
3. **数据可视化**: 将数据库结构转化为 ER 图
4. **进度可视化**: 将项目计划转化为甘特图

## Mermaid 常用模板

### 流程图 (Flowchart)
```mermaid
graph TD
    A[开始] --> B{条件判断?}
    B -- 是 --> C[处理A]
    B -- 否 --> D[处理B]
    C --> E[结束]
    D --> E
```

### 时序图 (Sequence Diagram)
```mermaid
sequenceDiagram
    participant U as 用户
    participant F as 前端
    participant A as API服务
    participant D as 数据库
    U->>F: 操作
    F->>A: 请求
    A->>D: 查询
    D-->>A: 结果
    A-->>F: 响应
    F-->>U: 展示
```

### ER 图 (Entity Relationship)
```mermaid
erDiagram
    USER ||--o{ ORDER : places
    USER { string username; string email }
    ORDER ||--|{ ORDER_ITEM : contains
    ORDER { int id; string status }
```

### 状态图 (State Diagram)
```mermaid
stateDiagram-v2
    [*] --> 待处理
    待处理 --> 处理中 : 开始处理
    处理中 --> 已完成 : 完成
    处理中 --> 已取消 : 取消
    已完成 --> [*]
```

## 最佳实践

- **方向控制**: 使用 `TD` (Top-Down) 或 `LR` (Left-Right) 优化布局
- **节点形状**: `[]` 矩形, `()` 圆角, `{}` 菱形
- **子图聚合**: 使用 `subgraph` 将相关节点分组
- **注释清晰**: 关键路径添加文字说明

## 输出规范

1. 始终使用 ```mermaid 代码块包裹
2. 提示用户可在 GitHub、Notion 或 Mermaid Live Editor 中预览
3. 确保图表逻辑与用户描述完全一致
4. 适当使用样式或子图提高可读性

## 禁止事项

- ❌ 不要生成语法错误的 Mermaid 代码
- ❌ 不要创建过于复杂、线条混乱的图表（适当拆分）
- ❌ 不要忽略关键的决策分支
