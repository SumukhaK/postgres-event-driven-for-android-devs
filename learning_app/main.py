"""Web entry point for the interactive learning experience."""
from pathlib import Path
import json
import os
import re
import sqlite3

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from learning_app.auth import check_same_origin, create_session, current_session, hash_password, verify_csrf, verify_password
from learning_app.storage import database


ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "src"
SITE = ROOT / "site"
DIST = Path(__file__).resolve().parent / "dist"
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$")
EXERCISES = json.loads((Path(__file__).parent / "static" / "exercises.json").read_text(encoding="utf-8"))
EXERCISE_SLUGS = {exercise["slug"] for exercise in EXERCISES}
DUMMY_PASSWORD_HASH = hash_password("not-a-real-account-password")

app = FastAPI(title="Postgres Lab", version="0.1.0")


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)


class ProgressUpdate(BaseModel):
    completed: bool = False


def course_catalog():
    """Read the course outline from its Markdown source files."""
    catalog = []
    for path in sorted(LESSONS.glob("*.md")):
        source = path.read_text(encoding="utf-8")
        match = FRONT_MATTER.match(source)
        if not match:
            continue
        metadata = dict(
            line.split(": ", 1)
            for line in match.group(1).splitlines()
            if ": " in line
        )
        catalog.append({"slug": path.stem, **metadata})
    return catalog


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/course")
def course():
    return {"lessons": course_catalog()}


def normalized_email(email):
    value = email.strip().lower()
    if not EMAIL.fullmatch(value):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    return value


@app.post("/api/auth/register", status_code=201)
def register(payload: Credentials, request: Request, response: Response):
    check_same_origin(request)
    email = normalized_email(payload.email)
    with database() as db:
        try:
            cursor = db.execute("INSERT INTO users(email, password_hash) VALUES (?, ?)",
                                (email, hash_password(payload.password)))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="An account already uses this email.")
        csrf = create_session(db, response, cursor.lastrowid)
    return {"user": {"email": email}, "csrf_token": csrf}


@app.post("/api/auth/login")
def login(payload: Credentials, request: Request, response: Response):
    check_same_origin(request)
    email = normalized_email(payload.email)
    with database() as db:
        row = db.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,)).fetchone()
        if not verify_password(payload.password, row["password_hash"] if row else DUMMY_PASSWORD_HASH):
            raise HTTPException(status_code=401, detail="Email or password did not match.")
        csrf = create_session(db, response, row["id"])
    return {"user": {"email": email}, "csrf_token": csrf}


@app.get("/api/auth/me")
def auth_me(request: Request):
    session = current_session(request, required=False)
    if not session:
        return {"user": None}
    return {"user": {"email": session.email}, "csrf_token": session.csrf_token}


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    session = current_session(request)
    verify_csrf(request, session)
    with database() as db:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (session.token_hash,))
    response.delete_cookie("learning_session", path="/", httponly=True, samesite="lax",
                           secure=os.environ.get("LEARNING_COOKIE_SECURE", "0") == "1")
    response.status_code = 204
    return response


@app.get("/api/progress")
def get_progress(request: Request):
    session = current_session(request)
    with database() as db:
        rows = db.execute("SELECT lesson_slug, attempts, completed_at FROM progress WHERE user_id = ?",
                          (session.user_id,)).fetchall()
    return {"activities": [
        {"slug": row["lesson_slug"], "attempts": row["attempts"], "completed": row["completed_at"] is not None}
        for row in rows
    ]}


@app.post("/api/progress/{slug}")
def update_progress(slug: str, payload: ProgressUpdate, request: Request):
    session = current_session(request)
    verify_csrf(request, session)
    if slug not in EXERCISE_SLUGS:
        raise HTTPException(status_code=404, detail="That course activity was not found.")
    with database() as db:
        db.execute("""
            INSERT INTO progress(user_id, lesson_slug, attempts, completed_at)
            VALUES (?, ?, 1, CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END)
            ON CONFLICT(user_id, lesson_slug) DO UPDATE SET
              attempts = progress.attempts + 1,
              completed_at = CASE WHEN excluded.completed_at IS NOT NULL
                THEN COALESCE(progress.completed_at, excluded.completed_at)
                ELSE progress.completed_at END,
              updated_at = CURRENT_TIMESTAMP
        """, (session.user_id, slug, payload.completed))
        row = db.execute("SELECT attempts, completed_at FROM progress WHERE user_id = ? AND lesson_slug = ?",
                         (session.user_id, slug)).fetchone()
    return {"slug": slug, "attempts": row["attempts"], "completed": row["completed_at"] is not None}


@app.get("/")
@app.get("/playground")
def playground():
    return FileResponse(DIST / "index.html")


app.mount("/playground-assets", StaticFiles(directory=DIST), name="playground-assets")
app.mount("/course", StaticFiles(directory=SITE, html=True), name="course")
