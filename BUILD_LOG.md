# Shinobi. — Build Log

A day-by-day record of what's been built so far. Useful for onboarding,
investor updates, or just remembering how we got here.

---

## Day 1 — 2026-06-11: Core pipeline + landing page

The foundation. Got the full video-repurposing pipeline working end to end:

- **Upload or paste a YouTube link** — `yt-dlp` handles URL downloads
- **Transcription** — local OpenAI Whisper model converts speech to a
  word-level transcript
- **Moment detection** — Claude reads the full transcript and picks the best
  short-form moments (hook strength, payoff, standalone clarity)
- **Clipping** — ffmpeg extracts each chosen moment from the source video
- **Silence removal** — automatically detects and trims dead air/pauses
- **Vertical reformat** — converts clips to 9:16 for TikTok/Reels/Shorts
- **Subtitle burn-in** — word-by-word animated subtitles via ASS files
- **AI metadata** — Claude generates titles, descriptions, tags, and
  Reddit-specific post text for each clip
- **FastAPI backend** — orchestrates the whole pipeline as background jobs
  with live progress/status polling
- Built the **landing page** (`/`), the **tool page** (`/app.html`), and a
  **technical overview page** (`/readme.html`)
- Stubbed out posting integrations for YouTube, X (Twitter), and Reddit

Result: a working "long video in, vertical clips out" tool with a real UI.

---

## Day 2 — 2026-06-12: Accounts, profiles, and the Copilot

Big day — turned the tool into a product people can have accounts on, and
added an AI assistant that can edit results after the fact.

**Accounts & profiles**
- Email/password signup & login with server-side sessions
- Profile pages: bio, custom username, avatar upload, connected-platform
  status (YouTube/X/Reddit), and a history of past projects
- Side-drawer navigation with hamburger menu, avatar + username shown in the
  nav bar linking to the profile

**Copilot — the AI editing assistant**
- Floating chat widget available on every page, with a model picker
  (Katana/Wakizashi/Kunai/Shuriken tiers)
- Copilot can **actively re-edit a finished job**:
  - "remove more of the silence" → re-renders all clips with adjusted
    `noise_db` / `min_duration` params
  - "include the part where I talk about X" → finds a new moment for that
    topic in the source video, clips/processes it, and appends it to results
- Tuned default silence-removal to be lighter-touch (`-35dB` / `0.6s`) so the
  pipeline doesn't over-trim by default

**Deployment groundwork**
- `Dockerfile` (Python 3.11 + ffmpeg), `.dockerignore`, `railway.toml` — app
  is container-ready for Railway/Fly/Render whenever we're ready to host
  publicly (deployment itself paused to avoid hosting costs for now)

---

## Day 3 — 2026-06-13: CMO brief

- Wrote up an internal brief for marketing covering product status, what's
  live vs. not (auto-posting OAuth, branding assets, domain/hosting,
  messaging), and immediate action items — plus follow-up sections on brand
  image and finding beta testers
- Kept this doc local-only (not in the GitHub repo) since it's an internal
  planning doc, not code

---

## Day 4 — 2026-06-14: Polish pass — branding, profile UX, project management

A full day of UI polish and new profile features.

**Visual branding**
- Reworked all gradients across the app (buttons, hero glows, Copilot button,
  progress bars) to be **purple-dominant and darker**, then matched the exact
  purple to the one in the Shinobi logo (`#5a41ec`) for consistency
- Copilot's floating button and accent colors now match the logo purple too

**Profile page**
- Replaced the static username display with a **keystroke-animated random
  greeting** (e.g. "Hello {username}, how are we today?") — picks from a pool
  of greetings and types it out letter-by-letter, matching the typewriter
  effect already used on the landing/tool pages

**Project management (new)**
- Projects are now **persisted permanently** — pipeline results are saved to
  disk (`result.json`) and no longer auto-deleted for logged-in users
- **Click a past project to reopen it** — `/app.html?job={id}` loads the saved
  results straight into the results view
- **Delete on hover** — each project card shows a white 2D trash-icon button
  on hover; clicking it moves the project to trash (with confirmation)
- **Dedicated Trash page** (`/trash.html`) — linked from the side menu, shows
  trashed projects with **Restore** and **Delete forever** (which also cleans
  up the files on disk) options; trash content no longer clutters the profile
  page

---

## Day 5 — 2026-06-16: Flexible clip count (1–10)

- **Up to 10 clips** — the clip count selector now runs from 1 to 10 (was
  capped at 3); backend enforces a hard max of 10
- **Landing page updated** — hero headline changed from "Three viral clips" to
  "Up to 10 viral clips" to reflect the new range
- **Trash moved to its own page** (`/trash.html`) — side-menu link, logged-in
  only; profile page no longer shows trash content

---

## Day 6 — 2026-06-16: Copilot removed, model picker added

- **Copilot scrapped** — removed the Copilot chat widget, all backend routes
  (`/api/copilot`, `/api/copilot/edit`), and the landing-page intro section
  entirely; `copilot.js` is no longer loaded
- **Model picker in the tool** — replaced the localStorage-based hidden model
  setting with a visible `<select>` dropdown (Katana 5.5 / Wakizashi 4.5 /
  Kunai 4.5 / Shuriken 3.5) sitting right beside the YouTube URL Fetch button,
  so the active model is always visible and changeable before every run

---

## Where things stand

- Core pipeline, accounts, Copilot live-editing, and project history/trash are
  all working locally
- Branding is consistent across the app (purple/red gradient theme matching
  the logo)
- Deployment is ready to go (Docker + Railway config) but paused until we
  decide to take on hosting costs
- Outstanding decisions (see CMO brief, local-only): auto-posting OAuth setup,
  final branding assets, domain/hosting budget, and beta-tester recruitment
