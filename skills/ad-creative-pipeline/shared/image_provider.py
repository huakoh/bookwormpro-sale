"""
AdCreativePipeline — ImageProvider 抽象接口
支持: DashScope qwen-image-plus (默认) · gpt-image-2 (中转站/OpenRouter)
v1.2 实战修正: DashScope 返回 url 非 b64_json · 并发限流 · 内容审核拦截
"""

import os, sys, time, base64, hashlib, requests
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── 数据模型 ──

@dataclass
class ImageResult:
    image_id: str
    path: str
    prompt_used: str
    model: str
    size: str
    cost_yuan: float
    duration_s: float
    metadata: dict = field(default_factory=dict)

@dataclass
class ProviderInfo:
    name: str
    display_name: str
    cost_per_image_yuan: float
    max_concurrent: int
    supported_sizes: list
    requires_api_key: bool
    requires_base_url: bool

# ── 抽象接口 ──

class ImageProvider(ABC):
    @abstractmethod
    def info(self) -> ProviderInfo: ...
    @abstractmethod
    def generate(self, prompt: str, size: str = "1024x1024",
                 negative_prompt: str = "", seed: Optional[int] = None,
                 output_dir: str = ".") -> ImageResult: ...
    @abstractmethod
    def health_check(self) -> bool: ...
    def cost_per_image(self) -> float:
        return self.info().cost_per_image_yuan

# ── 异常 ──

class SecurityError(Exception): pass

class ContentFilteredError(Exception):
    """DashScope 内容审核拦截——需重写 prompt 后重试"""
    pass

# ── DashScope Provider (默认) ──

class DashScopeProvider(ImageProvider):

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._retry_delay = 3  # 429 限流后等待秒数

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="dashscope",
            display_name="通义万相 qwen-image-plus",
            cost_per_image_yuan=0.04,
            max_concurrent=1,          # 实战: 并发>1 触发 429
            supported_sizes=["1024*1024", "720*1280", "1280*720"],
            requires_api_key=True,
            requires_base_url=False
        )

    def generate(self, prompt: str, size: str = "1024*1024",
                 negative_prompt: str = "", seed: Optional[int] = None,
                 output_dir: str = ".") -> ImageResult:

        from dashscope import ImageSynthesis

        start = time.time()
        truncated = prompt[:800]  # DashScope 800字符限制

        for attempt in range(3):
            response = ImageSynthesis.call(
                model="qwen-image-plus",
                prompt=truncated,
                n=1,
                size=size,
                api_key=self.api_key
            )

            if response.status_code == 429:
                if attempt < 2:
                    time.sleep(self._retry_delay * (attempt + 1))
                    continue
                raise RuntimeError(f"DashScope rate limited after 3 retries")

            if response.status_code != 200:
                raise RuntimeError(f"DashScope API error: {response.message}")

            task_id = response.output.task_id
            image_data = self._wait_for_task(task_id)
            break

        image_id = f"img_ds_{hashlib.md5(prompt.encode()).hexdigest()[:12]}"
        img_path = Path(output_dir) / f"{image_id}.png"
        img_path.write_bytes(image_data)

        validate_output_file(str(img_path))

        return ImageResult(
            image_id=image_id,
            path=str(img_path),
            prompt_used=prompt,
            model="qwen-image-plus",
            size=size,
            cost_yuan=0.04,
            duration_s=round(time.time() - start, 1)
        )

    def _wait_for_task(self, task_id: str, timeout: int = 120) -> bytes:
        from dashscope import ImageSynthesis

        start = time.time()
        while time.time() - start < timeout:
            result = ImageSynthesis.fetch(task_id, api_key=self.api_key)
            status = result.output.task_status
            if status == "SUCCEEDED":
                # DashScope 返回 url 非 b64_json (实战验证)
                img_url = result.output.results[0].url
                resp = requests.get(img_url, timeout=30)
                if resp.status_code != 200:
                    raise RuntimeError(f"Failed to download image: {resp.status_code}")
                return resp.content
            elif status == "FAILED":
                msg = result.output.message or "unknown"
                if "inappropriate" in msg.lower():
                    raise ContentFilteredError(f"DashScope 内容审核拦截: {msg}")
                raise RuntimeError(f"DashScope task failed: {msg}")
            time.sleep(2)
        raise TimeoutError(f"DashScope task {task_id} timed out")

    def health_check(self) -> bool:
        try:
            from dashscope import ImageSynthesis
            return True
        except ImportError:
            return False


# ── gpt-image-2 Provider (中转站, OpenAI 兼容) ──

class GPTImage2Provider(ImageProvider):

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="gpt-image-2",
            display_name="GPT Image 2 (via 中转站)",
            cost_per_image_yuan=0.15,
            max_concurrent=3,
            supported_sizes=["1024x1024", "1792x1024", "1024x1792"],
            requires_api_key=True,
            requires_base_url=True
        )

    def generate(self, prompt: str, size: str = "1024x1024",
                 negative_prompt: str = "", seed: Optional[int] = None,
                 output_dir: str = ".") -> ImageResult:

        start = time.time()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {"model": "gpt-image-2", "prompt": prompt, "n": 1, "size": size}

        resp = requests.post(f"{self.base_url}/images/generations", json=body,
                             headers=headers, timeout=120)

        if resp.status_code == 429:
            raise RuntimeError("gpt-image-2 rate limited — try dashscope fallback")
        if resp.status_code != 200:
            raise RuntimeError(f"gpt-image-2 error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        img_data = data["data"][0]

        # 兼容 url 和 b64_json 两种返回格式
        if "b64_json" in img_data:
            image_bytes = base64.b64decode(img_data["b64_json"])
        elif "url" in img_data:
            image_bytes = requests.get(img_data["url"], timeout=30).content
        else:
            raise RuntimeError("gpt-image-2 response missing image data")

        image_id = f"img_gpt2_{hashlib.md5(prompt.encode()).hexdigest()[:12]}"
        img_path = Path(output_dir) / f"{image_id}.png"
        img_path.write_bytes(image_bytes)

        validate_output_file(str(img_path))

        return ImageResult(
            image_id=image_id, path=str(img_path), prompt_used=prompt,
            model="gpt-image-2", size=size,
            cost_yuan=0.15, duration_s=round(time.time() - start, 1)
        )

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/models",
                                headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False



# ── Seedream Provider (火山引擎 ARK, OpenAI 兼容) ──

class SeedreamProvider(ImageProvider):
    """Doubao-Seedream-5.0-lite via 火山引擎 ARK (OpenAI /v3/images/generations 兼容)"""

    def __init__(self, api_key: str, base_url: str = "https://ark.cn-beijing.volces.com/api/v3"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            name="seedream",
            display_name="豆包 Seedream 5.0 (火山引擎)",
            cost_per_image_yuan=0.02,  # 需实测确认
            max_concurrent=3,
            supported_sizes=["1920x1920", "1664x2560", "2560x1664"],
            requires_api_key=True,
            requires_base_url=False
        )

    def generate(self, prompt: str, size: str = "1024x1024",
                 negative_prompt: str = "", seed: Optional[int] = None,
                 output_dir: str = ".") -> ImageResult:

        start = time.time()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {"model": "doubao-seedream-5-0-260128", "prompt": prompt,
                "n": 1, "size": size}

        resp = requests.post(f"{self.base_url}/images/generations",
                             json=body, headers=headers, timeout=120)

        if resp.status_code != 200:
            raise RuntimeError(f"Seedream error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        img_data = data["data"][0]

        # 兼容 url 和 b64_json
        if "b64_json" in img_data:
            image_bytes = base64.b64decode(img_data["b64_json"])
        elif "url" in img_data:
            image_bytes = requests.get(img_data["url"], timeout=30).content
        else:
            raise RuntimeError("Seedream response missing image data")

        image_id = f"img_sd_{hashlib.md5(prompt.encode()).hexdigest()[:12]}"
        img_path = Path(output_dir) / f"{image_id}.png"
        img_path.write_bytes(image_bytes)
        validate_output_file(str(img_path))

        return ImageResult(
            image_id=image_id, path=str(img_path), prompt_used=prompt,
            model="doubao-seedream-5-0-260128", size=size,
            cost_yuan=0.02, duration_s=round(time.time() - start, 1)
        )

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/models",
                                headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

# ── Provider 工厂 ──

_providers: dict[str, ImageProvider] = {}

def get_provider(name: str = "dashscope", **kwargs) -> ImageProvider:
    if name in _providers:
        return _providers[name]

    if name == "dashscope":
        api_key = kwargs.get("api_key") or os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY required")
        provider = DashScopeProvider(api_key)

    elif name == "seedream":
        api_key = kwargs.get("api_key") or os.environ.get("SEEDREAM_API_KEY", "")
        if not api_key:
            raise ValueError("SEEDREAM_API_KEY required (火山引擎 ARK API Key)")
        provider = SeedreamProvider(api_key)

    elif name == "gpt-image-2":
        base_url = kwargs.get("base_url") or os.environ.get("GPT_IMAGE_BASE_URL", "")
        api_key = kwargs.get("api_key") or os.environ.get("GPT_IMAGE_API_KEY", "")
        if not base_url or not api_key:
            raise ValueError("gpt-image-2 requires base_url and api_key")
        provider = GPTImage2Provider(base_url, api_key)

    else:
        raise ValueError(f"Unknown provider: {name}")

    _providers[name] = provider
    return provider

def get_fallback_provider(primary_name: str, **kwargs) -> Optional[ImageProvider]:
    fallback_map = {"dashscope": "seedream", "seedream": "dashscope", "gpt-image-2": "seedream"}
    fallback = fallback_map.get(primary_name)
    if not fallback:
        return None
    try:
        return get_provider(fallback, **kwargs)
    except Exception:
        return None


# ── 输出安全校验 ──

def validate_output_file(path: str):
    with open(path, "rb") as f:
        header = f.read(8)
        if header[:4] != b'\x89PNG':
            raise SecurityError(f"Invalid PNG header: {path}")
    from PIL import Image
    try:
        img = Image.open(path)
        img.verify()
    except Exception as e:
        os.remove(path)
        raise SecurityError(f"Invalid image: {path} — {e}")
