"""
Stage 4 修复版 — doubao-seed-1-6-vision 自动评审
替代原 vision_analyze（deepseek 不兼容），同一 ARK key
"""

import base64, json, requests
from pathlib import Path

ARK_KEY = "ark-YOUR-KEY-HERE
ARK_BASE = "https://ark.cn-beijing.volces.com/api/v3"
VISION_MODEL = "doubao-seed-1-6-vision-250815"

def _call_vision(image_path: str, question: str) -> str:
    """调用豆包视觉模型，返回文本"""
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    r = requests.post(f"{ARK_BASE}/chat/completions",
        json={
            "model": VISION_MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": question}
            ]}],
            "max_tokens": 500
        },
        headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
        timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Vision error {r.status_code}: {r.text[:200]}")
    return r.json()["choices"][0]["message"]["content"]


def critique_image(image_path: str, brand_context: dict = None, platform: str = "wechat") -> dict:
    """
    一枪四维评审（合并为一次 API 调用，省 token）
    返回: {overall_score, pass, needs_regeneration, details, issues}
    """
    question = """评估这张广告/产品图，0-10分:
1) contrast: 主体与背景层次、文字可读对比度
2) composition: 构图是否平衡、视觉焦点是否清晰
3) aesthetics: 光线质感、色彩和谐度、AI畸变检测
4) commercial: 商业可用性、是否可直接用于官网
返回纯JSON: {"contrast":分,"composition":分,"aesthetics":分,"commercial":分,"issues":["问题1"]}"""
    
    text = _call_vision(image_path, question)
    
    # Parse JSON from response
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    
    scores = json.loads(text)
    
    weights = {"contrast": 0.25, "composition": 0.25, "aesthetics": 0.25, "commercial": 0.25}
    overall = sum(scores.get(k, 5) * w for k, w in weights.items())
    
    return {
        "image_path": image_path,
        "overall_score": round(overall, 1),
        "details": {k: {"score": scores.get(k, 5)} for k in weights},
        "issues": scores.get("issues", []),
        "pass": overall >= 6.0,
        "needs_regeneration": overall < 4.0,
        "needs_fix": 4.0 <= overall < 6.0,
    }


def batch_critique(image_paths: list[str], brand_context: dict = None) -> list[dict]:
    """批量评审，每张一次 API 调用"""
    return [critique_image(p, brand_context) for p in image_paths]
