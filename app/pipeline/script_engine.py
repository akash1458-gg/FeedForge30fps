from __future__ import annotations

import asyncio
import json

from .. import models
from ..config import get_settings

_SYSTEM = (
    "You are a scriptwriter for short vertical videos on the Qoneqt Global Feed. "
    "Given a TOPIC, write a punchy, accurate, engaging 30-60s short. "
    "Open with a scroll-stopping hook. Each scene is ONE spoken line (<= 22 words), "
    "a vivid text-to-image prompt, and a 2-5 word stock-footage search phrase "
    "(video_query) describing concrete, filmable action or scenery for that line "
    "(e.g. 'city skyline timelapse', 'people laughing cafe'). Keep it factual and energetic."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "on_screen_text": {"type": "string"},
                    "image_prompt": {"type": "string"},
                    "video_query": {"type": "string"},
                },
                "required": ["narration", "image_prompt"],
            },
        },
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "hook", "scenes", "caption", "hashtags"],
}


async def generate_script(topic: str, scene_count: int, style: str) -> models.ScenePlan:
    settings = get_settings()
    if not settings.gemini_api_key:
        return _fallback_plan(topic, scene_count)

    prompt = (
        f"{_SYSTEM}\n\nTOPIC: {topic}\nTARGET SCENES: {scene_count}\n"
        f"VISUAL STYLE for every image_prompt: {style}\nReturn ONLY JSON."
    )
    from google import genai
    from google.genai import types

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
    except Exception as e:  # noqa: BLE001
        print(f"[script_engine] Gemini client init failed ({e!r}); using fallback plan")
        return _fallback_plan(topic, scene_count)

    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_SCHEMA,
        temperature=0.9,
    )
    # Primary model first, then lighter/older flashes that tend to have more
    # free-tier capacity when the newest model returns 503 "high demand".
    models_to_try: list[str] = []
    for m in [settings.gemini_model, "gemini-3.7-flash", "gemini-3.6-flash",
              "gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.8-flash"]:
        if m and m not in models_to_try:
            models_to_try.append(m)

    last_err = None
    for model in models_to_try:
        for attempt in range(2):
            try:
                resp = await client.aio.models.generate_content(model=model, contents=prompt, config=cfg)
                plan = _coerce_plan(json.loads(resp.text), topic, style)
                if model != settings.gemini_model:
                    print(f"[script_engine] primary model busy; used fallback {model}")
                return plan
            except Exception as e:  # noqa: BLE001
                last_err = e
                msg = str(e)
                if any(c in msg for c in ("404", "NOT_FOUND", "PERMISSION", "403")):
                    break  # model unusable for this key -> next model
                if any(c in msg for c in ("429", "500", "503", "UNAVAILABLE")) and attempt == 0:
                    await asyncio.sleep(2.0)
                    continue
                break  # other error -> next model

    print(f"[script_engine] Gemini unavailable ({last_err!r}); using fallback plan")
    return _fallback_plan(topic, scene_count)


def _coerce_plan(data: dict, topic: str, style: str) -> models.ScenePlan:
    scenes: list[models.Scene] = []
    for i, s in enumerate(data.get("scenes", [])):
        narration = (s.get("narration") or "").strip()
        if not narration:
            continue
        scenes.append(
            models.Scene(
                index=i,
                narration=narration,
                on_screen_text=(s.get("on_screen_text") or "").strip(),
                image_prompt=(s.get("image_prompt") or f"{topic}, {style}").strip(),
                video_query=(s.get("video_query") or s.get("on_screen_text") or topic).strip(),
            )
        )
    if not scenes:
        return _fallback_plan(topic, 5)
    for i, sc in enumerate(scenes):
        sc.index = i
    return models.ScenePlan(
        title=(data.get("title") or topic)[:120],
        hook=(data.get("hook") or "").strip(),
        scenes=scenes,
        caption=(data.get("caption") or "").strip(),
        hashtags=[str(h).lstrip("#") for h in data.get("hashtags", []) if h][:12],
    )


def _fallback_plan(topic: str, scene_count: int) -> models.ScenePlan:
    n = max(4, min(scene_count or 5, 7))
    beats = [
        ("Did you know?", f"Here's something surprising about {topic}."),
        ("The basics", f"{topic}, explained simply and fast."),
        ("Why it matters", f"This is why {topic} matters right now."),
        ("A key detail", f"One thing most people miss about {topic}."),
        ("The takeaway", f"Here's what to remember about {topic}."),
        ("Go deeper", f"There's so much more to explore in {topic}."),
        ("Your turn", f"What do you think about {topic}? Comment below."),
    ][:n]
    first_word = topic.split()[0].lower() if topic.split() else "trending"
    scenes = [
        models.Scene(
            index=i,
            narration=line,
            on_screen_text=head,
            image_prompt=f"{topic}, {head.lower()}, cinematic, vibrant, highly detailed, vertical 9:16",
            video_query=topic,
        )
        for i, (head, line) in enumerate(beats)
    ]
    return models.ScenePlan(
        title=f"{topic} — in 60 seconds",
        hook=f"Everything you should know about {topic}",
        scenes=scenes,
        caption=f"{topic}, explained in 60 seconds. Built with FeedForge.",
        hashtags=["qoneqt", "shorts", "learn", first_word],
    )
