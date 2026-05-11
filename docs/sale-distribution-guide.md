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

### 1. 安装 BookwormPRO

```bash
# 从 sale 仓安装 (仓库 URL 已在 install 脚本中替换)
./scripts/install.sh
```

### 2. 获取机器 HWID

```bash
bookworm license hwid
# 输出: Machine HWID: 24afab...4ac71c
# 将此值发送给供应商
```

### 3. 激活 License

收到供应商发来的 `.license` 文件后：

```bash
bookworm activate /path/to/your.license
```

输出：
```
┌─────────── Activation Successful ───────────┐
│ License activated                           │
│   Licensee:  Your Company                   │
│   Tier:      pro                            │
│   Expires:   2027-06-01                     │
│   Installed: ~/.bookwormpro/.license        │
└─────────────────────────────────────────────┘
```

### 4. 查看 License 状态

```bash
bookworm license status
```

### 5. 其他命令

```bash
bookworm license hwid          # 查看机器指纹
bookworm license deactivate    # 移除 license
```

### 6. 环境变量方式 (可选)

不使用 license 文件，直接设置环境变量：

```bash
export BOOKWORMPRO_LICENSE_KEY="your-aes-key"
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

| 症状 | 原因 | 解决 |
|------|------|------|
| `License required for skill` | 未激活或 key 错误 | `bookworm activate <file>` |
| `HWID mismatch` | 换了机器或虚拟机 | 重新运行 `bookworm license hwid` 联系供应商 |
| `License expired` | 过期 | 联系供应商续期 |
| `Invalid license signature` | 文件被篡改 | 重新获取原始 license 文件 |
| Skills 列表为空 | 加密文件存在但无法解密 | 检查 license 状态: `bookworm license status` |
