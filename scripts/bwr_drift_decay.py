#!/usr/bin/env python3
"""
BWR Drift 每日衰减脚本 — 由 cron 调用
防止反馈权重过拟合，每天将 boost/penalty 乘以 0.95 衰减系数。
"""
import sys
sys.path.insert(0, str(__import__('pathlib').Path.home() / "BookwormPRO"))

from agent.bwr_drift import get_corrector

corrector = get_corrector()
corrector.decay_adjustments()

stats = corrector.get_stats()
print(f"BWR Drift Decay 完成:")
print(f"  总事件: {stats['total_events']}")
print(f"  漂移率: {stats['drift_rate']:.1%}")
print(f"  24h漂移: {stats['drifts_24h']}")
if stats['avg_confidence_24h']:
    print(f"  24h平均置信度: {stats['avg_confidence_24h']:.3f}")
