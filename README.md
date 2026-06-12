# Shinobi.

**Creator-forward tools.** Turn a long-form video into multiple short-form, vertical, subtitled clips — automatically — and (optionally) post them to YouTube, Twitter/X, and Reddit.

---

## 1. Overview

Shinobi takes a single input video (uploaded file or YouTube URL) and runs it through an automated repurposing pipeline:

1. Transcribe the audio with word-level timestamps.
2. Use Claude to find the best 45–60s "viral moment" segments.
3. Clip those segments out of the source video.
4. Remove dead air / silence from each clip.
5. Reformat each clip to 9:16 vertical (with face-aware cropping).
6. Burn in animated, word-by-word subtitles.
7. Generate platform-ready titles, descriptions, tags, and Reddit post framing via Claude.
8. (Optional) Post each clip to connected YouTube / Twitter / Reddit accounts.

The result is a set of ready-to-post vertical clips with metadata, downloadable individually or in bulk.

---

## 2. Architecture

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
                     │  (stubbed, phase 2) │
                     │  - YouTube/X/Reddit │
                     │  - OAuth token db   │
                     └────────────────────┘
```

- **Backend**: FastAPI (Python), async route handlers, background `asyncio` tasks per job.
- **Frontend**: vanilla HTML/CSS/JS, no build step, served as static files.
- **Job state**: in-memory dict (`jobs.py`) — not persisted across restarts.
- **Media processing**: `ffmpeg`/`ffprobe` via async subprocess calls.
- **AI**: OpenAI Whisper (local model) for transcription, Anthropic Claude API for moment detection and metadata generation.

---

## 3. Tech stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + Uvicorn |
| Transcription | `openai-whisper` (local `"base"` model, runs in thread pool) |
| Moment detection & metadata | Anthropic Claude API (`claude-sonnet-4-5-20250929`) |
| Video processing | ffmpeg / ffprobe (subprocess), OpenCV (face detection for crop) |
| YouTube downloads | `yt-dlp` |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Fonts | Custom `@font-face` (Molgan), Arial fallback |
| OAuth / posting | `google-api-python-client` + `google-auth-oauthlib` (YouTube), `tweepy` (Twitter/X), `praw` (Reddit) — **stubbed, not yet implemented** |
| Token storage | SQLite (`tokens.db`) |
| Config | `.env` via `python-dotenv` |

---

## 4. Project structure

```
repurpose/
├── main.py                  # FastAPI app, routes, pipeline orchestration
├── jobs.py                  # In-memory job store & step/progress tracking
├── requirements.txt
├── .env / .env.example       # API keys & secrets
├── pipeline/
│   ├── transcribe.py        # Whisper transcription (+ fallback word-timing synthesis)
│   ├── moments.py            # Claude: identify best clip segments
│   ├── clip.py                # ffmpeg: extract clip segments
│   ├── silence.py             # ffmpeg: detect & remove silence
│   ├── reformat.py            # ffmpeg + OpenCV: 9:16 vertical reformat
│   ├── subtitles.py            # ASS subtitle generation & burn-in
│   └── metadata.py            # Claude: titles/descriptions/tags/Reddit copy
├── posting/
│   ├── youtube.py             # YouTube upload (stub)
│   ├── twitter.py              # Twitter/X post (stub)
│   └── reddit.py                # Reddit post (stub)
├── auth/
│   ├── oauth.py                # OAuth flow handlers (stub)
│   └── db.py                    # SQLite token storage
├── static/
│   ├── index.html              # Landing page (marketing)
│   ├── app.html                 # App page (upload, progress, results)
│   ├── logo-final.png, logo.svg, banner.png, logodark/light.png
│   └── fonts/Molgan-Regular.otf
├── uploads/                    # Temporary uploaded/downloaded source videos
├── output/{job_id}/            # Per-job working dirs (raw/, nosilence/, vertical/, final/)
└── tokens.db                   # OAuth tokens (SQLite)
```

---

## 5. Pipeline steps (detail)

The pipeline is orchestrated by `run_pipeline(job_id)` in `main.py`, which runs as a background `asyncio` task. Each step updates job state via `jobs.set_step(job_id, step_name, state)` where `state` is one of `pending | active | done | error`. Steps with non-critical failures (4–6) degrade gracefully by falling back to the previous stage's output.

### Step 1 — Transcribing (`pipeline/transcribe.py`)
- Runs Whisper (`base` model) in a thread-pool executor with `word_timestamps=True`.
- **Known issue handled**: Whisper's DTW word-alignment can throw `cannot reshape tensor of 0 elements into shape [1, 0, 8, -1]` on silent segments. On failure, falls back to segment-level transcription (`word_timestamps=False`) and synthesizes even word-level timings (`_synthesize_words`) by distributing each segment's duration evenly across its words.
- Output: `{ text, words: [{word, start, end}, ...] }`

### Step 2 — Finding moments (`pipeline/moments.py`)
- Builds a timestamped transcript (grouped into ~5s lines).
- Sends it to Claude with scoring criteria: strong hook in first 5s, high info density, standalone, emotionally engaging.
- Requests `num_clips` (default 3) segments, each 45–60s, aligned to transcript timestamps.
- Output: `[{start_sec, end_sec, reason, hook_score}]`

### Step 3 — Clipping (`pipeline/clip.py`)
- Extracts each moment from the source video using `ffmpeg -c copy` (stream copy) for speed, run in parallel via `asyncio.gather`.
- Falls back to re-encoding if stream-copy fails (e.g. keyframe alignment issues).

### Step 4 — Removing silence (`pipeline/silence.py`)
- Runs ffmpeg's `silencedetect` filter to find silent ranges.
- Builds "keep" intervals (non-silent ranges) and concatenates them via the concat demuxer.
- Returns `(output_path, keep_intervals)` — `keep_intervals` are used later to remap subtitle timestamps.
- On failure: logs and falls back to the raw clip.

### Step 5 — Reformatting to vertical (`pipeline/reformat.py`)
- Crops/pads to 9:16.
- For sources with a detectable face, uses OpenCV face detection (`_detect_face_x_offset`) to center the crop on the subject.
- For landscape sources without a usable crop, overlays the video on a blurred full-bleed background.
- On failure: falls back to the previous (no-silence) clip.

### Step 6 — Subtitles (`pipeline/subtitles.py`)
- `words_for_clip`: extracts the word list for a clip's time range from the full transcript.
- `remap_through_keep_intervals`: shifts word timestamps to account for silence removed in Step 4.
- `generate_ass` / `burn_subtitles` / `add_subtitles`: generates an ASS subtitle file with word-by-word (karaoke-style) highlighting and burns it into the video via ffmpeg.
- On failure: copies the vertical clip through unchanged (no subtitles).

### Step 7 — Metadata (`pipeline/metadata.py`)
- For each clip, joins the transcript words into clip text and sends it to Claude along with `tone`, `audience`, `niche`, `cta` options.
- Returns `{title, description, tags, reddit_title, reddit_body}`.
- On failure: falls back to a placeholder (`"Clip N"`, empty fields).

### Step 8/9 — Posting (handled separately, on demand)
- Not run automatically — triggered via `POST /post/{job_id}` after results are ready.
- For each clip, posts to whichever platforms are enabled (`options.platforms`) and connected via OAuth.
- **Currently stubbed**: `posting/youtube.py`, `posting/twitter.py`, `posting/reddit.py` and `auth/oauth.py` return `{"success": False, "error": "... not implemented yet"}` / raise `NotImplementedError`.

---

## 6. API reference

All responses follow the envelope:
```json
{ "success": true|false, "data": <object|null>, "error": <string|null> }
```

### `POST /upload`
Upload a video file to start a pipeline job.
- Form fields: `file` (mp4/mov/avi/mkv), `options` (JSON string, see [Options](#7-pipeline-options))
- Returns: `{ job_id }`

### `POST /url`
Start a pipeline job from a YouTube URL (downloaded via `yt-dlp`).
- JSON body: `{ "url": "...", "options": {...} }`
- Returns: `{ job_id }`

### `GET /status/{job_id}`
Poll job progress.
- Returns: `{ status, progress, current_step, steps: {step_name: state}, error, logs: [string] }`
- `status` ∈ `running | done | error`

### `GET /result/{job_id}`
Fetch final results once `status == "done"`.
- Returns: `{ clips: [{ index, video_path, video_url, moment, metadata, post_status }] }`

### `POST /post/{job_id}`
Post all clips to the platforms enabled in `options.platforms`. Updates and returns `post_status` per clip per platform.

### `GET /auth/status`
Returns connection status for `youtube`, `twitter`, `reddit`.

### `GET /auth/{platform}` & `/auth/{platform}/callback`
OAuth start/callback for `youtube` | `twitter` | `reddit`. Currently return `501 Not Implemented`.

### `GET /output/{job_id}/final/{filename}`
Serves a finished clip video file.

### Static files
Everything under `static/` is served from `/` (e.g. `static/app.html` → `/app.html`, `static/logo-final.png` → `/logo-final.png`).

---

## 7. Pipeline options

Passed as JSON in `/upload` (form field `options`) or `/url` (body field `options`):

```json
{
  "tone": "casual | professional | hype | educational | funny",
  "audience": "string — target audience description",
  "niche": "string — content niche",
  "cta": "string — call to action text",
  "num_clips": 3,
  "platforms": ["youtube", "twitter", "reddit"],
  "subreddit": "string — target subreddit (default: 'test')"
}
```

---

## 8. Frontend

Two static pages, sharing a charcoal/purple/red color system, the Molgan custom font, and a subtle grain overlay.

### `static/index.html` — Landing page
- Sticky nav with logo (`logo-final.png`), "How it works" link, and "Get started" CTA.
- Hero section with headline (red-accent highlight) and "Start repurposing" CTA.
- 6-step "How it works" feature grid.
- All CTAs link to `/app.html`.

### `static/app.html` — App
- **Platform bar**: connection status dots for YouTube / Twitter / Reddit (`/auth/status`, `/auth/{platform}`).
- **Input panel**: tab toggle between file upload (drag-and-drop) and YouTube URL, plus a "Customisation" details panel for tone/audience/niche/CTA/num_clips/platforms.
- **Progress panel**: live step list (`STEP_LABELS`/`STEP_ICONS`), progress bar, and a debug log viewer — driven by polling `GET /status/{job_id}` every 2s.
- **Results panel**: per-clip cards with video preview, editable title/description, tags, "Download all", "Copy all metadata", and "Post to platforms" actions.

### Design system
- CSS custom properties (`:root`) define the palette: `--bg`, `--bg-soft`, `--panel`, `--panel-2`, `--border`, `--purple`, `--purple-2`, `--red`, `--red-soft`, `--charcoal`, `--green`, `--text`, `--muted`.
- Flat design — **no gradients, no pure black** (charcoal base `#1c1b1f`).
- GitHub-style layout: compact 62px nav, boxed panels with header bars, 6px-radius flat buttons.
- White (`#ffffff`) 1px outlines on non-colored UI elements (panels, inputs, cards, ghost/secondary buttons); nav top border removed; panel header bottom border at 50% opacity white.
- Custom `@font-face` for "Molgan" (`static/fonts/Molgan-Regular.otf`), Arial/Helvetica fallback.

---

## 9. Configuration

`.env` (see `.env.example`):
```
ANTHROPIC_API_KEY=sk-ant-...
# (Phase 2 — posting/OAuth, currently unused)
# GOOGLE_CLIENT_ID=...
# GOOGLE_CLIENT_SECRET=...
# TWITTER_API_KEY=...
# REDDIT_CLIENT_ID=...
```

`main.py` also sets `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` to `certifi`'s bundle at startup to avoid SSL errors when Whisper downloads its model.

---

## 10. Running locally

```bash
cd repurpose
pip install -r requirements.txt
# ensure ffmpeg is installed and on PATH
python3 main.py
```

Server runs on `http://localhost:8000` (Uvicorn, auto-reload enabled). Visit `/` for the landing page, `/app.html` to use the tool.

---

## 11. Known limitations / Phase 2 work

- Job state is in-memory only — restarting the server loses all job history.
- Output directories are auto-cleaned 1 hour after a job completes.
- OAuth and posting to YouTube, Twitter/X, and Reddit are **stubbed** (return "not implemented yet") — wiring these up is the main remaining phase 2 task.
- Whisper runs the `"base"` model locally; larger models would improve transcription accuracy at the cost of speed/memory.
