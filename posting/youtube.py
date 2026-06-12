"""YouTube Data API v3 upload.

PHASE 2 STUB: requires a connected YouTube account (see auth/oauth.py).
"""

from auth import db


async def post_to_youtube(video_path, title, description, tags):
    if not db.is_connected("youtube"):
        return {"success": False, "error": "YouTube account not connected"}

    # TODO: build credentials from stored token, refresh if expired
    # TODO: use googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    # TODO: media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    # TODO: body = {
    #     "snippet": {
    #         "title": title,
    #         "description": description + "\n\n#Shorts",
    #         "tags": tags,
    #         "categoryId": "22",
    #     },
    #     "status": {"privacyStatus": "public"},
    # }
    # TODO: youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()

    return {"success": False, "error": "YouTube posting not implemented yet"}
