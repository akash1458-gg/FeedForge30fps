from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- LLM (Google Gemini) ----
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.7-flash"

    # ---- Images ----
    image_provider: str = "huggingface"  # huggingface | pollinations | gemini | placeholder
    hf_api_token: str = ""
    hf_image_model: str = "black-forest-labs/FLUX.1-schnell"
    hf_provider: str = "auto"
    gemini_image_model: str = "gemini-3.1-flash-image"

    # ---- Scene media ----
    media_mode: str = "video"  # "video" (Pexels stock footage) | "image" (AI stills)
    pexels_api_key: str = ""

    # ---- TTS ----
    tts_provider: str = "edge"  # edge (free, keyless) | fish (premium, needs key)
    tts_voice: str = "en-US-AriaNeural"  # edge-tts voice
    fish_api_key: str = ""
    fish_model: str = "s2.1-pro-free"
    fish_reference_id: str = ""  # optional Fish voice id (from a fish.audio voice URL)

    # ---- Video ----
    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30
    default_scene_count: int = 6

    # ---- App ----
    output_dir: str = "outputs"
    api_token: str = ""  # optional bearer token to protect /api/generate
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"


@lru_cache
def get_settings() -> Settings:
    return Settings()
