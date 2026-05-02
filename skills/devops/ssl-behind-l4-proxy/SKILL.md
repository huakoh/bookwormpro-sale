---
name: ssl-behind-l4-proxy
description: >
  Get Let's Encrypt SSL certificates for domains behind an L4 proxy
  when standard HTTP-01 challenge fails with 403. Uses acme.sh DNS
  manual validation to bypass L4 nginx interference. Also covers
  self-signed cert as temporary fallback and multi-nginx cleanup.
trigger_words: SSL behind proxy, L4 SSL, cert behind proxy, 403 acme, nginx 403 SSL
maturity: stable
---
# SSL Certificate Behind L4 Proxy

## Problem
Standard `certbot --webroot` and `certbot --standalone` fail with 403
when the domain sits behind an L4 proxy (nginx stream on port 443).
The L4 nginx intercepts HTTP-01 challenge requests.

## Root Cause
L4 proxy runs its own nginx on port 80 that handles ACME challenges
with `proxy_pass`. Even with standalone mode on the A server, DNS points
to the L4, so Let's Encrypt validation goes through L4 → fails.

## Solution A: DNS Manual Validation (acme.sh)

### Step 1: Install acme.sh
```bash
curl -s https://get.acme.sh | sh -s email=your@email.com
```

### Step 2: Issue cert with DNS challenge
```bash
/root/.acme.sh/acme.sh --issue --dns \
  -d domain.com -d www.domain.com \
  --yes-I-know-dns-manual-mode-enough-go-ahead-please
```
Outputs TXT records: `_acme-challenge.domain.com` and `_acme-challenge.www.domain.com`

### Step 3: Add TXT records at DNS provider
Verify: `nslookup -type=TXT _acme-challenge.domain.com`

### Step 4: Renew to complete
```bash
/root/.acme.sh/acme.sh --renew -d domain.com -d www.domain.com \
  --yes-I-know-dns-manual-mode-enough-go-ahead-please
```

### Step 5: Install to nginx
```bash
/root/.acme.sh/acme.sh --install-cert -d domain.com \
  --key-file /etc/letsencrypt/live/domain.com/privkey.pem \
  --fullchain-file /etc/letsencrypt/live/domain.com/fullchain.pem \
  --reloadcmd "nginx -s reload"
```

## Solution B: Self-Signed Fallback
When rate-limited or DNS not accessible:
```bash
mkdir -p /etc/letsencrypt/live/domain.com
openssl req -x509 -nodes -days 90 -newkey rsa:2048 \
  -keyout /etc/letsencrypt/live/domain.com/privkey.pem \
  -out /etc/letsencrypt/live/domain.com/fullchain.pem \
  -subj "/CN=domain.com"
```
Then upgrade to real cert later via DNS method.

## Solution C: L4 Config Debugging
If you MUST use HTTP validation, ensure:
1. L4 nginx server_name list includes the domain
2. L4 ACME challenge location proxies to A server correctly
3. A server nginx has ACME location pointing to existing webroot
4. No catch-all server blocks (like `server_name _;`) intercepting
   - Rename catch-all configs to sort AFTER the domain config (e.g., `z-catchall.conf`)
5. Test chain: `curl http://domain.com/.well-known/acme-challenge/test.txt`
   from L4, from A server, and externally

## Common Pitfalls
- **Rate limit**: 5 failures/hour/domain. Wait for `retry after` timestamp.
  Each failed attempt pushes the window forward.
- **post-hook error**: "nginx.service is not active" is cosmetic when nginx
  isn't managed by systemd. Cert IS issued despite this error.
  Check with `openssl x509 -issuer` to confirm Let's Encrypt vs self-signed.
- **Multiple nginx instances**: Check `netstat -tlnp | grep :443` to identify
  which nginx binary actually binds ports. On BT Panel servers there may be
  3+ nginx instances (system, BT panel, Docker containers).
- **nginx won't start after pkill**: `/usr/sbin/nginx -c /etc/nginx/nginx.conf`
- **PID file issues**: After pkill, PID file may be stale. Use `pkill -9 nginx`
- **L4 catch-all**: If another config has `server_name _` and sorts alphabetically
  before your domain, all ACME requests get captured → 403.
  Fix: `mv offending.conf z-offending.conf && nginx -s reload`
- **BT panel acme module**: `/www/server/panel/class/acme_v2.py` has Python 3.8
  dependency issues on Ubuntu 20.04. Use standalone acme.sh instead.
  then `/usr/sbin/nginx` to force restart.
- **Config test passes but no port binding**: Docker containers may have their
  own internal nginx. Check `docker ps` for port mappings.
- **NEVER stop L4 nginx**: DNS points to the L4 IP. If L4 nginx is stopped,
  ALL domains behind it become unreachable and ACME gets "Connection refused".
  Even acme.sh --standalone fails because L4 nginx on port 80 intercepts first.
- **acme.sh --standalone on A server also fails**: The L4 HTTP nginx on port 80
  still intercepts before acme.sh's standalone server can respond. Only DNS
  validation completely bypasses the L4 HTTP layer.
- **Error progression tells the story**: 403 → L4 intercepting. "Connection
  refused" → L4 stopped (worse!). Neither is the right path. DNS is.
- **Catch-all server_name (_)**: A config with `server_name _;` on port 80
  will intercept ACME requests if it sorts alphabetically BEFORE your
  domain config. Rename to `z-catchall.conf` to sort last.

## Troubleshooting Sequence (exact steps)

When certbot webroot returns 403 but local tests work:

1. Check if L4 has domain in server_name: `grep domain /usr/local/nginx/conf/nginx.conf`
2. Check for catch-all interception: `grep -rn "server_name _" /etc/nginx/sites-enabled/`
3. Rename catch-all: `mv catchall.conf z-catchall.conf`
4. Reload L4: `/usr/local/nginx/sbin/nginx -s reload`
5. Test ACME from L4: `curl -s http://domain/.well-known/acme-challenge/test.txt`
6. If all above passes but certbot still fails → switch to DNS manual mode
7. DNS mode: never stop nginx; add TXT records; run acme.sh --renew

## Domains Behind L4 — Architecture Reference

```
User DNS → YOUR_SERVER_IP (L4 B server)
                ├── Port 443: stream proxy → YOUR_SERVER_IP:443 (transparent)
                └── Port 80:  HTTP with server_name list + ACME challenge proxy
```

To add a new domain behind this L4:
1. Add domain to L4 nginx server_name list
2. Reload L4 nginx
3. Configure A server nginx for the domain
4. Get SSL via DNS manual mode (acme.sh)
