"""Simple email/password account system backed by SQLite.

Not meant to be bank-grade — passwords are hashed with PBKDF2-SHA256 and
sessions are random tokens stored server-side with an expiry.
"""

import hashlib
import os
import secrets
import sqlite3
import time

DB_PATH = "users.db"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            bio TEXT NOT NULL DEFAULT '',
            username TEXT,
            avatar_url TEXT
        )
    """)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(profiles)").fetchall()]
    if "username" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN username TEXT")
    if "avatar_url" not in cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN avatar_url TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id TEXT NOT NULL,
            title TEXT,
            clip_count INTEGER,
            thumbnail_url TEXT,
            created_at INTEGER NOT NULL
        )
    """)
    project_cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
    if "trashed" not in project_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN trashed INTEGER NOT NULL DEFAULT 0")
    return conn


def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return digest.hex(), salt


def create_user(email, password):
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Invalid email address")
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    password_hash, salt = _hash_password(password)
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (email, password_hash, salt, int(time.time())),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("An account with that email already exists")
    finally:
        conn.close()


def verify_user(email, password):
    email = email.strip().lower()
    conn = _connect()
    row = conn.execute(
        "SELECT id, password_hash, salt FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    if row is None:
        raise ValueError("No account with that email")

    user_id, stored_hash, salt = row
    candidate_hash, _ = _hash_password(password, salt)
    if candidate_hash != stored_hash:
        raise ValueError("Incorrect password")
    return user_id


def get_user(user_id):
    conn = _connect()
    row = conn.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row[0], "email": row[1], "created_at": row[2]}


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    conn = _connect()
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now, now + SESSION_TTL_SECONDS),
    )
    conn.commit()
    conn.close()
    return token


def get_session_user(token):
    if not token:
        return None
    conn = _connect()
    row = conn.execute(
        "SELECT user_id, expires_at FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    user_id, expires_at = row
    if time.time() >= expires_at:
        delete_session(token)
        return None
    return get_user(user_id)


def delete_session(token):
    conn = _connect()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def get_bio(user_id):
    conn = _connect()
    row = conn.execute("SELECT bio FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row[0] if row else ""


def set_bio(user_id, bio):
    conn = _connect()
    conn.execute(
        "INSERT INTO profiles (user_id, bio) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET bio = excluded.bio",
        (user_id, bio),
    )
    conn.commit()
    conn.close()


def get_profile_extra(user_id):
    conn = _connect()
    row = conn.execute("SELECT username, avatar_url FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return {"username": None, "avatar_url": None}
    return {"username": row[0], "avatar_url": row[1]}


def set_username(user_id, username):
    username = (username or "").strip()
    if username:
        conn = _connect()
        existing = conn.execute(
            "SELECT user_id FROM profiles WHERE username = ? AND user_id != ?", (username, user_id)
        ).fetchone()
        if existing:
            conn.close()
            raise ValueError("That username is already taken")
        conn.execute(
            "INSERT INTO profiles (user_id, username) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username",
            (user_id, username),
        )
        conn.commit()
        conn.close()
    else:
        conn = _connect()
        conn.execute(
            "INSERT INTO profiles (user_id, username) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username",
            (user_id, None),
        )
        conn.commit()
        conn.close()


def set_avatar(user_id, avatar_url):
    conn = _connect()
    conn.execute(
        "INSERT INTO profiles (user_id, avatar_url) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET avatar_url = excluded.avatar_url",
        (user_id, avatar_url),
    )
    conn.commit()
    conn.close()


def add_project(user_id, job_id, title, clip_count, thumbnail_url):
    conn = _connect()
    conn.execute(
        "INSERT INTO projects (user_id, job_id, title, clip_count, thumbnail_url, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, job_id, title, clip_count, thumbnail_url, int(time.time())),
    )
    conn.commit()
    conn.close()


def list_projects(user_id):
    conn = _connect()
    rows = conn.execute(
        "SELECT job_id, title, clip_count, thumbnail_url, created_at FROM projects "
        "WHERE user_id = ? AND trashed = 0 ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [
        {"job_id": r[0], "title": r[1], "clip_count": r[2], "thumbnail_url": r[3], "created_at": r[4]}
        for r in rows
    ]


def list_trashed_projects(user_id):
    conn = _connect()
    rows = conn.execute(
        "SELECT job_id, title, clip_count, thumbnail_url, created_at FROM projects "
        "WHERE user_id = ? AND trashed = 1 ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [
        {"job_id": r[0], "title": r[1], "clip_count": r[2], "thumbnail_url": r[3], "created_at": r[4]}
        for r in rows
    ]


def get_project(user_id, job_id):
    conn = _connect()
    row = conn.execute(
        "SELECT job_id, title, clip_count, thumbnail_url, created_at, trashed FROM projects "
        "WHERE user_id = ? AND job_id = ?",
        (user_id, job_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"job_id": row[0], "title": row[1], "clip_count": row[2], "thumbnail_url": row[3],
            "created_at": row[4], "trashed": bool(row[5])}


def set_project_trashed(user_id, job_id, trashed):
    conn = _connect()
    cur = conn.execute(
        "UPDATE projects SET trashed = ? WHERE user_id = ? AND job_id = ?",
        (1 if trashed else 0, user_id, job_id),
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def delete_project(user_id, job_id):
    conn = _connect()
    cur = conn.execute(
        "DELETE FROM projects WHERE user_id = ? AND job_id = ?",
        (user_id, job_id),
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed
