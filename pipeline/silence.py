import asyncio
import os
import re

SILENCE_RE_START = re.compile(r"silence_start:\s*([\d.]+)")
SILENCE_RE_END = re.compile(r"silence_end:\s*([\d.]+)")


async def _ffprobe_duration(input_path):
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return float(stdout.decode().strip())


async def _detect_silence(input_path, log_path, noise_db=-30, min_duration=0.3):
    args = [
        "ffmpeg", "-i", input_path,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stderr.decode(errors="replace")

    with open(log_path, "a") as f:
        f.write("CMD: " + " ".join(args) + "\n")
        f.write("STDERR:\n" + output + "\n")

    silences = []
    pending_start = None
    for line in output.splitlines():
        m = SILENCE_RE_START.search(line)
        if m:
            pending_start = float(m.group(1))
            continue
        m = SILENCE_RE_END.search(line)
        if m and pending_start is not None:
            silences.append((pending_start, float(m.group(1))))
            pending_start = None

    return silences


def _build_keep_intervals(duration, silences, min_keep=0.05):
    """Invert silence intervals to get non-silent (keep) intervals."""
    keep = []
    cursor = 0.0
    for s_start, s_end in silences:
        if s_start - cursor > min_keep:
            keep.append((cursor, s_start))
        cursor = max(cursor, s_end)
    if duration - cursor > min_keep:
        keep.append((cursor, duration))
    if not keep:
        keep = [(0.0, duration)]
    return keep


async def _run_ffmpeg(args, log_path):
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    with open(log_path, "a") as f:
        f.write("CMD: " + " ".join(args) + "\n")
        f.write("STDOUT:\n" + stdout.decode(errors="replace") + "\n")
        f.write("STDERR:\n" + stderr.decode(errors="replace") + "\n")
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (code {proc.returncode}), see {log_path}")


async def remove_silence(input_path, output_path, log_path, noise_db=-35, min_duration=0.6):
    """Detect silence gaps and concat the non-silent segments together.

    Returns (output_path, keep_intervals) where keep_intervals are the
    (start, end) ranges (in original-clip time) that were kept, in order.
    """
    duration = await _ffprobe_duration(input_path)
    silences = await _detect_silence(input_path, log_path, noise_db=noise_db, min_duration=min_duration)
    keep = _build_keep_intervals(duration, silences)

    if len(keep) <= 1:
        # nothing to remove
        await _run_ffmpeg(["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path], log_path)
        return output_path, keep

    work_dir = os.path.dirname(output_path)
    segment_paths = []
    for i, (s, e) in enumerate(keep):
        seg_path = os.path.join(work_dir, f"_seg_{os.path.basename(output_path)}_{i}.mp4")
        await _run_ffmpeg([
            "ffmpeg", "-y",
            "-ss", str(s), "-to", str(e),
            "-i", input_path,
            "-c:v", "libx264", "-c:a", "aac",
            seg_path,
        ], log_path)
        segment_paths.append(seg_path)

    list_path = os.path.join(work_dir, f"_concat_{os.path.basename(output_path)}.txt")
    with open(list_path, "w") as f:
        for p in segment_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    await _run_ffmpeg([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path,
    ], log_path)

    for p in segment_paths:
        os.remove(p)
    os.remove(list_path)

    return output_path, keep
