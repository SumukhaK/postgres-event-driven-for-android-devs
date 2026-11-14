from fastapi.testclient import TestClient

from learning_app.main import app


client = TestClient(app)


def test_health_check():
    assert client.get("/api/health").json() == {"ok": True}


def test_course_catalog_comes_from_all_markdown_lessons():
    lessons = client.get("/api/course").json()["lessons"]

    assert len(lessons) == 13
    assert lessons[0]["slug"] == "00-start-here"
    assert lessons[-1]["slug"] == "A2-portfolio-projects"


def test_app_and_course_pages_are_served():
    assert "Developer Studio" in client.get("/").text
    playground = client.get("/playground")
    assert playground.status_code == 200
    assert "Developer Studio" in playground.text
    assert "/playground-assets/index.js" in playground.text
    assert client.get("/playground-assets/index.js").status_code == 200
    assert "Start here" in client.get("/course/00-start-here.html").text
