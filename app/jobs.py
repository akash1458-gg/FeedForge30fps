from __future__ import annotations

import asyncio
import traceback
import uuid

from . import models
from .pipeline import orchestrator


class JobManager:
    """In-memory job store + background runner.

    In-memory is intentional for the hackathon demo: the app pins to a single
    instance. For horizontal scale, swap this for Redis/RQ or a DB-backed queue.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, models.JobStatus] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def create(self, req: models.GenerateRequest) -> models.JobStatus:
        job_id = uuid.uuid4().hex[:12]
        self._jobs[job_id] = models.JobStatus(id=job_id, topic=req.topic, message="Queued")
        self._tasks[job_id] = asyncio.create_task(self._run(job_id, req))
        return self._jobs[job_id]

    def get(self, job_id: str) -> models.JobStatus | None:
        return self._jobs.get(job_id)

    def _updater(self, job_id: str):
        def update(**kw) -> None:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for key, value in kw.items():
                setattr(job, key, value)

        return update

    async def _run(self, job_id: str, req: models.GenerateRequest) -> None:
        update = self._updater(job_id)
        try:
            await orchestrator.run_pipeline(job_id, req, update)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            update(state=models.JobState.error, error=str(exc), message="Pipeline failed")


manager = JobManager()
