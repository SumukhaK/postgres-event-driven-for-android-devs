"""Answer-reference and nudge-gentleness boundaries for tutor context, across every exercise.

T26 found two repeatable quality failures: a misleading EXPLAIN explanation that
implied full-table scans are inherently slow, and an overly prescriptive nudge that
supplied exact conditions, sorting, and projection. These tests hold the context
builder to the guidance boundaries for every course exercise.
"""
import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from learning_app import assistant, providers
from learning_app.main import app


ORIGIN = {"origin": "http://127.0.0.1"}
PASSWORD = "a-safe-course-password-123"
EXERCISES = json.loads((Path(assistant.__file__).parent / "static" / "exercises.json").read_text(encoding="utf-8"))


class Completion:
    status_code = 200

    def json(self):
        return {"output": [{"content": [{"type": "output_text", "text": "A grounded tutor answer."}]}]}


@pytest.fixture
def tutor(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_DB_PATH", str(tmp_path / "learning.sqlite3"))
    monkeypatch.setenv("LEARNING_CREDENTIAL_KEY", Fernet.generate_key().decode())
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as test_client:
        response = test_client.post("/api/auth/register", headers=ORIGIN,
                                    json={"email": "guidance@example.test", "password": PASSWORD})
        assert response.status_code == 201
        providers.save_credentials(1, "openai", {"api_key": "openai-test-api-key-123456"}, {})
        yield test_client, response.json()["csrf_token"]


def send(test_client, monkeypatch, csrf, action, lesson):
    captured = {}
    monkeypatch.setattr(assistant.httpx, "post",
                        lambda url, **kwargs: captured.update(url=url, **kwargs) or Completion())
    response = test_client.post("/api/assistant/respond", headers={**ORIGIN, "x-csrf-token": csrf}, json={
        "provider": "openai", "model": "gpt-test-1", "lesson_slug": lesson,
        "exercise_slug": lesson, "action": action, "message": "Which way should I start?",
    })
    assert response.status_code == 200
    return captured["json"]["instructions"], captured["json"]["input"]


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda exercise: exercise["slug"])
def test_hint_and_nudge_context_stays_free_of_answer_references(tutor, monkeypatch, exercise):
    test_client, csrf = tutor
    for action in ("nudge", "hint"):
        instructions, _ = send(test_client, monkeypatch, csrf, action, exercise["slug"])
        assert exercise["help"]["solution"] not in instructions
        assert exercise["help"]["explanation"] not in instructions
        assert "Verified answer reference" not in instructions
        assert "Verified explanation reference" not in instructions


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda exercise: exercise["slug"])
def test_explanation_context_is_grounded_without_the_worked_query(tutor, monkeypatch, exercise):
    test_client, csrf = tutor
    instructions, _ = send(test_client, monkeypatch, csrf, "explanation", exercise["slug"])
    assert exercise["help"]["explanation"] in instructions
    assert exercise["help"]["solution"] not in instructions


@pytest.mark.parametrize("exercise", EXERCISES, ids=lambda exercise: exercise["slug"])
def test_ask_and_solution_keep_the_verified_answer_reference(tutor, monkeypatch, exercise):
    test_client, csrf = tutor
    for action in ("ask", "solution"):
        instructions, _ = send(test_client, monkeypatch, csrf, action, exercise["slug"])
        assert "Verified answer reference" in instructions
        assert exercise["help"]["solution"] in instructions
        assert exercise["help"]["explanation"] in instructions


def test_explain_explanation_is_grounded_in_table_size_and_selectivity(tutor, monkeypatch):
    """The T26 14B failure: answers implied full-table scans are inherently slow."""
    test_client, csrf = tutor
    instructions, _ = send(test_client, monkeypatch, csrf, "explanation", "07-indexes-explain")
    assert "An index is not automatically faster" in instructions
    assert "sequential scan" in instructions


def test_nudge_request_points_at_the_step_kind_not_exact_identifiers(tutor, monkeypatch):
    test_client, csrf = tutor
    instructions, input_messages = send(test_client, monkeypatch, csrf, "nudge", "03-select")
    assert "not the exact columns, values, or clauses" in input_messages[-1]["content"]
    assert "describe the kind of step to try" in instructions
    assert "hints may name specific identifiers" in instructions
