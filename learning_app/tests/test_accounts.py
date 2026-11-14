import sqlite3

import pytest
from fastapi.testclient import TestClient

from learning_app.main import app


ORIGIN = {"origin": "http://testserver"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_DB_PATH", str(tmp_path / "learning.sqlite3"))
    with TestClient(app) as test_client:
        yield test_client


def register(test_client, email="learner@example.test", password="practice-safely-123"):
    return test_client.post("/api/auth/register", headers=ORIGIN,
                            json={"email": email, "password": password})


def test_account_session_csrf_progress_and_login(client, tmp_path):
    assert client.get("/api/progress").status_code == 401
    assert client.post("/api/auth/register", json={"email": "learner@example.test", "password": "practice-safely-123"}).status_code == 403

    created = register(client)
    assert created.status_code == 201
    csrf = created.json()["csrf_token"]
    cookie_header = created.headers["set-cookie"].lower()
    assert "httponly" in cookie_header and "samesite=lax" in cookie_header

    with sqlite3.connect(tmp_path / "learning.sqlite3") as db:
        password_hash, stored_session_hash = db.execute(
            "SELECT users.password_hash, sessions.token_hash FROM users JOIN sessions ON users.id = sessions.user_id"
        ).fetchone()
    assert password_hash.startswith("scrypt$") and password_hash != "practice-safely-123"
    assert stored_session_hash != client.cookies.get("learning_session")

    assert client.post("/api/progress/00-start-here", headers=ORIGIN,
                       json={"completed": True}).status_code == 403
    saved = client.post("/api/progress/00-start-here",
                        headers={**ORIGIN, "x-csrf-token": csrf}, json={"completed": True})
    assert saved.json() == {"slug": "00-start-here", "attempts": 1, "completed": True}
    retry = client.post("/api/progress/00-start-here",
                        headers={**ORIGIN, "x-csrf-token": csrf}, json={"completed": False})
    assert retry.json() == {"slug": "00-start-here", "attempts": 2, "completed": True}
    assert client.get("/api/progress").json()["activities"] == [
        {"slug": "00-start-here", "attempts": 2, "completed": True}
    ]

    assert client.post("/api/auth/logout", headers=ORIGIN).status_code == 403
    assert client.post("/api/auth/logout", headers={**ORIGIN, "x-csrf-token": csrf}).status_code == 204
    assert client.get("/api/auth/me").json() == {"user": None}
    assert client.post("/api/auth/login", headers=ORIGIN,
                       json={"email": "learner@example.test", "password": "incorrect-password"}).status_code == 401
    assert client.post("/api/auth/login", headers=ORIGIN,
                       json={"email": "learner@example.test", "password": "practice-safely-123"}).status_code == 200
    assert client.get("/api/progress").json()["activities"][0]["completed"] is True


def test_progress_is_private_to_the_signed_in_account(client):
    assert register(client).status_code == 201
    first_csrf = client.get("/api/auth/me").json()["csrf_token"]
    assert client.post("/api/progress/03-select", headers={**ORIGIN, "x-csrf-token": first_csrf},
                       json={"completed": True}).status_code == 200

    with TestClient(app) as another_learner:
        created = register(another_learner, "another@example.test")
        assert created.status_code == 201
        assert another_learner.get("/api/progress").json() == {"activities": []}
        csrf = created.json()["csrf_token"]
        assert another_learner.post("/api/progress/not-a-course", headers={**ORIGIN, "x-csrf-token": csrf},
                                    json={"completed": True}).status_code == 404

