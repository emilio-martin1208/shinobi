import asyncio
import os


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


async def extract_clip(input_path, start_sec, end_sec, output_path, log_path):
    args = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-i", input_path,
        "-c", "copy",
        output_path,
    ]
    try:
        await _run_ffmpeg(args, log_path)
    except RuntimeError:
        # -c copy can fail if cut points aren't on keyframes; re-encode as fallback
        args = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-to", str(end_sec),
            "-i", input_path,
            "-c:v", "libx264", "-c:a", "aac",
            output_path,
        ]
        await _run_ffmpeg(args, log_path)
    return output_path


async def extract_clips(input_path, moments, output_dir, log_path):
    """Extract all moment clips in parallel. Returns list of output paths."""
    os.makedirs(output_dir, exist_ok=True)
    tasks = []
    for i, m in enumerate(moments):
        out_path = os.path.join(output_dir, f"clip_{i}.mp4")
        tasks.append(extract_clip(input_path, m["start_sec"], m["end_sec"], out_path, log_path))
    return await asyncio.gather(*tasks)
