"""
Provider Health Probe — cron job runner
Probes all configured providers and reports health status.
"""
import sys
import os
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import provider_health as ph
from agent import circuit_breaker as cb

import yaml

def load_env(env_path: Path) -> dict:
    env_keys = {}
    if env_path.exists():
        for line in env_path.read_text(errors='replace').splitlines():
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, _, v = line.partition('=')
                env_keys[k.strip()] = v.strip()
                os.environ.setdefault(k.strip(), v.strip())
    return env_keys

def main():
    bwp_home = Path.home() / '.bookwormpro'
    cfg_path = bwp_home / 'config.yaml'
    env_path = bwp_home / '.env'

    with open(cfg_path) as f:
        config = yaml.safe_load(f)

    env_keys = load_env(env_path)

    # Build probe list — deduplicate by base_url
    providers_to_probe = []
    seen_base = set()

    # custom_providers — group by base_url
    for cp in config.get('custom_providers', []):
        bu = (cp.get('base_url') or '').strip()
        pk = (cp.get('provider_key') or '中转站').strip()
        if bu and bu not in seen_base:
            seen_base.add(bu)
            providers_to_probe.append({'name': pk, 'base_url': bu, 'type': 'relay'})

    # Named providers detected via env keys
    known = [
        ('deepseek',   'https://api.deepseek.com/v1',                              'DEEPSEEK_API_KEY'),
        ('google',     'https://generativelanguage.googleapis.com/v1beta',          'GOOGLE_API_KEY'),
        ('dashscope',  'https://dashscope.aliyuncs.com/compatible-mode/v1',         'DASHSCOPE_API_KEY'),
        ('doubao',     'https://ark.cn-beijing.volces.com/api/v3',                  'DOUBAO_API_KEY'),
    ]
    for pname, base_url, key_env in known:
        if env_keys.get(key_env):
            providers_to_probe.append({'name': pname, 'base_url': base_url, 'type': 'named'})

    print(f"Probing {len(providers_to_probe)} provider(s)...\n")

    results = []
    dead_providers = []
    degraded_providers = []
    healthy_providers = []

    for p in providers_to_probe:
        pname = p['name']
        base_url = p['base_url']
        ptype = p['type']

        try:
            record = ph.probe(pname, base_url, force=True)
            status_str = record.status.value if hasattr(record.status, 'value') else str(record.status)
            latency = record.last_latency_ms
            error = record.last_error or ''
            consec_fail = record.consecutive_failures

            entry = {
                'provider': pname,
                'type': ptype,
                'base_url': base_url,
                'status': status_str,
                'latency_ms': round(latency, 1),
                'consecutive_failures': consec_fail,
                'error': error[:120] if error else '',
            }
            results.append(entry)

            if status_str in ('dead', 'DEAD'):
                dead_providers.append(pname)
                # Trip circuit breaker
                try:
                    cb.report_failure(pname, reason=f'probe=DEAD: {error[:80]}')
                    entry['circuit_breaker_tripped'] = True
                except Exception as cbe:
                    entry['circuit_breaker_error'] = str(cbe)[:80]
            elif status_str in ('degraded', 'DEGRADED'):
                degraded_providers.append(pname)
            else:
                healthy_providers.append(pname)

        except Exception as e:
            entry = {
                'provider': pname,
                'type': ptype,
                'base_url': base_url,
                'status': 'probe_error',
                'error': str(e)[:120],
            }
            results.append(entry)
            dead_providers.append(pname)
            try:
                cb.report_failure(pname, reason=f'probe_exception: {str(e)[:80]}')
                entry['circuit_breaker_tripped'] = True
            except Exception:
                pass

    # Save log
    log_dir = bwp_home / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime('%Y-%m-%d_%H%M%S')
    log_file = log_dir / f'provider_health_probe_{ts}.json'
    log_file.write_text(json.dumps({
        'timestamp': ts,
        'summary': {
            'healthy': healthy_providers,
            'degraded': degraded_providers,
            'dead': dead_providers,
        },
        'results': results,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        'healthy': healthy_providers,
        'degraded': degraded_providers,
        'dead': dead_providers,
        'results': results,
    }

if __name__ == '__main__':
    data = main()
    # Print summary to stdout for cron delivery
    print(json.dumps(data, ensure_ascii=False, indent=2))
