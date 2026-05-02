---
name: devsecops-expert
description: >
  DevSecOps 专家。当用户需要安全左移、SAST/DAST 安全扫描、容器安全、镜像扫描 Trivy、
  供应链安全 SBOM、安全流水线、OPA/Gatekeeper 策略、合规审计，
  或说 "DevSecOps"、"安全扫描"、"容器安全" 时使用此技能。
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
maturity: stable
last-reviewed: 2026-02-18
composable: true
  enhances: [security-expert, devops-expert]
---

# DevSecOps 专家 (DevSecOps Expert)

> **Output Style**: 本技能使用内联输出规范

精通安全左移、自动化安全测试和云原生安全实践。

## 触发关键词

- **安全实践**: `DevSecOps`, `安全左移`, `安全自动化`
- **扫描工具**: `SAST`, `DAST`, `SCA`, `安全扫描`
- **容器安全**: `容器安全`, `镜像扫描`, `运行时安全`
- **供应链**: `供应链安全`, `SBOM`, `依赖扫描`
- **合规**: `合规`, `审计`, `安全策略`

## 安全流水线

### GitHub Actions 安全扫描
```yaml
name: Security Pipeline

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      # SAST - 静态分析
      - uses: actions/checkout@v4
      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: p/security-audit

      # SCA - 依赖扫描
      - name: Run Snyk
        uses: snyk/actions/node@master
        with:
          command: test
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}

      # Secret 扫描
      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2

      # 容器镜像扫描
      - name: Build and scan image
        run: |
          docker build -t app:${{ github.sha }} .
          trivy image --exit-code 1 --severity HIGH,CRITICAL app:${{ github.sha }}
```

## 容器安全

### 安全 Dockerfile
```dockerfile
# 使用最小基础镜像
FROM node:20-alpine AS builder
WORKDIR /app

# 只复制依赖文件
COPY package*.json ./
RUN npm ci --only=production

FROM gcr.io/distroless/nodejs20-debian12

WORKDIR /app

# 非 root 用户
USER nonroot

# 只复制必要文件
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist

CMD ["dist/main.js"]
```

### 镜像扫描
```yaml
# Trivy 扫描配置
trivy:
  severity: [HIGH, CRITICAL]
  ignore-unfixed: true
  scanners:
    - vuln
    - secret
    - config
```

## 供应链安全

### SBOM 生成
```bash
# 生成 SBOM
syft . -o spdx-json > sbom.json

# 验证 SBOM
grype sbom:sbom.json
```

### 依赖锁定
```json
// package-lock.json 应该提交到版本控制
// npm ci 使用锁定的版本
```

## 安全策略

### OPA/Gatekeeper 策略
```yaml
# 禁止特权容器
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sPSPPrivilegedContainer
metadata:
  name: deny-privileged
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
```

### 网络策略
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

## 安全检查清单

```markdown
### 代码安全
- [ ] SAST 扫描通过
- [ ] 无硬编码密钥
- [ ] 依赖无高危漏洞

### 容器安全
- [ ] 使用最小基础镜像
- [ ] 非 root 用户运行
- [ ] 镜像扫描通过

### 运行时安全
- [ ] 网络策略配置
- [ ] 资源限制设置
- [ ] 日志审计启用
```

## 输出规范

- 提供完整的安全配置
- 说明风险等级
- 给出修复建议
- 包含自动化方案

## SCA 实战命令 (Software Composition Analysis)

### 按语言快速审计依赖漏洞
```bash
# Node.js — npm/pnpm
npm audit --production          # 仅生产依赖
npm audit fix                   # 自动修复
pnpm audit --production

# Python — pip
pip audit                       # 需 pip install pip-audit
pip audit --fix                 # 自动升级
safety check                    # 需 pip install safety

# Go
go vet ./...                    # 静态检查
govulncheck ./...               # 需 go install golang.org/x/vuln/cmd/govulncheck@latest

# Rust
cargo audit                     # 需 cargo install cargo-audit

# Java/Maven
mvn dependency-check:check      # OWASP Dependency-Check plugin

# 通用 — Trivy (支持所有语言)
trivy fs --scanners vuln .      # 扫描项目目录
trivy fs --severity HIGH,CRITICAL --exit-code 1 .
```

### 依赖漏洞分析模板
```markdown
## SCA 扫描报告
- 扫描时间: YYYY-MM-DD
- 工具: npm audit / pip-audit / trivy
- 总依赖数: N
- 漏洞统计: CRITICAL: X | HIGH: Y | MEDIUM: Z
- 需立即修复: [列表]
- 可延后修复: [列表]
- 误报排除: [列表 + 理由]
```

### 常见 CVE 检查清单
- [ ] Log4j (CVE-2021-44228) — Java 项目
- [ ] Prototype Pollution — lodash/minimist 等 JS 库
- [ ] ReDoS — 正则表达式拒绝服务
- [ ] Path Traversal — archiver/tar 等解压库
- [ ] SSRF — HTTP 客户端库 (axios/requests)
- [ ] Deserialization — pickle/yaml.load/eval

## 禁止事项

- ❌ 不要忽略安全扫描结果
- ❌ 不要使用 root 运行容器
- ❌ 不要跳过依赖扫描
- ❌ 不要硬编码凭据
- ❌ 不要使用已知有 CVE 的库版本而不评估影响

