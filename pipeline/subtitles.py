import asyncio
import os

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,Arial,64,&H0000FFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,40,40,160,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _format_time(seconds):
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    centis = int(round((s - int(s)) * 100))
    return f"{h}:{m:02d}:{int(s):02d}.{centis:02d}"


def remap_through_keep_intervals(words, keep_intervals):
    """Remap word timestamps (relative to a clip) through the keep
    intervals produced by silence removal, dropping words that fall in
    removed (silent) gaps and shifting remaining words to the new
    concatenated timeline."""
    out = []
    offset = 0.0
    for k_start, k_end in keep_intervals:
        for w in words:
            if w["start"] >= k_start and w["end"] <= k_end:
                out.append({
                    "word": w["word"],
                    "start": w["start"] - k_start + offset,
                    "end": w["end"] - k_start + offset,
                })
        offset += (k_end - k_start)
    return out


def words_for_clip(words, clip_start, clip_end):
    """Filter whisper words to those within [clip_start, clip_end] and
    rebase timestamps to be relative to clip_start."""
    out = []
    for w in words:
        if w["end"] <= clip_start or w["start"] >= clip_end:
            continue
        out.append({
            "word": w["word"],
            "start": max(0.0, w["start"] - clip_start),
            "end": min(clip_end - clip_start, w["end"] - clip_start),
        })
    return out


def generate_ass(clip_words, ass_path):
    """Generate an ASS subtitle file with word-by-word pop, current word
    highlighted in yellow."""
    lines = [ASS_HEADER]
    for w in clip_words:
        start = _format_time(w["start"])
        end = _format_time(w["end"])
        text = w["word"].strip().replace("\\", "").replace("{", "").replace("}", "")
        if not text:
            continue
        # Yellow highlight for the active word (PrimaryColour already yellow)
        lines.append(f"Dialogue: 0,{start},{end},Word,,0,0,0,,{text}\n")
    with open(ass_path, "w") as f:
        f.writelines(lines)
    return ass_path


async def burn_subtitles(input_path, ass_path, output_path, log_path):
    args = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264", "-c:a", "aac",
        output_path,
    ]
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
    return output_path


async def add_subtitles(input_path, output_path, clip_words, work_dir, log_path):
    ass_path = os.path.join(work_dir, os.path.basename(output_path) + ".ass")
    generate_ass(clip_words, ass_path)
    return await burn_subtitles(input_path, ass_path, output_path, log_path)
