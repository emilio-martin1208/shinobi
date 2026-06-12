import asyncio
import functools

import whisper

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model


def _synthesize_words(segments):
    """Evenly distribute word timings across each segment's duration.

    Used as a fallback when Whisper's word-level DTW alignment fails
    (a known issue on segments containing silence)."""
    words = []
    for segment in segments:
        tokens = segment["text"].split()
        if not tokens:
            continue
        seg_start = segment["start"]
        seg_end = segment["end"]
        duration = max(seg_end - seg_start, 0.01)
        step = duration / len(tokens)
        for i, token in enumerate(tokens):
            words.append({
                "word": token.strip(),
                "start": seg_start + i * step,
                "end": seg_start + (i + 1) * step,
            })
    return words


def _run_transcribe(video_path):
    model = _get_model()

    try:
        result = model.transcribe(video_path, word_timestamps=True)
        words = []
        for segment in result.get("segments", []):
            for w in segment.get("words", []):
                words.append(
                    {
                        "word": w["word"].strip(),
                        "start": w["start"],
                        "end": w["end"],
                    }
                )
        if not words:
            raise RuntimeError("no word timestamps produced")
    except Exception:
        # Fall back to segment-level transcription with synthesized word timings
        result = model.transcribe(video_path, word_timestamps=False)
        words = _synthesize_words(result.get("segments", []))

    return {
        "text": result.get("text", "").strip(),
        "words": words,
    }


async def transcribe(video_path):
    """Run Whisper transcription in a thread pool so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    func = functools.partial(_run_transcribe, video_path)
    return await loop.run_in_executor(None, func)
