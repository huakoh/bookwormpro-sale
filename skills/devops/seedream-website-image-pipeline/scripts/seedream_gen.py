#!/usr/bin/env python3
"""Seedream 5.0 image generator — reusable template.
Usage: python seedream_gen.py "your prompt" output.png [size]
"""
import sys, time, base64, requests
from pathlib import Path

ARK_KEY = "ark-REPLACE-WITH-YOUR-KEY"
URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
MODEL = "doubao-seedream-5-0-260128"


def generate(prompt: str, output_path: str, size: str = "1920x1920", max_retries: int = 3) -> bool:
    """Generate one image via Seedream 5.0."""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "b64_json",
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                URL,
                headers={"Authorization": f"Bearer {ARK_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )

            if resp.status_code == 200:
                data = resp.json()
                img_b64 = data.get("data", [{}])[0].get("b64_json", "")
                if img_b64:
                    Path(output_path).write_bytes(base64.standard_b64decode(img_b64))
                    return True
                url = data.get("data", [{}])[0].get("url", "")
                if url:
                    Path(output_path).write_bytes(requests.get(url, timeout=60).content)
                    return True
                return False

            elif resp.status_code == 429:
                wait = 3 * (attempt + 1)
                print(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            else:
                print(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                continue

        except requests.exceptions.Timeout:
            print(f"Timeout (attempt {attempt+1})")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
        except Exception as e:
            print(f"Error: {e}")
            return False

    return False


def remove_watermark(image_path: str) -> None:
    """Remove Seedream AI watermark from bottom-right corner."""
    from PIL import Image
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    crop_r, crop_b = int(w * 0.04), int(h * 0.03)
    img = img.crop((0, 0, w - crop_r, h - crop_b))
    img = img.resize((w, h), Image.LANCZOS)
    img.save(image_path, quality=95)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python seedream_gen.py <prompt> <output.png> [size]")
        sys.exit(1)

    prompt = sys.argv[1]
    output = sys.argv[2]
    size = sys.argv[3] if len(sys.argv) > 3 else "1920x1920"

    print(f"Generating: {output} ({size})")
    t0 = time.time()
    ok = generate(prompt, output, size)
    dt = time.time() - t0

    if ok:
        print(f"Done: {dt:.1f}s, {Path(output).stat().st_size//1024}KB")
        remove_watermark(output)
        print(f"Watermark removed")
    else:
        print(f"Failed after {dt:.1f}s")
