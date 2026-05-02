---

name: guardian

category: 安全

version: 1.0.0

description: |
safety:
  level: low
  permissions: [read_file, search_files]

  统一安全守护技能。整合 freeze (目录编辑限制)、careful (破坏性命令警告)、

  unfreeze (解除限制) 和 guard (全量安全模式) 四项能力为单一入口。

  支持子命令: /guardian freeze [dir], /guardian unfreeze, /guardian careful,

  /guardian status。

  触发词: "guardian", "安全守护", "guard mode", "freeze", "careful",

  "restrict edits", "safety mode", "lock down"。

maturity: stable
cost_level: low

allowed-tools:

  - Bash

  - Read

  - AskUserQuestion

hooks:

  PreToolUse:

    - matcher: "Bash"

      hooks:

        - type: command

          command: "bash ${CLAUDE_SKILL_DIR}/../careful/bin/check-careful.sh"

          statusMessage: "Checking for destructive commands..."

    - matcher: "Edit"

      hooks:

        - type: command

          command: "bash ${CLAUDE_SKILL_DIR}/../freeze/bin/check-freeze.sh"

          statusMessage: "Checking freeze boundary..."

    - matcher: "Write"

      hooks:

        - type: command

          command: "bash ${CLAUDE_SKILL_DIR}/../freeze/bin/check-freeze.sh"

          statusMessage: "Checking freeze boundary..."

---



# /guardian — 统一安全守护



整合编辑限制、破坏性命令警告、解除限制三大能力为单一入口。



## 子命令解析



根据用户输入的参数或关键词匹配子命令：



| 子命令 | 触发词 | 功能 |

|--------|--------|------|

| `freeze [dir]` | "freeze", "冻结", "限制编辑", "restrict" | 限制编辑到指定目录 |

| `unfreeze` | "unfreeze", "解冻", "解除限制", "unlock" | 解除编辑限制 |

| `careful` | "careful", "小心模式", "safety", "谨慎" | 启用破坏性命令警告 |

| `status` | "status", "状态", 无参数 | 显示当前守护状态 |



**无参数时**: 显示当前状态，然后询问用户要启用哪个模式。



## freeze — 限制编辑范围



询问用户要限制编辑到哪个目录：



- 使用 AskUserQuestion: "哪个目录应该限制编辑？此路径外的文件将被阻止编辑。"

- 文本输入模式 — 用户输入路径



用户提供路径后：



1. 解析为绝对路径：

```bash

FREEZE_DIR=$(cd "<user-provided-path>" 2>/dev/null && pwd)

echo "$FREEZE_DIR"

```



2. 确保尾部斜杠并保存到状态文件：

```bash

FREEZE_DIR="${FREEZE_DIR%/}/"

STATE_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.gstack}"

mkdir -p "$STATE_DIR"

echo "$FREEZE_DIR" > "$STATE_DIR/freeze-dir.txt"

echo "Freeze boundary set: $FREEZE_DIR"

```



告知用户: "**Guardian freeze 已激活** — 编辑限制为 `<path>/`。使用 `/guardian unfreeze` 解除。"



## unfreeze — 解除编辑限制



```bash

STATE_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.gstack}"

if [ -f "$STATE_DIR/freeze-dir.txt" ]; then

  PREV=$(cat "$STATE_DIR/freeze-dir.txt")

  rm -f "$STATE_DIR/freeze-dir.txt"

  echo "Freeze boundary cleared (was: $PREV). Edits are now allowed everywhere."

else

  echo "No freeze boundary was set."

fi

```



告知用户解除结果。



## careful — 破坏性命令警告



告知用户: "**Guardian careful 已激活** — 以下命令执行前会发出警告："



| 模式 | 示例 | 风险 |

|------|------|------|

| `rm -rf` | `rm -rf /var/data` | 递归删除 |

| `DROP TABLE/DATABASE` | `DROP TABLE users;` | 数据丢失 |

| `TRUNCATE` | `TRUNCATE orders;` | 数据丢失 |

| `git push --force` | `git push -f origin main` | 历史重写 |

| `git reset --hard` | `git reset --hard HEAD~3` | 未提交工作丢失 |

| `kubectl delete` | `kubectl delete pod` | 生产影响 |

| `docker rm -f` / `docker system prune` | `docker system prune -a` | 容器/镜像丢失 |



安全例外 (不警告): `rm -rf node_modules/.next/dist/__pycache__/.cache/build/.turbo/coverage`



## status — 显示当前状态



```bash

STATE_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.gstack}"

echo "=== Guardian Status ==="

if [ -f "$STATE_DIR/freeze-dir.txt" ]; then

  echo "Freeze: ACTIVE — $(cat "$STATE_DIR/freeze-dir.txt")"

else

  echo "Freeze: INACTIVE"

fi

echo "Careful: ACTIVE (session-scoped, always on when /guardian is loaded)"

echo "========================"

```



## 工作原理



- **freeze** 通过状态文件 (`freeze-dir.txt`) 持久化，hook 在每次 Edit/Write 时检查

- **careful** 通过 session-scoped hook 在每次 Bash 命令时检查

- 两者独立运作，互不依赖

- hook 脚本复用 `careful/bin/check-careful.sh` 和 `freeze/bin/check-freeze.sh`



## 注意事项



- freeze 仅限制 Edit/Write 工具 — Read、Bash、Glob、Grep 不受影响

- careful 防止意外操作，不是安全边界 — 用户可以 override 每个警告

- 会话结束时所有守护自动解除

- 依赖 `careful/` 和 `freeze/` 目录下的 hook 脚本

