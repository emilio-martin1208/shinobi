"""OAuth flow handlers for YouTube, Twitter, and Reddit.

PHASE 2 STUB: routes and structure are wired into main.py, but the actual
OAuth exchanges need real client IDs/secrets in .env to function. Each
function below is a placeholder that documents the intended flow.
"""

from fastapi.responses import HTMLResponse

from . import db


def _popup_close_html(message):
    return HTMLResponse(f"""
    <html><body>
    <p>{message}</p>
    <script>
      if (window.opener) {{
        window.opener.postMessage({{ type: 'oauth_complete' }}, '*');
      }}
      window.close();
    </script>
    </body></html>
    """)


# ---- YouTube ----

async def youtube_auth_start():
    """TODO: build Google OAuth URL using google-auth-oauthlib with
    scope https://www.googleapis.com/auth/youtube.upload and redirect."""
    raise NotImplementedError("YouTube OAuth not configured. Set YOUTUBE_CLIENT_ID/SECRET in .env")


async def youtube_auth_callback(code):
    """TODO: exchange code for tokens, store via db.save_token('youtube', ...)."""
    raise NotImplementedError("YouTube OAuth not configured.")


# ---- Twitter ----

async def twitter_auth_start():
    """TODO: build Twitter OAuth2 PKCE URL with scopes
    tweet.write media.write users.read offline.access."""
    raise NotImplementedError("Twitter OAuth not configured. Set TWITTER_CLIENT_ID/SECRET in .env")


async def twitter_auth_callback(code):
    """TODO: exchange code for tokens, store via db.save_token('twitter', ...)."""
    raise NotImplementedError("Twitter OAuth not configured.")


# ---- Reddit ----

async def reddit_auth_start():
    """TODO: build Reddit OAuth2 URL via PRAW with scope 'submit identity'."""
    raise NotImplementedError("Reddit OAuth not configured. Set REDDIT_CLIENT_ID/SECRET in .env")


async def reddit_auth_callback(code):
    """TODO: exchange code for tokens, store via db.save_token('reddit', ...)."""
    raise NotImplementedError("Reddit OAuth not configured.")


def auth_status():
    return {
        "youtube": db.is_connected("youtube"),
        "twitter": db.is_connected("twitter"),
        "reddit": db.is_connected("reddit"),
    }
