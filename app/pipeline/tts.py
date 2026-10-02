from __future__ import annotations

import asyncio

import edge_tts
import httpx

from ..config import get_settings

_FISH_URL = "https://api.fish.audio/v1/tts"


async def synthesize(text: str, out_path: str, voice: str | None = None) -> list[dict]:
    """Generate speech to ``out_path`` (mp3). Returns word timings
    ``[{"text", "start", "end"}]`` in seconds.

    Provider order: Fish Audio (premium, if configured) -> edge-tts (free, returns
    real word-level timings) -> gTTS. Fish/gTTS return ``[]`` (no timings); the
    orchestrator then estimates word timings from the audio duration.
    """
    settings = get_settings()
    if settings.tts_provider.lower() == "fish" and settings.fish_api_key:
        try:
            await _fish(text, out_path, settings)
            return []
        except Exception as e:  # noqa: BLE001
            print(f"[tts] fish failed ({e!r}); falling back to edge-tts")

    voice = voice or settings.tts_voice
    try:
        return await _edge(text, out_path, voice)
    except Exception as e:  # noqa: BLE001
        print(f"[tts] edge-tts failed ({e!r}); falling back to gTTS")
        await asyncio.to_thread(_gtts, text, out_path)
        return []


async def _fish(text: str, out_path: str, s) -> None:
    headers = {
        "Authorization": f"Bearer {s.fish_api_key}",
        "Content-Type": "application/json",
        "model": s.fish_model,
    }
    body = {"text": text, "format": "mp3"}
    if s.fish_reference_id:
        body["reference_id"] = s.fish_reference_id
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(_FISH_URL, headers=headers, json=body)
        r.raise_for_status()
        data = r.content
    if not data or len(data) < 1000:
        raise RuntimeError("fish returned no audio")
    with open(out_path, "wb") as f:
        f.write(data)


async def _edge(text: str, out_path: str, voice: str) -> list[dict]:
    communicate = edge_tts.Communicate(text, voice)
    words: list[dict] = []
    got_audio = False
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
                got_audio = True
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append({"text": chunk["text"], "start": start,
                              "end": start + chunk["duration"] / 1e7})
    if not got_audio:
        raise RuntimeError("edge-tts returned no audio")
    return words


def _gtts(text: str, out_path: str) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="en").save(out_path)


def estimate_word_timings(text: str, duration: float) -> list[dict]:
    """Distribute ``duration`` across words (weighted by length) when the TTS
    engine gave no word boundaries. Keeps captions readable and roughly synced."""
    words = text.split()
    if not words or duration <= 0:
        return []
    weights = [max(1, len(w)) for w in words]
    total = sum(weights)
    t, out = 0.0, []
    for w, wt in zip(words, weights):
        d = duration * (wt / total)
        out.append({"text": w, "start": t, "end": t + d})
        t += d
    return out
