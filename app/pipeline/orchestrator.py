from __future__ import annotations

import asyncio
import glob
import os
import shutil

from ..config import get_settings
from ..models import JobState
from . import captions, compose, footage, images, script_engine, tts


async def run_pipeline(job_id: str, req, update) -> None:
    """End-to-end: topic -> script -> voice+images -> captions -> ffmpeg -> MP4."""
    s = get_settings()

    update(state=JobState.scripting, progress=0.05, message="Writing the script with Gemini…")
    scene_count = req.scene_count or s.default_scene_count
    plan = await script_engine.generate_script(req.topic, scene_count, req.style)
    update(
        title=plan.title,
        caption=f"{plan.hook}\n\n{plan.caption}".strip(),
        hashtags=plan.hashtags,
        progress=0.15,
        message=f"Script ready — {len(plan.scenes)} scenes",
    )

    workdir = os.path.abspath(os.path.join(s.output_dir, job_id, "work"))
    os.makedirs(workdir, exist_ok=True)

    update(state=JobState.generating_assets, message="Generating voiceover + images…")
    scenes_data: list[dict] = []
    for i, sc in enumerate(plan.scenes):
        sd = await _build_scene(workdir, i, sc, req, s)
        scenes_data.append(sd)
        update(progress=0.15 + 0.40 * ((i + 1) / len(plan.scenes)),
               message=f"Assets {i + 1}/{len(plan.scenes)} ready")
    update(progress=0.55, message="Assets ready — composing video…")

    update(state=JobState.composing, message="Rendering scenes with ffmpeg…")
    scene_files: list[str] = []
    for i, sd in enumerate(scenes_data):
        if sd["kind"] == "video":
            f = await compose.render_scene_video(
                workdir, i, sd["media"], sd["audio"], sd["ass"], sd["duration"], s)
        else:
            f = await compose.render_scene(
                workdir, i, sd["media"], sd["audio"], sd["ass"], sd["duration"], s)
        scene_files.append(f)
        # Free memory: remove source assets after rendering the scene MP4
        for tmp in (sd["media"], sd["audio"], sd["ass"]):
            p = os.path.join(workdir, tmp)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        update(progress=0.55 + 0.35 * ((i + 1) / len(scenes_data)),
               message=f"Rendered scene {i + 1}/{len(scenes_data)}")

    body = await compose.concat_scenes(workdir, scene_files, s)
    final_rel = await compose.add_music_and_finalize(workdir, body, _pick_music(), s)

    final_dst = os.path.abspath(os.path.join(s.output_dir, job_id, f"{job_id}.mp4"))
    shutil.copyfile(os.path.join(workdir, final_rel), final_dst)

    update(state=JobState.done, progress=1.0, message="Done ✅",
           video_url=f"/outputs/{job_id}/{job_id}.mp4")


async def _build_scene(workdir: str, i: int, scene, req, s) -> dict:
    audio = os.path.join(workdir, f"audio_{i:03d}.mp3")
    ass = os.path.join(workdir, f"cap_{i:03d}.ass")

    words, (media, kind) = await asyncio.gather(
        tts.synthesize(scene.narration, audio, req.voice),
        _fetch_media(workdir, i, scene, req, s),
    )
    dur = await compose.probe_duration(audio, s.ffprobe_bin)
    duration = max(2.0, dur + 0.6)
    if not words:  # TTS fallback gave no word boundaries — estimate them
        words = tts.estimate_word_timings(scene.narration, dur)
    captions.build_ass(words, s.video_width, s.video_height, ass,
                       scene_title=scene.on_screen_text, duration=duration)
    return {
        "media": media,
        "kind": kind,
        "audio": os.path.basename(audio),
        "ass": os.path.basename(ass),
        "duration": duration,
    }


async def _fetch_media(workdir: str, i: int, scene, req, s) -> tuple:
    """Returns (basename, kind) — 'video' (Pexels stock footage) or 'image' (AI still)."""
    if s.media_mode == "video" and s.pexels_api_key:
        clip = os.path.join(workdir, f"clip_{i:03d}.mp4")
        query = scene.video_query or scene.on_screen_text or req.topic
        if await footage.fetch_clip(query, clip, s):
            return os.path.basename(clip), "video"
    image = os.path.join(workdir, f"image_{i:03d}.jpg")
    await images.generate_image(scene.image_prompt, image, s.video_width, s.video_height,
                                req.style, seed=i + 1)
    return os.path.basename(image), "image"


def _pick_music() -> str | None:
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    tracks = sorted(glob.glob(os.path.join(here, "assets", "music", "*.mp3")))
    return tracks[0] if tracks else None
