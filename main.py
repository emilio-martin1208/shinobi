import asyncio
import json
import os
import shutil
import uuid

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from anthropic import AsyncAnthropic

import jobs
from auth import oauth, users
from pipeline import clip, metadata, moments, reformat, silence, subtitles, transcribe
from posting import reddit, twitter, youtube

load_dotenv()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("static/avatars", exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ok(data):
    return JSONResponse({"success": True, "data": data, "error": None})


def err(message, status=400):
    return JSONResponse({"success": False, "data": None, "error": message}, status_code=status)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

async def run_pipeline(job_id):
    job = jobs.get_job(job_id)
    video_path = job["video_path"]
    options = job["options"]
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    raw_dir = os.path.join(job_output_dir, "raw")
    log_path = os.path.join(job_output_dir, "log.txt")
    os.makedirs(job_output_dir, exist_ok=True)

    job["status"] = "running"

    try:
        # Step 1: transcribe
        jobs.set_step(job_id, "transcribing", "active")
        jobs.log(job_id, "Starting transcription")
        transcript = await transcribe.transcribe(video_path)
        jobs.set_step(job_id, "transcribing", "done")
        jobs.log(job_id, f"Transcription complete: {len(transcript['words'])} words")
    except Exception as e:
        jobs.set_step(job_id, "transcribing", "error")
        jobs.set_error(job_id, f"Transcription failed: {e}")
        return

    try:
        # Step 2: find moments
        jobs.set_step(job_id, "finding_moments", "active")
        found_moments = await moments.find_moments(transcript["words"], options)
        jobs.set_step(job_id, "finding_moments", "done")
        jobs.log(job_id, f"Found {len(found_moments)} moments")
    except Exception as e:
        jobs.set_step(job_id, "finding_moments", "error")
        jobs.set_error(job_id, f"Moment detection failed: {e}")
        return

    try:
        # Step 3: clip
        jobs.set_step(job_id, "clipping", "active")
        raw_clips = await clip.extract_clips(video_path, found_moments, raw_dir, log_path)
        jobs.set_step(job_id, "clipping", "done")
        jobs.log(job_id, f"Extracted {len(raw_clips)} clips")
    except Exception as e:
        jobs.set_step(job_id, "clipping", "error")
        jobs.set_error(job_id, f"Clipping failed: {e}")
        return

    # Step 4: remove silence (per clip; failures fall back to raw clip)
    jobs.set_step(job_id, "removing_silence", "active")
    nosilence_dir = os.path.join(job_output_dir, "nosilence")
    os.makedirs(nosilence_dir, exist_ok=True)
    nosilence_clips = []
    keep_intervals_per_clip = []
    for i, raw_clip_path in enumerate(raw_clips):
        out_path = os.path.join(nosilence_dir, f"clip_{i}_nosilence.mp4")
        try:
            _, keep = await silence.remove_silence(raw_clip_path, out_path, log_path)
            nosilence_clips.append(out_path)
            keep_intervals_per_clip.append(keep)
            jobs.log(job_id, f"Clip {i}: removed silence ({len(keep)} segments kept)")
        except Exception as e:
            jobs.log(job_id, f"Clip {i}: silence removal failed ({e}), using raw clip")
            nosilence_clips.append(raw_clip_path)
            keep_intervals_per_clip.append(None)
    jobs.set_step(job_id, "removing_silence", "done")

    # Step 5: reformat to vertical (failures fall back to nosilence clip)
    jobs.set_step(job_id, "reformatting", "active")
    vertical_dir = os.path.join(job_output_dir, "vertical")
    os.makedirs(vertical_dir, exist_ok=True)
    vertical_clips = []
    for i, src in enumerate(nosilence_clips):
        out_path = os.path.join(vertical_dir, f"clip_{i}_vertical.mp4")
        try:
            await reformat.reformat_to_vertical(src, out_path, log_path)
            vertical_clips.append(out_path)
            jobs.log(job_id, f"Clip {i}: reformatted to vertical")
        except Exception as e:
            jobs.log(job_id, f"Clip {i}: reformat failed ({e}), using previous clip")
            vertical_clips.append(src)
    jobs.set_step(job_id, "reformatting", "done")

    # Step 6: subtitles (failures fall back to vertical clip without subs)
    jobs.set_step(job_id, "subtitles", "active")
    final_dir = os.path.join(job_output_dir, "final")
    os.makedirs(final_dir, exist_ok=True)
    final_clips = []
    for i, src in enumerate(vertical_clips):
        out_path = os.path.join(final_dir, f"clip_{i}_final.mp4")
        try:
            m = found_moments[i]
            clip_words = subtitles.words_for_clip(transcript["words"], m["start_sec"], m["end_sec"])
            keep = keep_intervals_per_clip[i]
            if keep is not None:
                clip_words = subtitles.remap_through_keep_intervals(clip_words, keep)
            await subtitles.add_subtitles(src, out_path, clip_words, final_dir, log_path)
            final_clips.append(out_path)
            jobs.log(job_id, f"Clip {i}: subtitles burned in")
        except Exception as e:
            jobs.log(job_id, f"Clip {i}: subtitle burn-in failed ({e}), using clip without subs")
            shutil.copy(src, out_path)
            final_clips.append(out_path)
    jobs.set_step(job_id, "subtitles", "done")

    # Step 7: metadata
    jobs.set_step(job_id, "metadata", "active")
    clip_results = []
    for i, final_path in enumerate(final_clips):
        m = found_moments[i]
        clip_text_words = subtitles.words_for_clip(transcript["words"], m["start_sec"], m["end_sec"])
        clip_text = " ".join(w["word"] for w in clip_text_words)
        try:
            meta = await metadata.generate_metadata(clip_text, options)
        except Exception as e:
            jobs.log(job_id, f"Clip {i}: metadata generation failed ({e})")
            meta = {
                "title": f"Clip {i + 1}",
                "description": "",
                "tags": [],
                "reddit_title": f"Clip {i + 1}",
                "reddit_body": "",
            }
        clip_results.append({
            "index": i,
            "video_path": final_path,
            "video_url": f"/output/{job_id}/final/{os.path.basename(final_path)}",
            "moment": m,
            "metadata": meta,
            "post_status": {},
        })
    jobs.set_step(job_id, "metadata", "done")
    jobs.log(job_id, "Metadata generated for all clips")

    # Step 8/9: posting handled separately via POST /post/{job_id}
    jobs.set_step(job_id, "posting", "pending")

    jobs.set_result(job_id, {"clips": clip_results})
    # Keep raw materials around so Copilot can re-render clips with new edits later
    job["transcript"] = transcript
    job["found_moments"] = found_moments
    job["raw_clips"] = raw_clips
    job["job_output_dir"] = job_output_dir
    job["status"] = "done"
    jobs.log(job_id, "Pipeline complete")

    # Record this as a project on the user's profile, if they're logged in
    user_id = job.get("user_id")
    if user_id and clip_results:
        first_title = clip_results[0]["metadata"].get("title") or "Untitled project"
        users.add_project(user_id, job_id, first_title, len(clip_results), clip_results[0]["video_url"])

    # Move the uploaded source video into the job's output dir so Copilot can
    # pull additional clips from it later.
    try:
        source_dest = os.path.join(job_output_dir, "source" + os.path.splitext(video_path)[1])
        shutil.move(video_path, source_dest)
        job["source_video_path"] = source_dest
    except OSError:
        pass

    # Persist the result so saved projects can be reopened later from the profile page
    with open(os.path.join(job_output_dir, "result.json"), "w") as f:
        json.dump(job["result"], f)

    if user_id and clip_results:
        # Saved as a project on the user's profile — keep the output around
        # so it can be reopened later instead of cleaning it up.
        pass
    else:
        # Anonymous job — schedule cleanup of output dir after 1 hour
        asyncio.create_task(_cleanup_after_delay(job_output_dir, 3600))


async def _cleanup_after_delay(path, delay_seconds):
    await asyncio.sleep(delay_seconds)
    shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload(request: Request, file: UploadFile = File(...), options: str = Form("{}")):
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "")[1] or ".mp4"
    if ext.lower() not in (".mp4", ".mov", ".avi", ".mkv"):
        return err("Unsupported file type")

    try:
        parsed_options = json.loads(options)
    except json.JSONDecodeError:
        parsed_options = {}

    dest_path = os.path.join(UPLOAD_DIR, f"{job_id}{ext}")
    jobs.new_job(job_id, dest_path, parsed_options)
    jobs.get_job(job_id)["user_id"] = _current_user_id(request)
    jobs.set_step(job_id, "uploading", "active")

    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        jobs.set_error(job_id, f"Upload failed: {e}")
        return err(f"Upload failed: {e}")

    jobs.set_step(job_id, "uploading", "done")
    asyncio.create_task(run_pipeline(job_id))
    return ok({"job_id": job_id})


@app.post("/url")
async def from_url(request: Request):
    body = await request.json()
    url = body.get("url")
    if not url:
        return err("Missing 'url'")
    options = body.get("options", {})

    job_id = str(uuid.uuid4())
    dest_template = os.path.join(UPLOAD_DIR, f"{job_id}.%(ext)s")

    jobs.new_job(job_id, "", options)
    jobs.get_job(job_id)["user_id"] = _current_user_id(request)
    jobs.set_step(job_id, "uploading", "active")
    jobs.log(job_id, f"Downloading {url}")

    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "-f", "mp4/bestvideo+bestaudio", "-o", dest_template, url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode(errors="replace")[-1000:])

        downloaded = None
        for fname in os.listdir(UPLOAD_DIR):
            if fname.startswith(job_id):
                downloaded = os.path.join(UPLOAD_DIR, fname)
                break
        if not downloaded:
            raise RuntimeError("Download completed but file not found")

        job = jobs.get_job(job_id)
        job["video_path"] = downloaded
    except Exception as e:
        jobs.set_step(job_id, "uploading", "error")
        jobs.set_error(job_id, f"Download failed: {e}")
        return err(f"Download failed: {e}")

    jobs.set_step(job_id, "uploading", "done")
    asyncio.create_task(run_pipeline(job_id))
    return ok({"job_id": job_id})


@app.get("/status/{job_id}")
async def status(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        return err("Job not found", status=404)
    return ok({
        "status": job["status"],
        "progress": job["progress"],
        "current_step": job["current_step"],
        "steps": job["steps"],
        "error": job["error"],
        "logs": job["logs"],
    })


@app.get("/result/{job_id}")
async def result(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        return err("Job not found", status=404)
    if job["result"] is None:
        return err("Job not finished", status=409)
    return ok(job["result"])


@app.post("/post/{job_id}")
async def post_job(job_id: str):
    job = jobs.get_job(job_id)
    if job is None:
        return err("Job not found", status=404)
    if job["result"] is None:
        return err("Job not finished", status=409)

    jobs.set_step(job_id, "posting", "active")
    options = job["options"]
    platforms = options.get("platforms", ["youtube", "twitter", "reddit"])

    for c in job["result"]["clips"]:
        meta = c["metadata"]
        video_path = c["video_path"]
        post_status = c.setdefault("post_status", {})

        if "youtube" in platforms:
            try:
                post_status["youtube"] = await youtube.post_to_youtube(
                    video_path, meta["title"], meta["description"], meta["tags"]
                )
            except Exception as e:
                post_status["youtube"] = {"success": False, "error": str(e)}

        if "twitter" in platforms:
            try:
                post_status["twitter"] = await twitter.post_to_twitter(video_path, meta["title"])
            except Exception as e:
                post_status["twitter"] = {"success": False, "error": str(e)}

        if "reddit" in platforms:
            try:
                subreddit = options.get("subreddit", "test")
                post_status["reddit"] = await reddit.post_to_reddit(
                    video_path, meta["reddit_title"], meta["reddit_body"], subreddit
                )
            except Exception as e:
                post_status["reddit"] = {"success": False, "error": str(e)}

    jobs.set_step(job_id, "posting", "done")
    return ok(job["result"])


# ---------------------------------------------------------------------------
# Copilot widget proxy (keeps ANTHROPIC_API_KEY server-side)
# ---------------------------------------------------------------------------

_copilot_client = None


def _get_copilot_client():
    global _copilot_client
    if _copilot_client is None:
        _copilot_client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _copilot_client


@app.post("/api/copilot/edit")
async def copilot_edit(request: Request):
    """Let Copilot actively re-render clips for an already-finished job
    based on a natural-language instruction (e.g. "remove more silence")."""
    body = await request.json()
    job_id = body.get("job_id")
    instruction = body.get("instruction", "")
    job = jobs.get_job(job_id)
    if job is None or job.get("status") != "done" or not job.get("result"):
        return err("Job not found or not finished yet")

    # Ask Claude to translate the instruction into concrete silence-removal params
    try:
        client = _get_copilot_client()
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=300,
            system=(
                "You control a video repurposing pipeline for an already-processed job, and can "
                "take one of these actions based on the user's chat message:\n\n"
                "1. SILENCE — adjust how aggressively pauses are trimmed. The silence-removal "
                "step uses ffmpeg silencedetect with two parameters: noise_db (range -50 to -15; "
                "LESS negative = a higher noise floor = MORE audio counts as 'silence' = more "
                "gets cut) and min_duration (seconds, range 0.1 to 1.5; smaller = even short "
                "pauses get cut). Current defaults are noise_db=-35, min_duration=0.6 (a light "
                "touch — only longer, clearly silent pauses are cut).\n\n"
                "2. ADD_CLIP — the user wants a NEW clip added that covers a specific topic, "
                "quote, or part of the video they mention (e.g. \"include the part where I talk "
                "about X\", \"add the bit about Y\"). Extract a short search phrase/topic "
                "description for that part.\n\n"
                "3. NONE — the message doesn't call for either action (general chat, or about "
                "something not yet supported).\n\n"
                "Reply with ONLY a JSON object: "
                '{"action": "silence"|"add_clip"|"none", "noise_db": <int>, '
                '"min_duration": <float>, "topic": "<short search phrase, for add_clip>", '
                '"reply": "<short, friendly one-sentence reply to the user>"}. '
                "Include all fields every time (use sensible defaults/empty values for unused ones)."
            ),
            messages=[{"role": "user", "content": instruction}],
        )
        text = response.content[0].text if response.content else "{}"
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        decision = json.loads(text)
    except Exception as e:
        return err(f"Copilot edit request failed: {e}", status=502)

    action = decision.get("action", "none")
    if action == "none":
        return ok({"applied": False, "reply": decision.get("reply", "I didn't change anything for that.")})

    transcript = job.get("transcript")
    found_moments = job.get("found_moments")
    raw_clips = job.get("raw_clips")
    job_output_dir = job.get("job_output_dir")
    if not (transcript and found_moments and raw_clips and job_output_dir):
        return err("This job's source clips are no longer available for editing")

    log_path = os.path.join(job_output_dir, "log.txt")

    if action == "add_clip":
        return await _copilot_add_clip(job, job_id, decision, transcript, found_moments, raw_clips, job_output_dir, log_path)

    noise_db = max(-50, min(-15, int(decision.get("noise_db", -35))))
    min_duration = max(0.1, min(1.5, float(decision.get("min_duration", 0.6))))
    edit_tag = uuid.uuid4().hex[:8]
    nosilence_dir = os.path.join(job_output_dir, "nosilence")
    vertical_dir = os.path.join(job_output_dir, "vertical")
    final_dir = os.path.join(job_output_dir, "final")
    os.makedirs(nosilence_dir, exist_ok=True)
    os.makedirs(vertical_dir, exist_ok=True)
    os.makedirs(final_dir, exist_ok=True)

    updated_clips = []
    for i, raw_clip_path in enumerate(raw_clips):
        try:
            nosilence_out = os.path.join(nosilence_dir, f"clip_{i}_nosilence_{edit_tag}.mp4")
            _, keep = await silence.remove_silence(
                raw_clip_path, nosilence_out, log_path, noise_db=noise_db, min_duration=min_duration
            )

            vertical_out = os.path.join(vertical_dir, f"clip_{i}_vertical_{edit_tag}.mp4")
            await reformat.reformat_to_vertical(nosilence_out, vertical_out, log_path)

            m = found_moments[i]
            clip_words = subtitles.words_for_clip(transcript["words"], m["start_sec"], m["end_sec"])
            clip_words = subtitles.remap_through_keep_intervals(clip_words, keep)

            final_out = os.path.join(final_dir, f"clip_{i}_final_{edit_tag}.mp4")
            await subtitles.add_subtitles(vertical_out, final_out, clip_words, final_dir, log_path)

            video_url = f"/output/{job_id}/final/{os.path.basename(final_out)}"
            job["result"]["clips"][i]["video_path"] = final_out
            job["result"]["clips"][i]["video_url"] = video_url
            updated_clips.append({"index": i, "video_url": video_url})
            jobs.log(job_id, f"Copilot edit: clip {i} re-rendered (noise_db={noise_db}, min_duration={min_duration})")
        except Exception as e:
            jobs.log(job_id, f"Copilot edit: clip {i} failed ({e})")

    return ok({
        "applied": True,
        "clips": updated_clips,
        "reply": decision.get("reply", "Done — I've updated your clips."),
    })


async def _copilot_add_clip(job, job_id, decision, transcript, found_moments, raw_clips, job_output_dir, log_path):
    topic = (decision.get("topic") or "").strip()
    source_video_path = job.get("source_video_path")
    if not topic:
        return ok({"applied": False, "reply": decision.get("reply", "I'm not sure which part you mean — can you describe it a bit more?")})
    if not source_video_path or not os.path.exists(source_video_path):
        return err("The original video is no longer available, so I can't pull a new clip from it")

    try:
        sub_options = dict(job.get("options") or {})
        sub_options["num_clips"] = 1
        sub_options["instructions"] = (
            f"Find the single best ~30-60s standalone segment where the speaker talks about: \"{topic}\". "
            "This is in addition to clips already chosen — pick the best matching segment for this topic specifically."
        )
        new_moments = await moments.find_moments(transcript["words"], sub_options)
        if not new_moments:
            return ok({"applied": False, "reply": "I couldn't find a part of the video matching that — could you describe it differently?"})
        m = new_moments[0]

        i = len(raw_clips)
        edit_tag = uuid.uuid4().hex[:8]
        raw_dir = os.path.join(job_output_dir, "raw")
        nosilence_dir = os.path.join(job_output_dir, "nosilence")
        vertical_dir = os.path.join(job_output_dir, "vertical")
        final_dir = os.path.join(job_output_dir, "final")
        for d in (raw_dir, nosilence_dir, vertical_dir, final_dir):
            os.makedirs(d, exist_ok=True)

        raw_out = os.path.join(raw_dir, f"clip_{i}_{edit_tag}.mp4")
        await clip.extract_clip(source_video_path, m["start_sec"], m["end_sec"], raw_out, log_path)

        nosilence_out = os.path.join(nosilence_dir, f"clip_{i}_nosilence_{edit_tag}.mp4")
        _, keep = await silence.remove_silence(raw_out, nosilence_out, log_path)

        vertical_out = os.path.join(vertical_dir, f"clip_{i}_vertical_{edit_tag}.mp4")
        await reformat.reformat_to_vertical(nosilence_out, vertical_out, log_path)

        clip_words = subtitles.words_for_clip(transcript["words"], m["start_sec"], m["end_sec"])
        clip_words = subtitles.remap_through_keep_intervals(clip_words, keep)

        final_out = os.path.join(final_dir, f"clip_{i}_final_{edit_tag}.mp4")
        await subtitles.add_subtitles(vertical_out, final_out, clip_words, final_dir, log_path)

        clip_text = " ".join(w["word"] for w in clip_words)
        try:
            meta = await metadata.generate_metadata(clip_text, job.get("options") or {})
        except Exception:
            meta = {"title": f"Clip {i + 1}", "description": "", "tags": [], "reddit_title": f"Clip {i + 1}", "reddit_body": ""}

        video_url = f"/output/{job_id}/final/{os.path.basename(final_out)}"
        new_clip = {
            "index": i,
            "video_path": final_out,
            "video_url": video_url,
            "moment": m,
            "metadata": meta,
            "post_status": {},
        }
        job["result"]["clips"].append(new_clip)
        job["found_moments"].append(m)
        job["raw_clips"].append(raw_out)
        jobs.log(job_id, f"Copilot: added new clip {i} for topic '{topic}'")

        return ok({
            "applied": True,
            "new_clip": new_clip,
            "reply": decision.get("reply", "Done — I've added a new clip for that part."),
        })
    except Exception as e:
        return err(f"Couldn't add that clip: {e}", status=502)


@app.post("/api/copilot")
async def copilot(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    system = body.get("system", "")

    if not messages:
        return err("Missing 'messages'")

    try:
        client = _get_copilot_client()
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            system=system,
            messages=messages,
        )
        text = response.content[0].text if response.content else ""
        return ok({"content": [{"text": text}]})
    except Exception as e:
        return err(f"Copilot request failed: {e}", status=502)


# ---------------------------------------------------------------------------
# Account routes (email/password)
# ---------------------------------------------------------------------------

SESSION_COOKIE = "shinobi_session"


def _current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    return users.get_session_user(token)


def _current_user_id(request: Request):
    user = _current_user(request)
    return user["id"] if user else None


@app.post("/api/signup")
async def signup(request: Request):
    body = await request.json()
    email = body.get("email", "")
    password = body.get("password", "")

    try:
        user_id = users.create_user(email, password)
    except ValueError as e:
        return err(str(e))

    token = users.create_session(user_id)
    response = ok({"email": email.strip().lower()})
    response.set_cookie(SESSION_COOKIE, token, max_age=users.SESSION_TTL_SECONDS, httponly=True, samesite="lax")
    return response


@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    email = body.get("email", "")
    password = body.get("password", "")

    try:
        user_id = users.verify_user(email, password)
    except ValueError as e:
        return err(str(e), status=401)

    token = users.create_session(user_id)
    response = ok({"email": email.strip().lower()})
    response.set_cookie(SESSION_COOKIE, token, max_age=users.SESSION_TTL_SECONDS, httponly=True, samesite="lax")
    return response


@app.post("/api/logout")
async def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        users.delete_session(token)
    response = ok({})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/me")
async def me(request: Request):
    user = _current_user(request)
    if user is None:
        return ok({"logged_in": False})
    extra = users.get_profile_extra(user["id"])
    return ok({
        "logged_in": True,
        "email": user["email"],
        "username": extra["username"],
        "avatar_url": extra["avatar_url"],
    })


# ---------------------------------------------------------------------------
# Profile routes (bio + past projects)
# ---------------------------------------------------------------------------

@app.get("/api/profile")
async def get_profile(request: Request):
    user = _current_user(request)
    if user is None:
        return err("Not logged in", status=401)
    extra = users.get_profile_extra(user["id"])
    return ok({
        "email": user["email"],
        "bio": users.get_bio(user["id"]),
        "username": extra["username"],
        "avatar_url": extra["avatar_url"],
        "projects": users.list_projects(user["id"]),
    })


@app.post("/api/profile")
async def update_profile(request: Request):
    user = _current_user(request)
    if user is None:
        return err("Not logged in", status=401)
    body = await request.json()
    if "bio" in body:
        users.set_bio(user["id"], body.get("bio", ""))
    if "username" in body:
        try:
            users.set_username(user["id"], body.get("username", ""))
        except ValueError as e:
            return err(str(e), status=400)
    extra = users.get_profile_extra(user["id"])
    return ok({"bio": users.get_bio(user["id"]), "username": extra["username"], "avatar_url": extra["avatar_url"]})


@app.post("/api/profile/avatar")
async def upload_avatar(request: Request, file: UploadFile = File(...)):
    user = _current_user(request)
    if user is None:
        return err("Not logged in", status=401)
    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        ext = ".png"
    filename = f"user_{user['id']}{ext}"
    dest_path = os.path.join("static/avatars", filename)
    with open(dest_path, "wb") as f:
        f.write(await file.read())
    avatar_url = f"/avatars/{filename}"
    users.set_avatar(user["id"], avatar_url)
    return ok({"avatar_url": avatar_url})


@app.get("/api/project/{job_id}")
async def get_project(job_id: str, request: Request):
    user_id = _current_user_id(request)
    if not user_id:
        return err("Not logged in", status=401)
    project = users.get_project(user_id, job_id)
    if not project:
        return err("Project not found", status=404)

    job = jobs.get_job(job_id)
    if job and job.get("result"):
        return ok(job["result"])

    result_path = os.path.join(OUTPUT_DIR, job_id, "result.json")
    if not os.path.exists(result_path):
        return err("Project data not found", status=404)
    with open(result_path) as f:
        return ok(json.load(f))


@app.delete("/api/project/{job_id}")
async def trash_project(job_id: str, request: Request):
    user_id = _current_user_id(request)
    if not user_id:
        return err("Not logged in", status=401)
    if not users.set_project_trashed(user_id, job_id, True):
        return err("Project not found", status=404)
    return ok({"job_id": job_id})


@app.get("/api/projects/trash")
async def get_trash(request: Request):
    user_id = _current_user_id(request)
    if not user_id:
        return err("Not logged in", status=401)
    return ok({"projects": users.list_trashed_projects(user_id)})


@app.post("/api/project/{job_id}/restore")
async def restore_project(job_id: str, request: Request):
    user_id = _current_user_id(request)
    if not user_id:
        return err("Not logged in", status=401)
    if not users.set_project_trashed(user_id, job_id, False):
        return err("Project not found", status=404)
    return ok({"job_id": job_id})


@app.delete("/api/project/{job_id}/permanent")
async def delete_project_permanent(job_id: str, request: Request):
    user_id = _current_user_id(request)
    if not user_id:
        return err("Not logged in", status=401)
    project = users.get_project(user_id, job_id)
    if not project:
        return err("Project not found", status=404)
    users.delete_project(user_id, job_id)
    shutil.rmtree(os.path.join(OUTPUT_DIR, job_id), ignore_errors=True)
    return ok({"job_id": job_id})


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.get("/auth/status")
async def auth_status():
    return ok(oauth.auth_status())


@app.get("/auth/youtube")
async def auth_youtube():
    try:
        return await oauth.youtube_auth_start()
    except NotImplementedError as e:
        return err(str(e), status=501)


@app.get("/auth/youtube/callback")
async def auth_youtube_callback(code: str = ""):
    try:
        return await oauth.youtube_auth_callback(code)
    except NotImplementedError as e:
        return err(str(e), status=501)


@app.get("/auth/twitter")
async def auth_twitter():
    try:
        return await oauth.twitter_auth_start()
    except NotImplementedError as e:
        return err(str(e), status=501)


@app.get("/auth/twitter/callback")
async def auth_twitter_callback(code: str = ""):
    try:
        return await oauth.twitter_auth_callback(code)
    except NotImplementedError as e:
        return err(str(e), status=501)


@app.get("/auth/reddit")
async def auth_reddit():
    try:
        return await oauth.reddit_auth_start()
    except NotImplementedError as e:
        return err(str(e), status=501)


@app.get("/auth/reddit/callback")
async def auth_reddit_callback(code: str = ""):
    try:
        return await oauth.reddit_auth_callback(code)
    except NotImplementedError as e:
        return err(str(e), status=501)


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

@app.get("/output/{job_id}/final/{filename}")
async def get_output_file(job_id: str, filename: str):
    safe_job_id = os.path.basename(job_id)
    safe_filename = os.path.basename(filename)
    path = os.path.join(OUTPUT_DIR, safe_job_id, "final", safe_filename)
    if not os.path.isfile(path):
        return err("File not found", status=404)
    return FileResponse(path)


app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
