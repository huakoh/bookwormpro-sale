---
name: skill-guardian
description: 技能安全守护 — 安装前自动扫描恶意模式、危险命令、敏感数据外泄；高风险技能标记审批；与 guardian/security-expert 整合
version: 1.0.0
author: BookwormPRO (六专家会审产出)
tags: [security, skill-safety, scanner, guardian]
safety:
  level: low
  permissions: [read_file, search_files]
maturity: alpha
cost_level: low
---

# 技能安全守护 (Skill Guardian)

在技能安装前自动安全扫描，阻止恶意技能注入系统。

## 触发条件

- `bookworm skills install` 自动触发
- `bookworm skills audit` 重扫已安装技能
- 用户手动: `/skill-guardian scan <skill-name>`

## 扫描维度

### 1. 危险命令检测 (Critical)
扫描 SKILL.md + references/ + scripts/ 中的：
```
rm -rf /              → CRITICAL: 系统破坏
curl ... | bash       → CRITICAL: 远程代码执行
eval(...)              → HIGH: 动态代码执行
os.system(...)         → HIGH: 系统命令注入
subprocess(..., shell=True) → HIGH: shell注入
~/.ssh/                → MEDIUM: 敏感路径访问
/etc/passwd            → HIGH: 系统文件读取
```

### 2. 数据外泄检测 (High)
```
curl -X POST ... --data   → MEDIUM: 数据上传
webhook.site / requestbin  → HIGH: 已知外泄服务
.env / .bookwormpro/.env   → HIGH: 凭证文件读取
```

### 3. 权限越界检测 (Medium)
技能声明了但不需要的权限：
- 纯文档技能却声明 `terminal`
- 单一功能技能声明 `delegate_task`

## 风险评级

| 等级 | 条件 | 动作 |
|------|------|------|
| CRITICAL | 含 `rm -rf` / `curl|bash` | 自动拒绝 |
| HIGH | 数据外泄 / 系统文件修改 | 需人工审批 |
| MEDIUM | 越界权限 / 可疑 URL | 警告后安装 |
| LOW | 非关键问题 | 自动通过 |
| SAFE | 无任何问题 | 静默通过 |

## 集成方式

与 guardian 协同：
- guardian 负责运行时安全（命令审批、文件保护）
- skill-guardian 负责安装时安全（恶意检测、权限审计）
- 共享 `~/.bookwormpro/security/` 策略文件

## 可信源白名单

```yaml
trusted_sources:
  - anthropics/skills
  - vercel-labs/skills
  - vercel-labs/agent-skills
  - obra/superpowers
```
