# Claude 提示词工程规范参考

本文档汇总了 Claude 官方提示词工程的最佳实践，供优化提示词时参考。

## 目录

1. [核心原则](#核心原则)
2. [XML 标签使用规范](#xml-标签使用规范)
3. [示例提示 (Few-shot)](#示例提示-few-shot)
4. [思维链 (Chain of Thought)](#思维链-chain-of-thought)
5. [角色设定](#角色设定)
6. [输出格式控制](#输出格式控制)
7. [Claude 4 特别注意事项](#claude-4-特别注意事项)
8. [常见任务模板](#常见任务模板)

---

## 核心原则

### 1. 明确具体 (Be Explicit)

Claude 4 模型对清晰、明确的指令响应最好。

**不佳：**
```
创建一个分析仪表板
```

**优秀：**
```
创建一个分析仪表板。包含尽可能多的相关功能和交互。
超越基础，创建一个功能完整的实现。
```

### 2. 提供动机 (Provide Motivation)

解释为什么需要某种行为，帮助 Claude 更好地理解目标。

**不佳：**
```
不要使用省略号
```

**优秀：**
```
你的回复将被文字转语音引擎朗读，所以不要使用省略号，
因为文字转语音引擎不知道如何发音。
```

### 3. 正向表述 (Positive Framing)

告诉 Claude 要做什么，而不是不要做什么。

**不佳：**
```
不要使用 Markdown 格式
```

**优秀：**
```
你的回复应该由流畅连贯的散文段落组成。
```

### 4. 适度复杂性 (Right-size Complexity)

简单任务用简单提示词，复杂任务才需要详细结构。

---

## XML 标签使用规范

### 为什么使用 XML 标签

- **清晰度**：清楚分隔提示词的不同部分
- **准确性**：减少 Claude 误解提示词的错误
- **灵活性**：便于查找、添加、删除或修改部分内容
- **可解析性**：便于从输出中提取特定部分

### 推荐的标签名称

| 标签 | 用途 |
|------|------|
| `<instructions>` | 主要指令 |
| `<context>` | 背景信息 |
| `<input>` / `<input_data>` | 输入数据 |
| `<examples>` | 示例集合 |
| `<example>` | 单个示例 |
| `<output_format>` | 输出格式定义 |
| `<constraints>` | 限制条件 |
| `<thinking>` | 思考过程 |
| `<answer>` | 最终答案 |
| `<document>` | 文档内容 |
| `<role>` | 角色设定 |

### 使用原则

1. **一致性**：整个提示词使用相同的标签名称
2. **语义化**：标签名称应反映其内容含义
3. **嵌套合理**：对层次内容使用嵌套标签 `<outer><inner></inner></outer>`
4. **引用标签**：在指令中引用标签名称，如"使用 `<contract>` 标签中的合同..."

### 示例

```xml
<instructions>
分析以下合同，识别关键条款和潜在风险。
</instructions>

<contract>
{{CONTRACT_TEXT}}
</contract>

<output_format>
1. 关键条款摘要
2. 潜在风险点
3. 建议行动
</output_format>
```

---

## 示例提示 (Few-shot)

### 何时使用

- 需要特定输出格式
- 复杂任务需要展示期望标准
- 减少对指令的误解

### 最佳实践

1. **数量**：提供 3-5 个多样化的示例
2. **相关性**：示例应与实际用例相似
3. **多样性**：覆盖边缘情况和挑战
4. **清晰度**：使用 `<example>` 标签包裹

### 示例格式

```xml
<examples>
<example>
<input>Added user authentication with JWT tokens</input>
<o>
feat(auth): implement JWT-based authentication

Add login endpoint and token validation middleware
</o>
</example>

<example>
<input>Fixed bug where dates displayed incorrectly</input>
<o>
fix(reports): correct date formatting in timezone conversion

Use UTC timestamps consistently across report generation
</o>
</example>
</examples>
```

---

## 思维链 (Chain of Thought)

### 何时使用

- 复杂的分析或推理任务
- 数学或逻辑问题
- 需要多步骤决策的任务

### 优势

- **准确性**：逐步推理减少错误
- **连贯性**：结构化思考产生更有组织的回复
- **可调试性**：便于发现提示词问题

### 实现方式

**基础方式：**
```
在回答之前，请先逐步思考这个问题。
```

**结构化方式：**
```xml
<instructions>
分析这个问题，将你的思考过程放在 <thinking> 标签中，
最终答案放在 <answer> 标签中。
</instructions>
```

**详细步骤方式：**
```xml
<instructions>
请按以下步骤分析：
1. 识别问题的关键要素
2. 列出相关的已知信息
3. 考虑可能的解决方案
4. 评估每个方案的优缺点
5. 选择最佳方案并解释原因

将思考过程放在 <thinking> 标签中，结论放在 <answer> 标签中。
</instructions>
```

---

## 角色设定

### 何时使用

- 需要特定专业视角
- 希望调整语气和风格
- 模拟特定场景

### 最佳实践

```xml
<role>
你是一位拥有 10 年经验的高级软件架构师，专注于分布式系统设计。
你的风格是严谨但易于理解，善于用类比解释复杂概念。
</role>
```

### 角色要素

- 专业背景和经验年限
- 专长领域
- 沟通风格
- 特定约束（如面向新手）

---

## 输出格式控制

### 方法 1：明确描述格式

```
以 JSON 格式输出，包含 name、age、skills（数组）字段。
```

### 方法 2：提供模板

```xml
<output_format>
# [标题]

## 背景
[一段话描述背景]

## 主要发现
- 发现 1
- 发现 2

## 建议
1. 建议 1
2. 建议 2
</output_format>
```

### 方法 3：使用示例

```xml
<example_output>
{
  "summary": "简要总结",
  "score": 85,
  "details": ["细节1", "细节2"]
}
</example_output>
```

### 方法 4：格式指示器

使用 `<format_indicator>` 标签要求特定格式：
```xml
<format_indicator>pure_json</format_indicator>
```

---

## Claude 4 特别注意事项

### 1. 显式请求

Claude 4 更精确地遵循指令。如果需要"超越基础"的行为，需要明确请求：

```
包含尽可能多的相关功能和交互。超越基础，创建一个功能完整的实现。
```

### 2. 示例的影响

Claude 4 对示例非常敏感。确保：
- 示例与期望行为一致
- 避免示例中包含不想要的模式

### 3. 并行工具调用

Claude 4 擅长并行执行多个工具。可以添加提示：
```
为了最高效率，当需要执行多个独立操作时，
请同时调用所有相关工具，而不是顺序调用。
```

### 4. 思考能力

利用 Claude 4 的 interleaved thinking：
```
在收到工具结果后，仔细反思其质量，
在继续之前确定最佳下一步。
使用你的思考来规划和迭代。
```

---

## 常见任务模板

### 文本总结

```xml
<role>
你是一位专业的内容摘要专家。
</role>

<instructions>
请总结以下文本的要点。要求：
1. 保留核心信息，去除冗余
2. 使用简洁的语言
3. 保持原文的主要观点
4. 字数控制在原文的 20% 以内
</instructions>

<input>
{{TEXT}}
</input>

<output_format>
## 摘要
[一段话核心总结]

## 要点
- 要点 1
- 要点 2
- 要点 3
</output_format>
```

### 代码生成

```xml
<role>
你是一位经验丰富的 {{LANGUAGE}} 开发者。
</role>

<instructions>
请编写代码实现以下功能：
{{REQUIREMENTS}}

要求：
1. 代码简洁高效
2. 包含必要的错误处理
3. 添加清晰的注释
4. 遵循 {{LANGUAGE}} 最佳实践
</instructions>

<constraints>
- 使用 {{FRAMEWORK/VERSION}}
- 不使用外部依赖（除非必要）
- 代码需要可直接运行
</constraints>

<output_format>
首先简要说明实现思路，然后提供完整代码。
</output_format>
```

### 内容创作

```xml
<role>
你是一位专业的 {{CONTENT_TYPE}} 创作者，
风格 {{STYLE}}，面向 {{AUDIENCE}}。
</role>

<instructions>
请创作一篇关于 {{TOPIC}} 的内容。

要求：
1. 语气：{{TONE}}
2. 长度：约 {{LENGTH}} 字
3. 结构：{{STRUCTURE_REQUIREMENTS}}
4. 关键点：{{KEY_POINTS}}
</instructions>

<examples>
[如需要，提供风格示例]
</examples>

<constraints>
- 原创内容，不要复制现有材料
- 保持一致的语气和风格
- 确保内容准确性
</constraints>
```

### 数据分析

```xml
<role>
你是一位资深数据分析师。
</role>

<context>
{{BUSINESS_CONTEXT}}
</context>

<instructions>
分析以下数据，重点关注：
1. {{FOCUS_AREA_1}}
2. {{FOCUS_AREA_2}}

分析步骤：
1. 数据质量检查
2. 描述性统计
3. 趋势和模式识别
4. 洞察和建议
</instructions>

<data>
{{DATA}}
</data>

<output_format>
## 执行摘要
[关键发现的一段话总结]

## 数据质量
[数据质量评估]

## 分析发现
[详细分析，包含具体数据支持]

## 建议
[基于分析的可行建议]
</output_format>
```

---

## 优化检查清单

优化提示词后，检查以下项目：

- [ ] 任务目标明确、无歧义
- [ ] 提供了必要的上下文
- [ ] 指令具体、可执行
- [ ] 使用了适当的 XML 结构
- [ ] 复杂任务包含示例或分步骤
- [ ] 定义了明确的输出格式
- [ ] 使用正向表述而非否定
- [ ] 如需要，设定了合适的角色
- [ ] 约束条件清晰
- [ ] 提供了足够的变量占位符
