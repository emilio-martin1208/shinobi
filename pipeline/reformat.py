import asyncio
import json

TARGET_W = 1080
TARGET_H = 1920


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


async def _probe_dimensions(input_path):
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        input_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    info = json.loads(stdout.decode())
    stream = info["streams"][0]
    return stream["width"], stream["height"]


def _detect_face_x_offset(input_path, width, height):
    """Try to detect a face in the middle frame and return a horizontal
    centre offset (in source pixels) to bias the crop towards. Returns
    None if detection isn't possible or no face is found."""
    try:
        import cv2
    except ImportError:
        return None

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        return None

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count // 2))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    if len(faces) == 0:
        return None

    # use the largest detected face
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return x + w / 2


async def reformat_to_vertical(input_path, output_path, log_path):
    width, height = await _probe_dimensions(input_path)

    if width == TARGET_W and height == TARGET_H:
        await _run_ffmpeg(["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path], log_path)
        return output_path

    # Already taller than wide (e.g. 9:16-ish) -> centre-crop to exact 9:16
    if height > width:
        crop_w = int(height * 9 / 16)
        if crop_w <= width:
            face_x = _detect_face_x_offset(input_path, width, height)
            if face_x is not None:
                x_offset = int(min(max(face_x - crop_w / 2, 0), width - crop_w))
            else:
                x_offset = (width - crop_w) // 2
            vf = f"crop={crop_w}:{height}:{x_offset}:0,scale={TARGET_W}:{TARGET_H}"
            await _run_ffmpeg([
                "ffmpeg", "-y", "-i", input_path,
                "-vf", vf,
                "-c:v", "libx264", "-c:a", "aac",
                output_path,
            ], log_path)
            return output_path
        # fall through to blurred-background approach if width too small

    # Landscape (or crop not possible): blurred background + centred original
    filter_complex = (
        f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},gblur=sigma=20[bg];"
        f"[0:v]scale={TARGET_W}:-2:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
    )
    await _run_ffmpeg([
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[out]", "-map", "0:a?",
        "-c:v", "libx264", "-c:a", "aac",
        output_path,
    ], log_path)
    return output_path
