from __future__ import annotations

import os

import httpx

from ..config import Settings

# Fetches a real stock video clip per scene from Pexels (free API key, no card).
# ffmpeg later trims/loops + crops it to vertical, so clip length/orientation are
# not critical. Returns False on any failure so the caller can fall back to a still.

_SEARCH_URL = "https://api.pexels.com/videos/search"


async def fetch_clip(query: str, out_path: str, s: Settings) -> bool:
    if not s.pexels_api_key:
        return False
    headers = {"Authorization": s.pexels_api_key}
    params = {"query": query, "orientation": "portrait", "per_page": 12, "size": "medium"}
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            r = await client.get(_SEARCH_URL, params=params, headers=headers)
            r.raise_for_status()
            link = _pick_file(r.json().get("videos", []))
            if not link:
                print(f"[footage] no clip for query {query!r}")
                return False
            # Stream to disk to avoid buffering entire clip in memory
            async with client.stream("GET", link) as vr:
                vr.raise_for_status()
                with open(out_path, "wb") as f:
                    async for chunk in vr.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
    except Exception as e:  # noqa: BLE001
        print(f"[footage] pexels failed ({e!r})")
        return False

    if os.path.getsize(out_path) < 10000:
        os.remove(out_path)
        return False
    return True


def _pick_file(videos: list) -> str | None:
    """Prefer a portrait mp4 at up to 1080x1920, closest to ~1280px tall."""
    candidates = []
    for v in videos:
        for f in v.get("video_files", []):
            if f.get("file_type") != "video/mp4":
                continue
            w, h = f.get("width") or 0, f.get("height") or 0
            if not (w and h) or h > 2200:
                continue
            candidates.append((h >= w, min(h, 1920), -abs(h - 1280), f.get("link")))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][3]
