<div align="center">

<img src="static/banner.png" alt="Shinobi." width="100%" />

# Shinobi.

**Turn one long-form video into a dozen ready-to-post vertical clips — automatically.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Powered by Claude](https://img.shields.io/badge/AI-Claude-purple)](https://www.anthropic.com/)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey)](#license)

[Overview](#overview) • [Features](#features) • [Quick start](#quick-start) • [Architecture](#architecture) • [API](#api-reference) • [Roadmap](#roadmap)

</div>

---

## Overview

Shinobi takes a single input video — an uploaded file or a YouTube URL — and runs it through an automated repurposing pipeline that transcribes it, finds the most engaging moments, cuts them into clips, reformats them for vertical platforms, and burns in animated subtitles. The output is a set of ready-to-post, platform-native clips with AI-generated titles, descriptions, and tags.

```
long-form video  →  transcript  →  best moments  →  clips  →  vertical + subtitled  →  ready to post
```

## Features

- **Automatic transcription** — word-level timestamps via local Whisper
- **AI moment detection** — Claude scores and selects the strongest 45–60s segments (hook strength, info density, standalone-ness)
- **Silence removal** — trims dead air from every clip
- **Vertical reformatting** — 9:16 crop with face-aware centering, or blurred full-bleed fallback for landscape sources
- **Animated subtitles** — word-by-word, karaoke-style burn-in
- **AI metadata generation** — per-clip titles, descriptions, tags, and Reddit-ready post copy
- **Selectable model tiers** — Katana 5.5 / Wakizashi 4.5 (most capable) and Kunai 4.5 / Shuriken 3.5 (fast), chosen per run
- **Adaptive brand image** — set your aesthetic, voice, palette, and reference photos once; Shinobi keeps every clip on-brand
- **Accounts & projects** — sign in, revisit past projects, trash/restore
- **One-click publishing** *(in progress)* — direct posting to YouTube, X/Twitter, and Reddit

## Quick start

**Requirements:** Python 3.10+, [ffmpeg](https://ffmpeg.org/) on your `PATH`, an [Anthropic API key](https://console.anthropic.com/).

```bash
git clone https://github.com/emilio-martin1208/shinobi.git
cd shinobi
pip install -r requirements.txt

cp .env.example .env        # then add your ANTHROPIC_API_KEY

python3 main.py
```

The server starts at `http://localhost:8000` — visit `/` for the landing page or `/app.html` to start repurposing a video.

## Architecture

```
┌─────────────┐     ┌────────────────────┐     ┌──────────────────┐
│  Frontend    │────▶│  FastAPI backend    │────▶│  Pipeline modules │
│ (static/*)   │     │  (main.py)          │     │  (pipeline/*)     │
│ index.html   │◀────│  - job orchestration│◀────│  - whisper        │
│ app.html     │     │  - in-memory jobs   │     │  - claude api     │
└─────────────┘     │  - REST API + polling│     │  - ffmpeg/opencv  │
                     └────────────────────┘     └──────────────────┘
                              │
                              ▼
                     ┌────────────────────┐
                     │  posting / auth     │
                     │  (in progress)      │
                     │  - YouTube/X/Reddit │
                     │  - OAuth token db   │
                     └────────────────────┘
```

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn (async, background `asyncio` jobs) |
| Transcription | `openai-whisper` (local `base` model) |
| Moment detection & metadata | Anthropic Claude API |
| Video processing | ffmpeg / ffprobe, OpenCV (face-aware crop) |
| YouTube downloads | `yt-dlp` |
| Frontend | Vanilla HTML/CSS/JS — no build step |
| OAuth / posting | `google-api-python-client`, `tweepy`, `praw` *(in progress)* |
| Token storage | SQLite (`tokens.db`) |

<details>
<summary><strong>Project structure</strong></summary>

```
repurpose/
├── main.py              # FastAPI app, routes, pipeline orchestration
├── jobs.py              # In-memory job store & progress tracking
├── pipeline/
│   ├── transcribe.py    # Whisper transcription
│   ├── moments.py       # Claude: identify best clip segments
│   ├── clip.py          # ffmpeg: extract clip segments
│   ├── silence.py       # ffmpeg: detect & remove silence
│   ├── reformat.py      # ffmpeg + OpenCV: 9:16 vertical reformat
│   ├── subtitles.py     # ASS subtitle generation & burn-in
│   └── metadata.py      # Claude: titles/descriptions/tags
├── posting/              # YouTube / Twitter / Reddit publishing
├── auth/                 # OAuth flow handlers & token storage
├── static/                # Landing page, app UI, assets
├── uploads/                # Temporary source videos
└── output/{job_id}/         # Per-job working directories
```

</details>

## API reference

All responses follow the envelope `{ success, data, error }`.

| Endpoint | Description |
|---|---|
| `POST /upload` | Start a job from an uploaded video file |
| `POST /url` | Start a job from a YouTube URL |
| `GET /status/{job_id}` | Poll job progress and step state |
| `GET /result/{job_id}` | Fetch finished clips and metadata |
| `POST /post/{job_id}` | Publish clips to connected platforms |
| `GET /auth/status` | Connection status for YouTube / Twitter / Reddit |
| `GET /api/profile` | Current user's profile, projects, and settings |
| `GET /api/brand` | Current user's adaptive brand-image profile |
| `GET /health` | Liveness probe for uptime monitoring |

<details>
<summary><strong>Pipeline options</strong> (passed to <code>/upload</code> or <code>/url</code>)</summary>

```json
{
  "tone": "casual | professional | hype | educational | funny",
  "audience": "target audience description",
  "niche": "content niche",
  "cta": "call to action text",
  "num_clips": 5,
  "model": "katana-5.5 | wakizashi-4.5 | kunai-4.5 | shuriken-3.5",
  "instructions": "free-text steering (brand image is auto-merged in)",
  "platforms": ["youtube", "twitter", "reddit"],
  "subreddit": "test"
}
```

</details>

## Roadmap

- [x] Core pipeline: transcribe → detect moments → clip → reformat → subtitle → metadata
- [x] Web app with live progress and downloadable results
- [x] Accounts, profiles, and persistent project history
- [x] Selectable model tiers and adaptive brand image
- [ ] Direct publishing to YouTube, X/Twitter, and Reddit (OAuth wired, not yet live)
- [ ] Persistent job storage (currently in-memory)
- [ ] Pinterest OAuth for automatic brand-board import
- [ ] Larger Whisper models for higher transcription accuracy

## Related projects

Also from Shinobi Tools: [**Forge**](https://github.com/emilio-martin1208/forge) —
the AI software architect. Connect a GitHub repo and Forge builds a
deterministic understanding of it, then generates documentation and
grounded context packages from what's actually there.

## License

Proprietary — all rights reserved.
