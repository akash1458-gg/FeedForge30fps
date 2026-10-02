from __future__ import annotations

import asyncio
import os

from ..config import Settings

# All ffmpeg calls run with cwd = the job's work dir and use RELATIVE filenames.
# This sidesteps the notorious Windows path-escaping problem in the subtitles/ass
# filter (drive-letter colons), which is the #1 cause of caption rendering failures.


async def _run(args: list[str], cwd: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=cwd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        tail = (stderr or b"").decode("utf-8", "ignore")[-1500:]
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {' '.join(args[:3])}...\n{tail}")


async def probe_duration(path: str, ffprobe: str) -> float:
    try:
        proc = await asyncio.create_subprocess_exec(
            ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        return float(out.decode().strip())
    except Exception:  # noqa: BLE001
        return 3.0


async def render_scene(
    workdir: str, idx: int, image_file: str, audio_file: str, ass_file: str,
    duration: float, s: Settings,
) -> str:
    w, h, fps = s.video_width, s.video_height, s.video_fps
    frames = max(1, int(round(duration * fps)))
    sw, sh = int(w * 1.2), int(h * 1.2)
    fade_out = max(0.1, duration - 0.4)
    out = f"scene_{idx:03d}.mp4"
    vf = (
        f"[0:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh},"
        f"zoompan=z='min(zoom+0.0010,1.30)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={w}x{h}:fps={fps},setsar=1,"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out:.2f}:d=0.4,"
        f"ass={ass_file},format=yuv420p[v]"
    )
    args = [
        s.ffmpeg_bin, "-y", "-threads", "1",
        "-loop", "1", "-framerate", str(fps), "-t", f"{duration:.3f}", "-i", image_file,
        "-i", audio_file,
        "-filter_complex", vf,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "1",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-t", f"{duration:.3f}", out,
    ]
    await _run(args, workdir)
    return out


async def render_scene_video(
    workdir: str, idx: int, video_file: str, audio_file: str, ass_file: str,
    duration: float, s: Settings,
) -> str:
    """Render one scene from a stock video clip: loop/trim to the scene length,
    cover-crop to vertical, overlay captions, and use the voiceover as audio."""
    w, h, fps = s.video_width, s.video_height, s.video_fps
    fade_out = max(0.1, duration - 0.4)
    out = f"scene_{idx:03d}.mp4"
    vf = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out:.2f}:d=0.4,"
        f"ass={ass_file},format=yuv420p[v]"
    )
    args = [
        s.ffmpeg_bin, "-y", "-threads", "1",
        "-stream_loop", "-1", "-t", f"{duration:.3f}", "-i", video_file,
        "-i", audio_file,
        "-filter_complex", vf,
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "1",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-t", f"{duration:.3f}", out,
    ]
    await _run(args, workdir)
    return out


async def concat_scenes(workdir: str, scene_files: list[str], s: Settings) -> str:
    listing = "\n".join(f"file '{f}'" for f in scene_files) + "\n"
    with open(os.path.join(workdir, "concat.txt"), "w", encoding="utf-8") as f:
        f.write(listing)
    await _run(
        [s.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
         "-c", "copy", "body.mp4"],
        workdir,
    )
    return "body.mp4"


async def add_music_and_finalize(workdir: str, body: str, music_path: str | None, s: Settings) -> str:
    if music_path and os.path.exists(music_path):
        args = [
            s.ffmpeg_bin, "-y", "-i", body, "-stream_loop", "-1", "-i", music_path,
            "-filter_complex",
            "[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest", "final.mp4",
        ]
    else:
        args = [s.ffmpeg_bin, "-y", "-i", body, "-c", "copy",
                "-movflags", "+faststart", "final.mp4"]
    await _run(args, workdir)
    return "final.mp4"
