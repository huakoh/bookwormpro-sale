"""
AdCreativePipeline — 自动清理 (P1-5 · O2)
每周清理 7 天前已完成 Pipeline 的中间文件
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta

OUTPUT_BASE = Path.home() / ".bookwormpro" / "output"
RETENTION_DAYS = 7
STAGES_TO_KEEP = ["stage5"]  # 仅保留最终导出

def cleanup_old_pipelines(dry_run: bool = True) -> dict:
    """
    清理过期 Pipeline 目录
    - 保留: Stage 5 导出文件 + state.json
    - 删除: Stage 3/4 中间图片 + 日志
    - 删除: >7 天的已完成 Pipeline
    """
    if not OUTPUT_BASE.exists():
        return {"deleted": 0, "freed_mb": 0}

    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted = 0
    freed_bytes = 0

    for pipeline_dir in OUTPUT_BASE.iterdir():
        if not pipeline_dir.is_dir():
            continue

        state_file = pipeline_dir / "state.json"
        if not state_file.exists():
            # 无状态文件 → 直接删除
            size = _dir_size(pipeline_dir)
            if not dry_run:
                shutil.rmtree(pipeline_dir)
            deleted += 1
            freed_bytes += size
            continue

        # 读取状态
        try:
            with open(state_file) as f:
                state = json.load(f)
        except Exception:
            continue

        created = state.get("created_at", "")
        try:
            created_dt = datetime.fromisoformat(created)
        except Exception:
            created_dt = datetime.fromtimestamp(pipeline_dir.stat().st_ctime)

        status = state.get("status", "")

        if status == "completed" and created_dt < cutoff:
            # 已完成且过期 → 清理中间文件，保留导出
            size = _cleanup_intermediate(pipeline_dir, dry_run)
            freed_bytes += size
        elif status in ("failed", "aborted") and created_dt < cutoff:
            # 失败/终止 → 7天后全删
            size = _dir_size(pipeline_dir)
            if not dry_run:
                shutil.rmtree(pipeline_dir)
            deleted += 1
            freed_bytes += size

    return {
        "deleted_dirs": deleted,
        "freed_mb": round(freed_bytes / (1024 * 1024), 1)
    }


def _cleanup_intermediate(pipeline_dir: Path, dry_run: bool) -> int:
    """清理中间文件，仅保留最终输出"""
    freed = 0
    for item in pipeline_dir.iterdir():
        if item.name in ("exports", "state.json", "metadata.json"):
            continue  # 保留
        if item.is_dir():
            size = _dir_size(item)
            if not dry_run:
                shutil.rmtree(item)
            freed += size
        elif item.suffix in (".png", ".jpg", ".log", ".jsonl"):
            if not dry_run:
                item.unlink()
            freed += item.stat().st_size
    return freed


def _dir_size(path: Path) -> int:
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


# CLI: python cleanup.py [--execute]
if __name__ == "__main__":
    import sys
    dry_run = "--execute" not in sys.argv
    result = cleanup_old_pipelines(dry_run=dry_run)
    action = "将清理" if dry_run else "已清理"
    print(f"{action} {result['deleted_dirs']} 个目录, 释放 {result['freed_mb']}MB")
    if dry_run:
        print("加 --execute 实际执行")
