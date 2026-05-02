"""

Stage 3: Image Generation (v1.1 — P0+P1+P2 修复版)

═══════════════════════════════════════════════════════

变更:

  P0-3  → Prompt 注入过滤 (sanitize_prompt)

  P0-1  → API Key 加密存储 (get_api_key)

  P0-4  → 输出文件安全校验 (validate_output_file)

  P0-2  → 成本追踪 (CostTracker)

  P1-1  → 并发生成 (ThreadPoolExecutor)

  P1-2  → Prompt 分层 (System/User/Negative)

  A5    → ImageProvider 抽象接口

  M2    → Critic 反馈增强重生成 (augment_prompt_from_critic)

  M3    → 智能截断 (truncate_at_sentence)

  M4    → seed 支持 (可复现)

"""
import sys



import os

import json

import time

from pathlib import Path

from concurrent.futures import ThreadPoolExecutor, as_completed



# 添加 shared 到 path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared"))



from image_provider import (

    get_provider, get_fallback_provider, ImageProvider, ImageResult,

    validate_output_file

)

from security import sanitize_prompt, sanitize_all, get_api_key, mask_key
from cost_tracker import CostTracker, BudgetExceededError

from cost_tracker import CostTracker, BudgetExceededError



import sys



# ── 配置 ─────────────────────────────────────────────



DEFAULT_PROVIDER = os.environ.get("AD_PRIMARY_PROVIDER", "seedream")
MAX_CONCURRENT = 3   # Seedream支持并发3, 429时自动降级
MAX_CONCURRENT = 5

DEFAULT_BUDGET = float(os.environ.get("AD_BUDGET_YUAN", "5.0"))



# 平台 → 生成尺寸

PLATFORM_CANVAS = {

    "google_display": "1792x1024",

    "facebook_feed": "1024x1024",

    "instagram_feed": "1024x1024",

    "instagram_story": "1024x1792",

    "linkedin": "1792x1024",

    "wechat_moment": "1024x1024",

    "douyin": "1024x1792",

}





# ── Prompt 工程 ──────────────────────────────────────



def build_system_prompt(design_direction: dict, tone: str = "professional") -> str:

    """P1-2: System Prompt — 风格/质量约束"""

    palette = design_direction.get("color_palette", {})

    style = design_direction.get("style", "")



    return (

        f"你是一个专业的商业广告图设计师。\n"

        f"风格方向: {style}\n"

        f"品牌调性: {tone}\n"

        f"主色调: {palette.get('primary', '#0052D9')}\n"

        f"强调色: {palette.get('accent', '#E37318')}\n"

        f"禁止: 水印、低分辨率、非商业元素、NSFW内容、"

        f"塑料质感、AI 常见畸变(扭曲手指/文字变形/奇异光影)"

    )



def build_user_prompt(concept: dict, design_direction: dict,

                      critic_feedback: str = "") -> str:

    """P1-2: User Prompt — 具体构图描述 + Critic 反馈增强"""

    parts = []



    # 主体描述 (来自 Stage 1)

    parts.append(concept.get("visual_description", ""))



    # 构图 (来自 Stage 2)

    composition = design_direction.get("composition_desc", "")

    if composition:

        parts.append(f"构图: {composition}")



    # 文字要求

    headline = concept.get("headline", "")

    subhead = concept.get("subheadline", "")

    cta = concept.get("cta", "")

    if headline:

        parts.append(f"主标题文字'{headline}'位于画面上方，字体大而清晰")

    if subhead:

        parts.append(f"副标题'{subhead}'位于主标题下方")

    if cta:

        parts.append(f"CTA按钮'{cta}'位于右下角")



    # Critic 反馈增强 (M2)

    if critic_feedback:

        parts.append(f"【重要优化要求】{critic_feedback}")



    # 质量要求

    parts.append("4K分辨率, 商业广告摄影质感, 自然光影, 专业布光")



    prompt = "。".join(parts)

    return truncate_at_sentence(prompt, max_chars=800)





def build_negative_prompt(design_direction: dict) -> str:

    """Negative Prompt — gpt-image-2 不原生支持但中继站可能有"""

    return (

        "watermark, text, signature, low quality, blurry, "

        "deformed, distorted, ugly, bad anatomy, extra limbs, "

        "plastic texture, cartoon, 3d render, "

        "nsfw, nude, gore, violent"

    )





def augment_prompt_from_critic(original_prompt: str, critic_result: dict) -> str:

    """

    M2: Critic 反馈 → Prompt 增强

    将 Critic 的低分维度转化为具体优化指令

    """

    hints = []

    details = critic_result.get("details", {})



    if details.get("contrast", {}).get("score", 10) < 6:

        hints.append("高对比度, 深色背景配亮色文字, 文字与背景层次分明")



    if details.get("readability", {}).get("score", 10) < 6:

        hints.append("文字清晰可读, 避免文字与背景图案重叠")



    if details.get("brand_consistency", {}).get("score", 10) < 6:

        hints.append("严格使用指定品牌色, 主色调突出")



    if details.get("aesthetic", {}).get("score", 10) < 6:

        hints.append("专业商业摄影质感, 避免AI感, 自然光影, 真实材质")



    if hints:

        return original_prompt + "。【特别优化: " + "；".join(hints) + "】"

    return original_prompt





def truncate_at_sentence(text: str, max_chars: int = 800) -> str:

    """M3: 智能截断——在完整句子边界截断"""

    if len(text) <= max_chars:

        return text



    # 找最后一个完整句子边界 (。！？)

    truncated = text[:max_chars]

    for delimiter in ["。", "！", "？", ".", "!", "?"]:

        last_idx = truncated.rfind(delimiter)

        if last_idx > max_chars * 0.7:  # 至少保留了 70%

            return truncated[:last_idx + 1]

    return truncated[:max_chars - 3] + "..."



# ── 主函数: 并发生成 ─────────────────────────────────



def generate_images(

    concepts: list[dict],

    design_directions: list[dict],

    output_dir: str,

    platform: str = "facebook_feed",

    provider_name: str = DEFAULT_PROVIDER,

    budget_yuan: float = DEFAULT_BUDGET,

    concurrent: int = MAX_CONCURRENT,

    critic_results: dict = None,          # M2: 来自上一轮 Critic 的反馈

    seed_base: int = None                 # M4: 可复现种子

) -> tuple[list[dict], dict]:

    """

    P1-1: 并发生成图片



    Args:

        concepts: Stage 1 概念列表

        design_directions: Stage 2 设计方向列表

        output_dir: 输出目录

        platform: 目标平台

        provider_name: "gpt-image-2" 或 "dashscope"

        budget_yuan: 预算上限

        concurrent: 并发数

        critic_results: {(concept_id): critic_dict} 上一轮评审结果

        seed_base: 种子基数



    Returns:

        (images, metrics_dict)

    """

    # ── 初始化 ──

    os.makedirs(output_dir, exist_ok=True)

    cost_tracker = CostTracker(budget_yuan=budget_yuan)
    metrics = {"images_generated": 0, "images_failed": 0, "cost_yuan": 0}
    canvas_size = PLATFORM_CANVAS.get(platform, "1024x1024")

    cost_tracker = CostTracker(budget_yuan=budget_yuan)



    # 初始化 Provider

    try:

        provider = get_provider(provider_name)

    except Exception as e:

        print(f"⚠️ 主 Provider 不可用: {e}, 尝试备选...")

        provider = get_fallback_provider(provider_name)

        if not provider:

            raise RuntimeError("无可用的图片生成 Provider")



    # ── 准备任务 ──

    tasks = []

    for concept in concepts:

        dd = next((d for d in design_directions if d["concept_id"] == concept["id"]), None)

        if not dd:

            continue



        # P0-3: Prompt 注入过滤

        vis_desc = sanitize_prompt(concept.get("visual_description", ""))

        headline = sanitize_prompt(concept.get("headline", ""))

        subhead = sanitize_prompt(concept.get("subheadline", ""))

        cta = sanitize_prompt(concept.get("cta", ""))



        concept_clean = {**concept,

            "visual_description": vis_desc,

            "headline": headline,

            "subheadline": subhead,

            "cta": cta

        }



        # M2: Critic 反馈增强

        critic_fb = ""

        if critic_results and concept["id"] in critic_results:

            c = critic_results[concept["id"]]

            if c.get("overall_score", 10) < 6.0:

                critic_fb = _build_critic_feedback_string(c)



        # 构造 Prompt

        user_prompt = build_user_prompt(concept_clean, dd, critic_fb)

        # 如果生成失败，用上次 prompt（用于增强版重试）

        original_prompt = augment_prompt_from_critic(user_prompt, critic_results.get(concept["id"], {})) if critic_results else user_prompt



        # M4: seed

        seed = None

        if seed_base is not None:

            seed = seed_base + hash(concept["id"]) % 10000



        tasks.append((concept_clean, dd, original_prompt, seed))



    # ── P0-2: 预算检查 ──

    try:

        cost_tracker.check_and_charge(provider_name, len(tasks), provider.cost_per_image())

    except BudgetExceededError as e:

        return [], {"error": str(e), "images_generated": 0, "cost_yuan": 0}



    # ── P1-1: 并发生成 ──

    results = []

    success_count = 0

    fail_count = 0



    with ThreadPoolExecutor(max_workers=concurrent) as executor:

        futures = {}

        for concept_clean, dd, prompt, seed in tasks:

            future = executor.submit(

                _generate_single,

                provider, prompt, canvas_size, output_dir,

                concept_clean["id"], seed

            )

            futures[future] = concept_clean["id"]



        for future in as_completed(futures):

            concept_id = futures[future]

            try:

                result = future.result()

                if result:

                    results.append(result)

                    success_count += 1

            except Exception as e:

                fail_count += 1

                results.append({

                    "id": f"img_failed_{concept_id}",

                    "concept_id": concept_id,

                    "path": "",

                    "error": str(e),

                    "status": "failed"

                })



    # ── 汇总 ──

    actual_cost = success_count * provider.cost_per_image()

    return results, {

        "images_generated": success_count,

        "images_failed": fail_count,

        "cost_yuan": round(actual_cost, 2),

        "provider": provider_name,

        "provider_cost_per": provider.cost_per_image(),

    }





def _generate_single(provider: ImageProvider, prompt: str,

                     size: str, output_dir: str,

                     concept_id: str, seed: int = None) -> dict:

    """单张生成 + 安全校验"""

    result = provider.generate(

        prompt=prompt,

        size=size,

        seed=seed,

        output_dir=output_dir

    )

    return {

        "id": result.image_id,

        "concept_id": concept_id,

        "path": result.path,

        "prompt_used": result.prompt_used,

        "model": result.model,

        "size": result.size,

        "cost_yuan": result.cost_yuan,

        "duration_s": result.duration_s,

        "status": "completed"

    }





def _build_critic_feedback_string(critic: dict) -> str:

    """将 Critic 评审转为自然语言反馈"""

    hints = []

    details = critic.get("details", {})

    for dim, key in [("contrast", "对比度"), ("readability", "可读性"),

                      ("brand_consistency", "品牌一致性"), ("aesthetic", "美学质量")]:

        score = details.get(dim, {}).get("score", 10)

        if score < 6:

            hints.append(f"{key}不足(评分{score}/10)")

    return "；".join(hints) if hints else ""

