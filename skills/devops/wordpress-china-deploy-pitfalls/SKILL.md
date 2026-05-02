---
name: wordpress-china-deploy-pitfalls
description: >
  WordPress站点面向中国用户部署时的关键陷阱与解决方案。
  当用户需要在中国服务器部署WordPress、面向中国用户建站、或站点在中国出现渲染异常时使用。
  触发词: WordPress中国、阿里云部署、网站被墙、字体加载慢、CSS不渲染。
allowed-tools: Read, Write, Edit, Bash, Grep
maturity: stable
last-reviewed: 2026-05-01
---

# WordPress 中国部署关键陷阱

面向中国用户的WordPress站点需要避开多个特有的技术陷阱，否则会导致页面完全无法渲染。

## 陷阱1: Google Fonts 阻塞CSS渲染 (最严重)

**症状**: 网站HTML正常返回200，但CSS完全不加载，页面呈现纯文本堆叠、无样式、布局破碎。

**根因**: `fonts.googleapis.com` 在中国大陆被完全屏蔽。如果在 `functions.php` 中将Google Fonts设为theme stylesheet的依赖 (`array('google-fonts-handle')`)，则CSS会等待字体加载超时后才渲染。超时时间通常30秒以上，用户看到的始终是破碎页面。

**检测**:
```bash
curl -sk https://目标站/ | grep -c fonts.googleapis.com
```
若返回值 > 0，立即修复。

**P0修复方案 - 系统字体栈** (推荐):
```php
// functions.php - 替换Google Fonts
wp_register_style('theme-fonts', false);
wp_enqueue_style('theme-fonts');
wp_add_inline_style('theme-fonts',
    ':root {'
    . '--font-body: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", sans-serif;'
    . '--font-heading: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", serif;'
    . '}'
    . 'body { font-family: var(--font-body); }'
    . 'h1,h2,h3,h4,h5,h6,.site-title { font-family: var(--font-heading); }'
);

// 主样式表 - 移除Google Fonts依赖！
wp_enqueue_style('theme-style', get_template_directory_uri() . '/style.css', array(), '1.0.0');
```

**关键**: `array()` 而非 `array('google-fonts')`。CSS必须独立加载，不依赖任何被墙资源。

**备选方案 - 自托管字体**: 下载Noto Sans SC woff2文件到 `/assets/fonts/`，用 `@font-face` 本地加载。适用于必须使用特定字体的项目。

**验证**: 修复后 `grep -c fonts.googleapis.com` 必须返回0。

---

## 陷阱2: 任何境外CDN资源都可能被墙

不仅是Google Fonts，以下服务在中国均不稳定或不可用:
- `fonts.googleapis.com` - 被墙
- `ajax.googleapis.com` - 被墙
- `cdnjs.cloudflare.com` - 极慢
- `unpkg.com` - 不稳定
- `jsdelivr.net` - 曾可用，2023年后不稳定
- Gravatar (`*.gravatar.com`) - 极慢

**修复**: wp-config.php 中禁用Gravatar:
```php
add_filter('get_avatar', function() { return ''; });
```

或在主题中替换所有外部CDN引用为本地托管或国内CDN。

---

## 陷阱3: PHP display_errors=On 导致Warning输出破坏页面

**症状**: 页面顶部出现 `Warning: Constant XXX already defined in /path/to/file.php on line N`，登录页表单消失。

**根因**: 宝塔面板 (BT Panel) 的PHP默认 `display_errors = On`。

**修复**:
```bash
sed -i 's/^display_errors = On/display_errors = Off/' /www/server/php/80/etc/php.ini
kill -USR2 $(cat /www/server/php/80/var/run/php-fpm.pid)
```

**验证**: `grep '^display_errors' php.ini` 必须显示 `Off`。

---

## 陷阱4: wp-config.php 安全常量重复定义

**症状**: 同上 - Warning: Constant XXX already defined。

**根因**: 多次向wp-config.php追加安全设置时，可能重复定义 `DISALLOW_FILE_EDIT`、`FORCE_SSL_ADMIN` 等常量。

**修复**: 使用 `if (!defined('CONSTANT'))` 守卫:
```php
if (!defined('DISALLOW_FILE_EDIT')) {
    define('DISALLOW_FILE_EDIT', true);
}
if (!defined('FORCE_SSL_ADMIN')) {
    define('FORCE_SSL_ADMIN', true);
}
```

**验证**: `php -l wp-config.php` 语法检查 + `curl` 检查页面无Warning输出。

---

## 陷阱5: AI生成内容的幻觉核查

**症状**: 网站上线后内容与实际不符（产品名错误、地址错误、版本号编造、合作伙伴编造）。

**根因**: AI在缺乏真实数据时会自行"补全"信息。

**P0核查清单**:
1. 公司全称 → 核对工商注册名
2. 地址 → 核对官网/天眼查
3. 成立时间 → 核对真实里程碑
4. 产品名/版本号 → 只使用官方渠道确认的名称
5. 合作伙伴 → 不提及未经证实的合作方
6. 技术参数 → 每个数字都需要来源

**流程**: 线上搜索确认 → 逐条对比 → 替换 → 删除编造新闻帖 → 仅保留可溯源内容。

---

## 陷阱6: Windows CRLF + patch 工具写入失败

**症状**: 在 Windows Git Bash 环境下使用 `write_file` 或 `patch` 修改主题文件时，反复出现 `Post-write verification failed: on-disk content differs from intended write`，文件无法保存。

**根因**: Windows 文件使用 CRLF (`\r\n`)，但工具写入使用 LF (`\n`)，导致字节级别的验证失败。多层 Python 字符串转义（paramiko → shell → Python heredoc）加剧了问题。

**P0解决方案 - 服务端Python脚本** (最可靠):
```python
# 不直接使用 write_file/patch，而是在服务端执行Python脚本
fix_script = '''
with open("/var/www/目标站/wp-content/themes/xxx/functions.php") as f:
    content = f.read()
# 执行字符串替换
content = content.replace("old_text", "new_text")
with open("/var/www/目标站/wp-content/themes/xxx/functions.php", "w") as f:
    f.write(content)
'''
# 上传脚本到服务器执行（避免shell转义）
ssh_exec(client, f"cat > /tmp/fix.py << 'PYEOF'\n{fix_script}\nPYEOF")
ssh_exec(client, "python3 /tmp/fix.py")
ssh_exec(client, "rm -f /tmp/fix.py")
```

**重要**: 在 `<< 'PYEOF'` 中使用单引号包围分隔符，阻止shell对Python代码中的 `$`、`\`、反引号进行转义。

**备选方案**: 本地修改文件后通过SFTP直接上传：
```python
sftp = client.open_sftp()
sftp.put(r'C:\path\to\local\file.php', '/var/www/.../remote/path.php')
sftp.close()
```
注意：SFTP上传会保留本地文件的行尾格式，需先在本地规范化换行为 `\n`。

---

## 陷阱7: 宝塔面板(BT Panel)特殊路径

**症状**: 使用常规 `apt install`、`systemctl`、`/etc/` 路径操作无效，服务位于非标准位置。

**BT Panel 路径速查**:
```
PHP:     /www/server/php/80/              (版本号在路径中)
PHP-FPM: /www/server/php/80/sbin/php-fpm
php.ini: /www/server/php/80/etc/php.ini
socket:  /tmp/php-cgi-80.sock
MySQL:   /www/server/mysql/
socket:  /tmp/mysql.sock
Nginx:   /www/server/nginx/sbin/nginx    (v1.26.3，独立于系统nginx)
vhost:   /www/server/panel/vhost/nginx/
面板DB:  /www/server/panel/data/default.db
日志:    /www/wwwlogs/
```

**MySQL root 密码提取** (宝塔面板存储):
```python
ssh_exec("python3 -c \"import sqlite3; db=sqlite3.connect('/www/server/panel/data/default.db'); row=db.execute('SELECT mysql_root FROM config WHERE id=1').fetchone(); print(row[0] if row else 'NOT FOUND')\"")
```

**PHP-FPM 操作**:
```bash
# 重载配置
kill -USR2 $(cat /www/server/php/80/var/run/php-fpm.pid)
# 状态检查
ps aux | grep php-fpm | grep -v grep
ls /tmp/php-cgi-80.sock  # socket存在 = 正常运行
```

**Nginx 注意**: 宝塔面板和系统可能各有一个Nginx实例。检查实际监听端口的进程：
```bash
netstat -tlnp | grep -E ':80 |:443 '
# 然后检查对应的二进制路径:
readlink -f /proc/<PID>/exe
```

```bash
# Google Fonts残留
curl -sk https://目标站/ | grep -c fonts.googleapis.com

# PHP错误输出
curl -sk https://目标站/ | grep -c "Warning:\|Fatal error:"

# display_errors状态  
grep '^display_errors' /www/server/php/*/etc/php.ini

# 安全常量重复
php -l /var/www/*/wp-config.php

# 全页面HTTP状态
for p in / /products/ /about/ /contact/; do
  echo -n "$p: "; curl -sk -o /dev/null -w '%{http_code}' https://目标站$p
done
```

---

## 陷阱8: Customizer值覆盖PHP默认值

**症状**: 修改了 `functions.php` 或 `customizer.php` 中的默认值（如电话、地址、ICP号），但前端仍然显示旧值。

**根因**: WordPress Customizer (`get_theme_mod()`) 优先读取数据库中的已保存值。一旦用户通过后台"外观→自定义"保存过设置（或主题激活时自动保存），数据库中的旧值会永久覆盖PHP源码中的默认值。

**检测**:
```bash
sudo -u www php -r "
require '/var/www/站点/wp-load.php';
echo 'Phone: ' . get_theme_mod('theme_phone') . PHP_EOL;
echo 'ICP: '   . get_theme_mod('theme_icp') . PHP_EOL;
"
```
若输出与PHP源码不一致，说明数据库值在覆盖。

**P0修复 - 双管齐下**:
```bash
# 1. 修改PHP源码默认值（治本）
sed -i "s/'400-xxx-xxxx'/'400-XXX-XXXX'/g" customizer.php functions.php

# 2. 更新数据库已保存值（治标 + 立即生效）
sudo -u www php -r "
require '/var/www/站点/wp-load.php';
set_theme_mod('theme_phone', '400-XXX-XXXX');
set_theme_mod('theme_address', 'YOUR_COMPANY_ADDRESS');
"

# 3. 清除缓存（WP Fastest Cache 等会缓存旧值）
rm -rf /var/www/站点/wp-content/cache/all/*
```

**注意**: 如果主题中同一个值用了两个不同的 key（如 `mingyuan_phone` 和 `theme_phone`），必须同时更新两个key，或统一为一个key。

**验证**: `curl -sk https://站点/ | grep '400-XXX-XXXX'` 必须返回新值。

---

## 陷阱9: 远端逐页审计 — 无浏览器环境下的全站检查

**症状**: 浏览器工具被网络策略拦截（`Blocked: URL targets a private or internal address`），web_extract 不可用。只能通过 SSH 操作远端服务器，但无法看到页面渲染效果。

**根因**: 服务器在中国内网/经 L4 转发，Claude 的浏览器/web_extract 工具走的是境外出口，无法访问。

**P0解决方案 — 服务端 curl + Python 审计** (可靠):

```python
# Step 1: 通过 SSH 批量抓取页面
ssh_exec("mkdir -p /tmp/page-snapshots && for p in / /products/ /about/ /contact/; do "
         "name=$(echo $p | tr '/' '_' | sed 's/^_/home/;s/_$//'); "
         "curl -sk https://站点$p -o /tmp/page-snapshots/$name.html; done")

# Step 2: 上传 Python 审计脚本到服务器执行（避免 heredoc 转义）
# 本地写脚本 → scp → 服务器执行
audit_script = """..."""  # 正则扫描: 占位符/空div/CDN引用/语义标签/alt缺失/H1层级/meta标签
# scp上传 + ssh python3 执行

# Step 3: 关键检测项
checks = {
    'PLACEHOLDER': r'(xxx+|XXXX+|占位|placeholder|TODO|待填)',
    'EMPTY-DIV': r'<div[^>]*class="[^"]*"[^>]*>\s*</div>',
    'CDN-BLOCKED': r'(fonts\.googleapis|cdnjs\.cloudflare|ajax\.googleapis)',
    'A11Y-IMG-ALT': r'<img(?![^>]*alt=)[^>]*>',
    'A11Y-NO-H1': lambda html: html.count('<h1') == 0,
    'SEO-NO-META-DESC': r'<meta\s+name="description"',
    'SEMANTIC-LOW': lambda html: sum([
        '<main' in html, '<article' in html, '<section' in html,
        '<nav' in html, '<header' in html, '<footer' in html
    ]) < 4,
}
```

**重要**: 
- 所有修改操作通过 `scp` 上传 Python 脚本执行，避免 SSH heredoc 中 PHP `$` 符号被 shell 转义
- 审计脚本应返回每个页面的问题数量和类型，便于批量定位
- 修改后必须清除 WP Fastest Cache：`rm -rf /var/www/站点/wp-content/cache/all/*`

**备选方案 — PHP 脚本直接查询 WordPress**:
```bash
sudo -u www php -r "
require '/var/www/站点/wp-load.php';
echo 'Pages: ' . wp_count_posts('page')->publish . PHP_EOL;
echo 'Posts: ' . wp_count_posts()->publish . PHP_EOL;
\$active = get_option('active_plugins'); 
echo 'Plugins: ' . count(\$active) . ' active' . PHP_EOL;
"
```

**验证**: 审计脚本输出每页的问题清单 + 汇总统计。修复后重新运行确认 0 问题。

---

## 陷阱10: CSS类名不匹配导致文字"反色"/不可见

**症状**: 用户反馈文字"显示出现反色"、文字模糊半透明、看不清。前端HTML 200、无PHP Warning、CSS文件可访问，但文字在深色背景上几乎不可见。

**根因**: PHP模板中的HTML class名（如 `hero__title`）与 style.css 中定义的CSS选择器（如 `.hero-title`）使用了不同的命名约定（BEM双下划线 vs 单破折号），导致CSS规则完全不匹配，文字回退到浏览器默认样式或无样式状态。

**检测**:
```bash
# 对比HTML渲染出的class和CSS定义的class
curl -sk https://站点/ | grep -oP 'class="[^"]*hero[^"]*"' | head -10
grep -oP '\.hero[_-][a-z]+' style.css | sort -u
```
若两边不一致（如 HTML用 `hero__title` 但CSS只有 `.hero-title`），立即修复。

**P0修复 - 添加BEM别名**:
```css
/* 在style.css中为每个不匹配的class添加双下划线别名 */
.hero__title,
.hero-title {
    /* 原有样式保持不变 */
}
.hero__subtitle,
.hero-description {
    /* 原有样式保持不变 */
}
```
不要只改HTML或只改CSS——两者之一可能有其他依赖。添加别名是最安全的修复。

**验证**: `curl -sk https://站点/ | grep 'hero__title'` 应返回带有完整样式的class名。

**常见不匹配模式**:
- `hero__title` (HTML) vs `.hero-title` (CSS)
- `hero__subtitle` vs `.hero-description`
- `hero__cta` vs `.hero-actions`
- `hero__content` vs `.hero-content`

---

## 陷阱11: Hero区域透明按钮在深色渐变上不可见

**症状**: 首页Hero区域的outline/ghost按钮（如"关于我们"）在深色渐变背景上完全透明，文字边缘模糊，低对比度不符合WCAG标准。

**根因**: `.btn--outline` 使用 `background: transparent`，在深色渐变Hero上缺乏视觉支撑。

**修复**:
```css
.hero .btn--outline {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.55);
    backdrop-filter: blur(4px);
}
.hero .btn--outline:hover {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.9);
}
```

---

## 陷阱12: 产品图片缺失 — 本地资产库→服务端压缩→模板替换

**症状**: WordPress主题中产品/服务展示区域使用了SVG占位符或CSS背景色块，无真实产品照片。本地资产库（如 `~/assets`）有照片但未上传。

**根因**: 主题开发时无实物照片，用占位符替代。后期需要从本地资产库匹配、优化、上传。

**P0解决方案 — 服务端PIL/ImageMagick处理管线**:

```bash
# Step 1: 映射产品→图片文件
# 根据产品名称匹配本地资产库中的文件名关键词
# 例: AVITS → vaccine_system_sorter_full_04.png

# Step 2: 上传原图到服务器 /tmp
scp "~/assets\photos\product.jpg" root@服务器:/tmp/

# Step 3: 服务端压缩（重点：大印刷品文件可能30MB+） 
python3 << 'PYEOF'
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 防止DecompressionBombError
img = Image.open('/tmp/product_raw.jpg')
w, h = img.size  # 可能 9449×23622（300dpi印刷品）
if w > 800:
    ratio = 800 / w
    img = img.resize((800, int(h*ratio)), Image.LANCZOS)
img.save('/var/www/站点/.../assets/images/product-web.jpg', 'JPEG', quality=82, optimize=True)
PYEOF

# Step 4: 替换主题模板中的SVG占位符
# page-products.php 中:
# <div class="product-placeholder"><svg>...</svg></div>
# → <img src="<?php echo get_template_directory_uri(); ?>/assets/images/product-web.jpg" ...>

# Step 5: 添加图片CSS
# .product-image { width:100%; border-radius:var(--radius-lg); box-shadow:var(--shadow-lg); }
```

**PIL常见错误**:
- `DecompressionBombError` → 加 `Image.MAX_IMAGE_PIXELS = None`
- ImageMagick `width or height exceeds limit` → 改用PIL+MAX_IMAGE_PIXELS
- 转换后需 `php -l` 语法检查 + 清除WP Fastest Cache

**备选 — 二维码裁剪专用流程**:
```bash
# 企业微信二维码卡片 → 纯二维码图片
# 1. 上传卡片原图，vision_analyze确认二维码位置
# 2. PIL crop() 多次迭代（比例估算→vision验证→微调）
# 3. 最终输出纯二维码PNG（含白边静区，380×380px）
# 4. 替换footer.php中"QR Code"文字占位符
```

**验证**: 图片HTTP 200 + 产品页HTML含 `<img src="...product-web.jpg">` + 0 PHP Warning

---

## 陷阱8: Customizer值覆盖PHP默认值

**症状**: 修改了 `functions.php` 或 `customizer.php` 中的默认值（如电话、地址、ICP号），但前端仍然显示旧值。

**根因**: WordPress Customizer (`get_theme_mod()`) 优先读取数据库中的已保存值。一旦用户通过后台"外观→自定义"保存过设置（或主题激活时自动保存），数据库中的旧值会永久覆盖PHP源码中的默认值。

**检测**:
```bash
sudo -u www php -r "
require '/var/www/站点/wp-load.php';
echo 'Phone: ' . get_theme_mod('theme_phone') . PHP_EOL;
echo 'ICP: '   . get_theme_mod('theme_icp') . PHP_EOL;
"
```
若输出与PHP源码不一致，说明数据库值在覆盖。

**P0修复 - 双管齐下**:
```bash
# 1. 修改PHP源码默认值（治本）
sed -i "s/'400-xxx-xxxx'/'400-XXX-XXXX'/g" customizer.php functions.php

# 2. 更新数据库已保存值（治标 + 立即生效）
sudo -u www php -r "
require '/var/www/站点/wp-load.php';
set_theme_mod('theme_phone', '400-XXX-XXXX');
set_theme_mod('theme_address', 'YOUR_COMPANY_ADDRESS');
"

# 3. 清除缓存（WP Fastest Cache 等会缓存旧值）
rm -rf /var/www/站点/wp-content/cache/all/*
```

**注意**: 如果主题中同一个值用了两个不同的 key（如 `mingyuan_phone` 和 `theme_phone`），必须同时更新两个key，或统一为一个key。

**验证**: `curl -sk https://站点/ | grep '400-XXX-XXXX'` 必须返回新值。

---

## 陷阱9: CSS类名BEM双下划线不匹配

**症状**: HTML模板使用 `hero__title`（BEM双下划线），但CSS定义了 `.hero-title`（单破折号）。样式完全不生效，文字以浏览器默认样式渲染，在深色背景上几乎不可见。

**根因**: 开发时类名约定不一致——模板用了BEM命名（`block__element`），但CSS用了单破折号（`block-element`）。

**检测**:
```bash
# 检查HTML使用了什么类名
curl -sk https://站点/ | grep -o 'class="[^"]*"' | sort -u

# 检查CSS定义了什么类名
grep -o '\.[a-z_-]*{' style.css | sort -u

# 对比两者，找出不匹配的
```

**P0修复**: 在CSS中同时添加BEM别名：
```css
/* 同时支持两种命名 */
.hero__title,
.hero-title {
    font-size: 3.2rem;
    color: var(--color-white);
}
```

更健壮的做法：统一使用一种命名约定。如果项目已经用BEM，CSS也应该用BEM。

---

## 陷阱13: WordPress域名迁移 — 全链路操作指南

**场景**: 将现有WordPress站点从 `旧域名.com` 迁移到 `新域名.com`，服务器上宝塔面板nginx与系统nginx共存。

### 13.1 前置检查
```bash
# 1. DNS是否已解析？
nslookup 新域名.com 8.8.8.8

# 2. 服务器上有几个nginx实例？
ps aux | grep 'nginx.*master'
netstat -tlnp | grep -E ':80 |:443 '

# 3. 识别谁在监听端口
for pid in $(netstat -tlnp | grep ':80 ' | awk -F/ '{print $1}' | awk '{print $NF}'); do
  readlink -f /proc/$pid/exe
done
# 输出可能是: /usr/sbin/nginx（系统）或 /www/server/nginx/sbin/nginx（宝塔）
```

### 13.2 配置实际处理请求的nginx（非宝塔那个）
```bash
# 复制旧域名配置
cp /etc/nginx/sites-enabled/旧域名.com.conf /etc/nginx/sites-enabled/新域名.com.conf
sed -i 's/旧域名\\.com/新域名.com/g' /etc/nginx/sites-enabled/新域名.com.conf

# ⚠️ 删除重复的 limit_req_zone（如果有）
sed -i '/limit_req_zone.*mylogin/d' /etc/nginx/sites-enabled/新域名.com.conf
```

### 13.3 处理server_name通配符拦截（关键！）
```bash
# 致命陷阱：其他配置文件中可能有 server_name _ 通配符，
# 按字母序排在前面时会拦截所有请求（返回403/404）
grep -rn 'server_name.*_\\|server_name.*新域名' /etc/nginx/

# 如果有通配符配置排在前面 → 重命名到字母序末尾
mv /etc/nginx/sites-enabled/mybiolearn.conf /etc/nginx/sites-enabled/z-mybiolearn.conf
```

### 13.4 SSL证书申请
```bash
# webroot方式（推荐，不中断服务）
certbot certonly --webroot -w /var/www/letsencrypt -d 新域名.com --non-interactive --agree-tos --email admin@域名.com

# 如果webroot反复403，可能是通配符拦截（见13.3）
# 备用方案：standalone模式（会短暂中断所有服务）
/usr/sbin/nginx -s stop
certbot certonly --standalone -d 新域名.com --non-interactive --agree-tos --email admin@域名.com
/usr/sbin/nginx

# ⚠️ Let's Encrypt限速：5次/小时/域名。连续失败会触发限速，
# 需等待整小时重置。可先用自签证书保底：
mkdir -p /etc/letsencrypt/live/新域名.com
openssl req -x509 -nodes -days 90 -newkey rsa:2048 \
  -keyout /etc/letsencrypt/live/新域名.com/privkey.pem \
  -out /etc/letsencrypt/live/新域名.com/fullchain.pem \
  -subj '/CN=新域名.com'
```

### 13.5 WordPress域名替换
```bash
# ⚠️ 先检查 wp-config.php 是否有硬编码（会覆盖数据库值！）
grep -n 'WP_HOME\\|WP_SITEURL' wp-config.php

# 如果有硬编码 → 直接改 define
sed -i "s|define('WP_HOME', 'https://旧域名.com');|define('WP_HOME', 'https://新域名.com');|" wp-config.php
sed -i "s|define('WP_SITEURL', 'https://旧域名.com');|define('WP_SITEURL', 'https://新域名.com');|" wp-config.php

# 数据库内链替换（用PHP脚本文件，不要用shell heredoc——$符号会被转义）
# 写入 /tmp/migrate-wp.php，然后 sudo -u www php /tmp/migrate-wp.php
```

### 13.6 配置SSL nginx后恢复
```bash
# 拿到证书后，写完整SSL server块
# HSTS + 安全头 + FastCGI + 静态缓存 + xmlrpc=404

# 重载（注意PID文件可能损坏）
kill -HUP $(ps aux | grep 'nginx.*master.*/usr/sbin/nginx' | grep -v grep | awk '{print $2}')
```

---\n\n## 陷阱14: 企业微信/微信二维码图片处理导致无法扫码

**症状**: 从企业微信名片卡片裁剪出的二维码图片，视觉上完全正常（纯白底、无蓝边、四角定位图案完整、中心头像可见），但手机扫码始终失败。多次调整裁剪参数（尺寸、位置、格式）均无效。

**根因**: 企业微信/微信的二维码（尤其是带中心头像的）使用高纠错等级（~30%），QR模块像素值精确编码。**任何PIL (Pillow) 图像处理——包括 crop、resize、format conversion、JPEG重编码——都会引入亚像素级变化，破坏QR码数据完整性。** 视觉正常 ≠ 可扫描。

**绝对不要做的事**:
```python
# 以下任何操作都会导致扫码失败：
img = Image.open('card.jpg')
cropped = img.crop((x, y, w, h))      # ← 会失败
cropped.save('qr.png', 'PNG')          # ← 会失败
cropped.save('qr.jpg', 'JPEG', quality=100)  # ← 会失败
large = cropped.resize((600,600), Image.LANCZOS)   # ← 会失败
large = cropped.resize((600,600), Image.NEAREST)   # ← 会失败
```

**P0解决方案 — 使用原始文件，零处理**:
```bash
# 直接使用原始卡片文件
scp "D:\原始\企业微信二维码.jpg" root@服务器:/var/www/.../assets/images/wecom-qr.jpg
# 页脚引用：
# <img src=".../assets/images/wecom-qr.jpg" width="200">
```

**如果必须裁剪** (如去掉人名):
1. `jpegtran -crop WxH+X+Y card.jpg > qr.jpg` (JPEG无损裁剪，不重编码)
2. CSS `clip-path` / `overflow:hidden` 在浏览器端裁剪
3. 或用CSS白色遮罩覆盖名字区域

**页脚QR码显示增强**:
```css
.footer-qr {
    background: #ffffff;
    border-radius: var(--radius-md);
    padding: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    width: 210px;
    height: auto;
}
```

---\n\n## 陷阱8: Customizer值覆盖PHP默认值

**症状**: 修改了 `functions.php` 或 `customizer.php` 中的默认值（如电话、地址、ICP号），但前端仍然显示旧值。

**根因**: WordPress Customizer (`get_theme_mod()`) 优先读取数据库中的已保存值。一旦用户通过后台"外观→自定义"保存过设置（或主题激活时自动保存），数据库中的旧值会永久覆盖PHP源码中的默认值。

**检测**:
```bash
sudo -u www php -r "
require '/var/www/站点/wp-load.php';
echo 'Phone: ' . get_theme_mod('theme_phone') . PHP_EOL;
echo 'ICP: '   . get_theme_mod('theme_icp') . PHP_EOL;
"
```
若输出与PHP源码不一致，说明数据库值在覆盖。

**P0修复 - 双管齐下**:
```bash
# 1. 修改PHP源码默认值（治本）
sed -i "s/'400-xxx-xxxx'/'400-XXX-XXXX'/g" customizer.php functions.php

# 2. 更新数据库已保存值（治标 + 立即生效）
sudo -u www php -r "
require '/var/www/站点/wp-load.php';
set_theme_mod('theme_phone', '400-XXX-XXXX');
set_theme_mod('theme_address', 'YOUR_COMPANY_ADDRESS');
"

# 3. 清除缓存（WP Fastest Cache 等会缓存旧值）
rm -rf /var/www/站点/wp-content/cache/all/*
```

**注意**: 如果主题中同一个值用了两个不同的 key（如 `mingyuan_phone` 和 `theme_phone`），必须同时更新两个key，或统一为一个key。

**验证**: `curl -sk https://站点/ | grep '400-XXX-XXXX'` 必须返回新值。

---

## 陷阱9: WordPress域名迁移 — WP_HOME硬编码覆盖数据库

**症状**: 执行 `update_option('siteurl', 'https://新域名.com')` 后，`get_option('siteurl')` 仍然返回旧域名。

**根因**: `wp-config.php` 中硬编码了 `define('WP_HOME', 'https://旧域名.com')` 和 `define('WP_SITEURL', 'https://旧域名.com')`，这会阻止数据库中的选项生效。PHP常量优先级高于数据库选项。

**检测**:
```bash
grep -n 'WP_HOME\|WP_SITEURL' wp-config.php
```
若存在，必须修改这些 define。

**P0修复 — 改wp-config.php而非数据库**:
```bash
sed -i "s|define('WP_HOME', 'https://旧域名.com');|define('WP_HOME', 'https://新域名.com');|" wp-config.php
sed -i "s|define('WP_SITEURL', 'https://旧域名.com');|define('WP_SITEURL', 'https://新域名.com');|" wp-config.php
```

**数据库同步**（可选但推荐）:
```php
// 同时更新数据库中的选项，保持一致性
$wpdb->query("UPDATE {$wpdb->prefix}options SET option_value = REPLACE(option_value, 'https://旧域名.com', 'https://新域名.com') WHERE option_value LIKE '%旧域名.com%'");
$wpdb->query("UPDATE {$wpdb->prefix}posts SET post_content = REPLACE(post_content, 'https://旧域名.com', 'https://新域名.com')");
$wpdb->query("UPDATE {$wpdb->prefix}postmeta SET meta_value = REPLACE(meta_value, 'https://旧域名.com', 'https://新域名.com') WHERE meta_value LIKE '%旧域名.com%'");
```

---

## 陷阱10: Nginx双实例 + server_name通配符导致ACME验证403

**症状**: certbot webroot验证时，本地 `curl -H 'Host: 新域名'` 测试通过（200），但Let's Encrypt服务器始终收到403。Nginx日志显示 `conflicting server name` 警告。

**根因**: 服务器上存在多个nginx实例（系统nginx + 宝塔nginx + Docker容器nginx），且某个配置文件的 `server_name _`（通配符）按字母序排在新域名的配置文件之前，拦截了ACME验证请求。

**检测**:
```bash
# 找出所有nginx实例
ps aux | grep 'nginx.*master'
# 检查谁在监听80/443
netstat -tlnp | grep -E ':80 |:443 '
# 找出哪个server block在拦截
grep -rn 'server_name.*_\|server_name.*mybiocrv' /etc/nginx/
```

**P0修复 — 字母序调整**:
```bash
# 将通配符server_name的配置文件重命名到字母序末尾
mv /etc/nginx/sites-enabled/mybiolearn.conf /etc/nginx/sites-enabled/z-mybiolearn.conf
/usr/sbin/nginx -s reload
```

**终极方案 — 用standalone模式绕过nginx**:
```bash
# 如果webroot方式持续失败，用standalone（certbot自带临时服务器）
/usr/sbin/nginx -s stop
certbot certonly --standalone -d 新域名.com --non-interactive --agree-tos --email admin@域名.com
/usr/sbin/nginx
```

**注意**: standalone会短暂中断所有nginx服务。如果多次失败会触发Let's Encrypt限速（5次/小时/域名），需等待1小时重置。备用方案是先用自签证书让站点跑起来，再通过宝塔面板GUI申请正式证书。

---

## 陷阱11: QR码图片经过PIL处理后无法扫码

**症状**: 从企业微信名片中裁剪出二维码，保存为PNG/JPG后，手机无法扫码识别。图片视觉上看起来完整，四角定位图案清晰。

**根因**: PIL (Pillow) 对JPEG图片的编解码会引入细微的像素值变化（颜色空间转换、压缩伪影、亚像素平滑等）。QR码需要像素级的精确性——任何单个模块的灰度偏移都可能导致纠错失败。特别是企业微信二维码中心嵌入了头像照片，本身已经占用了部分纠错容量。

**P0方案 — 绝不重编码**:
```bash
# 错误做法：用PIL裁剪后save（会重编码）
img = Image.open('card.jpg')
cropped = img.crop((x,y,w,h))
cropped.save('qr.png')  # ← 破坏了QR码数据

# 正确做法1：直接使用原文件，用CSS裁剪显示
css: object-fit: none; object-position: -Xpx -Ypx; width: 200px; height: 200px;

# 正确做法2：用jpegtran做无损裁剪（不重编码）
jpegtran -crop WxH+X+Y card.jpg > qr.jpg

# 正确做法3：接受原图完整显示，不裁剪
```

**验证**: 裁剪后必须立即用手机扫描测试。如果扫不了，回退到原图方案。

---

## 陷阱9: Nginx `server_name _` 通配符拦截 ACME 挑战

**症状**: ACME 测试文件 `test.txt` 从服务器本地 curl 返回 200，但从 L4 代理/外网访问返回 403。Let's Encrypt 验证反复失败。

**根因**: 某个 nginx 站点配置使用了 `server_name _;`（通配符/默认服务器），且该配置文件在字母序上排在目标域名之前，导致目标域名的请求被通配符 server block 拦截，而非命中正确的 ACME challenge location。

**检测**:
```bash
# 查找通配符 server_name
grep -rn "server_name _" /etc/nginx/sites-enabled/ /www/server/panel/vhost/nginx/

# 查看字母序
ls /etc/nginx/sites-enabled/ | grep -A1 -B1 "目标域名"
```

**修复**:
```bash
# 将通配符配置文件改名，确保排序在目标域名之后
mv /etc/nginx/sites-enabled/mybiolearn.conf /etc/nginx/sites-enabled/z-mybiolearn.conf
nginx -s reload
```

**验证**: `curl -s http://目标域名/.well-known/acme-challenge/test.txt` 必须返回 200。

---

---

## 陷阱13: WordPress域名迁移 — 全链路检查清单

**场景**: 将一个WordPress站点从旧域名迁移到新域名。服务器上可能有多个nginx实例共存（系统nginx + 宝塔nginx + Docker容器nginx）。

### 13.1 前置检查
```bash
nslookup 新域名.com 8.8.8.8                          # DNS是否解析
ps aux | grep 'nginx.*master'                        # 有几个nginx实例
netstat -tlnp | grep -E ':80 |:443 '                 # 谁在监听
for pid in $(netstat -tlnp | grep ':80 ' | awk -F/ '{print $1}' | awk '{print $NF}'); do
  readlink -f /proc/$pid/exe                          # 确认nginx二进制路径
done
```

### 13.2 致命陷阱: server_name _ 通配符拦截
```bash
# 如果某个配置有 server_name _，且字母序排在目标域名之前，会拦截所有请求
grep -rn "server_name _" /etc/nginx/sites-enabled/
# 修复: 将通配符配置重命名到末尾
mv bad.conf /etc/nginx/sites-enabled/z-bad.conf
```

### 13.3 wp-config.php 硬编码覆盖数据库
```bash
# 如果存在这些 define，update_option 不会生效
grep -n 'WP_HOME\|WP_SITEURL' wp-config.php
# 直接改 define，不要只改数据库
sed -i "s|define('WP_HOME', 'https://旧域名.com');|define('WP_HOME', 'https://新域名.com');|" wp-config.php
```

### 13.4 数据库内链替换
```php
// 用 PHP 脚本文件执行，不要用 shell heredoc ($符号会被转义)
$wpdb->query("UPDATE {$wpdb->prefix}posts SET post_content = REPLACE(post_content, '旧域名', '新域名')");
$wpdb->query("UPDATE {$wpdb->prefix}postmeta SET meta_value = REPLACE(meta_value, '旧域名', '新域名') WHERE meta_value LIKE '%旧域名%'");
```

### 13.5 SSL证书 (L4代理环境)
```bash
# webroot方式优先
certbot certonly --webroot -w /var/www/letsencrypt -d 新域名.com
# 如果反复403，用standalone（会短暂中断所有nginx服务）
/usr/sbin/nginx -s stop && certbot certonly --standalone -d 新域名.com && /usr/sbin/nginx
# ⚠ 限速: 5次/小时/域名。连续失败后需等1小时重置
# 保底: 自签证书让站点先跑着
openssl req -x509 -nodes -days 90 -newkey rsa:2048 \
  -keyout /etc/letsencrypt/live/新域名.com/privkey.pem \
  -out /etc/letsencrypt/live/新域名.com/fullchain.pem \
  -subj '/CN=新域名.com'
```

---

## 陷阱14: 企业微信二维码 — 绝对不要用PIL加工

**症状**: 从企业微信名片裁剪出二维码后，手机扫码始终失败。图片视觉上完全正常（纯白底、四角定位完整、中心头像可见），但就是扫不了。

**根因**: PIL (Pillow) 的任何操作——`crop()`、`resize()`、`save('PNG')`、`save('JPEG')`——都会引入亚像素级变化。企业微信二维码使用高纠错等级（~30%），中心嵌入头像进一步挤压纠错容量。任何像素级偏差都会导致扫码失败。**视觉正常 ≠ 可扫描。**

**绝对不要做的事**:
```python
# 以下任何操作都会破坏QR码:
img = Image.open('card.jpg')
cropped = img.crop((x,y,w,h))       # ← 失败
cropped.save('qr.png')              # ← 失败  
large = cropped.resize((600,600), any_filter)  # ← 失败
```

**P0方案 — 直接用原始文件，零加工**:
```bash
# 1. 上传原始文件到服务器，不做任何处理
scp "D:\原始\企业微信二维码.jpg" root@服务器:/var/www/.../images/wecom-qr.jpg
# 2. 页脚直接引用原图
<img src="wecom-qr.jpg" width="200" style="max-width:200px; height:auto;">
```

**如果必须去掉人名**: 用CSS遮罩隐藏，不要裁剪图片。
```css
.qr-wrapper { overflow: hidden; width: 200px; height: 200px; }
.qr-wrapper img { margin-top: -30px; } /* CSS裁剪，不破坏像素 */
```

**如果必须裁剪**: 用 `jpegtran -crop`（JPEG 无损裁剪，不重编码），或先 JPEG→PNG 解码→PNG crop→保存 PNG（PNG 裁剪不重编码像素）。

---

## 修复后验证

所有修复完成后，用户应刷新浏览器（Ctrl+Shift+R 强制刷新），确认:
1. 页面CSS正常渲染
2. 无PHP Warning/Error输出
3. 字体正常显示
4. 页面TTFB < 1秒
5. 所有内页HTTP 200


## 陷阱9: QR 码不要用图片库加工

**症状**: 从原始二维码裁剪/缩放后扫码失败。

**根因**: PIL/ImageMagick 重编码引入像素伪影。二维码需要精确黑白像素。

**P0**: 直接用原文件，CSS 控制显示，不做任何加工。

**如必须裁剪**: JPEG→PNG 解码→PNG 裁剪→保存 PNG。缩放用 NEAREST 插值。


## 陷阱10: CSS 类名 BEM 不匹配

**症状**: HTML class="hero__title" 但 CSS 定义 .hero-title，样式丢失。

**修复**: CSS 添加别名 `.hero__title, .hero-title { }`
6. Hero文字清晰可读（非半透明/反色）
