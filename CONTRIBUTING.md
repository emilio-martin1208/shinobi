# Contributing to Shinobi

Shinobi is a proprietary project. This guide is for authorized contributors.

## Getting set up

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
uvicorn main:app --reload
```

You'll also need `ffmpeg` and `yt-dlp` available on your PATH.

## Project layout

| Path | What it holds |
|------|---------------|
| `main.py` | FastAPI app + pipeline orchestration |
| `pipeline/` | Processing stages (transcribe → moments → clip → silence → reformat → subtitles → metadata) |
| `auth/` | Accounts, sessions, profiles, OAuth token storage |
| `posting/` | YouTube / X / Reddit publishing |
| `jobs.py` | In-memory job/step tracking |
| `static/` | Front-end pages and assets |
| `waitlist/` | Standalone demand-validation landing page |

## Conventions

- **Python:** 4-space indent, module + function docstrings, keep imports sorted
  (stdlib → third-party → local). See `.editorconfig`.
- **Web:** 2-space indent; keep pages self-contained and theme-consistent.
- **Commits:** short imperative subject line; explain the "why" in the body.
- Don't commit secrets, `users.db`, `tokens.db`, or anything under
  `uploads/`, `output/`, or `static/brand/`.

## Before you push

- Run the app and exercise the change end to end.
- Confirm `python -c "import main"` succeeds (no import errors).
- Update `BUILD_LOG.md` for anything user-facing.
