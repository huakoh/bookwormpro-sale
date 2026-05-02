---
name: domain-migration-wordpress-l4
description: >
  WordPress 域名迁移全链路：DNS → L4 代理 → Nginx 配置 → SSL 证书 → WordPress 替换。
  适用于多服务器架构（L4 透明代理 + A 服务器），多 Nginx 实例共存环境。
  触发词：域名迁移、更换域名、WordPress 换域名、L4 转发添加域名。
maturity: stable
cost_level: high
---

# WordPress 域名迁移（L4 代理架构）

## 适用场景

- L4 透明代理 (stream proxy) → A 服务器 的架构
- 服务器上存在多个 Nginx 实例 (系统 + 宝塔 + Docker)
- WordPress 站点从旧域名迁移到新域名

## 前置检查

```bash
# 1. DNS 是否已解析
nslookup 新域名.com 8.8.8.8

# 2. 确认 L4 代理架构
ssh L4服务器 "cat /usr/local/nginx/conf/nginx.conf"
# 确认 stream 块配置、HTTP server_name 列表

# 3. 确认 A 服务器 nginx 实例
ssh A服务器 "netstat -tlnp | grep -E ':80 |:443 '"
```

## Step 1: L4 代理添加新域名

在 L4 服务器上：
```bash
# 编辑 stream 或 HTTP 配置
# 1. 443 端口 stream 块 → 如果是全透传模式 (proxy_pass 所有流量)，无需修改
# 2. 80 端口 HTTP 块 → 添加新域名到 server_name 列表

sed -i 's/旧域名 www.旧域名;/旧域名 www.旧域名 新域名 www.新域名;/' nginx.conf
nginx -s reload
```

## Step 2: A 服务器 Nginx 配置

### 陷阱：多 Nginx 实例

```bash
# 先确认谁在监听 80/443
netstat -tlnp | grep -E ':80 |:443 '
readlink -f /proc/PID/exe   # 确认哪个 nginx 二进制
```

### 陷阱：通配符 server_name `_` 拦截

```bash
# 如果存在 catch-all server 块 (server_name _;)，它会拦截新域名
# 确保新域名配置排在 catch-all 之前（字母序）
grep -rn 'server_name _' /etc/nginx/
# 必要时改名：mv catch-all.conf z-catch-all.conf
```

### 陷阱：limit_req_zone 重复

```bash
# 如果复制旧配置，limit_req_zone 不能重复定义
# 解决：删除新配置中的 limit_req_zone 行
```

### 陷阱：SSL 证书引用

```bash
# 新域名还没有证书时，注释 SSL 相关行
sed -i 's/^    ssl_/    #ssl_/g' 新域名.conf
sed -i 's/^    listen 443/    #listen 443/g' 新域名.conf
```

## Step 3: SSL 证书

### 陷阱：Let's Encrypt 限速

- 每域名每小时最多 5 次失败
- 每次失败重置 1 小时倒计时窗口
- **先做 staging dry-run 验证通，再做 production**

```bash
# 先验证
certbot certonly --webroot -w /var/www/letsencrypt -d 新域名.com --dry-run --staging

# 通过后再正式申请
certbot certonly --webroot -w /var/www/letsencrypt -d 新域名.com
```

### 如果 webroot 一直 403

- 检查 nginx access log 看请求命中哪个 server block
- 检查 `root` 路径和权限 (nginx 通常以 www 用户运行)
- 检查是否有 catch-all 通配符拦截

### 应急方案：自签证书

```bash
mkdir -p /etc/letsencrypt/live/新域名.com
openssl req -x509 -nodes -days 90 -newkey rsa:2048 \
  -keyout /etc/letsencrypt/live/新域名.com/privkey.pem \
  -out /etc/letsencrypt/live/新域名.com/fullchain.pem \
  -subj "/CN=新域名.com"
```

拿到正式证书后替换：
```bash
certbot certonly --webroot -w /var/www/letsencrypt -d 新域名.com
```

## Step 4: WordPress 域名替换

### 检查 wp-config.php 硬编码

```bash
grep 'WP_HOME\|WP_SITEURL' wp-config.php
# 如果有 define，直接修改：
sed -i 's|旧域名|新域名|g' wp-config.php
```

### 数据库替换

```php
<?php
require 'wp-load.php';
global $wpdb;
$old = 'https://旧域名.com';
$new = 'https://新域名.com';
$wpdb->query("UPDATE {$wpdb->prefix}posts SET post_content = REPLACE(post_content, '$old', '$new')");
$wpdb->query("UPDATE {$wpdb->prefix}posts SET guid = REPLACE(guid, '$old', '$new')");
$wpdb->query("UPDATE {$wpdb->prefix}postmeta SET meta_value = REPLACE(meta_value, '$old', '$new') WHERE meta_value LIKE '%$old%'");
```

## Step 5: 恢复 SSL 配置

证书拿到后恢复 nginx SSL 配置：
```bash
sed -i 's/#ssl_/ssl_/g' 域名.conf
sed -i 's/#listen 443/listen 443/g' 域名.conf
nginx -t && nginx -s reload
```

## Step 6: 验证

```bash
for p in / /products/ /about/ /contact/; do
  curl -sk -o /dev/null -w "%{http_code}\n" https://新域名.com$p
done
# 全部 200 = 成功
```

## 常见失败模式

| 症状 | 根因 | 修复 |
|------|------|------|
| certbot webroot 一直 403 | catch-all server_name 拦截 | 改名确保字母序在 catch-all 前 |
| nginx -t 报 limit_req_zone 重复 | 复制配置时带了 limit_req_zone | 删除新配置中的 limit_req_zone |
| certbot 报 rate limited | 1 小时内失败超过 5 次 | 等 1 小时，先用 --dry-run --staging |
| HTTPS 000/无法连接 | SSL 配置没有 listen 或证书路径错 | 检查 listen 443 和证书文件存在 |
| curl 本地 200 但外网 403 | L4 代理未重载 | `nginx -s reload` L4 服务器 |
| WordPress 仍显示旧域名 | wp-config.php 硬编码了 WP_HOME | 直接修改 wp-config.php |
