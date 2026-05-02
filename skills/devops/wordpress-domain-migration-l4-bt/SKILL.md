---
name: wordpress-domain-migration-l4-bt
description: WordPress domain migration behind L4 proxy on BT Panel server. Covers DNS setup L4 nginx SSL via acme.sh wp-config fix DB search-replace and cache clearing.
maturity: stable
cost_level: high
---

# WordPress Domain Migration - L4 Proxy + BT Panel

## Pre-check
```bash
nslookup NEW_DOMAIN 8.8.8.8
netstat -tlnp | grep ':80\|:443'
ls -l /proc/PID/exe
```

## Step 1: L4 Proxy
Add NEW_DOMAIN to HTTP server_name list in `/usr/local/nginx/conf/nginx.conf`
Reload: `kill -HUP $(cat /usr/local/nginx/logs/nginx.pid)`

## Step 2: A Server Nginx
Copy OLD.conf to NEW.conf, sed replace domain.
Remove duplicate configs from both system nginx and BT panel nginx.
Watch for catch-all `server_name _` intercepting requests.

## Step 3: SSL via acme.sh DNS
```bash
/root/.acme.sh/acme.sh --issue --dns -d DOMAIN --yes-I-know-dns-manual-mode-enough-go-ahead-please
# User adds TXT record, then:
/root/.acme.sh/acme.sh --renew -d DOMAIN
/root/.acme.sh/acme.sh --install-cert -d DOMAIN --key-file ... --fullchain-file ...
```
Fallback: `openssl req -x509 -nodes -days 90`

## Step 4: WordPress
1. wp-config.php: define WP_HOME and WP_SITEURL to NEW_DOMAIN
2. Database: UPDATE posts/postmeta with REPLACE old->new
3. Clear cache: `rm -rf wp-content/cache/all/*`

## Key Pitfalls
- catch-all server_name blocks new domain requests
- wp-config hardcoded URLs override database options
- system nginx vs BT panel nginx dual instances
- certbot rate limit 5/hour per identifier
- WP Fastest Cache masks template and DB changes
