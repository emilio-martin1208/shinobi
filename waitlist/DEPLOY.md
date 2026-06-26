# Shinobi Waitlist — Deploy Guide

A self-contained static page to validate demand before deploying the real app.
**No backend, no hosting cost** — it's just HTML + a free form service.

Everything it needs is in this `waitlist/` folder:
- `index.html` — the page
- `logo-final.png` — logo
- `fonts/Molgan-Regular.otf` — brand font

---

## Step 1 — Set up form capture (Formspree, ~2 min)

1. Go to https://formspree.io and create a **free** account.
2. Create a new form (name it "Shinobi waitlist").
3. Copy its endpoint URL — it looks like `https://formspree.io/f/abcd1234`.
4. Open `index.html`, find this line near the bottom:
   ```js
   const FORM_ENDPOINT = "PASTE_YOUR_FORMSPREE_ENDPOINT_HERE";
   ```
   Replace the placeholder with your endpoint URL. Save.

Submissions (email + which plan they picked) land in your Formspree inbox and
dashboard, and you can export them to CSV anytime.

> Prefer Google Sheets or Tally instead? Any service that accepts a JSON POST
> works — just swap the URL. The form sends `{ email, plan }`.

---

## Step 2 — Deploy the page (free)

Pick ONE. All have generous free tiers and zero cost for a static page.

### Option A — Netlify Drop (easiest, no account math)
1. Go to https://app.netlify.com/drop
2. Drag the entire `waitlist/` folder onto the page.
3. It's live on a `random-name.netlify.app` URL in seconds.

### Option B — Vercel
1. `npm i -g vercel` (once), then from inside `waitlist/`: `vercel`
2. Follow the prompts. Live in ~1 min.

### Option C — GitHub Pages
1. Push the repo to GitHub.
2. Settings → Pages → deploy from branch, point it at the folder.
   (Or copy `waitlist/`'s contents to a `gh-pages` branch root.)

---

## Step 3 — (Optional) Custom domain

Buy a domain (e.g. `getshinobi.app`) and point it at your host in their
dashboard. Netlify/Vercel both have one-click domain setup + free HTTPS.

---

## Step 4 — Drive traffic & measure

Share the URL everywhere (founder DMs, r/podcasting, r/NewTubers, X, creator
Discords). What to watch:
- **Signups** = raw interest
- **Plan picked** = willingness to pay (the signal that matters)
- A healthy mix of Creator/Pro picks > a pile of "Free" = real demand

Set a target before you start (e.g. *"100 signups with 30%+ choosing a paid
tier"*). Hit it → deploy the real app with confidence. Miss it → fix the
message or the audience before spending on hosting.

---

## What this page does NOT do

- It does **not** run the Shinobi pipeline (no video processing, no API costs).
- It does **not** expose `/app.html` or any backend — nothing to break or bill.
- It is purely a demand-validation funnel.
