---
name: ssl-acme-dns-manual
description: >
  SSL certificate issuance when HTTP challenges are blocked by L4 proxy/firewall.
  Uses acme.sh with DNS manual verification as fallback. Covers: certbot failures,
  L4 proxy 403, standalone mode, acme.sh install, DNS TXT records, cert install.
  Trigger: SSL证书失败, certbot 403, acme.sh, L4代理阻挡, DNS验证
maturity: stable
cost_level: medium
---

# SSL 证书 — 绕过 L4/防火墙的 DNS 验证方案

## 适用场景

当 certbot webroot/standalone 反复失败且报以下错误时：
- `YOUR_SERVER_IP: Invalid response ... 403`
- `Connection refused`（L4 代理关闭时）
- Rate limit hit after 5 failed attempts

根因：L4 代理（Nginx stream）在 YOUR_SERVER_IP 拦截 HTTP 请求，
Let's Encrypt 验证流量无法直达目标服务器 YOUR_SERVER_IP:80。

## 解决方案：acme.sh + DNS 手动验证

### 1. 安装 acme.sh

```bash
curl -s https://get.acme.sh | sh -s email=your@email.com
```

### 2. 发起 DNS 验证

```bash
/root/.acme.sh/acme.sh --issue --dns \
  -d domain.com -d www.domain.com \
  --yes-I-know-dns-manual-mode-enough-go-ahead-please
```

输出会给出需要添加的 TXT 记录。

### 3. DNS 添加 TXT 记录

去阿里云/腾讯云 DNS 控制台添加：
- 主机记录: `_acme-challenge`
- 记录类型: `TXT`
- 记录值: （acme.sh 输出的值）

验证生效：
```bash
nslookup -type=TXT _acme-challenge.domain.com
```

### 4. 签发证书

```bash
/root/.acme.sh/acme.sh --renew \
  -d domain.com -d www.domain.com \
  --yes-I-know-dns-manual-mode-enough-go-ahead-please
```

### 5. 安装到 nginx

```bash
/root/.acme.sh/acme.sh --install-cert -d domain.com \
  --key-file /etc/letsencrypt/live/domain.com/privkey.pem \
  --fullchain-file /etc/letsencrypt/live/domain.com/fullchain.pem \
  --reloadcmd "nginx -s reload"
```

### 6. 自动续期

acme.sh 安装时自动添加 cron 任务 (`/root/.acme.sh/acme.sh --cron`)，
但 DNS manual mode 需要每次手动添加 TXT 记录。

## 常见陷阱

| 陷阱 | 现象 | 解决 |
|------|------|------|
| L4 代理拦截 | certbot webroot 报 403 | 用 DNS 验证 |
| L4 nginx 关闭 | standalone 报 Connection refused | DNS 指向 L4，不能关 |
| Rate limit | `too many failed authorizations (5)` | 等 1 小时或换域名 |
| Post-hook 报错 | `nginx.service is not active` | 忽略，systemd 问题非 nginx 问题 |
| 证书是自签 | issuer=CN=domain.com | 检查 `/root/.acme.sh/domain_ecc/` |

## 自签证书（临时方案）

```bash
mkdir -p /etc/letsencrypt/live/domain.com
openssl req -x509 -nodes -days 90 -newkey rsa:2048 \
  -keyout /etc/letsencrypt/live/domain.com/privkey.pem \
  -out /etc/letsencrypt/live/domain.com/fullchain.pem \
  -subj "/CN=domain.com"
```

## certbot 已失败的方法（避免重复尝试）

- ✗ webroot — L4 代理 403
- ✗ standalone — L4 代理拦截，DNS 指向 L4
- ✗ BT 面板 acme — Python 3.8 依赖冲突
