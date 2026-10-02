from __future__ import annotations

import asyncio
import urllib.parse

import httpx

from ..config import get_settings


async def generate_image(
    prompt: str, out_path: str, width: int, height: int, style: str = "", seed: int = 0
) -> None:
    """Generate one still image for a scene. Never raises: on any failure it
    writes a gradient placeholder so the pipeline keeps running in a demo."""
    settings = get_settings()
    full_prompt = f"{prompt}, {style}".strip(", ") if style else prompt
    provider = settings.image_provider.lower()
    if provider == "placeholder":  # offline / deterministic mode
        _placeholder(out_path, width, height, prompt)
        return
    try:
        if provider in ("huggingface", "hf"):
            if not settings.hf_api_token:
                print("[images] HF_API_TOKEN not set; using placeholder. Create a free token "
                      "(with the 'Inference Providers' permission) at "
                      "https://huggingface.co/settings/tokens")
                _placeholder(out_path, width, height, prompt)
                return
            await _hf_image(full_prompt, out_path)
        elif provider == "gemini" and settings.gemini_api_key:
            await _gemini_image(full_prompt, out_path)
        elif provider == "pollinations":
            await _pollinations_image(full_prompt, out_path, width, height, seed)
        else:
            _placeholder(out_path, width, height, prompt)
    except Exception as e:  # noqa: BLE001
        print(f"[images] generation failed ({e!r}); using placeholder")
        _placeholder(out_path, width, height, prompt)


async def _hf_image(prompt: str, out_path: str) -> None:
    """Hugging Face Inference Providers → FLUX.1-schnell (free tier). Returns a
    768x1344 vertical still; ffmpeg's Ken-Burns step covers it to the final size."""
    def _call() -> None:
        from huggingface_hub import InferenceClient

        s = get_settings()
        client = InferenceClient(token=s.hf_api_token, provider=(s.hf_provider.strip() or "auto"))
        image = client.text_to_image(prompt, model=s.hf_image_model, width=768, height=1344)
        image.save(out_path, "JPEG", quality=90)

    await asyncio.to_thread(_call)


async def _pollinations_image(prompt, out_path, width, height, seed) -> None:
    enc = urllib.parse.quote(prompt, safe="")
    url = f"https://image.pollinations.ai/prompt/{enc}"
    params = {"width": width, "height": height, "nologo": "true", "model": "flux", "seed": seed}
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.content
    if not data or len(data) < 1000:
        raise RuntimeError("empty/invalid image response")
    with open(out_path, "wb") as f:
        f.write(data)


async def _gemini_image(prompt, out_path) -> None:
    def _call() -> None:
        from google import genai
        from google.genai import types

        settings = get_settings()
        client = genai.Client(api_key=settings.gemini_api_key)
        resp = client.models.generate_images(
            model=settings.gemini_image_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="9:16"),
        )
        data = resp.generated_images[0].image.image_bytes
        with open(out_path, "wb") as f:
            f.write(data)

    await asyncio.to_thread(_call)


def _placeholder(out_path, width, height, text) -> None:
    import colorsys
    import hashlib

    from PIL import Image, ImageDraw

    h = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
    hue = (h % 360) / 360.0
    top = tuple(int(c * 255) for c in colorsys.hls_to_rgb(hue, 0.35, 0.6))
    bot = tuple(int(c * 255) for c in colorsys.hls_to_rgb((hue + 0.12) % 1.0, 0.12, 0.6))
    img = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / height
        draw.line([(0, y), (width, y)], fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) > 22:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    draw.multiline_text((int(width * 0.08), int(height * 0.42)), "\n".join(lines[:6]),
                        fill=(255, 255, 255), spacing=12)
    img.save(out_path, "JPEG", quality=90)
