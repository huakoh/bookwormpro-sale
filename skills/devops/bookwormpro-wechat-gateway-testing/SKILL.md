---
name: bookwormpro-wechat-gateway-testing
description: >
  Test and debug BookwormPRO's WeChat (Weixin/WeCom) gateway integration.
  Covers iLink API quirks, gateway log analysis, DNS troubleshooting,
  and channel directory inspection. Trigger: 微信测试、企业微信对接、
  weixin gateway、wecom 调试、iLink API.
maturity: stable
cost_level: low
---

# BookwormPRO WeChat/WeCom Gateway Testing

## Architecture Overview

```
WeChat/WeCom → iLink/WebSocket API → Gateway (gateway/run.py)
    → AIAgent → Gateway → iLink/WebSocket API → WeChat/WeCom
```

- **Weixin (个人微信)**: Uses iLink HTTP long-poll (`ilinkai.weixin.qq.com`)
  Adapter: `gateway/platforms/weixin.py` (2053 lines)
- **WeCom (企业微信)**: Uses WebSocket (`openws.work.weixin.qq.com`)
  Adapter: `gateway/platforms/wecom.py` (1602 lines)
- **WeCom Callback**: Alternative HTTP callback mode
  Adapter: `gateway/platforms/wecom_callback.py`

## Quick Health Check

```bash
# 1. Check if gateway is running
tasklist /FI "IMAGENAME eq python.exe" | grep -i "gateway\|run.py"

# 2. Check registered channels
cat ~/.bookwormpro/channel_directory.json | python -m json.tool

# 3. Check env vars (masked)
grep "WEIXIN\|WECOM" ~/.bookwormpro/.env | sed 's/=.*/=***/'

# 4. Check recent gateway logs
tail -50 ~/.bookwormpro/logs/gateway.log | grep -E "weixin|wecom|inbound|response"
```

## iLink API Critical Quirk: Empty `{}` = SUCCESS

The iLink `sendmessage` API (`ilink/bot/sendmessage`) returns HTTP 200 + `{}`
when a message is **successfully accepted**. This is NOT an error.

The gateway's `_send_chunk()` correctly handles this (line 1514-1538 of weixin.py):
```python
ret = resp.get("ret")       # None for {}
errcode = resp.get("errcode")  # None for {}
# If both are None → falls through to `return` → SUCCESS
if (ret is not None and ret not in (0,)) or \
   (errcode is not None and errcode not in (0,)):
    raise RuntimeError(...)  # Only raises on actual error codes
return  # Empty {} response → success
```

**Do NOT treat `{}` as failure.** The test script `_test_weixin_send.py`
incorrectly reports errcode=N/A as failure — it's actually success.

### Response format patterns:
| Response | Meaning |
|----------|---------|
| `{}` | Success (message accepted) |
| `{"ret": 0}` | Success |
| `{"ret": -14}` | Session expired (auto-retried) |
| `{"errcode": 40001}` | Invalid credential |

## Testing Steps

### Step 1: Verify API connectivity (no gateway needed)
```bash
cd ~/BookwormPRO && python _test_weixin_api.py
```
Expect: HTTP 200, `msgs count: 0` (no pending messages is normal)

### Step 2: Send test message via direct API
```bash
cd ~/BookwormPRO && python _test_weixin_send.py
```
Expect: HTTP 200, `Response: {}` → **this means SUCCESS**

### Step 3: Check gateway logs for round-trip
```bash
grep "inbound\|response ready\|Sending response" ~/.bookwormpro/logs/agent.log | tail -20
```
A complete round-trip shows:
```
inbound message: platform=weixin ... msg='...'
response ready: platform=weixin ... time=Xs api_calls=N response=Y chars
Sending response (Y chars) to ...
```

### Step 4: Start gateway for live testing
```bash
cd ~/BookwormPRO
python gateway/run.py
# Or via CLI:
bookworm gateway start
```

## Common Issues

### DNS Resolution Failures
```
ERROR: Cannot connect to host ilinkai.weixin.qq.com:443 ssl:default [getaddrinfo failed]
```
- This is intermittent, likely related to GFW/proxy DNS
- The gateway has built-in retry (3 attempts with backoff)
- WeCom reconnects automatically when DNS resolves
- Check proxy/VPN status if persistent

### WeCom WebSocket Disconnects
```
WARNING: [Wecom] WebSocket error: WeCom websocket closed
```
- Normal to see occasional disconnects
- Gateway auto-reconnects (log will show `[Wecom] Reconnected`)
- If never reconnecting, verify `WECOM_BOT_ID` and `WECOM_SECRET`

### Session Expiry (errcode -14)
- iLink sessions expire after inactivity
- Gateway auto-retries without `context_token` on -14
- User sending a new message refreshes the session

## Channel Directory

`~/.bookwormpro/channel_directory.json` tracks registered channels:
```json
{
  "platforms": {
    "weixin": [{"id": "xxx@im.wechat", "name": "...", "type": "dm"}],
    "wecom": [],
    "wecom_callback": []
  }
}
```

- `type: "dm"` = direct message, `"group"` = group chat
- Empty array = platform configured but no channels registered
- Run `bookworm gateway setup` to register new channels via QR scan

## Key Files

| File | Purpose |
|------|---------|
| `gateway/platforms/weixin.py` | Weixin iLink adapter (2053 lines) |
| `gateway/platforms/wecom.py` | WeCom WebSocket adapter (1602 lines) |
| `gateway/platforms/wecom_callback.py` | WeCom HTTP callback adapter |
| `gateway/channel_directory.py` | Channel directory builder |
| `_test_weixin_api.py` | Direct iLink API connectivity test |
| `_test_weixin_send.py` | Direct iLink message send test |
| `~/.bookwormpro/channel_directory.json` | Registered channels |
| `~/.bookwormpro/logs/gateway.log` | Gateway runtime log |
| `~/.bookwormpro/logs/agent.log` | Agent processing log |

## WeCom Bot Setup (企业微信)

Requires in `~/.bookwormpro/config.yaml` or `.env`:
```yaml
platforms:
  wecom:
    enabled: true
    extra:
      bot_id: "your-bot-id"     # or WECOM_BOT_ID
      secret: "your-secret"     # or WECOM_SECRET
```
WebSocket URL: `wss://openws.work.weixin.qq.com`

## Verification Checklist

- [ ] `_test_weixin_api.py` returns HTTP 200
- [ ] `_test_weixin_send.py` returns HTTP 200 + `{}`
- [ ] Gateway log shows `inbound` messages
- [ ] Gateway log shows `response ready` + `Sending response`
- [ ] Message appears in WeChat client
- [ ] WeCom WebSocket shows `Reconnected` (if configured)
- [ ] No persistent `getaddrinfo failed` errors
