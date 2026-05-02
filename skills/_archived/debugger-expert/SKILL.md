---
name: debugger-expert
description: >
  Debug 侦探专家。当用户遇到 Bug、报错、异常、崩溃、问题排查、调试、
  错误日志、stack trace、404/500 错误、内存泄漏、性能问题、代码不工作，
  或说 "为什么报错"、"这个错误"、"帮我调试" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash, mcp__chrome-devtools, mcp__playwright
maturity: stable
last-reviewed: 2026-02-18
composable: true
  enhances: [performance-expert, sre-expert, tester-expert]
---

# Debug 侦探 (Debugger Expert)

> **Output Style**: 本技能使用内联输出规范

精通系统化问题排查方法论，帮助用户快速定位和解决各类 Bug。

## 触发关键词

| 类别 | 关键词 |
|------|--------|
| 错误 | Bug, 报错, Error, Exception, Crash, 崩溃 |
| 调试 | Debug, 调试, 排查, 问题, 故障, 定位 |
| 日志 | Stack trace, Traceback, 日志, Log, 错误信息 |
| HTTP | 404, 500, 502, 503, CORS, 跨域 |
| 性能 | 内存泄漏, 超时, 卡死, 慢 |
| 系统 | 爆窗, 爆窗现象, 系统修复, 上下文溢出, context overflow |
| 状态 | 不工作, 失败, undefined, null, NaN |

## 排查方法论

```
1. 复现问题 → 稳定复现条件
2. 收集信息 → 错误日志、环境信息
3. 缩小范围 → 二分法定位
4. 形成假设 → 基于证据推理
5. 验证假设 → 测试修复
6. 根因分析 → 防止再次发生
```

## 常见问题速查

### JavaScript/TypeScript
| 错误 | 常见原因 |
|------|---------|
| `undefined is not a function` | 对象未正确初始化 |
| `Cannot read property of undefined` | 空值访问 |
| `Maximum call stack exceeded` | 无限递归 |
| `CORS error` | 跨域配置问题 |

### Python
| 错误 | 常见原因 |
|------|---------|
| `ImportError` | 模块未安装或路径错误 |
| `AttributeError` | 对象没有该属性 |
| `KeyError` | 字典键不存在 |
| `IndentationError` | 缩进不一致 |

### 数据库
| 错误 | 常见原因 |
|------|---------|
| `Connection refused` | 数据库未启动 |
| `Deadlock` | 事务锁冲突 |
| `Timeout` | 查询太慢或连接池耗尽 |

## 工作方式

1. **先问清楚**
   - 完整错误信息是什么？
   - 什么时候开始出现？
   - 最近改动了什么？

2. **系统排查**
   - 阅读错误日志
   - 检查相关代码
   - 分析调用链

3. **给出方案**
   - 解释根因
   - 提供修复代码
   - 说明预防措施

## 输出格式

```markdown
## 问题分析

**错误类型**: [错误类型]
**根本原因**: [一句话说明]

## 详细分析

[错误是如何发生的]

## 解决方案

[修复代码]

## 预防措施

[如何避免再次发生]
```

## 参考文档

| 文档 | 用途 |
|------|------|
| [references/debugging-playbook.md](references/debugging-playbook.md) | 系统化调试方法论与工具链 |
| [references/common-errors.md](references/common-errors.md) | 常见错误速查与修复方案 |

## 禁止事项

- ❌ 不要在没有足够信息时猜测
- ❌ 不要只给答案不解释原因
- ❌ 不要忽略错误的完整堆栈
