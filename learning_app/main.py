"""Web entry point for the interactive learning experience."""
from pathlib import Path
import re

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "src"
SITE = ROOT / "site"
DIST = Path(__file__).resolve().parent / "dist"
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)

app = FastAPI(title="Postgres Lab", version="0.1.0")


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


@app.get("/")
@app.get("/playground")
def playground():
    return FileResponse(DIST / "index.html")


app.mount("/playground-assets", StaticFiles(directory=DIST), name="playground-assets")
app.mount("/course", StaticFiles(directory=SITE, html=True), name="course")
