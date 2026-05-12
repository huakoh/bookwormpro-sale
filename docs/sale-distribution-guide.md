# BookwormPRO Sale Distribution Guide

## Overview

Sale 分发版通过三层保护确保 IP 安全：

| 层 | 技术 | 保护对象 |
|---|---|---|
| Cython 编译 | .py → .pyd/.so | 6 核心模块源码 |
| AES-256-GCM 加密 | SKILL.md → .skill.enc | 135 技能文件 |
| Ed25519 签名 License | HWID + 有效期 + 签名 | 防拷贝/防篡改 |

---

## 发行方操作手册

### 1. 环境准备

```bash
pip install cython cryptography
```

**C 编译器：**
- Windows: MSVC Build Tools (`publish-sale.ps1` 自动加载 vcvars64)
- Linux: `apt install build-essential`
- macOS: `xcode-select --install`

### 2. 首次设置 (仅一次)

```bash
# 生成 Ed25519 密钥对
python scripts/generate_license.py keygen --output-dir keys

# 输出:
#   keys/private.key  — 私钥 (离线保管，绝不泄露)
#   keys/public.key   — 公钥
#   公钥 Base64: YIvc...l4w=
```

公钥 Base64 已嵌入 `agent/skill_crypto.py` 的 `_LICENSE_PUBLIC_KEY_B64`。
如需更换密钥对，替换该值并重新发布。

> **私钥安全：** `keys/` 已在 `.gitignore` 中，备份到离线存储后可删除本地副本。

### 3. 为客户签发 License

```bash
# 客户先运行此命令获取 HWID
bookworm license hwid
# 输出: Machine HWID: 24afab...4ac71c

# 发行方签发 (替换 HWID 和到期日)
python scripts/generate_license.py issue \
    --licensee "客户公司名" \
    --hwid <客户提供的HWID> \
    --tier pro \
    --expires 2027-06-01 \
    --aes-key "your-aes-key-at-least-16ch" \
    --private-key keys/private.key \
    --output customer.license
```

License 文件格式 (JSON):
```json
{
  "licensee": "客户公司名",
  "hwid": "sha256-hex-64位",
  "tier": "pro",
  "expires": "2027-06-01",
  "key": "aes-key-material",
  "signature": "ed25519-base64-签名"
}
```

### 4. 构建并发布 Sale 仓

**Windows:**
```powershell
.\scripts\publish-sale.ps1 -LicenseKey "your-aes-key-at-least-16ch"

# 预览模式 (不实际执行)
.\scripts\publish-sale.ps1 -LicenseKey "your-aes-key" -DryRun
```

**Linux/macOS:**
```bash
./scripts/publish-sale.sh --license-key "your-aes-key-at-least-16ch"

# 预览模式
./scripts/publish-sale.sh --license-key "your-aes-key" --dry-run
```

流水线 6 步：
1. 检查环境 (Python + Cython + cryptography + C compiler)
2. 创建临时 `sale-build` 分支
3. 脱敏 (删除内部文档 + 替换敏感 URL)
4. Cython 编译 6 核心模块
5. AES-256 加密 135 SKILL.md
6. 提交并推送到 `sale` remote

> **AES Key 一致性：** `publish-sale` 的 `--license-key` 必须与 `issue` 的 `--aes-key` 一致。

### 5. 验证 License

```bash
python scripts/generate_license.py verify customer.license --public-key keys/public.key
```

---

## 客户操作手册

> 在线版: https://portable.bookwormweb.com/quick-start

### 0. 前置条件

| 依赖 | 说明 |
|------|------|
| **Git** | 必须预装。Windows: `winget install Git.Git` |
| **AI API Key** | 任一 Provider 的 Key。推荐 [DeepSeek](https://platform.deepseek.com) (支付宝充值 1 元起) |

Python、Node.js、ripgrep、ffmpeg 等由安装脚本自动处理。

### 0.5 清理旧版本 (如有)

```powershell
# 有 bookworm 命令的:
bookworm uninstall

# 没有 uninstall 命令 (早期版本):
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\bookworm","$HOME\.bookwormpro","$HOME\.hermes" -ErrorAction SilentlyContinue
```

清理后重开终端。

### 1. 安装 BookwormPRO

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/huakoh/bookwormpro-sale/master/scripts/install.ps1 | iex
```

**Linux / macOS / WSL2:**
```bash
curl -fsSL https://raw.githubusercontent.com/huakoh/bookwormpro-sale/master/scripts/install.sh | bash
```

安装完成后**关闭并重新打开终端**，验证:
```bash
bookworm version
# 应输出: BookwormPRO v7.0.0
```

### 2. 配置 AI 模型

```bash
bookworm setup --quick    # 快速模式，30 秒完成
bookworm setup model      # 或只配置模型
```

向导中选择 Provider 并填入 API Key。支持 28 个 Provider (DeepSeek / Anthropic / OpenAI / Gemini / Kimi 等)。

### 3. 激活

**方式 A: 免费试用 7 天**
```bash
bookworm trial
```
无需注册，每台机器可试用一次 (HWID 绑定)。

**方式 B: 激活正式 License**

```bash
# 1. 获取机器 HWID
bookworm license hwid
# 输出: Machine HWID: 24afab...4ac71c (发送给供应商)

# 2. 收到 .license 文件后激活
bookworm activate /path/to/your.license

# 3. 确认激活状态
bookworm license status
```

### 4. 开始使用

```bash
bookworm              # 经典 CLI 模式
bookworm --tui        # 图形化 TUI (鼠标支持)
bookworm --continue   # 继续上次会话
```

进入对话后直接用中文描述需求，AI 自动匹配技能。

### 5. 常用命令

| 命令 | 用途 |
|------|------|
| `bookworm setup` | 完整配置向导 |
| `bookworm setup model` | 只改 AI 模型 |
| `bookworm setup gateway` | 配置消息平台 (Telegram/微信等) |
| `bookworm gateway start` | 启动 Gateway |
| `bookworm license status` | 查看 License 状态 |
| `bookworm license hwid` | 查看机器指纹 |
| `bookworm license deactivate` | 移除 License |
| `bookworm canary` | 快速烟雾测试 (无网络) |
| `bookworm canary --live` | 烟雾测试 + API 连通验证 |
| `bookworm doctor` | 完整诊断报告 |
| `bookworm update` | 更新到最新版本 |
| `bookworm uninstall` | 卸载 BookwormPRO |
| `bookworm dump` | 生成调试摘要 (发给技术支持) |

### 6. 环境变量方式 (可选)

不使用 license 文件，直接设置环境变量：

```bash
# Linux/macOS
export BOOKWORMPRO_LICENSE_KEY="your-aes-key"

# Windows PowerShell
$env:BOOKWORMPRO_LICENSE_KEY = "your-aes-key"
```

> 优先级: 环境变量 > .license 文件

---

## 技术细节

### 加密规格

| 参数 | 值 |
|------|-----|
| 算法 | AES-256-GCM |
| Key 派生 | PBKDF2-HMAC-SHA256, 600,000 iterations |
| Salt | 16 bytes, 每文件随机 |
| Nonce | 12 bytes, 每文件随机 |
| Wire Format | `[1B version][16B salt][12B nonce][ciphertext+tag]` |

### HWID 采集

| 平台 | 采集源 (按优先级) |
|------|---|
| Windows | CIM Win32_ComputerSystemProduct UUID → 注册表 MachineGuid → uuid.getnode |
| Linux | /etc/machine-id → /var/lib/dbus/machine-id → uuid.getnode |
| macOS | ioreg IOPlatformUUID → uuid.getnode |
| 辅助 | 首个真实 MAC 地址 (排除虚拟网卡) |

最终 HWID = `SHA-256(primary|mac:hex)` 的 64 位 hex digest。

### License 签名

- 算法: Ed25519
- 签名范围: `{licensee, hwid, tier, expires, key}` 的 canonical JSON (sorted keys, no whitespace)
- 验签: 运行时内嵌公钥，离线验证，无需网络

### Cython 编译目标

| 模块 | 保护内容 |
|------|---------|
| `agent/prompt_builder.py` | 系统提示构建逻辑 |
| `agent/skill_preprocessing.py` | SKILL.md 模板引擎 |
| `agent/context_compressor.py` | 上下文压缩算法 |
| `agent/prompt_caching.py` | 提示缓存策略 |
| `agent/redact.py` | 输出脱敏规则 |
| `agent/skill_crypto.py` | 加解密 + license 验证 |

---

## 故障排查

### 安装阶段

| 症状 | 原因 | 解决 |
|------|------|------|
| `irm ... 404` | sale 仓 Private 或分支名错误 | 确认仓库 Public + URL 用 `/master/` 不是 `/main/` |
| `Repository not found` (HTTPS clone) | install.ps1 仓库 URL 未替换 | 必须先跑 `publish-sale.ps1` 构建，不能手动复制 install.ps1 |
| 安装卡住不动 | tinker-atropos 拉 PyTorch (~2GB) | 最新 install.ps1 已跳过此步 |
| `No module named 'yaml'` / `'dotenv'` | `uv pip install -e .` 静默失败 | install.ps1 安全网已覆盖 12 个核心包；手动: `python -m pip install pyyaml python-dotenv` |
| `No module named 'bwm_cli'` | sale 仓缺少应用代码 | 必须跑 `publish-sale.ps1` 构建完整 sale 仓 |
| `SyntaxError: invalid character '─'` | Cython .pyd 是 cp312 但 venv 是 3.11 | install.ps1 的 `$PythonVersion` 必须与构建时的 Python 版本一致 |
| `bookworm: not recognized` | PATH 未生效 | 关闭终端重新打开。仍不行: `$env:PATH += ";$env:LOCALAPPDATA\bookworm\bookwormpro\venv\Scripts"` |

### 运行阶段

| 症状 | 原因 | 解决 |
|------|------|------|
| `'gbk' codec can't decode` | 中文 Windows 默认 GBK 编码 | `[Environment]::SetEnvironmentVariable("PYTHONUTF8","1","User")` 后重开终端 |
| `HTTP 401: Authentication Fails` | API Key 无效/过期/粘贴重复 | 检查 `$env:LOCALAPPDATA\bookworm\.env` 中 Key 是否正确且只出现一次 |
| `ValueError: unexpected '{'` | setup summary 格式化 bug | 不影响功能，忽略即可 |
| `UnboundLocalError: '_'` | setup wizard i18n bug | 绕过: 直接编辑 `.env` 文件配置 Key |
| `License required for skill` | 未激活或 key 错误 | `bookworm activate <file>` 或 `bookworm trial` |
| `HWID mismatch` | 换了机器或虚拟机 | 重新运行 `bookworm license hwid` 联系供应商 |
| `License expired` | 过期 | 联系供应商续期 |
| Skills 列表为空 | 加密文件存在但无法解密 | 检查 license 状态: `bookworm license status` |

---

## 发行方避坑指南 (2026-05-12 实测总结)

> 以下所有坑均来自首次真机装机测试，已逐一修复。

### 1. 必须跑 publish-sale.ps1，不能手动同步

sale 仓与主仓是**完全不同的代码**。`publish-sale.ps1` 负责:
- 脱敏 (删内部文档 + 替换敏感 URL)
- Cython 编译 6 核心模块 → .pyd
- AES-256 加密 135 SKILL.md → .skill.enc
- 替换 install.ps1 中的仓库 URL (`BookwormPRO` → `bookwormpro-sale`)
- 推送到 sale remote

**手动复制 install.ps1 到 sale 仓会导致仓库 URL 未替换 → 客户克隆私有仓 → 404。**

### 2. Python 版本必须对齐

Cython `.pyd` 绑定 Python minor version (`cp312` 只能在 3.12 上加载)。
代码中 f-string 嵌套语法也要求 3.12+。

| 环节 | 必须一致 |
|------|---------|
| `build_sale.py` 构建环境 | Python 3.12 |
| `install.ps1` 中 `$PythonVersion` | `"3.12"` |
| 客户机 venv | Python 3.12 (由 uv 自动安装) |

### 3. sale 仓分支是 master

sale 仓默认分支是 `master`，`build_sale.py` 推送目标是 `sale-build:master`。
所有 raw.githubusercontent.com URL 必须用 `/master/` 而不是 `/main/`。

### 4. 中文 Windows GBK 编码

中文 Windows 的 Python 默认 GBK 编码，遇到 UTF-8 文件会报 `UnicodeDecodeError`。
install.ps1 应在创建 venv 后自动设置 `PYTHONUTF8=1`。

### 5. 发布 checklist

每次发布新版本前:

```
1. [ ] 构建: .\scripts\publish-sale.ps1 -LicenseKey "xxx"
2. [ ] 验证 Python 版本对齐 (3.12)
3. [ ] 验证 sale 仓 install.ps1 中 URL 指向 bookwormpro-sale
4. [ ] 验证 sale 仓 install.ps1 中 $Branch = "master"
5. [ ] 验证 sale 仓 Public 可见
6. [ ] 全新机器测试: irm ... | iex → bookworm version → bookworm trial → bookworm
7. [ ] 部署落地页: scp landing.html + quick-start.html 到服务器
```
