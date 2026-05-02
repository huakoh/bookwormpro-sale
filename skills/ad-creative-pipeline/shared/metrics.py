"""
AdCreativePipeline — 运行时指标收集 (P2-4)
每阶段耗时/成功率/成本 → metrics.jsonl
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

METRICS_FILE = "metrics.jsonl"

@dataclass
class StageMetrics:
    pipeline_id: str
    stage: str
    status: str            # "started" | "completed" | "failed"
    duration_s: float = 0.0
    images_generated: int = 0
    images_passed: int = 0
    cost_yuan: float = 0.0
    provider: str = ""
    error: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

class MetricsCollector:
    def __init__(self, pipeline_id: str, output_dir: str):
        self.pipeline_id = pipeline_id
        self.path = Path(output_dir) / METRICS_FILE
        self._stages: dict[str, float] = {}  # stage → start_time

    def start_stage(self, stage: str):
        self._stages[stage] = time.time()
        self._write(StageMetrics(
            pipeline_id=self.pipeline_id,
            stage=stage,
            status="started"
        ))

    def end_stage(self, stage: str, **kwargs):
        duration = time.time() - self._stages.get(stage, time.time())
        self._write(StageMetrics(
            pipeline_id=self.pipeline_id,
            stage=stage,
            status=kwargs.pop("status", "completed"),
            duration_s=round(duration, 2),
            **kwargs
        ))

    def _write(self, m: StageMetrics):
        with open(self.path, "a") as f:
            f.write(json.dumps(asdict(m), ensure_ascii=False) + "\n")

    def summary(self) -> dict:
        """聚合统计"""
        if not self.path.exists():
            return {}
        records = []
        with open(self.path) as f:
            for line in f:
                records.append(json.loads(line))

        completed = [r for r in records if r["status"] == "completed"]
        return {
            "total_duration_s": sum(r["duration_s"] for r in completed),
            "total_cost_yuan": sum(r["cost_yuan"] for r in completed),
            "total_images": sum(r["images_generated"] for r in completed),
            "stages_completed": len(completed),
            "failures": len([r for r in records if r["status"] == "failed"]),
        }
