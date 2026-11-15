import json
import logging
import re
import sqlite3

from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient

from learning_app import assistant, providers
from learning_app.main import app


ORIGIN = {"origin": "http://testserver"}
PASSWORD = "safe-diagnostics-test-password"


def diagnostic_records(caplog):
    return [json.loads(record.message) for record in caplog.records
            if record.name == "learning_app.diagnostics"]


def test_request_id_is_generated_and_lifecycle_logs_exclude_query(caplog):
    caplog.set_level(logging.INFO, logger="learning_app.diagnostics")
    with TestClient(app) as client:
        response = client.get("/api/course?token=do-not-log-this",
                              headers={"x-request-id": "caller-controlled-id"})

    request_id = response.headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)
    assert request_id != "caller-controlled-id"
    records = diagnostic_records(caplog)
    assert [record["outcome"] for record in records] == ["started", "success"]
    assert all(record["request_id"] == request_id for record in records)
    assert records[-1]["route"] == "/api/course"
    assert records[-1]["status_code"] == 200
    assert records[-1]["duration_ms"] >= 0
    assert "do-not-log-this" not in caplog.text
    assert "caller-controlled-id" not in caplog.text


def test_account_and_provider_logs_do_not_include_credentials_or_identity(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("LEARNING_DB_PATH", str(tmp_path / "learning.sqlite3"))
    monkeypatch.setenv("LEARNING_CREDENTIAL_KEY", Fernet.generate_key().decode())
    caplog.set_level(logging.INFO, logger="learning_app.diagnostics")
    email = "private-learner@example.test"
    key = "secret-provider-key-never-log"
    with TestClient(app) as client:
        registered = client.post("/api/auth/register", headers=ORIGIN,
                                 json={"email": email, "password": PASSWORD})
        assert registered.status_code == 201
        csrf = registered.json()["csrf_token"]

        def reject_key(provider, submitted_key):
            assert provider == "opencode"
            assert submitted_key == key
            raise HTTPException(status_code=422, detail="Rejected")

        monkeypatch.setattr(providers, "validate_api_key", reject_key)
        rejected = client.post("/api/providers/opencode/key",
                               headers={**ORIGIN, "x-csrf-token": csrf},
                               json={"api_key": key})

    assert rejected.status_code == 422
    with sqlite3.connect(tmp_path / "learning.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM provider_connections").fetchone()[0] == 0
    records = diagnostic_records(caplog)
    stage_records = [record for record in records if record.get("stage") == "provider_key_validation"]
    assert [record["outcome"] for record in stage_records] == ["started", "error"]
    assert stage_records[-1]["provider"] == "opencode"
    assert stage_records[-1]["status_code"] == 422
    assert email not in caplog.text
    assert PASSWORD not in caplog.text
    assert key not in caplog.text


def test_assistant_stages_are_correlated_without_logging_question_or_answer(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("LEARNING_DB_PATH", str(tmp_path / "learning.sqlite3"))
    monkeypatch.setenv("LEARNING_CREDENTIAL_KEY", Fernet.generate_key().decode())
    caplog.set_level(logging.INFO, logger="learning_app.diagnostics")
    question = "Which exact column should I use?"
    answer = "Use is_active."
    with TestClient(app) as client:
        registered = client.post("/api/auth/register", headers=ORIGIN,
                                 json={"email": "assistant-stage@example.test", "password": PASSWORD})
        csrf = registered.json()["csrf_token"]
        providers.save_credentials(1, "openai", {"api_key": "assistant-stage-test-key"}, {})
        monkeypatch.setattr(assistant, "provider_response", lambda *args, **kwargs: answer)
        response = client.post("/api/assistant/respond", headers={**ORIGIN, "x-csrf-token": csrf}, json={
            "provider": "openai", "model": "gpt-test", "lesson_slug": "03-select",
            "action": "ask", "message": question,
        })

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    records = [record for record in diagnostic_records(caplog) if record.get("stage")]
    assert [record["stage"] for record in records] == [
        "lesson_context", "lesson_context", "provider_inference", "provider_inference",
    ]
    assert all(record["request_id"] == request_id for record in records)
    request_records = [record for record in diagnostic_records(caplog)
                       if record.get("request_id") == request_id and record["event"] == "http_request"]
    assert request_records[-1]["route"] == "/api/assistant/respond"
    assert all(record["model"] == "gpt-test" and record["action"] == "ask"
               and record["lesson"] == "03-select" for record in records)
    assert question not in caplog.text and answer not in caplog.text
