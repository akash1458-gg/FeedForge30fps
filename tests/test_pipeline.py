import asyncio

from app.pipeline import captions, script_engine


def test_fallback_plan_offline(monkeypatch):
    # Force no API key so the fallback path is exercised deterministically (no network).
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    plan = asyncio.run(script_engine.generate_script("space travel", 5, "cinematic"))
    get_settings.cache_clear()
    assert len(plan.scenes) >= 4
    assert all(s.narration for s in plan.scenes)
    assert all(s.image_prompt for s in plan.scenes)
    assert plan.hashtags


def test_build_ass(tmp_path):
    words = [
        {"text": "hello", "start": 0.0, "end": 0.4},
        {"text": "world", "start": 0.4, "end": 0.9},
    ]
    out = tmp_path / "cap.ass"
    captions.build_ass(words, 1080, 1920, str(out), scene_title="Intro", duration=1.0)
    data = out.read_text(encoding="utf-8")
    assert "Dialogue:" in data
    assert "hello" in data and "world" in data
    assert "Intro" in data  # title line present
