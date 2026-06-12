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

import jobs
from auth import oauth
from pipeline import clip, metadata, moments, reformat, silence, subtitles, transcribe
from posting import reddit, twitter, youtube

load_dotenv()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

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
    job["status"] = "done"
    jobs.log(job_id, "Pipeline complete")

    # Clean up uploaded source video
    try:
        os.remove(video_path)
    except OSError:
        pass

    # Schedule cleanup of output dir after 1 hour
    asyncio.create_task(_cleanup_after_delay(job_output_dir, 3600))


async def _cleanup_after_delay(path, delay_seconds):
    await asyncio.sleep(delay_seconds)
    shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload(file: UploadFile = File(...), options: str = Form("{}")):
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
