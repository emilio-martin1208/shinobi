"""Twitter/X posting via Tweepy v4 (OAuth 2.0 PKCE).

PHASE 2 STUB: requires a connected Twitter account (see auth/oauth.py).
"""

from auth import db


async def post_to_twitter(video_path, text):
    if not db.is_connected("twitter"):
        return {"success": False, "error": "Twitter account not connected"}

    # TODO: build tweepy.Client with stored OAuth2 user token, refresh if expired
    # TODO: chunked media upload via tweepy.API (v1.1 media endpoint) for video
    # TODO: client.create_tweet(text=text, media_ids=[media_id])

    return {"success": False, "error": "Twitter posting not implemented yet"}
