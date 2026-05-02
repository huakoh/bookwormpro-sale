"""
AdCreativePipeline — Pre-flight 健康检查 (P1-6)
Pipeline 启动前验证所有依赖可用
"""

import os
import sys
from pathlib import Path

CHECKS = []

def register_check(name: str):
    """装饰器: 注册健康检查"""
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator

@register_check("pillow_installed")
def check_pillow():
    try:
        from PIL import Image
        return True, "Pillow OK"
    except ImportError:
        return False, "pip install Pillow"

@register_check("output_writable")
def check_output_dir():
    output = Path.home() / ".bookwormpro" / "output"
    try:
        output.mkdir(parents=True, exist_ok=True)
        test_file = output / ".preflight_test"
        test_file.write_text("test")
        test_file.unlink()
        return True, f"Output dir writable: {output}"
    except Exception as e:
        return False, f"Output dir not writable: {e}"

@register_check("disk_space")
def check_disk_space():
    try:
        import shutil
        usage = shutil.disk_usage(Path.home())
        free_gb = usage.free / (1024**3)
        if free_gb < 1:
            return False, f"磁盘空间不足: {free_gb:.1f}GB < 1GB"
        return True, f"磁盘剩余: {free_gb:.1f}GB"
    except Exception:
        return True, "disk check skipped (non-POSIX)"

@register_check("primary_provider")
def check_primary_provider():
    provider = os.environ.get("AD_PRIMARY_PROVIDER", "gpt-image-2")
    try:
        from shared.image_provider import get_provider
        p = get_provider(provider)
        if p.health_check():
            return True, f"Primary provider OK: {provider}"
        return False, f"Provider health check failed: {provider}"
    except Exception as e:
        return False, f"Provider init failed: {e}"

@register_check("fallback_provider")
def check_fallback_provider():
    try:
        from shared.image_provider import get_fallback_provider
        primary = os.environ.get("AD_PRIMARY_PROVIDER", "gpt-image-2")
        fb = get_fallback_provider(primary)
        if fb and fb.health_check():
            return True, f"Fallback provider OK: {fb.info().name}"
        return True, "No fallback available (non-critical)"
    except Exception:
        return True, "Fallback check skipped"

def run_all_checks() -> dict:
    """运行全部健康检查, 返回结果汇总"""
    results = {}
    all_pass = True
    for name, check_fn in CHECKS:
        try:
            passed, message = check_fn()
        except Exception as e:
            passed, message = False, str(e)
        results[name] = {"pass": passed, "message": message}
        if not passed:
            all_pass = False
    return {"all_pass": all_pass, "checks": results}

def print_check_report(results: dict):
    """打印检查报告"""
    for name, r in results["checks"].items():
        icon = "✅" if r["pass"] else "❌"
        print(f"  {icon} {name}: {r['message']}")
    if results["all_pass"]:
        print("\n✅ 全部检查通过, Pipeline 就绪")
    else:
        print("\n❌ 部分检查未通过, 请修复后重试")
        sys.exit(1)
