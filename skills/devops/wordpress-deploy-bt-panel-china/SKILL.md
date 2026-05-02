---
name: wordpress-deploy-bt-panel-china
description: >
  在中国阿里云/腾讯云服务器上部署 WordPress 网站（宝塔面板环境）。
  覆盖：BT Panel 路径适配、MySQL 密码提取与重置、PHP-FPM 配置、
  Nginx 双实例冲突解决、自定义主题开发、Yoast SEO 配置、ICP 合规、
  百度验证、内容脱敏。触发词：WordPress部署、宝塔面板、阿里云建站、
  企业官网、ICP备案、WordPress theme、BT panel。
maturity: stable
cost_level: high
---

# WordPress 部署 — 宝塔面板（中国云服务器）

## 触发条件

- 用户要求在中国云服务器（阿里云/腾讯云）上部署 WordPress
- 服务器安装了宝塔面板（BT Panel / aaPanel）
- 需要中文企业官网，包含 ICP 备案号展示、百度 SEO 等中国特有要求
- 触发词：WordPress部署、宝塔面板、阿里云建站、企业官网、ICP备案

## 前置条件确认

部署前必须确认：
1. SSH 访问（root 或 sudo 用户）
2. 域名已解析到服务器 IP
3. ICP 备案是否已完成（国内服务器必须备案）
4. 用户提供的凭据不可在代码/日志/文件中明文持久化
5. 使用 `paramiko` SSH 库（Windows Git Bash 无 `sshpass`）

```bash
pip install paramiko
```

## Phase 0: 服务器探查

### 0.1 识别宝塔面板环境

```python
# 标准检查
ssh_exec("ls /www/server/ 2>/dev/null")  # 面板目录
ssh_exec("bt default 2>/dev/null | head -10")  # 面板入口信息
```

### 0.2 关键路径映射（宝塔 vs 标准）

| 组件 | 宝塔路径 | 标准路径 |
|------|---------|---------|
| MySQL | `/www/server/mysql/` | `/usr/bin/mysql` |
| PHP | `/www/server/php/{ver}/` | `/usr/bin/php` |
| Nginx | `/www/server/nginx/` | `/usr/sbin/nginx` |
| 网站根目录 | `/www/wwwroot/` (默认) | `/var/www/` |
| PHP-FPM socket | `/tmp/php-cgi-{ver}.sock` | `/run/php/php{ver}-fpm.sock` |
| PHP-FPM 用户 | `www` | `www-data` |
| Nginx vhost | `/www/server/panel/vhost/nginx/` | `/etc/nginx/sites-available/` |

### 0.3 MySQL root 密码提取

宝塔面板将 MySQL root 密码存储在 SQLite 数据库中：

```python
extract_script = """
import sqlite3
db = sqlite3.connect('/www/server/panel/data/default.db')
row = db.execute("SELECT mysql_root FROM config WHERE id=1").fetchone()
print(row[0] if row else 'NOT FOUND')
"""
# 写入服务器 Python 脚本执行，避免 shell 转义问题
ssh_exec("cat > /tmp/extract_pass.py << 'PYEOF'\n" + extract_script + "\nPYEOF")
out, _ = ssh_exec("python3 /tmp/extract_pass.py")
```

如果提取的密码无法连接（可能是加密的），使用服务器 root 权限重置：

```bash
# 停止 MySQL → skip-grant-tables 启动 → 重置密码 → 重启
/etc/init.d/mysqld stop
/www/server/mysql/bin/mysqld_safe --skip-grant-tables --skip-networking &
sleep 4
mysql -u root --socket=/tmp/mysql.sock -e "
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED BY 'NewPassword!@#';
FLUSH PRIVILEGES;"
killall mysqld mysqld_safe
/etc/init.d/mysqld start
```

### 0.4 Nginx 双实例冲突

最常见的陷阱：系统 nginx (`/usr/sbin/nginx`) 和宝塔 nginx (`/www/server/nginx/sbin/nginx`) 同时存在。

```python
# 检查谁在监听 80/443
ssh_exec("netstat -tlnp | grep -E ':80 |:443 '")
# 检查 nginx 二进制路径
ssh_exec("readlink -f /proc/$(pgrep -f 'nginx: master')/exe")
```

**策略：使用系统 nginx（已配置 SSL 和现有站点），修改其配置文件添加 PHP-FPM 支持。**

不要试图切换 nginx 实例，这会影响同服务器上的其他站点。

## Phase 1: WordPress 安装

### 1.1 创建数据库

```sql
CREATE DATABASE IF NOT EXISTS wordpress_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'wp_user'@'localhost' IDENTIFIED BY 'StrongPass!@#';
GRANT ALL PRIVILEGES ON wordpress_db.* TO 'wp_user'@'localhost'; FLUSH PRIVILEGES;
```

MySQL socket 必须是 `/tmp/mysql.sock`（宝塔路径）。

### 1.2 下载 WordPress

```bash
cd /tmp && wget -q https://wordpress.org/latest.tar.gz
tar xzf latest.tar.gz -C /var/www/YOUR_SITE --strip-components=1
chown -R www:www /var/www/YOUR_SITE
```

### 1.3 wp-config.php（关键：避免 shell 转义陷阱）

**不要** 用 shell heredoc 写入 wp-config.php（PHP define 中的引号和特殊字符会被破坏）。

正确方法：
1. 通过 Python 在服务器上写一个小脚本
2. 用 Python 的文件写入功能创建 wp-config.php
3. 即时从 `https://api.wordpress.org/secret-key/1.1/salt/` 获取 salts

```python
salts = ssh_exec("curl -s https://api.wordpress.org/secret-key/1.1/salt/")[0]
config = f"""<?php
define('DB_NAME', 'wordpress_db');
define('DB_USER', 'wordpress_db');
define('DB_PASSWORD', 'pass');
define('DB_HOST', 'localhost:/tmp/mysql.sock');
define('DB_CHARSET', 'utf8mb4');
define('DB_COLLATE', '');
{salts}
$table_prefix = 'wp_';
define('WP_DEBUG', false);
define('FS_METHOD', 'direct');
if (!defined('ABSPATH')) define('ABSPATH', __DIR__ . '/');
require_once ABSPATH . 'wp-settings.php';
"""
# 通过 Python 写入
write_script = f"config = '''{config}'''\nwith open('/var/www/YOUR_SITE/wp-config.php', 'w') as f:\n    f.write(config)"
ssh_exec("cat > /tmp/write_config.py << 'PYEOF'\n" + write_script + "\nPYEOF")
ssh_exec("python3 /tmp/write_config.py")
```

### 1.4 Nginx 配置（支持 PHP-FPM）

关键是 `fastcgi_pass` 指向宝塔的 socket：

```nginx
location ~ \.php$ {
    include fastcgi_params;
    fastcgi_pass unix:/tmp/php-cgi-80.sock;
    fastcgi_index index.php;
    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
    fastcgi_param HTTPS on;
}
```

**重要：`fastcgi_pass` 不要用 `127.0.0.1:9000`**，宝塔 PHP-FPM 默认用 Unix socket！

### 1.5 安装 WordPress

创建 PHP 安装脚本（避免 curl form POST 中的 nonce 问题）：

```php
<?php
define('WP_INSTALLING', true);
require_once '/var/www/YOUR_SITE/wp-load.php';
require_once '/var/www/YOUR_SITE/wp-admin/includes/upgrade.php';
$result = wp_install('网站标题', 'admin_user', 'admin@domain.com', 1, '', 'StrongPass!@#');
echo is_wp_error($result) ? 'ERROR: ' . $result->get_error_message() : 'SUCCESS';
```

```bash
sudo -u www php /tmp/install-wp.php
# 安装完成后立即删除此脚本
rm /tmp/install-wp.php
```

**注意：**
- 必须 `sudo -u www` 因为 PHP-FPM 以 `www` 用户运行
- 不要使用 `wp core install`（WP-CLI 可能未安装，且在 root 下会报错）
- 安装后设置 `WPLANG` 为 `zh_CN`，并下载中文语言包到 `wp-content/languages/`

### 1.6 安装插件

```php
<?php
require_once '/var/www/YOUR_SITE/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin-install.php';
require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
require_once ABSPATH . 'wp-admin/includes/file.php';
require_once ABSPATH . 'wp-admin/includes/misc.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';

// 安装
$upgrader = new Plugin_Upgrader(new Automatic_Upgrader_Skin());
$upgrader->install("https://downloads.wordpress.org/plugin/wordpress-seo.latest-stable.zip");
// 激活
activate_plugin('wordpress-seo/wp-seo.php');
```

## Phase 2: 自定义主题开发

### 2.1 主题文件清单（企业官网标准18文件）

```
YOUR_THEME/
├── style.css              # 主题头 + CSS变量 + 全部样式
├── functions.php          # 主题设置、菜单注册、资源加载
├── header.php             # 页头 + 导航（移动端汉堡菜单）
├── footer.php             # 页脚 + ICP备案号 + 版权
├── index.php              # 回退模板
├── front-page.php         # 首页（Hero + 产品 + 关于 + 新闻）
├── page.php               # 默认页面
├── page-products.php      # 产品中心
├── page-solutions.php     # 解决方案
├── page-about.php         # 关于我们
├── page-news.php          # 新闻动态
├── page-join.php          # 加入我们
├── page-contact.php       # 联系我们
├── page-download.php      # 资料下载
├── single.php             # 单篇文章
├── archive.php            # 归档页
├── template-parts/content.php
├── template-parts/content-none.php
└── inc/customizer.php     # 主题自定义设置
```

### 2.2 CSS 变量设计（品牌色系统）

```css
:root {
    --color-primary: #0a6e8a;
    --color-primary-dark: #085a70;
    --color-primary-light: #0d8aaa;
    --color-primary-lighter: #e6f2f5;
    --color-secondary: #e8a817;
    --color-dark: #0f172a;
    --color-light: #f8fafc;
    /* 间距、阴影等 */
}
```

### 2.3 内容脱敏规则（中国企业官网）

| 信息类型 | 处理方式 |
|---------|---------|
| 团队姓名 | → "博士团队" / "创始团队" / 姓+职务 |
| 财务数据 | → 不体现于官网 |
| 客户/合作方 | → 可使用真实名称（疾控中心、三甲医院等） |
| 专利号 | → 已授权可展示 |
| 电话/地址 | → 400电话和具体地址可展示 |
| 身份证/银行账号 | → NEVER 出现 |

### 2.4 ICP 合规

- 页脚必须展示 ICP 备案号
- 使用 `get_theme_mod('mingyuan_icp')` 可后台自定义
- 百度验证文件通过 nginx 直接返回（不走 PHP）

```nginx
location = /baidu_verify_codeva-XXX.html {
    default_type text/plain;
    return 200 "验证码";
}
```

### 2.5 页面创建与菜单

通过 PHP 脚本批量创建页面并分配模板：

```php
$id = wp_insert_post([
    'post_title' => '产品中心',
    'post_name' => 'products',
    'post_type' => 'page',
    'post_status' => 'publish',
    'meta_input' => ['_wp_page_template' => 'page-products.php'],
]);
```

创建导航菜单并分配到位置：
```php
$menu_id = wp_create_nav_menu('main-menu');
wp_update_nav_menu_item($menu_id, 0, [
    'menu-item-title' => '产品中心',
    'menu-item-url' => home_url('/products'),
    'menu-item-status' => 'publish',
]);
$locations = get_theme_mod('nav_menu_locations');
$locations['primary'] = $menu_id;
set_theme_mod('nav_menu_locations', $locations);
```

## Phase 3: SEO + 缓存

### 3.1 Yoast SEO 配置

```php
update_option('wpseo_website_name', '公司名称');
update_option('wpseo_company_name', '公司全称');
update_option('wpseo_company_or_person', 'company');
update_option('wpseo_enable_xml_sitemap', true);
```

### 3.2 robots.txt（百度 + Google 双爬虫）

```
User-agent: Baiduspider
Allow: /
Crawl-delay: 1

User-agent: Googlebot
Allow: /
Crawl-delay: 0

Sitemap: https://domain.com/sitemap_index.xml
```

### 3.3 Schema.org 结构化数据

在 footer.php 或通过 wp_head 钩子注入 Organization schema。

### 3.4 WP Fastest Cache

```php
update_option('WpFastestCacheStatus', 'on');
update_option('WpFastestCachePreload', 'on');
update_option('WpFastestCacheHtml', 'on');
update_option('WpFastestCacheGzip', 'on');
```

## Phase 4: 安全加固

1. **wp-config.php 安全常量**
```php
define('DISALLOW_FILE_EDIT', true);
define('FORCE_SSL_ADMIN', true);
define('WP_AUTO_UPDATE_CORE', 'minor');
```

2. **Nginx 层面阻断**
```nginx
location = /xmlrpc.php { deny all; return 404; }
location ~* /wp-content/uploads/.*\.php$ { deny all; return 404; }
```

3. **用户枚举防护**：禁用 REST API 用户端点

4. **隐藏 WP 版本**：主题 functions.php 中 `remove_action('wp_head', 'wp_generator')`

## 常见陷阱

| 陷阱 | 症状 | 解决 |
|------|------|------|
| PHP-FPM socket 不匹配 | 502 Bad Gateway | 检查 `/tmp/php-cgi-{ver}.sock`，宝塔不用 9000 端口 |
| Nginx 双实例 | 修改的配置不生效 | `netstat -tlnp` 确认哪个 nginx 监听 80/443 |
| wp-config.php 语法错误 | "unexpected identifier AUTH_KEY" | 用 Python 文件写入，不要用 shell heredoc |
| 文件权限不匹配 | "Permission denied" on wp-config | PHP-FPM 以 `www` 用户运行，非 `www-data` |
| MySQL socket 路径错误 | "Can't connect to MySQL" | 宝塔用 `/tmp/mysql.sock` |
| Permalink 301 重定向 | 页面返回 301 而非 200 | 确保 URL 尾部斜杠与 permalink 结构一致；刷新 rewrite rules |
| delegate_task 超时 | 600s 限制 | 超时后立即检查文件系统（subagent-filesystem-recovery），文件常已写入 |
| shell 命令中的引号 | SyntaxError | 复杂命令写成 Python 脚本文件传到服务器执行 |
| **display_errors = On** | PHP Warning 输出在 HTML 之前，破坏页面渲染（尤其是 wp-login.php 表单完全消失） | 修改 `/www/server/php/{ver}/etc/php.ini` → `display_errors = Off` → `kill -USR2 $(cat php-fpm.pid)` 重载 |
| **安全常量重复定义** | `Warning: Constant FORCE_SSL_ADMIN already defined` 在首页和登录页显示 | 用 `if (!defined('XXX')) { define('XXX', value); }` 包裹；Phase 4 安全加固追加到 wp-config.php 时要检查是否已在前面定义 |
| **Customizer key 命名不一致** | footer 和 contact 页显示不同地址 | 统一使用 `theme_address`（customizer 注册名）和 `mingyuan_address`（简写别名）；在 `theme_info()` 函数中同时设置两个 key |
| **Meta description 不渲染** | Yoast SEO 插件不输出 `<meta name="description">` | 直接在 header.php 的 `wp_head()` 前注入条件 meta 标签：`if (is_page() && !is_front_page()) { echo '<meta name="description" content="...">'; }`

## Phase 5: 代码审查与修复闭环

主题部署完成后，必须运行独立代码审查（见 `requesting-code-review` 技能）。

### 5.1 审查管线

1. **静态安全扫描**（本地 grep 扫描）
   - 硬编码密钥、eval/exec、SQL 注入模式
   - shell 注入、debug 语句残留、缺少转义
   
2. **独立代理审查**（`delegate_task` 分派审查者）
   - FAIL-CLOSED：安全漏洞或逻辑错误 → `passed: false`
   - 重点检查：CSRF nonce、输入转义、WordPress API 正确使用

3. **修复循环**（最多 2 轮）
   - 对每个问题精准修复，不重构
   - 修复后重新打包 → SFTP 上传 → 解压覆盖 → 语法检查 → 验证

### 5.2 WordPress 主题常见审查发现

| 发现 | 严重度 | 修复方式 |
|------|--------|---------|
| 联系表单缺少 `wp_nonce_field()` | 🔴安全 | 添加 nonce + `wp_verify_nonce()` + `sanitize_*()` + `wp_mail()` |
| Customizer 设置名与模板不匹配 | 🟡逻辑 | 统一命名（如 `mingyuan_hero_tagline` → `mingyuan_hero_title`） |
| `echo '<style>'` 内联 CSS | 💡规范 | 改用 `wp_add_inline_style('wp-admin', ...)` + `admin_enqueue_scripts` 钩子 |
| `admin_head` 钩子加载样式 | 💡规范 | 改用 `admin_enqueue_scripts`（确保目标样式表已入队） |

### 5.3 修复部署流程

```python
# 1. 本地验证修复
for f in ['page-contact.php', 'inc/customizer.php', 'functions.php']:
    assert all(keyword in open(f).read() for keyword in expected_keywords[f])

# 2. 打包 → SFTP → 解压覆盖（仅变更文件）
sftp.put(tar_path, '/tmp/theme-fix.tar.gz')
ssh_exec("cd /tmp && tar xzf theme-fix.tar.gz && cp -f theme-fix/*.php /var/www/.../theme/")

# 3. 服务端 PHP 语法检查
ssh_exec("php -l /var/www/.../theme/page-contact.php")

# 4. 功能验证
ssh_exec("curl -sk https://domain.com/contact/ | grep -c 'wp_nonce_field'")
ssh_exec("curl -sk -o /dev/null -w '%{http_code}' https://domain.com/contact/")
```

### 5.4 审查通过标准

- [ ] 静态扫描：0 项严重/高危
- [ ] 独立审查：`security_concerns` + `logic_errors` 均为空数组
- [ ] 修复后重新验证全部 8 页面 HTTP 200
- [ ] 修复后 PHP 语法检查全部通过
- [ ] CSRF nonce 在 HTML 源码中可检测到

---

## Phase 6: 域名迁移 (your-domain.com → your-domain.com 等)

完整迁移涉及三层：DNS → L4 代理 → A 服务器 Nginx → WordPress DB。

### 6.1 DNS 配置

在阿里云/腾讯云 DNS 控制台添加 A 记录：
- `@` → 服务器 IP（或 L4 代理 IP，如 YOUR_SERVER_IP）
- `www` → 同上
- `*`（通配符）→ 同上（可选）

**验证**: `nslookup 新域名 8.8.8.8` 必须返回正确 IP。

### 6.2 L4 代理配置（如有中间层）

如果使用 L4 透明代理（如独立 Nginx stream 转发），需将新域名加入 `server_name` 列表，否则 Let's Encrypt HTTP 验证无法到达后端。

```nginx
# /usr/local/nginx/conf/nginx.conf (L4 代理服务器)
stream {
    server {
        listen 443;
        proxy_pass YOUR_SERVER_IP:443;  # 全透传，不需要 SNI
    }
}
http {
    server {
        listen 80;
        server_name old.com www.old.com new.com www.new.com;  # ← 加新域名
        location /.well-known/acme-challenge/ {
            proxy_pass http://YOUR_SERVER_IP:80;  # 透传 ACME 验证
        }
    }
}
```

**关键**: L4 的 HTTP server_name 列表必须包含新域名，否则 `curl http://新域名/.well-known/...` 返回 444/403。

### 6.3 A 服务器 Nginx 配置

**核心陷阱：catch-all `server_name _` 拦截**

系统 Nginx 的 `sites-enabled/` 目录中可能存在带 `server_name _;` 的配置文件（通配符匹配所有域名）。如果该文件按字母序排在目标域名配置**之前**，所有新域名请求都会被它拦截。

```bash
# 检测
grep -rn 'server_name _' /etc/nginx/sites-enabled/
ls /etc/nginx/sites-enabled/ | sort  # 看字母序

# 修复：将通配符配置重命名到最后
mv /etc/nginx/sites-enabled/catchall.conf \
   /etc/nginx/sites-enabled/z-catchall.conf
/usr/sbin/nginx -s reload
```

**验证 ACME 路径可用**:
```bash
echo 'test123' > /var/www/letsencrypt/.well-known/acme-challenge/test.txt
curl -s http://新域名/.well-known/acme-challenge/test.txt
# 必须返回 "test123"
```

**如果本地返回 200 但 Let's Encrypt 服务器返回 403**：
检查 L4 代理的 nginx 是否已 reload（`/usr/local/nginx/sbin/nginx -s reload`）。
如果 L4 代理的 HTTP server_name 列表没加新域名，LE 验证请求会被默认 server 返回 444/403。

### 6.4 SSL 证书申请

```bash
# 先确保 nginx 正常运行
certbot certonly --webroot -w /var/www/letsencrypt \
    -d 新域名.com -d www.新域名.com \
    --non-interactive --agree-tos --email admin@域名.com

# 如果遭遇 Let's Encrypt 限速（5 次失败/小时）
# 错误: "too many failed authorizations (5)"
# 解决: 等待整点后的下一个重置时间，或先用 --dry-run 验证
```

### 6.5 WordPress 数据库迁移

**双管齐下**：源码默认值 + 数据库已存值都要改。

```python
# 1. 更新 siteurl / home
update_option('siteurl', 'https://新域名.com');
update_option('home', 'https://新域名.com');

# 2. 全局替换 post_content / guid / postmeta / options 中的旧域名
global $wpdb;
foreach (['posts', 'postmeta', 'options'] as $table) {
    $sql = $wpdb->prepare(
        "UPDATE {$wpdb->prefix}{$table} SET ... = REPLACE(..., %s, %s)",
        'https://旧域名.com', 'https://新域名.com'
    );
    $wpdb->query($sql);
}

# 3. 验证剩余引用
$count = $wpdb->get_var(
    "SELECT COUNT(*) FROM {$wpdb->prefix}posts WHERE post_content LIKE '%旧域名.com%'"
);
// 必须为 0
```

### 6.6 旧域名归还

迁移完成后：
- 从 nginx `sites-enabled/` 移除旧域名配置（或改为 301 跳转到新域名）
- 从 L4 代理的 `server_name` 列表移除旧域名（如果不再使用）
- 保留旧 SSL 证书不变（不影响）

**检查旧项目是否还在运行**：
```bash
# 查看原域名 nginx 备份中的 proxy_pass 目标
grep 'proxy_pass' /etc/nginx/sites-available/旧域名.conf.bak*
# 检查那个端口是否还有 Docker 容器在运行
docker ps | grep 端口号
curl -s http://localhost:端口号/ | grep '<title>'
```
真实案例：your-domain.com 迁移到 your-domain.com 后，发现 your-domain.com 原本指向 Docker 容器 `letcareme:8020` 的 Next.js 集团官网——还一直在运行！只需恢复 nginx 配置即可"归还"。

### 6.7 Let's Encrypt 限速处理

certbot 失败有 5 次/小时/域名限制。**每次失败都延长限速窗口**，导致"死亡螺旋"。

**避免策略**：
1. 先用 `--dry-run --staging` 验证，通过后再用生产环境
2. 遇到 5 次失败后，检查 `grep 'retry after' /var/log/letsencrypt/letsencrypt.log` 获取重置时间
3. 重置时间 = 最早失败时间 + 1 小时（而非最后一次）
4. **自签证书作为临时方案**：
   ```bash
   openssl req -x509 -nodes -days 90 -newkey rsa:2048 \
     -keyout /etc/letsencrypt/live/域名/privkey.pem \
     -out /etc/letsencrypt/live/域名/fullchain.pem \
     -subj "/CN=域名"
   ```
   网站立即可用 HTTPS（浏览器会警告），后续通过宝塔面板 GUI 换正式证书。

### 6.8 Docker 容器中的原项目

当旧域名指向 Docker 容器内的 Next.js/React 应用时：
- **源码在镜像内**（`docker inspect` 无 mounts 时），不可直接修改
- **恢复方法**：nginx 配置改回 `proxy_pass http://127.0.0.1:容器端口`
- **修改内容**（如加 sameAs 链接）需重建 Docker 镜像

---\n\n## 交付检查清单

- [ ] 8 个页面全部 HTTP 200
- [ ] SSL 证书有效
- [ ] HSTS 头存在
- [ ] ICP 备案号在页脚
- [ ] 百度验证文件可访问（200）
- [ ] XML Sitemap 可访问（200）
- [ ] robots.txt 可访问（200）
- [ ] 无 WP 版本号泄露
- [ ] xmlrpc.php 返回 404
- [ ] 内容已脱敏（团队姓名→职务、财务数据不体现）
- [ ] 插件已激活：Yoast SEO + Really Simple SSL + WP Fastest Cache
- [ ] 4+ 篇示例文章已发布
- [ ] 导航菜单 8 项完整
- [ ] 代码审查已通过（静态扫描 + 独立代理）
- [ ] 联系表单含 CSRF nonce + 服务端处理

---

## Phase 6: 本地素材库 → WordPress 产品图片上线

当主题中产品/服务页面使用 SVG 图标或 `div.product-placeholder` 占位，而本地素材库（`~/assets` 或桌面存档）中有实物照片时，执行此流程。

### 6.1 素材搜索与匹配

```bash
# 搜索本地资产库中的产品图片
search_files(pattern='vaccine|robot|rfid|sorter|分拨|传输', 
             target='files', path='D:\\assets')
search_files(file_glob='*.{jpg,jpeg,png,webp}', 
             target='files', path='D:\\assets\\05-prints')
```

按文件名语义匹配产品名称，建立映射表：

| 产品 | 匹配关键词 | 预期来源 |
|------|-----------|---------|
| 疫苗系统 | vaccine, sorter, system | dedup/ 或 rollup/ |
| 机器人 | robot, arm, AMR | rollup/ |
| RFID标签 | etag, rfid, 标签 | brochure/electronic-tag/ |

### 6.2 图片压缩优化

**关键问题**：印刷品图片可达 9449×23622px / 38MB，需大幅压缩。

```python
# 服务端压缩（SCP 上传原始文件后执行）
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 绕过超大图反压缩炸弹保护

img = Image.open('/tmp/raw_image.jpg')
w, h = img.size  # 如 9449×23622

# Web 优化：最大宽度 800px，保持宽高比
if w > 800:
    ratio = 800 / w
    img = img.resize((800, int(h * ratio)), Image.LANCZOS)

# 保存为 JPEG，质量 82-85，启用优化
dest = '/var/www/站点/wp-content/themes/xxx/assets/images/product-name.jpg'
img.save(dest, 'JPEG', quality=82, optimize=True)
# 典型结果: 38MB → 254KB, 2400×1333 → 800×444 / 39KB
```

**如果 PIL 拒绝**（`DecompressionBombError`）：
- 先设置 `Image.MAX_IMAGE_PIXELS = None`
- 如果 ImageMagick 也报 `width or height exceeds limit`，用 PIL + max pixels override

### 6.3 上传到主题资源目录

**不要**走 WordPress Media Library（增加数据库开销，且需额外 PHP 脚本）。

直接上传到主题 `assets/images/` 目录：

```bash
# 创建目录
mkdir -p /var/www/站点/wp-content/themes/主题名/assets/images/

# SCP 上传（本地文件 → 服务器）
scp "~/assets/99-archive/dedup-2026-04-25/product_photo.png" \
    root@YOUR_SERVER_IP:/var/www/.../assets/images/product-name.png

# 服务端压缩（大文件）
python3 << 'PYEOF'
from PIL import Image; Image.MAX_IMAGE_PIXELS = None
img = Image.open('/tmp/raw.jpg')
img = img.resize((800, int(img.size[1]*800/img.size[0])), Image.LANCZOS)
img.save('/var/www/.../assets/images/product-name.jpg', 'JPEG', quality=82, optimize=True)
PYEOF
```

### 6.4 替换模板占位符

产品模板中的 SVG 占位符结构：
```html
<div class="product-grid__image">
    <div class="product-placeholder">
        <svg width="120" height="120">...</svg>
    </div>
</div>
```

替换为真实 `<img>` 标签：
```html
<div class="product-grid__image">
    <img src="<?php echo esc_url(get_template_directory_uri()); ?>/assets/images/product-name.jpg" 
         alt="<?php echo esc_attr__('产品中文名', 'theme-slug'); ?>" 
         class="product-image"
         loading="lazy">
</div>
```

**批量替换策略**（Python 正则）：
```python
import re
# 找出所有 product-placeholder 块
pattern = re.compile(
    r'(<div class="product-placeholder">\s*<svg[^>]*>.*?</svg>\s*</div>)',
    re.DOTALL
)
placeholders = pattern.findall(template_content)
# 按索引替换：placeholder[0] → AVITS图, placeholder[1] → AMR图, ...
```

**无实物照片的产品**：保留 SVG 图标占位，不替换。

### 6.5 CSS 配套样式

```css
.product-image {
    width: 100%;
    height: auto;
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    object-fit: cover;
    display: block;
}
.product-grid__image {
    overflow: hidden;
    border-radius: var(--radius-lg);
}
```

注入位置：`.product-grid {` 之前。

### 6.6 验证清单

```bash
# 1. 图片可访问性
for img in product-avits.png product-amr-robot.jpg; do
  curl -sk -o /dev/null -w '%{http_code}' \
    "https://域名/wp-content/themes/主题/assets/images/$img"
done  # 全部应返回 200

# 2. 产品页 HTML 含 img 标签
curl -sk https://域名/products/ | grep -c 'product-image'

# 3. 清除缓存 + 全页验证
rm -rf /var/www/站点/wp-content/cache/all/*
for p in / /products/ /about/ /contact/; do
  curl -sk -o /dev/null -w "%{http_code}\n" "https://域名$p"
done  # 8 页全 200, 0 warnings
```

### 6.7 典型优化结果

| 来源 | 原始尺寸 | 原始大小 | Web 尺寸 | Web 大小 | 压缩比 |
|------|---------|---------|---------|---------|-------|
| 实物照片 PNG | ~2000px | 825KB | 不变 | 825KB | 1:1 (PNG) |
| 微信照片 JPG | 2400×1333 | 1.7MB | 800×444 | 39KB | 43:1 |
| 印刷展架 JPG | 9449×23622 | 38.2MB | 800×1999 | 254KB | 150:1 |
| 宣传册 SVG | - | 406KB | 不变 | 406KB | 1:1 (矢量)
