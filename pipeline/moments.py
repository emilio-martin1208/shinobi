import json
import os

from anthropic import AsyncAnthropic

MODEL = "claude-sonnet-4-5-20250929"

# Map Shinobi's branded model picker names to real Claude models.
MODEL_MAP = {
    "katana-5.5": "claude-sonnet-4-5-20250929",
    "wakizashi-4.5": "claude-sonnet-4-5-20250929",
    "kunai-4.5": "claude-3-5-haiku-20241022",
    "shuriken-3.5": "claude-3-5-haiku-20241022",
}


def _resolve_model(options):
    return MODEL_MAP.get((options or {}).get("model"), MODEL)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _build_transcript_with_timestamps(words):
    """Group words into ~5s lines with timestamps for the prompt."""
    lines = []
    current = []
    current_start = None
    for w in words:
        if current_start is None:
            current_start = w["start"]
        current.append(w["word"])
        if w["end"] - current_start >= 5:
            lines.append(f"[{current_start:.1f}-{w['end']:.1f}] {' '.join(current)}")
            current = []
            current_start = None
    if current:
        lines.append(f"[{current_start:.1f}-{words[-1]['end']:.1f}] {' '.join(current)}")
    return "\n".join(lines)


async def find_moments(words, options=None):
    """Ask Claude to identify the top 3 standalone 45-60s segments.

    Returns: [{start_sec, end_sec, reason, hook_score}]
    """
    options = options or {}
    num_clips = options.get("num_clips", 3)
    instructions = (options.get("instructions") or "").strip()
    transcript_with_ts = _build_transcript_with_timestamps(words)
    total_duration = words[-1]["end"] if words else 0

    instructions_block = ""
    if instructions:
        instructions_block = f"""
The user has given you these specific instructions for selecting clips. Follow them closely,
even if it means overriding the default scoring criteria below (e.g. if they ask you to make
sure a specific moment, topic, or line is included, prioritize that):
\"\"\"{instructions}\"\"\"
"""

    prompt = f"""You are given a timestamped transcript of a video (total duration ~{total_duration:.1f}s).

Transcript (format: [start-end] text):
{transcript_with_ts}

Identify the {num_clips} best standalone segments that would work as short-form clips (e.g. for YouTube Shorts / TikTok / Reels).
{instructions_block}
Scoring criteria:
- Strong hook in the first 5 seconds
- High information density
- Works without prior context (standalone)
- Emotionally engaging or surprising

Each segment MUST be between 45 and 60 seconds long, and must align with timestamps present in the transcript.

Respond with ONLY a JSON array (no markdown, no commentary), with exactly {num_clips} objects in this shape:
[{{"start_sec": <float>, "end_sec": <float>, "reason": "<short explanation>", "hook_score": <int 1-10>}}]
"""

    client = _get_client()
    response = await client.messages.create(
        model=_resolve_model(options),
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    moments = json.loads(text)

    for m in moments:
        m["start_sec"] = max(0.0, float(m["start_sec"]))
        m["end_sec"] = min(float(total_duration), float(m["end_sec"]))
        if m["end_sec"] - m["start_sec"] < 45:
            m["end_sec"] = min(float(total_duration), m["start_sec"] + 45)

    return moments
