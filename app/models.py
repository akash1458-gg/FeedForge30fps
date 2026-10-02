from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Scene(BaseModel):
    index: int = 0
    narration: str = Field(..., description="Voiceover line spoken in this scene")
    on_screen_text: str = Field("", description="Short title/caption shown on screen")
    image_prompt: str = Field(..., description="Text-to-image prompt for the visual")
    video_query: str = Field("", description="Short stock-footage search phrase (2-5 words)")


class ScenePlan(BaseModel):
    title: str
    hook: str
    scenes: list[Scene]
    caption: str = ""
    hashtags: list[str] = []


class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=500)
    scene_count: Optional[int] = Field(default=None, ge=3, le=10)
    voice: Optional[str] = None
    style: str = "cinematic, vibrant, highly detailed"


class JobState(str, Enum):
    queued = "queued"
    scripting = "scripting"
    generating_assets = "generating_assets"
    composing = "composing"
    done = "done"
    error = "error"


class JobStatus(BaseModel):
    id: str
    state: JobState = JobState.queued
    progress: float = 0.0
    message: str = ""
    topic: str = ""
    title: str = ""
    caption: str = ""
    hashtags: list[str] = []
    video_url: Optional[str] = None
    error: Optional[str] = None
