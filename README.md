# FeedForge

> **An AI content engine for the Qoneqt Global Feed** — forge a feed's worth of publish-ready vertical Qlips from a single topic.
> Built for **CTRL FREAK 2026 · The Qoneqt AI Challenge**.
> Turn any topic, prompt, idea, or trend into a **publish-ready vertical video** for the Qoneqt Global Feed — automatically, repeatably, and for near-zero cost.

**FeedForge** is not a one-off generator — it's a **repeatable pipeline**: give it a topic, and an LLM writes the script, a free TTS engine voices it, an image model paints each scene, and `ffmpeg` assembles a captioned 9:16 short ready to post.

```
INPUT                AI ENGINE                                   OUTPUT
topic  ──▶  Gemini → hook + narration + scene plan (JSON)
           edge-tts → voiceover + word-level timestamps
           FLUX.1-schnell (HF) → one AI still per scene     ──▶  publish-ready
           ffmpeg → Ken-Burns + animated captions + music         1080×1920 MP4
                    + transitions, stitched into one video        + caption + hashtags
                                                              ──▶  Qoneqt Global Feed
```

## Why these choices

| Stage | Tool | Cost | Why |
|-------|------|------|-----|
| Script / story | **Google Gemini** (`gemini-3.7-flash`, auto-fallback chain) | Free tier | Fast, strong JSON output for a structured scene plan |
| Voiceover | **edge-tts** / **Fish Audio** | Free | edge-tts is keyless with word-level caption timing; Fish Audio (free tier) is an optional premium voice |
| Visuals | **FLUX.1-schnell** via Hugging Face | Free tier | AI-generated stills; swap to Gemini images or Pexels via config |
| Assembly | **ffmpeg** | Free | Ken-Burns motion, karaoke captions, music ducking, transitions |
| Backend | **FastAPI** + async jobs | Free | Non-blocking generation; poll for progress |

Every default is **free and needs no credit card**. You'll want two free keys — a **Gemini API key** (scripts) and a **Hugging Face token** (images), both free with no card. Without them the app still runs end to end (templated script + placeholder visuals).

## Quickstart (local)

Requires **Python 3.11+** and **ffmpeg** on your PATH.

```bash
# 1. install ffmpeg (Windows: winget install Gyan.FFmpeg  |  macOS: brew install ffmpeg
#    Debian/Ubuntu: sudo apt install ffmpeg)

# 2. set up the app
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

# 3. (optional) add a Gemini key for better scripts
cp .env.example .env              # then paste your key into GEMINI_API_KEY

# 4. run
uvicorn app.main:app --reload
```

Open **http://localhost:8000**, type a topic, and watch it build.
Without a Gemini key the app still runs end-to-end using a built-in fallback script.

## Quickstart (Docker)

```bash
docker build -t feedforge .
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key feedforge
```

## Deploy (free)

The included **Dockerfile** installs ffmpeg + fonts and works on any container host.
- **Render** — push to GitHub, "New → Blueprint", pick this repo (`render.yaml`), set `GEMINI_API_KEY`. Done.
- **Hugging Face Spaces** (Docker SDK), **Fly.io**, **Google Cloud Run** — same image.

> The async job model (return a `job_id`, poll `/api/jobs/{id}`) means long renders never hit HTTP request timeouts.

## Configuration

All via environment variables (see `.env.example`):

| Var | Default | Notes |
|-----|---------|-------|
| `GEMINI_API_KEY` | *(empty)* | From [Google AI Studio](https://aistudio.google.com/apikey). Empty = fallback script. |
| `GEMINI_MODEL` | `gemini-3.7-flash` | Any current Gemini text model (auto-falls back if busy). |
| `IMAGE_PROVIDER` | `huggingface` | `huggingface` (free token), `pollinations`, `gemini`, or `placeholder`. |
| `HF_API_TOKEN` | *(empty)* | Free HF token with the "Inference Providers" permission → FLUX images. |
| `MEDIA_MODE` | `video` | `video` = Pexels stock footage (real motion), `image` = AI stills. |
| `PEXELS_API_KEY` | *(empty)* | Free Pexels key for stock video; falls back to AI stills if empty. |
| `TTS_PROVIDER` | `edge` | `edge` (free, keyless, word-timed) or `fish` (premium Fish Audio voice). |
| `TTS_VOICE` | `en-US-AriaNeural` | Any edge-tts voice (when `TTS_PROVIDER=edge`). |
| `FISH_API_KEY` | *(empty)* | Free Fish Audio key — needed when `TTS_PROVIDER=fish`. |
| `VIDEO_WIDTH`/`HEIGHT`/`FPS` | `1080`/`1920`/`30` | Vertical by default. |
| `API_TOKEN` | *(empty)* | If set, `/api/generate` requires `Authorization: Bearer <token>`. |

## API

| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/api/generate` | `{topic, scene_count?, voice?, style?}` → returns a `job_id` |
| `GET` | `/api/jobs/{id}` | Job status + progress + result metadata |
| `GET` | `/api/jobs/{id}/publish` | Caption/hashtags + manual publish steps |
| `GET` | `/api/health` | Liveness + config echo |
| `GET` | `/outputs/{id}/{id}.mp4` | The finished video |

## How it maps to the challenge

- **INPUT** — a topic/prompt/idea/trend via the web UI or API.
- **AI ENGINE** — LLM (Gemini) for script & story; multimodal models for visuals; ffmpeg to compose/process. Orchestrated as a reliable, repeatable workflow.
- **OUTPUT** — a complete, engaging, Global-Feed-formatted vertical video + caption + hashtags.
- **SHIP IT** — deploy the Docker image, demo the UI, download the MP4, and publish it to the Qoneqt Global Feed.

## Publishing to Qoneqt

Qoneqt has no sanctioned public upload API and create-post flows are auth-gated, so publishing is **guided-manual**: the pipeline produces the ready-to-post MP4 + caption + hashtags, and you post it via the Qoneqt app/site (steps shown in-app under *Publish to Qoneqt*). This satisfies the "at least one generated video published to the Global Feed" requirement.

## Project structure

```
app/
  main.py            FastAPI app + routes + static UI
  config.py          env-driven settings
  models.py          Pydantic models (ScenePlan, JobStatus, …)
  jobs.py            in-memory job store + background runner
  pipeline/
    script_engine.py Gemini → structured scene plan (+ offline fallback)
    tts.py           edge-tts → voiceover + word timings
    images.py        Pollinations/Gemini → scene stills (+ placeholder fallback)
    captions.py      word timings → animated ASS karaoke captions
    compose.py       ffmpeg: Ken-Burns, concat, music ducking, finalize
    orchestrator.py  runs a topic end-to-end
    publish.py       Qoneqt publish metadata + steps
  static/            index.html, styles.css, app.js
assets/music/        drop an .mp3 for background music (optional)
tests/               offline unit tests
```

## Resilience (built for a live demo)

Every external call has a fallback so a demo never hard-fails: no Gemini key → templated script; **edge-tts blocked (some datacenter IPs return 403) → gTTS fallback** with estimated caption timing; image API down → gradient placeholder; no music file → voiceover-only. When edge-tts works, captions use its real word-level timestamps and stay perfectly in sync even if you swap voices.

## Limitations & scaling

- In-memory job store → pin to one instance; use Redis/RQ or a DB queue to scale out.
- Free image/TTS endpoints are unofficial/rate-limited — fine for a demo, add paid providers (and persistent object storage for outputs) for production volume.
- Endpoints are open unless `API_TOKEN` is set — set it before any public deployment.

## License

MIT — built for CTRL FREAK 2026.

