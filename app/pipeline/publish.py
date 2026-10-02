from __future__ import annotations

from .. import models

# Qoneqt exposes no sanctioned public upload API, and create-post flows are
# auth + captcha gated. So publishing is guided-manual: the pipeline produces a
# ready-to-post MP4 + caption + hashtags, and the user finishes the publish.


def prepare_publish(job: models.JobStatus, video_path: str) -> dict:
    tags = " ".join(f"#{h.lstrip('#')}" for h in job.hashtags)
    caption = f"{job.caption}\n\n{tags}".strip()
    return {
        "video_path": video_path,
        "caption": caption,
        "hashtags": job.hashtags,
        "steps": [
            "Download the generated MP4 from this page.",
            "Open qoneqt.com (or the Qoneqt app) and sign in.",
            "On the Global Feed, tap Create Post / Create Qlip.",
            "Upload the MP4 and paste the caption + hashtags shown here.",
            "Publish to the Qoneqt Global Feed. 🎉",
        ],
        "note": (
            "No sanctioned public Qoneqt upload API is wired in, so publishing is "
            "guided-manual. The pipeline reliably produces the publish-ready MP4, "
            "caption, and hashtags."
        ),
    }
