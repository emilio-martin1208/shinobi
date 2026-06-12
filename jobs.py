import time

STEPS = [
    "uploading",
    "transcribing",
    "finding_moments",
    "clipping",
    "removing_silence",
    "reformatting",
    "subtitles",
    "metadata",
    "posting",
]

# In-memory job store: job_id -> dict
JOBS = {}


def new_job(job_id, video_path, options):
    JOBS[job_id] = {
        "id": job_id,
        "video_path": video_path,
        "options": options,
        "status": "pending",
        "progress": 0,
        "current_step": None,
        "steps": {s: "pending" for s in STEPS},
        "logs": [],
        "error": None,
        "result": None,
        "created_at": time.time(),
    }
    return JOBS[job_id]


def get_job(job_id):
    return JOBS.get(job_id)


def log(job_id, message):
    job = JOBS.get(job_id)
    if job is None:
        return
    job["logs"].append(f"[{time.strftime('%H:%M:%S')}] {message}")


def set_step(job_id, step, state):
    """state: pending | active | done | error"""
    job = JOBS.get(job_id)
    if job is None:
        return
    job["steps"][step] = state
    if state == "active":
        job["current_step"] = step
    job["progress"] = int(
        100 * sum(1 for s in job["steps"].values() if s == "done") / len(STEPS)
    )


def set_error(job_id, message):
    job = JOBS.get(job_id)
    if job is None:
        return
    job["status"] = "error"
    job["error"] = message
    log(job_id, f"ERROR: {message}")


def set_result(job_id, result):
    job = JOBS.get(job_id)
    if job is None:
        return
    job["result"] = result
    job["status"] = "done"
