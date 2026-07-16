"""Alibaba DashScope image generation backend (通义万相 / Qwen-Image).

Exposes Alibaba's Qwen-Image and Wanx models through DashScope API as an
:class:`ImageGenProvider` implementation. Uses async task-based API
(create → poll → download) with the official ``dashscope`` SDK.

Models
------
* ``qwen-image-max`` — Qwen Image Max (旗舰，最高质量，复杂文本渲染)
* ``qwen-image-plus`` — Qwen Image Plus (均衡，推荐日常使用)
* ``qwen-image`` — Qwen Image (基础，快速)

All output base64/URL images are downloaded and saved under
``$BOOKWORMPRO_HOME/cache/images/``.

Selection precedence (first hit wins):
1. ``DASHSCOPE_IMAGE_MODEL`` env var
2. ``image_gen.dashscope.model`` in ``config.yaml``
3. ``image_gen.model`` in ``config.yaml`` (when matching our IDs)
4. :data:`DEFAULT_MODEL` — ``qwen-image-plus``

API Key
-------
Uses ``DASHSCOPE_API_KEY`` from ``~/.bookwormpro/.env``.
Get a key at https://bailian.console.aliyun.com/

Pricing (as of 2026-05)
-----------------------
* qwen-image-max: ¥0.12/张
* qwen-image-plus: ¥0.04/张
* qwen-image: ¥0.02/张
* 新用户有免费试用额度
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# DashScope is China-hosted — no proxy needed (and proxy may interfere)
DASHSCOPE_NO_PROXY = True

# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

_MODELS: Dict[str, Dict[str, Any]] = {
    "qwen-image-max": {
        "display": "Qwen Image Max (通义万相·旗舰)",
        "speed": "~8s",
        "strengths": "最高质量，复杂文本渲染，多行布局，细粒度细节",
        "price": "¥0.12/张",
        "badge": "premium",
        "sizes": ["1024*1024", "1280*720", "720*1280", "1024*768", "768*1024"],
    },
    "qwen-image-plus": {
        "display": "Qwen Image Plus (通义万相·增强)",
        "speed": "~5s",
        "strengths": "均衡质量/速度，推荐日常使用",
        "price": "¥0.04/张",
        "badge": "recommended",
        "sizes": ["1024*1024", "1280*720", "720*1280", "1024*768", "768*1024"],
    },
    "qwen-image": {
        "display": "Qwen Image (通义万相·基础)",
        "speed": "~3s",
        "strengths": "快速，经济实惠",
        "price": "¥0.02/张",
        "badge": "budget",
        "sizes": ["1024*1024", "1280*720", "720*1280"],
    },
}

DEFAULT_MODEL = "qwen-image-plus"

# Aspect ratio → DashScope size mapping
_ASPECT_RATIO_SIZES = {
    "square": "1024*1024",
    "landscape": "1280*720",
    "portrait": "720*1280",
}


def _resolve_api_key() -> Optional[str]:
    """Return the DashScope API key from environment, or None."""
    key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    return key if key else None


def _load_dashscope_config() -> Dict[str, Any]:
    """Read ``image_gen`` section from config.yaml; returns {} on failure."""
    try:
        from bwm_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen config: %s", exc)
        return {}


def _resolve_model() -> Tuple[str, Dict[str, Any]]:
    """Decide which DashScope image model to use; returns ``(model_id, meta)``."""
    env_override = os.environ.get("DASHSCOPE_IMAGE_MODEL")
    if env_override and env_override in _MODELS:
        return env_override, _MODELS[env_override]

    cfg = _load_dashscope_config()
    ds_cfg = cfg.get("dashscope") if isinstance(cfg.get("dashscope"), dict) else {}
    candidate: Optional[str] = None

    # 1. image_gen.dashscope.model in config.yaml
    if isinstance(ds_cfg, dict):
        value = ds_cfg.get("model")
        if isinstance(value, str) and value in _MODELS:
            candidate = value

    # 2. image_gen.model (top-level, when it matches our IDs)
    if candidate is None:
        top = cfg.get("model")
        if isinstance(top, str) and top in _MODELS:
            candidate = top

    if candidate is not None:
        return candidate, _MODELS[candidate]

    return DEFAULT_MODEL, _MODELS[DEFAULT_MODEL]


def _resolve_size(aspect_ratio: str, model_id: str) -> str:
    """Map aspect_ratio to a supported size for the given model."""
    size = _ASPECT_RATIO_SIZES.get(aspect_ratio, "1024*1024")
    # Validate against model's supported sizes
    meta = _MODELS.get(model_id, {})
    supported = meta.get("sizes", ["1024*1024"])
    if size not in supported:
        # Fall back to square if the preferred size isn't supported
        if "1024*1024" in supported:
            return "1024*1024"
        return supported[0]
    return size


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class DashScopeImageGenProvider(ImageGenProvider):
    """Alibaba DashScope image generation backend — 通义万相 / Qwen-Image."""

    @property
    def name(self) -> str:
        return "dashscope"

    @property
    def display_name(self) -> str:
        return "通义万相 (DashScope)"

    def is_available(self) -> bool:
        if not _resolve_api_key():
            return False
        try:
            from dashscope import ImageSynthesis  # noqa: F401

            return True
        except ImportError:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": model_id,
                "display": meta["display"],
                "speed": meta["speed"],
                "strengths": meta["strengths"],
                "price": meta["price"],
                "badge": meta.get("badge", ""),
            }
            for model_id, meta in _MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "通义万相 (DashScope)",
            "badge": "cn",
            "tag": "Qwen-Image 系列 — 国内直连，支付宝/微信，异步生成",
            "env_vars": [
                {
                    "key": "DASHSCOPE_API_KEY",
                    "prompt": "阿里云 DashScope API Key",
                    "url": "https://bailian.console.aliyun.com/",
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider="dashscope",
                aspect_ratio=aspect,
            )

        api_key = _resolve_api_key()
        if not api_key:
            return error_response(
                error=(
                    "DASHSCOPE_API_KEY not set. Get a key at "
                    "https://bailian.console.aliyun.com/ then add to "
                    "~/.bookwormpro/.env"
                ),
                error_type="auth_required",
                provider="dashscope",
                aspect_ratio=aspect,
            )

        try:
            from dashscope import ImageSynthesis
        except ImportError:
            return error_response(
                error="dashscope SDK not installed. Run: pip install dashscope",
                error_type="missing_dependency",
                provider="dashscope",
                aspect_ratio=aspect,
            )

        model_id, meta = _resolve_model()
        size = _resolve_size(aspect, model_id)

        # ------------------------------------------------------------------
        # Step 1: Create async generation task
        # ------------------------------------------------------------------
        try:
            task_resp = ImageSynthesis.async_call(
                model=model_id,
                prompt=prompt,
                n=1,
                size=size,
                api_key=api_key,
            )
        except Exception as exc:
            logger.error("DashScope async_call failed: %s", exc, exc_info=True)
            return error_response(
                error=f"DashScope task creation failed: {exc}",
                error_type="api_error",
                provider="dashscope",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Check for immediate errors
        if hasattr(task_resp, "status_code") and task_resp.status_code != 200:
            msg = getattr(task_resp, "message", "") or str(task_resp)
            code = getattr(task_resp, "code", "unknown")
            if "AccessDenied" in str(msg) or "InvalidApiKey" in str(msg):
                return error_response(
                    error=f"DashScope authentication failed: {msg}",
                    error_type="auth_error",
                    provider="dashscope",
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            if "Throttling" in str(msg) or "RateQuota" in str(msg):
                return error_response(
                    error=f"DashScope rate limit: {msg}",
                    error_type="rate_limit",
                    provider="dashscope",
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            return error_response(
                error=f"DashScope error ({code}): {msg}",
                error_type="api_error",
                provider="dashscope",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        task_id = None
        try:
            task_id = task_resp.output.get("task_id", "")
        except Exception:
            pass

        if not task_id:
            return error_response(
                error="DashScope returned no task_id",
                error_type="invalid_response",
                provider="dashscope",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # ------------------------------------------------------------------
        # Step 2: Poll for completion
        # ------------------------------------------------------------------
        max_polls = 30  # 30 * 2s = 60s max
        image_url = None

        for poll_num in range(max_polls):
            time.sleep(2)
            try:
                status_resp = ImageSynthesis.fetch(task_id, api_key=api_key)
            except Exception as exc:
                logger.error("DashScope poll %d failed: %s", poll_num, exc)
                continue

            task_status = status_resp.output.get("task_status", "")

            if task_status == "SUCCEEDED":
                results = status_resp.output.get("results", [])
                if results:
                    image_url = results[0].get("url", "")
                break
            elif task_status == "FAILED":
                err_msg = status_resp.output.get("message", "Unknown failure")
                return error_response(
                    error=f"DashScope generation failed: {err_msg}",
                    error_type="generation_failed",
                    provider="dashscope",
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            # else: PENDING or RUNNING — continue polling

        if not image_url:
            return error_response(
                error=f"DashScope generation timed out after {max_polls * 2}s",
                error_type="timeout",
                provider="dashscope",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # ------------------------------------------------------------------
        # Step 3: Download image from OSS URL
        # ------------------------------------------------------------------
        try:
            # DashScope OSS URLs are China-hosted — no proxy needed
            with httpx.Client(timeout=60.0, proxy=None) as client:
                dl_resp = client.get(image_url)
                dl_resp.raise_for_status()
                image_bytes = dl_resp.content
        except httpx.HTTPStatusError as exc:
            return error_response(
                error=f"Failed to download image ({exc.response.status_code})",
                error_type="download_error",
                provider="dashscope",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except httpx.TimeoutException:
            return error_response(
                error="Image download timed out (60s)",
                error_type="timeout",
                provider="dashscope",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Determine extension from URL or default to png
        ext = "png"
        url_ext = image_url.split(".")[-1].split("?")[0].lower()
        if url_ext in ("jpg", "jpeg", "png", "webp"):
            ext = url_ext

        # Save image via base64 (reuse existing helper)
        import base64
        b64 = base64.b64encode(image_bytes).decode("ascii")
        try:
            saved_path = save_b64_image(b64, prefix=f"dashscope_{model_id}", extension=ext)
        except Exception as exc:
            return error_response(
                error=f"Could not save image to cache: {exc}",
                error_type="io_error",
                provider="dashscope",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        extra: Dict[str, Any] = {
            "task_id": task_id,
            "size": size,
            "file_size": len(image_bytes),
        }

        return success_response(
            image=str(saved_path),
            model=model_id,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="dashscope",
            extra=extra,
        )


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx: Any) -> None:
    """Register this provider with the image gen registry."""
    ctx.register_image_gen_provider(DashScopeImageGenProvider())
