#!/usr/bin/env python3
"""
AdCreativePipeline CLI — 一键全流程
用法:
  python run_pipeline.py --brand "D-阿洛酮糖" --product "健康曲奇" --platform wechat --auto
  python run_pipeline.py --brand "明远生物" --product "AVITS温控" --platform linkedin --concepts 3 --provider dashscope
"""

import sys, os, json, time, argparse
from pathlib import Path

SKILL_DIR = Path.home() / ".bookwormpro" / "skills" / "ad-creative-pipeline"
sys.path.insert(0, str(SKILL_DIR / "shared"))

# Load .env
env_file = Path.home() / ".bookwormpro" / ".env"
if env_file.exists():
    for line in open(env_file).readlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

import yaml
from image_provider import get_provider
from cost_tracker import CostTracker
from metrics import MetricsCollector
from critic_vision import batch_critique


def main():
    ap = argparse.ArgumentParser(description="AdCreativePipeline — 广告图全流程生成")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--audience", default="通用受众")
    ap.add_argument("--platform", default="wechat")
    ap.add_argument("--tone", default="professional")
    ap.add_argument("--colors", default="")
    ap.add_argument("--concepts", type=int, default=3)
    ap.add_argument("--provider", default="seedream")
    ap.add_argument("--budget", type=float, default=10.0)
    ap.add_argument("--output", default="")
    ap.add_argument("--auto", action="store_true", help="跳过人工Gate")
    ap.add_argument("--resume", default="", help="恢复pipeline_id")
    args = ap.parse_args()

    # Init output
    if args.resume:
        output_dir = Path(args.resume)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_dir = Path(args.output or f"./ad-output/acp_{ts}")
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"🚀 AdCreativePipeline")
    print(f"   品牌: {args.brand} | 产品: {args.product}")
    print(f"   平台: {args.platform} | Provider: {args.provider} | 预算: ¥{args.budget}")
    print(f"   输出: {output_dir}")
    print()

    # Pre-flight
    provider = get_provider(args.provider)
    print(f"✅ Provider: {provider.info().display_name}")

    tracker = CostTracker(budget_yuan=args.budget)
    metrics = MetricsCollector("acp_cli", str(output_dir))

    # === Stage 1+2: 需要LLM执行，CLI模式用预定模板 ===
    # 在实际使用中，Stage 1+2 由 BookwormPRO LLM 执行
    # CLI 模式使用简化流程：直接用 product_description 构造 prompt
    print("Stage 1+2: 跳过（CLI模式直接用产品描述构造prompt）")
    print()

    # === Stage 3: Generate ===
    print(f"Stage 3: 生成 {args.concepts} 张广告图...")
    metrics.start_stage("stage3")

    # Simple prompts from product description
    prompts = [
        f"{args.product}产品特写，精致展示，{args.brand}品牌高端定位。商业摄影，4K，{args.platform}广告图。",
        f"{args.product}生活场景中自然使用，{args.brand}品牌。自然光，lifestyle摄影，4K。",
        f"{args.product}极近特写，纹理细节清晰可见，{args.brand}品牌。微距商业摄影，4K。",
    ][:args.concepts]

    images = []
    total_cost = 0
    for i, prompt in enumerate(prompts):
        tracker.check_and_charge(args.provider, 1, provider.cost_per_image())
        print(f"  [{i+1}/{len(prompts)}] 生成中...")
        result = provider.generate(prompt, output_dir=str(output_dir))
        images.append({
            "id": result.image_id,
            "path": result.path,
            "prompt": prompt,
            "cost": result.cost_yuan,
            "duration": result.duration_s,
        })
        total_cost += result.cost_yuan
        print(f"  ✅ {result.image_id}.png ({result.duration_s}s, ¥{result.cost_yuan})")

    metrics.end_stage("stage3", images_generated=len(images), cost_yuan=total_cost, provider=args.provider)
    print(f"  Stage 3 done: {len(images)} images, ¥{total_cost}")
    print()

    # === Stage 4: Critique ===
    print("Stage 4: AI 评审...")
    metrics.start_stage("stage4")

    image_paths = [img["path"] for img in images]
    reviews = batch_critique(image_paths)

    passed = sum(1 for r in reviews if r["pass"])
    failed = sum(1 for r in reviews if r["needs_regeneration"])
    print(f"  通过: {passed} | 需重生成: {failed}")
    for i, r in enumerate(reviews):
        icon = "✅" if r["pass"] else "⚠️" if r["needs_fix"] else "❌"
        print(f"  {icon} 图{i+1}: {r['overall_score']}/10")

    metrics.end_stage("stage4")
    print()

    # === Stage 5: Export ===
    print("Stage 5: 导出...")
    metrics.start_stage("stage5")
    export_dir = output_dir / "exports"
    export_dir.mkdir(exist_ok=True)
    for img in images:
        (export_dir / Path(img["path"]).name).symlink_to(Path(img["path"]).resolve()) if hasattr(Path, "symlink_to") else None
    # Simple copy
    import shutil
    for img in images:
        shutil.copy2(img["path"], export_dir / Path(img["path"]).name)
    print(f"  ✅ {len(images)} files → {export_dir}")

    metrics.end_stage("stage5")
    print()
    print("=" * 50)
    print(f"✅ Pipeline 完成")
    print(f"   📁 {output_dir}")
    print(f"   💰 ¥{total_cost} | ⏱️ {sum(img['duration'] for img in images):.0f}s")
    print(f"   📊 {passed}/{len(reviews)} 通过评审")


if __name__ == "__main__":
    main()
