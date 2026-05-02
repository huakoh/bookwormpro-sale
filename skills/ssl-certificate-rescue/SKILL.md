---
name: ssl-certificate-rescue
description: >
  SSL证书获取失败时的兜底方案。当certbot webroot/standalone均失败（403/Connection refused等），
  使用acme.sh+DNS手动验证绕过所有网络层限制。触发词：SSL失败、证书拿不到、certbot 403、acme.sh。
maturity: stable
cost_level: medium
---

# SSL 证书救援方案

当 certbot 的 webroot 和 standalone 模式都失败时，使用 acme.sh DNS 手动验证。

## 常见失败原因

| 失败模式 | 根因 | 症状 |
|---------|------|------|
| L4 代理拦截 | 中间 nginx/HAProxy 拦截 ACME 请求 | certbot webroot → 403 |
| L4 standalone 端口冲突 | L4 自己占用 80 端口 | certbot standalone → Connection refused |
| 宝塔面板 nginx 冲突 | 多 nginx 实例争端口 | nginx 启动失败 |
| Let's Encrypt 限速 | 5次/小时/域名 | "too many failed authorizations" |

## 终极方案: acme.sh DNS 手动验证

### Step 1: 安装 acme.sh

```bash
curl -s https://get.acme.sh | sh -s email=your@email.com
```

### Step 2: 发起 DNS 手动验证

```bash
/root/.acme.sh/acme.sh --issue --dns \
  -d example.com -d www.example.com \
  --yes-I-know-dns-manual-mode-enough-go-ahead-please
```

输出会给出两条 TXT 记录:
```
Domain: '_acme-challenge.example.com'
TXT value: 'sWv2gQ6j8CYI7eBqCPVJ...'
Domain: '_acme-challenge.www.example.com'
TXT value: 'UQxoQB880xFH2NpHhQK...'
```

### Step 3: 用户添加 DNS TXT 记录

在域名 DNS 管理面板（阿里云/腾讯云等）添加:
- 主机记录: `_acme-challenge` → TXT → 记录值
- 主机记录: `_acme-challenge.www` → TXT → 记录值

### Step 4: 验证 DNS 生效

```bash
nslookup -type=TXT _acme-challenge.example.com
```

### Step 5: 签发证书

```bash
/root/.acme.sh/acme.sh --renew \
  -d example.com -d www.example.com \
  --yes-I-know-dns-manual-mode-enough-go-ahead-please
```

### Step 6: 安装到 nginx

```bash
/root/.acme.sh/acme.sh --install-cert -d example.com \
  --key-file /etc/letsencrypt/live/example.com/privkey.pem \
  --fullchain-file /etc/letsencrypt/live/example.com/fullchain.pem \
  --reloadcmd "nginx -s reload"
```

## L4 代理排查

当怀疑 L4 代理拦截时:

```bash
# 在 L4 服务器检查
grep "目标域名" /usr/local/nginx/conf/nginx.conf
# 确保域名在 server_name 列表中
# 确保 /.well-known/acme-challenge/ 有 proxy_pass 到后端

# A 服务器本地测试
echo test > /var/www/letsencrypt/.well-known/acme-challenge/test.txt
curl http://目标域名/.well-known/acme-challenge/test.txt -H 'Host: 目标域名'
```

## 限速处理

Let's Encrypt 限速: 5 次失败/小时/域名
- 等 1 小时后再试
- 用 `--dry-run --staging` 先测试
- 不要反复尝试

## nginx 多实例问题

```bash
# 查谁占用端口
netstat -tlnp | grep ':80 |:443 '
# 确认使用的 nginx 二进制
readlink -f /proc/<PID>/exe
# 必要时 kill 所有并重启正确实例
pkill -9 nginx
/usr/sbin/nginx  # 或 /www/server/nginx/sbin/nginx
```
