---
name: domain-migration-l4-proxy
description: WordPress 域名迁移全链路：DNS → L4 代理 → Nginx 配置 → SSL 证书 → WordPress 数据替换。适用于使用 L4 透传代理 + 宝塔面板的架构。触发词：域名迁移、换域名、WordPress搬家、replace domain。
maturity: stable
cost_level: high
allowed-tools: Read, Write, Bash, Grep
---

# WordPress 域名迁移 — L4 代理架构

## 前置条件

1. 确认新旧域名的 DNS 解析目标
2. 确认 L4 代理服务器和 A 服务器的角色
3. SSH 访问两台服务器
4. 了解 WordPress 安装在哪个 nginx 实例下（系统 nginx vs BT nginx）

## Phase 0: 环境探查

```bash
# A 服务器：确认哪个 nginx 监听 80/443
netstat -tlnp | grep -E ':80 |:443 '
# 确认 WordPress 路径和 nginx 配置来源
grep -rn 'server_name.*旧域名' /etc/nginx/ /www/server/panel/
```

## Phase 1: DNS + L4 代理

```bash
# L4 服务器 (B)：在 HTTP server_name 列表添加新域名
sed -i 's/旧域名 www.旧域名;/旧域名 www.旧域名 新域名 www.新域名;/' /usr/local/nginx/conf/nginx.conf
/usr/local/nginx/sbin/nginx -t && /usr/local/nginx/sbin/nginx -s reload
```

## Phase 2: A 服务器 Nginx

1. 复制旧域名配置 → 新域名
2. 简化配置（先 HTTP only）
3. 注意 `limit_req_zone` 重复问题（删除重复定义）
4. 注意通配符 `server_name _` 字母序拦截（重命名 catch-all 文件）
5. 不要用 BT panel nginx（路径是 /www/server/panel/vhost/nginx/），用系统 nginx（/etc/nginx/sites-enabled/）

## Phase 3: SSL

**不要用命令行 certbot** —— 在 L4 代理架构下反复失败（ACME 验证 403）。正确做法：
- 宝塔面板 GUI → 网站 → SSL → Let's Encrypt（宝塔有自己的验证机制）
- 或先用自签证书过渡：`openssl req -x509 -nodes -days 90 -newkey rsa:2048 -keyout ... -out ... -subj '/CN=新域名'`

SSL 就位后恢复完整 nginx 配置（listen 443 ssl + 证书路径 + HSTS 等）

## Phase 4: WordPress 域名替换

```bash
# 1. 更新 wp-config.php (最高优先级，会覆盖数据库)
sed -i "s|define('WP_HOME', 'https://旧域名');|define('WP_HOME', 'https://新域名');|" wp-config.php
sed -i "s|define('WP_SITEURL', 'https://旧域名');|define('WP_SITEURL', 'https://新域名');|" wp-config.php

# 2. 数据库批量替换
sudo -u www php -r "
require '/var/www/站点/wp-load.php';
global \$wpdb;
\$wpdb->query(\"UPDATE {\$wpdb->prefix}posts SET post_content = REPLACE(post_content, 'https://旧域名', 'https://新域名')\");
\$wpdb->query(\"UPDATE {\$wpdb->prefix}posts SET guid = REPLACE(guid, 'https://旧域名', 'https://新域名')\");
\$wpdb->query(\"UPDATE {\$wpdb->prefix}postmeta SET meta_value = REPLACE(meta_value, 'https://旧域名', 'https://新域名') WHERE meta_value LIKE '%旧域名%'\");
\$wpdb->query(\"UPDATE {\$wpdb->prefix}options SET option_value = REPLACE(option_value, 'https://旧域名', 'https://新域名') WHERE option_value LIKE '%旧域名%'\");
echo 'DONE';
"

# 3. 清除 WP Fastest Cache
rm -rf wp-content/cache/all/* wp-content/cache/wpfc-minified/*

# 4. 验证
curl -sk https://新域名/ | grep '<title>'
```

## Phase 5: 旧域名处理

- 保留原 nginx 配置（恢复指向原始服务）
- 如果是 Docker 服务，检查容器是否在线：`docker ps | grep 容器名`
- 旧域名 nginx 改回代理到原端口

## 已知陷阱

| 陷阱 | 症状 | 解决 |
|------|------|------|
| PHP-FPM socket 不匹配 | 502 Bad Gateway | 检查 `/tmp/php-cgi-{ver}.sock`，宝塔不用 9000 端口 |
| Nginx 双实例 | 修改的配置不生效 | `netstat -tlnp` 确认哪个 nginx 监听 80/443 |
| **wp-config 硬编码 URL** ⭐ | `update_option(siteurl)` 无效，前端仍显示旧域名 | `grep -n "WP_HOME\|WP_SITEURL" wp-config.php` 找到 `define('WP_HOME', 'https://旧域名')` 并直接修改 |
| **catch-all server_name 拦截 ACME** | Let's Encrypt 验证 403 | 检查 `server_name _;` 配置，重命名为 `z-*.conf` |
| L4 代理 server_name 丢失 | 新域名 HTTP 不可达 | L4 nginx 重启后需重新确认 `/usr/local/nginx/conf/nginx.conf` 中的域名列表 |
| BT panel acme 模块 | Python 依赖错误 | 改用 `acme.sh --dns` 手动验证或 BT panel GUI |
| Docker nginx 进程残留 | 端口被占用 | `pkill -9 nginx` 清理所有实例后重新启动需要的 nginx |
| limit_req_zone 重复 | nginx -t 报 duplicate zone | 删除新配置中的重复定义 |
| wp-config 硬编码 URL | 数据库替换后仍用旧域名 | 优先改 wp-config.php |
| BT nginx 和 系统 nginx 双实例 | 改了配置不生效 | 确认谁在监听 80/443端口 |
| certbot 命令行反复 403 | 限速 + 验证失败 | 用宝塔面板 GUI 申请 |
| system nginx 启动后端口空 | Docker 容器抢端口 | `pkill -9 nginx` 后重试 `/usr/sbin/nginx` |
