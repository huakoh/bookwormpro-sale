---
name: bookwormpro-gitbash-deadlock-recovery
description: BookwormPRO 找不到 Git Bash 时的死锁恢复流程。当所有工具报 "Git Bash not found" 时，按此流程引导用户在自有终端手动修复。
triggers:
  - 'Git Bash not found'
  - 'BOOKWORMPRO_GIT_BASH_PATH'
  - 'bookworm status 报 bash 找不到'
  - '所有 terminal/read_file 工具全挂'
  - 'cmd /c 也报 Git Bash not found'
version: 1.0.0
created: 2026-05-01
category: devops
---

# BookwormPRO Git Bash 死锁恢复

## 故障现象
所有工具（terminal / read_file / patch / write_file）统一报：
```
RuntimeError: Git Bash not found. BookwormPRO requires Git for Windows on Windows.
```
此时 AI 端完全瘫痪，**必须引导用户在自有终端手动修复**。

## 死锁原因
BookwormPRO 所有工具都依赖 Git Bash 作为 shell backend。Git Bash 找不到 → 工具全挂 → 连 `cmd /c` 也走不通（因为也是通过同一 shell 路由）。

## 恢复步骤（用户在 MINGW64 / Git Bash 终端执行）

### Step 1: 确认 bash.exe 存在
```bash
ls -la "D:/Git/usr/bin/bash.exe"
# 或查找其他位置
find /c/ -name "bash.exe" -path "*/Git/*" 2>/dev/null
```

### Step 2: 查看并修复 config.env
```bash
cat ~/.bookwormpro/config.env
```

**关键规则: config.env 的值不能带引号！**

错误 ❌:
```
BOOKWORMPRO_GIT_BASH_PATH="D:/Git/usr/bin/bash.exe"
```

正确 ✅:
```
BOOKWORMPRO_GIT_BASH_PATH=D:/Git/usr/bin/bash.exe
```

修复命令:
```bash
cat > ~/.bookwormpro/config.env << 'EOF'
BOOKWORMPRO_GIT_BASH_PATH=D:/Git/usr/bin/bash.exe
EOF
```

### Step 3: 验证
```bash
cat ~/.bookwormpro/config.env
bookworm gateway restart
bookworm status
```

## Windows 路径注意事项

在 Git Bash 中使用 Windows 路径时，用 Unix 风格避免反斜杠被吃：
```bash
# ✅ 正确
python /c/Users/BOOKWORMPRO_USER/BookwormPRO/scripts/hermes-gateway start

# ❌ 错误（反斜杠被 bash 转义吃掉）
python C:\Users\BOOKWORMPRO_USER\BookwormPRO\scripts\hermes-gateway start
```

## Gateway 服务常见状态
- `[错误] 服务已存在` → 已安装，直接 start
- `[错误] 实例已在运行` → 已在跑，无需操作
- 如需管理员权限 → 用 `powershell -Command "Start-Process ... -Verb RunAs"` 提权
