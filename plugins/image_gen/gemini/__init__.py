"""Google Gemini image generation backend.

Exposes Google's Gemini image generation models (Nano Banana series) as
an :class:`ImageGenProvider` implementation. Supports two transport paths:

1. **OpenRouter proxy** (default, recommended): Uses OpenRouter's
   OpenAI-compatible endpoint with Gemini models. Requires
   ``OPENROUTER_API_KEY`` env var. Works from China without VPN.

2. **Native Gemini API**: Direct ``generativelanguage.googleapis.com``
   calls. Requires ``GOOGLE_API_KEY`` env var. Blocked in China.

Models
------
* ``gemini-2.5-flash-image`` — Nano Banana 2 (free tier, fast)
* ``gemini-3-pro-image`` — Nano Banana Pro (paid tier, highest quality)

Both output base64 PNG images saved under ``$BOOKWORMPRO_HOME/cache/images/``.

Selection precedence (first hit wins):
1. ``GEMINI_IMAGE_MODEL`` env var
2. ``image_gen.gemini.model`` in ``config.yaml``
3. ``image_gen.model`` in ``config.yaml`` (when it matches one of our IDs)
4. :data:`DEFAULT_MODEL` — ``gemini-2.5-flash-image`` (free tier)

API Keys
--------
- OpenRouter: set ``OPENROUTER_API_KEY`` in ``~/.bookwormpro/.env``
- Google direct: set ``GOOGLE_API_KEY`` in ``~/.bookwormpro/.env``

Free Tier Limits (as of 2026-05)
--------------------------------
* Nano Banana 2 (gemini-2.5-flash-image): 500 requests/day via API
* Nano Banana Pro (gemini-3-pro-image): No free tier (paid only)
"""

from __future__ import annotations

import base64
import logging
import os
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

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
API_MODEL_FLASH_IMAGE = "gemini-3.1-flash-image-preview"
API_MODEL_FLASH_IMAGE_LEGACY = "gemini-2.5-flash-image"
API_MODEL_PRO_IMAGE = "gemini-3-pro-image-preview"

# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

_MODELS: Dict[str, Dict[str, Any]] = {
    "gemini-2.5-flash-image": {
        "display": "Gemini 2.5 Flash Image (Nano Banana 2)",
        "speed": "~8s",
        "strengths": "Free tier, fast, good for iteration",
        "price": "Free (500/day)",
        "api_model": API_MODEL_FLASH_IMAGE,
        "badge": "free",
    },
    "gemini-3-pro-image": {
        "display": "Gemini 3 Pro Image (Nano Banana Pro)",
        "speed": "~20s",
        "strengths": "Highest quality, best prompt adherence, chart/text precision",
        "price": "$0.134/image (2K)",
        "api_model": API_MODEL_PRO_IMAGE,
        "badge": "paid",
    },
}

DEFAULT_MODEL = "gemini-2.5-flash-image"

# Aspect ratio mapping for Gemini imageGenerationConfig
# (format: "W:H" string as expected by the API)
_ASPECT_RATIO_MAP = {
    "landscape": "16:9",
    "square": "1:1",
    "portrait": "9:16",
}

# Prompt-based aspect ratio hints (fallback when imageGenerationConfig unavailable)
_ASPECT_RATIO_PROMPTS = {
    "landscape": "landscape orientation, 16:9 aspect ratio, wide horizontal composition",
    "square": "square format, 1:1 aspect ratio, balanced composition",
    "portrait": "portrait orientation, 9:16 aspect ratio, tall vertical composition",
}


def _get_proxy_url() -> Optional[str]:
    """Detect system proxy for httpx. Returns proxy URL or None."""
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(var, "").strip()
        if val:
            return val
    return None


def _resolve_api_key() -> Optional[str]:
    """Return the Google API key from environment, or None."""
    for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        key = os.environ.get(var, "").strip()
        if key:
            return key
    return None


def _load_gemini_config() -> Dict[str, Any]:
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
    """Decide which Gemini image model to use; returns ``(model_id, meta)``."""
    env_override = os.environ.get("GEMINI_IMAGE_MODEL")
    if env_override and env_override in _MODELS:
        return env_override, _MODELS[env_override]

    cfg = _load_gemini_config()
    gemini_cfg = cfg.get("gemini") if isinstance(cfg.get("gemini"), dict) else {}
    candidate: Optional[str] = None

    # 1. image_gen.gemini.model in config.yaml
    if isinstance(gemini_cfg, dict):
        value = gemini_cfg.get("model")
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


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class GeminiImageGenProvider(ImageGenProvider):
    """Google Gemini image generation backend — Nano Banana 2 & Pro."""

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    def is_available(self) -> bool:
        if not _resolve_api_key():
            return False
        return True

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
            "name": "Google Gemini",
            "badge": "free",
            "tag": "Nano Banana 2 (free) + Nano Banana Pro (paid) — Google AI Studio",
            "env_vars": [
                {
                    "key": "GOOGLE_API_KEY",
                    "prompt": "Google AI Studio API key",
                    "url": "https://aistudio.google.com/apikey",
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
                provider="gemini",
                aspect_ratio=aspect,
            )

        api_key = _resolve_api_key()
        if not api_key:
            return error_response(
                error=(
                    "GOOGLE_API_KEY not set. Get a free key at "
                    "https://aistudio.google.com/apikey then set it via "
                    "`bookworm setup` or add to ~/.bookwormpro/.env"
                ),
                error_type="auth_required",
                provider="gemini",
                aspect_ratio=aspect,
            )

        model_id, meta = _resolve_model()
        api_model = meta["api_model"]

        # Resolve base URL from env or default
        base_url = (
            os.environ.get("GEMINI_BASE_URL", "")
            .strip()
            .rstrip("/")
        ) or DEFAULT_BASE_URL

        # Build the image generation prompt with aspect ratio hint
        ar_hint = _ASPECT_RATIO_PROMPTS.get(aspect, "")
        full_prompt = prompt
        if ar_hint:
            full_prompt = f"{prompt} — {ar_hint}"

        # ------------------------------------------------------------------
        # Build Gemini native API request
        # ------------------------------------------------------------------
        url = f"{base_url}/models/{api_model}:generateContent"

        # generationConfig with image output modality
        generation_config: Dict[str, Any] = {
            "responseModalities": ["IMAGE", "TEXT"],
        }

        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": full_prompt}],
                }
            ],
            "generationConfig": generation_config,
        }

        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

        # ------------------------------------------------------------------
        # Call Gemini API
        # ------------------------------------------------------------------
        try:
            proxy_url = _get_proxy_url()
            client_kwargs: Dict[str, Any] = {"timeout": 120.0}
            if proxy_url:
                client_kwargs["proxy"] = proxy_url
            with httpx.Client(**client_kwargs) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            try:
                err_body = exc.response.json()
                err_msg = err_body.get("error", {}).get("message", str(exc))
            except Exception:
                err_msg = exc.response.text[:500] if exc.response else str(exc)
            logger.error("Gemini image gen failed (%d): %s", status, err_msg)

            # Detect common auth errors
            if status == 403:
                return error_response(
                    error=(
                        f"Gemini API authentication failed (403): {err_msg}\n"
                        "Your API key may be invalid or from a restricted project. "
                        "Get a new key at https://aistudio.google.com/apikey"
                    ),
                    error_type="auth_error",
                    provider="gemini",
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            elif status == 429:
                return error_response(
                    error=(
                        f"Gemini API rate limit exceeded (429): {err_msg}\n"
                        "Free tier: 500 requests/day. Consider upgrading to "
                        "a paid plan or switching to gemini-2.5-flash-image."
                    ),
                    error_type="rate_limit",
                    provider="gemini",
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            return error_response(
                error=f"Gemini image generation failed ({status}): {err_msg}",
                error_type="api_error",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except httpx.TimeoutException:
            return error_response(
                error="Gemini image generation timed out (120s)",
                error_type="timeout",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except httpx.ConnectError as exc:
            return error_response(
                error=f"Gemini connection error: {exc}",
                error_type="connection_error",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # ------------------------------------------------------------------
        # Parse Gemini response
        # ------------------------------------------------------------------
        try:
            result = resp.json()
        except Exception as exc:
            return error_response(
                error=f"Gemini returned invalid JSON: {exc}",
                error_type="invalid_response",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Extract inline image data from candidates
        # Response shape:
        #   candidates[0].content.parts[] → {text: ...} | {inlineData: {mimeType, data}}
        candidates = result.get("candidates", [])
        if not candidates:
            # Check for prompt feedback / safety blocks
            fb = result.get("promptFeedback", {})
            block_reason = fb.get("blockReason", "")
            if block_reason:
                return error_response(
                    error=f"Gemini blocked the prompt: {block_reason}",
                    error_type="content_filter",
                    provider="gemini",
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            return error_response(
                error="Gemini returned no candidates (empty response)",
                error_type="empty_response",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "STOP")

        # Check for safety filter
        if finish_reason == "SAFETY":
            return error_response(
                error="Gemini blocked the output due to safety filters",
                error_type="content_filter",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        content = candidate.get("content", {})
        parts = content.get("parts", [])

        # Find the first inlineData (image) part
        image_b64 = None
        image_mime = "image/png"
        response_text = ""

        for part in parts:
            if "inlineData" in part:
                inline = part["inlineData"]
                image_b64 = inline.get("data", "")
                image_mime = inline.get("mimeType", "image/png")
                break
            elif "text" in part:
                response_text += part.get("text", "")

        if not image_b64:
            # No image generated — may have returned text-only (e.g. describing image)
            if response_text:
                return error_response(
                    error=f"Gemini returned text but no image: {response_text[:300]}",
                    error_type="no_image_generated",
                    provider="gemini",
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            return error_response(
                error="Gemini response contained no image data",
                error_type="empty_response",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # ------------------------------------------------------------------
        # Save image to cache
        # ------------------------------------------------------------------
        # Determine file extension from MIME type
        ext = "png"
        if "jpeg" in image_mime or "jpg" in image_mime:
            ext = "jpg"
        elif "webp" in image_mime:
            ext = "webp"

        try:
            saved_path = save_b64_image(image_b64, prefix=f"gemini_{model_id}", extension=ext)
        except Exception as exc:
            return error_response(
                error=f"Could not save image to cache: {exc}",
                error_type="io_error",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        extra: Dict[str, Any] = {
            "finish_reason": finish_reason,
            "mime_type": image_mime,
        }
        if response_text:
            extra["response_text"] = response_text[:500]

        return success_response(
            image=str(saved_path),
            model=model_id,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="gemini",
            extra=extra,
        )


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx: Any) -> None:
    """Register this provider with the image gen registry."""
    ctx.register_image_gen_provider(GeminiImageGenProvider())
