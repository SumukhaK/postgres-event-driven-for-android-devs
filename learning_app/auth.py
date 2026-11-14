"""Session, password, and same-origin request helpers."""
from dataclasses import dataclass
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Response

from learning_app.storage import database


COOKIE_NAME = "learning_session"
SESSION_TTL = 14 * 24 * 60 * 60


@dataclass
class LearnerSession:
    user_id: int
    email: str
    token_hash: str
    csrf_token: str


def hash_token(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password):
    salt = os.urandom(16)
    n, r, p = 2**14, 8, 1
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=64 * 1024 * 1024)
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def verify_password(password, encoded):
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$", 5)
        n, r, p = int(n), int(r), int(p)
        if algorithm != "scrypt" or n < 2**12 or n > 2**16 or n & (n - 1) or r < 1 or r > 16 or p < 1 or p > 4:
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=n, r=r, p=p, dklen=32, maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def check_same_origin(request: Request):
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(status_code=403, detail="A same-origin request is required.")
    actual, expected = urlsplit(origin), urlsplit(str(request.base_url))
    if (actual.scheme.lower(), actual.netloc.lower()) != (expected.scheme.lower(), expected.netloc.lower()):
        raise HTTPException(status_code=403, detail="A same-origin request is required.")


def current_session(request: Request, *, required=True):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        if required:
            raise HTTPException(status_code=401, detail="Sign in to continue.")
        return None
    token_hash = hash_token(token)
    with database() as db:
        row = db.execute("""
            SELECT users.id, users.email, sessions.token_hash, sessions.csrf_token, sessions.expires_at
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
        """, (token_hash,)).fetchone()
        if row and row["expires_at"] <= int(time.time()):
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            row = None
    if not row:
        if required:
            raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.")
        return None
    return LearnerSession(row["id"], row["email"], row["token_hash"], row["csrf_token"])


def verify_csrf(request: Request, session: LearnerSession):
    check_same_origin(request)
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not hmac.compare_digest(supplied, session.csrf_token):
        raise HTTPException(status_code=403, detail="Refresh the page and try again.")


def create_session(db: sqlite3.Connection, response: Response, user_id: int):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    token_hash = hash_token(token)
    expires_at = int(time.time()) + SESSION_TTL
    db.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
    db.execute("INSERT INTO sessions(token_hash, csrf_token, user_id, expires_at) VALUES (?, ?, ?, ?)",
               (token_hash, csrf, user_id, expires_at))
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_TTL, httponly=True,
        secure=os.environ.get("LEARNING_COOKIE_SECURE", "0") == "1",
        samesite="lax", path="/",
    )
    return csrf
