from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles

from . import models
from .config import get_settings
from .jobs import manager
from .pipeline import publish

settings = get_settings()
os.makedirs(settings.output_dir, exist_ok=True)

BASE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="FeedForge", version="1.0.0")


@app.on_event("startup")
async def _warn_open() -> None:
    if not settings.api_token:
        print("[security] API_TOKEN is empty — /api/generate is OPEN. "
              "Set API_TOKEN before any public deployment.")


def _auth(authorization: str | None = Header(default=None)) -> None:
    if settings.api_token and authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "model": settings.gemini_model,
            "image_provider": settings.image_provider,
            "gemini_configured": bool(settings.gemini_api_key)}


@app.post("/api/generate", response_model=models.JobStatus)
async def generate(req: models.GenerateRequest, _: None = Depends(_auth)) -> models.JobStatus:
    return manager.create(req)


@app.get("/api/jobs/{job_id}", response_model=models.JobStatus)
async def job_status(job_id: str) -> models.JobStatus:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/api/jobs/{job_id}/publish")
async def job_publish(job_id: str) -> dict:
    job = manager.get(job_id)
    if job is None or job.state != models.JobState.done:
        raise HTTPException(status_code=400, detail="job not finished")
    path = os.path.abspath(os.path.join(settings.output_dir, job_id, f"{job_id}.mp4"))
    return publish.prepare_publish(job, path)


# Serve generated videos, then the web UI (mounted last so /api/* wins).
app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")
app.mount("/", StaticFiles(directory=os.path.join(BASE, "static"), html=True), name="ui")
