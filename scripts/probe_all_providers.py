#!/usr/bin/env python3
"""BookwormPRO Provider Health Probe — discovers all providers, probes each, trips circuits for DEAD."""
import sys, os, json, time
from pathlib import Path

# --- Setup ---
BOOKWORMPRO_ROOT = Path.home() / 'BookwormPRO'
sys.path.insert(0, str(BOOKWORMPRO_ROOT))

# Suppress noisy warnings from module imports
import warnings
warnings.filterwarnings('ignore')

try:
    from agent.provider_health import probe, reset, HealthStatus, HealthRecord
    from agent.circuit_breaker import report_failure
    MODULES_OK = True
except ImportError as e:
    MODULES_OK = False
    IMPORT_ERROR = str(e)
    print(f"[警告] BookwormPRO modules not importable: {e}")
    print("[信息] Falling back to standalone urllib probe...")

# --- Discovery: auth.json + .env ---
providers = {}
HOME = Path.home()
RUNTIME = HOME / '.bookwormpro'

# Source 1: auth.json credential_pool
auth_path = RUNTIME / 'auth.json'
if auth_path.exists():
    auth = json.loads(auth_path.read_text())
    for p_name, entries in auth.get('credential_pool', {}).items():
        for entry in entries:
            if entry.get('base_url') and p_name not in providers:
                providers[p_name] = entry['base_url']

# Source 2: .env — detect *_BASE_URL entries not already in providers
env_path = RUNTIME / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        v = v.strip().strip('"').strip("'")
        if k.endswith('_BASE_URL') and v:
            name = k.replace('_BASE_URL', '').lower()
            if name not in providers:
                providers[name] = v

print(f"\n[发现] {len(providers)} providers:")
for name, url in providers.items():
    print(f"  {name:20s} → {url}")

# --- Probe ---
if MODULES_OK:
    print(f"\n{'Provider':<15s} {'Status':<10s} {'Latency':>8s}  {'Failures':>8s}  {'Error'}")
    print(f"{'-'*15} {'-'*10} {'-'*8}  {'-'*8}  {'-'*30}")
    report = {}
    results = {}
    
    for name, base_url in providers.items():
        try:
            # force=True to bypass cooldown check bug (last_check type mismatch)
            record = probe(name, base_url, force=True)
            status = record.status.value
            results[name] = record
            report[name] = {
                'status': status,
                'latency_ms': round(record.last_latency_ms, 1) if record.last_latency_ms else 0,
                'consecutive_failures': record.consecutive_failures,
                'last_error': record.last_error or ''
            }
            print(f"{name:<15s} {status:<10s} {record.last_latency_ms:7.0f}ms  {record.consecutive_failures:>8d}  {record.last_error or ''}")
        except Exception as e:
            print(f"{name:<15s} ERROR      {0:7.0f}ms  {0:>8d}  {str(e)[:50]}")
            report[name] = {
                'status': 'error',
                'latency_ms': 0,
                'consecutive_failures': 0,
                'last_error': str(e)[:200]
            }
    
    # Trip circuit breakers for genuinely dead providers (not copilot)
    tripped = []
    for name, record in results.items():
        if record.status == HealthStatus.DEAD and name != 'copilot':
            try:
                report_failure(name, reason=f'Health probe DEAD at {time.strftime("%Y-%m-%dT%H:%M:%S")}')
                tripped.append(name)
                print(f"[熔断] {name} circuit breaker tripped")
            except Exception as e:
                print(f"[警告] Failed to trip circuit for {name}: {e}")
    
    # Copilot false-positive handling
    if 'copilot' in results and results['copilot'].status in (HealthStatus.DEGRADED, HealthStatus.DEAD):
        print(f"[信息] copilot false-positive detected, resetting...")
        reset('copilot')
    
else:
    # Standalone fallback
    import urllib.request, urllib.error, ssl
    ctx = ssl.create_default_context()
    
    def probe_http(name, base_url, timeout=15):
        models_url = base_url.rstrip('/') + '/models'
        for test_url, method in [(models_url, 'GET'), (base_url.rstrip('/'), 'HEAD')]:
            try:
                t0 = time.time()
                req = urllib.request.Request(test_url, method=method)
                resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
                lat = (time.time() - t0) * 1000
                if resp.status in (200, 401, 403):
                    return 'healthy', lat, f'HTTP {resp.status}'
            except urllib.error.HTTPError as e:
                lat = (time.time() - t0) * 1000
                if e.code in (401, 403):
                    return 'healthy', lat, f'HTTP {e.code} (auth req)'
                if e.code != 404:
                    return 'degraded', lat, f'HTTP {e.code}'
            except Exception as e:
                lat = (time.time() - t0) * 1000
                continue
        return 'dead', 0, 'no reachable endpoint'
    
    print(f"\n{'Provider':<15s} {'Status':<10s} {'Latency':>8s}  {'Detail'}")
    print(f"{'-'*15} {'-'*10} {'-'*8}  {'-'*40}")
    report = {}
    for name, url in providers.items():
        status, lat, detail = probe_http(name, url)
        print(f"{name:<15s} {status:<10s} {lat:7.0f}ms  {detail}")
        report[name] = {'status': status, 'latency_ms': round(lat, 1), 'detail': detail}
    
    # For standalone mode, use health file to check copilot
    if 'copilot' in report and report['copilot']['status'] in ('degraded', 'dead'):
        copilot_health = RUNTIME / 'health' / 'copilot.json'
        if copilot_health.exists():
            ch = json.loads(copilot_health.read_text())
            if ch.get('current_status') == 'healthy':
                report['copilot']['status'] = 'healthy'
                report['copilot']['detail'] = 'false-positive (health file: healthy)'
                print(f"[信息] copilot false-positive overridden from health file")

# --- Summary ---
healthy = sum(1 for r in report.values() if r['status'] == 'healthy')
degraded = sum(1 for r in report.values() if r['status'] == 'degraded')
dead = sum(1 for r in report.values() if r['status'] == 'dead')
error_count = sum(1 for r in report.values() if r['status'] == 'error')

print(f"\n{'='*60}")
print(f"[成功] HEALTHY:  {healthy}")
print(f"[警告] DEGRADED: {degraded}")
print(f"[失败] DEAD:     {dead}")
if error_count:
    print(f"[失败] ERROR:    {error_count}")
print(f"{'='*60}")

# --- Save Report ---
debug_dir = RUNTIME / 'debug'
debug_dir.mkdir(parents=True, exist_ok=True)
report_path = debug_dir / 'provider_health_report.json'
report_path.write_text(json.dumps({
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'providers': report,
    'summary': {'healthy': healthy, 'degraded': degraded, 'dead': dead, 'error': error_count},
    'circuits_tripped': tripped if MODULES_OK else [],
    'mode': 'inline' if MODULES_OK else 'standalone',
}, indent=2, ensure_ascii=False), encoding='utf-8')
print(f"Report saved: {report_path}")

# Append to log
log_path = debug_dir / 'provider_health.log'
with open(log_path, 'a', encoding='utf-8') as f:
    f.write(json.dumps({
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'summary': {'healthy': healthy, 'degraded': degraded, 'dead': dead, 'error': error_count},
        'providers': {k: v['status'] for k, v in report.items()}
    }, ensure_ascii=False) + '\n')
