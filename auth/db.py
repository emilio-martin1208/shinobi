import sqlite3
import time

DB_PATH = "tokens.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            platform TEXT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            expires_at INTEGER
        )
    """)
    return conn


def save_token(platform, access_token, refresh_token=None, expires_at=None):
    conn = _connect()
    conn.execute(
        "INSERT INTO tokens (platform, access_token, refresh_token, expires_at) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(platform) DO UPDATE SET "
        "access_token=excluded.access_token, "
        "refresh_token=COALESCE(excluded.refresh_token, tokens.refresh_token), "
        "expires_at=excluded.expires_at",
        (platform, access_token, refresh_token, expires_at),
    )
    conn.commit()
    conn.close()


def get_token(platform):
    conn = _connect()
    row = conn.execute(
        "SELECT access_token, refresh_token, expires_at FROM tokens WHERE platform = ?",
        (platform,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"access_token": row[0], "refresh_token": row[1], "expires_at": row[2]}


def is_connected(platform):
    token = get_token(platform)
    return token is not None and token["access_token"] is not None


def is_expired(platform):
    token = get_token(platform)
    if token is None or token["expires_at"] is None:
        return False
    return time.time() >= token["expires_at"]
