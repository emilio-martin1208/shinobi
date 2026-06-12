import json
import os

from anthropic import AsyncAnthropic

MODEL = "claude-sonnet-4-5-20250929"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


async def generate_metadata(clip_text, options=None):
    """Generate title, description, tags, and reddit framing for a clip.

    Returns: {title, description, tags, reddit_title, reddit_body}
    """
    options = options or {}
    tone = options.get("tone", "casual")
    audience = options.get("audience", "general audience")
    niche = options.get("niche", "")
    cta = options.get("cta", "")

    prompt = f"""Here is the transcript of a short video clip:

\"\"\"{clip_text}\"\"\"

Context:
- Tone: {tone}
- Target audience: {audience}
- Niche: {niche}
- Call to action: {cta}

Generate metadata for posting this clip to social platforms. Respond with ONLY a JSON object (no markdown, no commentary) in this exact shape:
{{
  "title": "<punchy title, under 60 chars, no clickbait, platform-native>",
  "description": "<2-3 sentences plus relevant hashtags>",
  "tags": ["<tag1>", "...", "<tag10>"],
  "reddit_title": "<question or discussion framing>",
  "reddit_body": "<2 paragraphs of context, ending with a mention that the clip is linked>"
}}
"""

    client = _get_client()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    return json.loads(text)
