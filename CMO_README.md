# Shinobi. — Brief for the CMO

This doc is for marketing/brand — what the product is, what's live, and what we need from you right now.

## What Shinobi is

Shinobi turns a long-form video (upload or YouTube link) into multiple short,
vertical, subtitled clips ready for TikTok/Reels/Shorts/Reddit — automatically.
It transcribes the video, finds the best moments, removes dead air, reformats
to 9:16, burns in animated subtitles, and writes titles/descriptions/tags for
each clip. A built-in AI "Copilot" can also tweak results after the fact
(e.g. "remove more silence," "include the part where I talk about X").

## What's live today

- Core pipeline: upload/URL → transcription → AI moment-detection → clipping →
  silence removal → vertical reformat → subtitle burn-in → AI metadata
- Landing page (`/`), tool (`/app.html`), tech overview (`/readme.html`)
- Accounts: email/password signup/login, session-based
- Profile pages: bio, username, avatar, past projects history
- "Copilot" assistant: floating widget, model picker, live-edits finished clips
- Codebase is on GitHub, Docker-ready for deployment whenever we're ready to host it publicly

## What's NOT live yet (and needs your input before it can go live)

### 1. Direct posting to YouTube / X (Twitter) / Reddit
The UI has "Connect" buttons for all three platforms on the profile page, but
they're stubbed — clicking them currently returns "OAuth not configured."
To turn this on we need, **per platform**:

- **YouTube**: a Google Cloud project + OAuth client (Client ID/Secret) with
  YouTube Data API access. Google requires app verification/branding review
  for public use — this can take time, so worth starting early.
- **X (Twitter)**: a developer account + app with OAuth2 client credentials
  (and the right API tier for posting video).
- **Reddit**: a Reddit "app" registration (Client ID/Secret) plus a decision
  on which subreddit(s) we're allowed to auto-post to (most mod teams flag
  bot-posted video).

**Ask for you**: do we want auto-posting as a v1 feature, or is "download the
clip and post it yourself" good enough for launch? If we want it, someone
(you or whoever owns our social accounts) needs to register these apps —
I can walk through the technical registration steps once you're ready.

### 2. Branding assets
- Current logo is a placeholder (`logo-final.png`). Do we have final brand
  assets (logo, favicon, color palette sign-off, font license for "Molgan")?
- Current palette: purple `#8b5cf6` / red `#ff4d5e` / charcoal `#0d0d14`.
  Confirm this is approved for public launch.

### 3. Public domain & hosting
The app isn't deployed publicly yet (deliberately paused to avoid hosting
costs until we're ready). Before a public/marketing push we'll need:
- A domain name (e.g. `shinobi.app` or similar) — is one already owned?
- A decision on hosting budget (small monthly cost, ~$5–20/mo range depending
  on usage) so we can deploy

### 4. Messaging / positioning input
The landing page currently pitches: "repurpose your video, instantly" with
a step-by-step "how it works" section and an AI-model lineup (Katana/Wakizashi/
Kunai/Shuriken naming theme). Marketing input welcome on:
- Tagline / value prop wording
- Whether the "ninja blade" model-naming theme stays for external users or is
  internal-only
- Any compliance language needed (AI-generated content disclosure, ToS/Privacy
  pages — currently none exist)

## Immediate action items for CMO

1. **Decide**: do we need auto-posting (YouTube/X/Reddit) for launch, or can
   v1 ship as "download your clips"?
2. **Provide or approve**: final logo/branding assets and color palette
3. **Decide**: domain name + greenlight a small hosting budget when ready
4. **Review**: landing page copy/positioning (`/` and `/readme.html`) and flag
   anything off-brand or that needs legal language (ToS/Privacy/AI disclosure)
5. **If auto-posting is wanted**: start the YouTube OAuth verification process
   early, since Google's review can take days/weeks
