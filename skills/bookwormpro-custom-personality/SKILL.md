---
name: bookwormpro-custom-personality
description: 为 BookwormPRO 创建自定义 personality。当用户需要定制 AI 助手人格风格、添加新的 /personality 选项时使用。
version: 1.0.0
category: devops
---

# BookwormPRO 自定义 Personality 创建

## 触发条件
用户说 "/personality"、想自定义人格、要写自己的 personality。

## 关键文件

| 文件 | 作用 |
|------|------|
| `C:/Users/<user>/BookwormPRO/cli.py` 285-299 行 | 内置默认 personalities（参考格式） |
| `~/.bookwormpro/config.yaml` | 用户自定义 personalities + 激活 |

## 格式

```yaml
# 激活为默认（可选）
display:
  personality: "名字"

# 定义（必须）
agent:
  personalities:
    名字: |
      你是xxx——这里写 system prompt。
      支持多行，用 | 块标量。
      YAML 里中文引号需转义：\"全做\"。
```

## 工作流

### 1. 了解用户风格
从 memory/session 提取：语言偏好、指令风格（简洁/详细）、回复习惯（编号选项/批量执行）、角色定位（CTO/工程师/学生等）。

### 2. 参考内置格式
读 `BookwormPRO/cli.py` 285-299 行看已有 personality 的 prompt 风格。

### 3. 起草 prompt
关键原则：
- 名字要有辨识度（中文名可以）
- prompt 控制在 5-8 行，太长会被截断
- 融入 soul.md 核心精神（诚实、不夸大、代码质量）
- 对齐用户实际交互风格

### 4. 写入 config
先 `read_file` 完整读 `~/.bookwormpro/config.yaml`，然后用 `write_file` 整体写入（不要用 patch，见下方陷阱）。

### 5. 验证
```bash
python -c "import yaml; yaml.safe_load(open(r'C:\Users\<user>\.bookwormpro\config.yaml')); print('YAML OK')"
```

## 关键陷阱

### patch 工具在 Windows + UTF-8 中文时的误报
**症状**: patch 返回 `"Post-write verification failed: on-disk content differs from intended write"`
**真相**: 实际写入成功。patch 的字符数统计在 Windows CRLF + UTF-8 环境下有偏差。
**正确做法**: patch 后 `read_file` 验证内容，不要信任错误消息。
**更可靠的方式**: 用 `write_file` 整文件写入，避开 patch。

### YAML 转义
- 中文引号 `"..."` 在 YAML 字符串中需转义：`\"全做\"`
- 用 `|` 块标量避免大部分转义问题

## 审查清单
写完 personality 后逐行过：
1. 有没有语义矛盾？（如"不装"却说假话）
2. 是否对齐 soul.md 核心原则？（诚实、安全、质量）
3. 是否匹配用户实际交互风格？
4. YAML 语法合法？
