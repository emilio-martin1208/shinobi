"""Reddit posting via PRAW.

PHASE 2 STUB: requires a connected Reddit account (see auth/oauth.py).
"""

from auth import db


async def post_to_reddit(video_path, title, body, subreddit):
    if not db.is_connected("reddit"):
        return {"success": False, "error": "Reddit account not connected"}

    # TODO: build praw.Reddit instance using stored refresh token
    # TODO: subreddit_obj = reddit.subreddit(subreddit)
    # TODO: submission = subreddit_obj.submit_video(title=title, video_path=video_path)
    # TODO: optionally post `body` as a top-level comment for context

    return {"success": False, "error": "Reddit posting not implemented yet"}
