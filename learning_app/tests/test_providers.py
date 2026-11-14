import base64
import hashlib
import json
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from learning_app import assistant, providers
from learning_app.credentials import decrypt
from learning_app.main import app


ORIGIN = {"origin": "http://127.0.0.1"}
PASSWORD = "a-safe-course-password-123"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_DB_PATH", str(tmp_path / "learning.sqlite3"))
    monkeypatch.setenv("LEARNING_CREDENTIAL_KEY", Fernet.generate_key().decode())
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as test_client:
        yield test_client, tmp_path / "learning.sqlite3"


def connect_user(client):
    response = client.post("/api/auth/register", headers=ORIGIN,
                           json={"email": "provider@example.test", "password": PASSWORD})
    assert response.status_code == 201
    return response.json()["csrf_token"]


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_token(private_key, claims, kid="key-one"):
    header = b64url(json.dumps({"alg": "RS256", "kid": kid}, separators=(",", ":")).encode())
    payload = b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{b64url(signature)}"


def jwk_for(public_key, kid="key-one"):
    numbers = public_key.public_numbers()
    return {
        "kid": kid, "kty": "RSA",
        "n": b64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": b64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }


def test_api_keys_are_validated_encrypted_and_disconnectable(client, monkeypatch):
    test_client, db_path = client
    csrf = connect_user(test_client)
    key = "opencode-test-personal-key-123456"
    checked = []
    monkeypatch.setattr(providers, "validate_api_key", lambda provider, value: checked.append((provider, value)))

    response = test_client.post("/api/providers/opencode/key", headers={**ORIGIN, "x-csrf-token": csrf},
                                json={"api_key": key})
    assert response.status_code == 200 and response.json()["connected"] is True
    assert checked == [("opencode", key)]
    with sqlite3.connect(db_path) as db:
        ciphertext = db.execute("SELECT encrypted_credentials FROM provider_connections WHERE provider='opencode'").fetchone()[0]
    assert key not in ciphertext
    assert decrypt(ciphertext) == {"api_key": key}
    assert test_client.get("/api/providers").json()["connections"][3]["connected"] is True

    disconnected = test_client.delete("/api/providers/opencode", headers={**ORIGIN, "x-csrf-token": csrf})
    assert disconnected.json() == {"provider": "opencode", "connected": False}
    assert test_client.get("/api/providers").json()["connections"][3]["connected"] is False


def test_missing_encryption_key_or_rejected_provider_key_is_not_saved(client, monkeypatch):
    test_client, db_path = client
    csrf = connect_user(test_client)
    monkeypatch.setenv("LEARNING_CREDENTIAL_KEY", "")
    unavailable = test_client.post("/api/providers/openai/key", headers={**ORIGIN, "x-csrf-token": csrf},
                                   json={"api_key": "openai-test-api-key-123456"})
    assert unavailable.status_code == 503
    assert test_client.get("/api/providers").json()["credential_storage_ready"] is False

    monkeypatch.setenv("LEARNING_CREDENTIAL_KEY", Fernet.generate_key().decode())
    def reject(provider, key):
        raise HTTPException(status_code=422, detail="The provider rejected this key.")
    monkeypatch.setattr(providers, "validate_api_key", reject)
    rejected = test_client.post("/api/providers/anthropic/key", headers={**ORIGIN, "x-csrf-token": csrf},
                                json={"api_key": "anthropic-test-api-key-123456"})
    assert rejected.status_code == 422
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT count(*) FROM provider_connections").fetchone()[0] == 0


def test_local_model_endpoint_is_probed_and_saved_encrypted(client, monkeypatch):
    test_client, db_path = client
    csrf = connect_user(test_client)
    endpoint = "http://host.docker.internal:11434/v1"
    key = "local-model-test-key-123"
    calls = []

    class Models:
        status_code = 200

        def json(self):
            return {"data": [{"id": "llama3.1:8b"}]}

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Models()

    monkeypatch.setattr(providers.httpx, "get", get)
    response = test_client.post("/api/providers/local", headers={**ORIGIN, "x-csrf-token": csrf},
                                json={"base_url": endpoint, "api_key": key})

    assert response.status_code == 200
    assert response.json() == {"provider": "local", "connected": True}
    assert calls[0][0] == f"{endpoint}/models"
    assert calls[0][1]["headers"]["Authorization"] == f"Bearer {key}"
    assert calls[0][1]["follow_redirects"] is False
    assert providers.load_credentials(1, "local") == {"api_base": endpoint, "api_key": key}
    with sqlite3.connect(db_path) as db:
        ciphertext = db.execute("SELECT encrypted_credentials FROM provider_connections WHERE provider='local'").fetchone()[0]
    assert key not in ciphertext
    connection = next(item for item in test_client.get("/api/providers").json()["connections"] if item["provider"] == "local")
    assert connection == {"provider": "local", "connected": True, "email": None, "plan_enabled": None, "api_base": endpoint}
    disconnected = test_client.delete("/api/providers/local", headers={**ORIGIN, "x-csrf-token": csrf})
    assert disconnected.json() == {"provider": "local", "connected": False}
    assert providers.load_credentials(1, "local") is None


@pytest.mark.parametrize("base_url", [
    "http://127.0.0.1:11434/v1",
    "http://localhost:11434/v1",
    "http://[::1]:11434/v1",
])
def test_local_model_base_url_allows_loopback(base_url):
    assert providers.validate_local_base_url(base_url) == base_url


@pytest.mark.parametrize("base_url", [
    "https://example.com/v1",
    "http://192.168.1.20:11434/v1",
    "http://169.254.169.254/latest/meta-data/",
    "http://user@127.0.0.1:11434/v1",
    "http://127.0.0.1:11434/v1?token=value",
])
def test_local_model_connection_rejects_nonlocal_or_malformed_urls(client, monkeypatch, base_url):
    test_client, _ = client
    csrf = connect_user(test_client)
    calls = []
    monkeypatch.setattr(providers.httpx, "get", lambda *args, **kwargs: calls.append(args[0]))

    response = test_client.post("/api/providers/local", headers={**ORIGIN, "x-csrf-token": csrf},
                                json={"base_url": base_url})

    assert response.status_code == 422
    assert calls == []


def test_local_model_connection_is_disabled_on_remote_app_host(client, monkeypatch):
    test_client, _ = client
    remote = TestClient(app, base_url="https://learn.example.test", client=("203.0.113.7", 45000))
    registered = remote.post("/api/auth/register", headers={"origin": "https://learn.example.test"}, json={
        "email": "remote-provider@example.test", "password": PASSWORD,
    })
    assert registered.status_code == 201
    calls = []
    monkeypatch.setattr(providers.httpx, "get", lambda *args, **kwargs: calls.append(args[0]))

    response = remote.post("/api/providers/local", headers={"origin": "https://learn.example.test",
                                                             "x-csrf-token": registered.json()["csrf_token"]},
                           json={"base_url": "http://host.docker.internal:11434/v1"})

    assert response.status_code == 403
    assert calls == []


def test_local_chatgpt_start_creates_pkce_state_and_one_time_encrypted_connection(client, monkeypatch):
    test_client, db_path = client
    csrf = connect_user(test_client)
    started = test_client.post("/api/providers/chatgpt/start", headers={**ORIGIN, "x-csrf-token": csrf})
    assert started.status_code == 200
    params = parse_qs(urlsplit(started.json()["authorization_url"]).query)
    assert params["client_id"] == ["dynamic_agent_client"]
    assert params["agent_name_hint"] == ["Postgres Lab Developer Studio"]
    assert params["scope"] == ["openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"]
    assert params["redirect_uri"][0].startswith("http://127.0.0.1:")
    assert urlsplit(params["redirect_uri"][0]).path == "/auth/callback"
    assert params["ext_agent_host_id"][0].startswith("urn:uuid:")
    state = params["state"][0]
    attempt = providers._pending[state]
    expected_challenge = b64url(hashlib.sha256(attempt["verifier"].encode()).digest())
    assert params["code_challenge"] == [expected_challenge]
    assert attempt["expires_at"] > int(time.time())

    class TokenResponse:
        status_code = 200
        def json(self):
            return {
                "id_token": "signed-id-token", "access_token": "chatgpt-access-token",
                "refresh_token": "chatgpt-refresh-token", "expires_in": 3600,
                "scope": "openid email resource.invoke chatgpt.tokens.use.direct",
            }

    monkeypatch.setattr(providers.httpx, "post", lambda *args, **kwargs: TokenResponse())
    monkeypatch.setattr(providers, "verify_openai_id_token", lambda token, client_id, nonce: {
        "sub": "chatgpt-subject", "email": "learner@example.test",
    })
    assert providers.complete_chatgpt_signin(state, "one-time-code", "oaiapp_test") is True
    assert providers.complete_chatgpt_signin(state, "one-time-code", "oaiapp_test") is False
    credentials = providers.load_credentials(1, "chatgpt")
    assert credentials["client_id"] == "oaiapp_test"
    assert credentials["refresh_token"] == "chatgpt-refresh-token"
    with sqlite3.connect(db_path) as db:
        ciphertext = db.execute("SELECT encrypted_credentials FROM provider_connections WHERE provider='chatgpt'").fetchone()[0]
    assert "chatgpt-refresh-token" not in ciphertext
    assert test_client.get("/api/providers").json()["connections"][0]["plan_enabled"] is True
    monkeypatch.setattr(providers, "revoke_chatgpt", lambda credentials: False)
    disconnected = test_client.delete("/api/providers/chatgpt", headers={**ORIGIN, "x-csrf-token": csrf})
    assert disconnected.json()["remote_revocation_confirmed"] is False
    assert providers.load_credentials(1, "chatgpt") is None


def test_chatgpt_identity_token_signature_and_claims_are_verified(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    claims = {"iss": providers.OPENAI_ISSUER, "aud": "oaiapp_test", "sub": "subject-1",
              "nonce": "nonce-1", "exp": now + 300, "iat": now, "nbf": now}

    class JwksResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"keys": [jwk_for(private_key.public_key())]}

    monkeypatch.setattr(providers.httpx, "get", lambda *args, **kwargs: JwksResponse())
    token = make_token(private_key, claims)
    assert providers.verify_openai_id_token(token, "oaiapp_test", "nonce-1")["sub"] == "subject-1"
    with pytest.raises(ValueError):
        providers.verify_openai_id_token(token, "oaiapp_test", "wrong-nonce")
    with pytest.raises(ValueError):
        providers.verify_openai_id_token(token, "another-client", "nonce-1")

    claims["exp"] = now - 1
    expired = make_token(private_key, claims)
    with pytest.raises(ValueError):
        providers.verify_openai_id_token(expired, "oaiapp_test", "nonce-1")


def test_chatgpt_plan_use_is_blocked_for_remote_hosts(tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNING_DB_PATH", str(tmp_path / "learning.sqlite3"))
    monkeypatch.setenv("LEARNING_CREDENTIAL_KEY", Fernet.generate_key().decode())
    remote = TestClient(app, base_url="https://learn.example.test", client=("203.0.113.10", 41000))
    created = remote.post("/api/auth/register", headers={"origin": "https://learn.example.test"},
                          json={"email": "remote@example.test", "password": PASSWORD})
    assert created.status_code == 201
    response = remote.post("/api/providers/chatgpt/start",
                           headers={"origin": "https://learn.example.test", "x-csrf-token": created.json()["csrf_token"]})
    assert response.status_code == 403


def test_assistant_lists_models_and_sends_only_selected_lesson_context(client, monkeypatch):
    test_client, _ = client
    csrf = connect_user(test_client)
    providers.save_credentials(1, "openai", {"api_key": "openai-test-api-key-123456"}, {})

    class ModelResponse:
        status_code = 200
        def json(self):
            return {"data": [{"id": "gpt-test-1"}, {"id": "invalid model id"}]}

    class Completion:
        status_code = 200
        def json(self):
            return {"output": [{"content": [{"type": "output_text", "text": "Use a join condition."}]}]}

    sent = {}
    monkeypatch.setattr(assistant.httpx, "get", lambda *args, **kwargs: ModelResponse())
    monkeypatch.setattr(assistant.httpx, "post", lambda url, **kwargs: sent.update(url=url, **kwargs) or Completion())
    models = test_client.get("/api/assistant/models?provider=openai")
    assert models.json() == {"models": [{"id": "gpt-test-1", "name": "gpt-test-1"}]}
    response = test_client.post("/api/assistant/respond", headers={**ORIGIN, "x-csrf-token": csrf}, json={
        "provider": "openai", "model": "gpt-test-1", "lesson_slug": "05-joins",
        "exercise_slug": "05-joins", "action": "ask", "message": "What joins these rows?",
    })
    assert response.status_code == 200 and response.json() == {"answer": "Use a join condition."}
    assert sent["url"] == f"{providers.OPENAI_RESOURCE}/responses"
    assert sent["json"]["model"] == "gpt-test-1" and sent["json"]["store"] is False
    assert sent["json"]["instructions"].startswith("You are the PostgreSQL course tutor.")
    assert "Current activity: Connect customers to orders" in sent["json"]["instructions"]
    assert sent["json"]["input"] == [{"role": "user", "content": "What joins these rows?"}]


@pytest.mark.parametrize("key", ["local-model-test-key-123", ""])
def test_local_assistant_discovers_models_and_sends_contextual_chat_completion(client, monkeypatch, key):
    test_client, _ = client
    csrf = connect_user(test_client)
    base = "http://host.docker.internal:11434/v1"
    credentials = {"api_base": base}
    if key:
        credentials["api_key"] = key
    providers.save_credentials(1, "local", credentials, {})
    calls = []

    class ModelResponse:
        status_code = 200
        def json(self):
            return {"data": [{"id": "llama3.1:8b"}, {"id": "invalid model id"}]}

    class Completion:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "A join connects related rows."}}]}

    def get(url, **kwargs):
        calls.append(("get", url, kwargs))
        return ModelResponse()

    def post(url, **kwargs):
        calls.append(("post", url, kwargs))
        return Completion()

    monkeypatch.setattr(assistant.httpx, "get", get)
    monkeypatch.setattr(assistant.httpx, "post", post)
    models = test_client.get("/api/assistant/models?provider=local")
    response = test_client.post("/api/assistant/respond", headers={**ORIGIN, "x-csrf-token": csrf}, json={
        "provider": "local", "model": "llama3.1:8b", "lesson_slug": "05-joins",
        "exercise_slug": "05-joins", "action": "ask", "message": "Why use a join?",
    })

    assert models.json() == {"models": [{"id": "llama3.1:8b", "name": "llama3.1:8b"}]}
    assert response.status_code == 200
    assert response.json() == {"answer": "A join connects related rows."}
    assert calls[0][0:2] == ("get", f"{base}/models")
    assert calls[1][0:2] == ("post", f"{base}/chat/completions")
    assert calls[1][2]["headers"].get("Authorization") == (f"Bearer {key}" if key else None)
    body = calls[1][2]["json"]
    assert body["model"] == "llama3.1:8b"
    assert body["messages"][0]["role"] == "system"
    assert "Current activity: Connect customers to orders" in body["messages"][0]["content"]
    assert body["messages"][-1] == {"role": "user", "content": "Why use a join?"}


@pytest.mark.parametrize("path,method", [
    ("/api/assistant/models?provider=local", "get"),
    ("/api/assistant/respond", "post"),
])
def test_local_assistant_is_blocked_on_remote_app_hosts(tmp_path, monkeypatch, path, method):
    monkeypatch.setenv("LEARNING_DB_PATH", str(tmp_path / "learning.sqlite3"))
    monkeypatch.setenv("LEARNING_CREDENTIAL_KEY", Fernet.generate_key().decode())
    remote = TestClient(app, base_url="https://learn.example.test", client=("203.0.113.10", 41000))
    created = remote.post("/api/auth/register", headers={"origin": "https://learn.example.test"}, json={
        "email": "remote-local-model@example.test", "password": PASSWORD,
    })
    providers.save_credentials(1, "local", {"api_base": "http://host.docker.internal:11434/v1"}, {})
    calls = []
    monkeypatch.setattr(assistant.httpx, "get", lambda *args, **kwargs: calls.append(args[0]))
    monkeypatch.setattr(assistant.httpx, "post", lambda *args, **kwargs: calls.append(args[0]))
    headers = {"origin": "https://learn.example.test", "x-csrf-token": created.json()["csrf_token"]}
    response = remote.get(path) if method == "get" else remote.post(path, headers=headers, json={
        "provider": "local", "model": "llama3.1:8b", "lesson_slug": "05-joins",
        "action": "ask", "message": "Why use a join?",
    })

    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize("status,expected", [(400, 422), (200, 502)])
def test_local_assistant_rejects_unknown_models_and_malformed_completion(client, monkeypatch, status, expected):
    test_client, _ = client
    csrf = connect_user(test_client)
    providers.save_credentials(1, "local", {"api_base": "http://127.0.0.1:11434/v1"}, {})

    class Response:
        status_code = status
        def json(self):
            return {} if status == 200 else {"error": "internal server detail"}

    monkeypatch.setattr(assistant.httpx, "post", lambda *args, **kwargs: Response())
    response = test_client.post("/api/assistant/respond", headers={**ORIGIN, "x-csrf-token": csrf}, json={
        "provider": "local", "model": "missing-model", "lesson_slug": "05-joins",
        "action": "ask", "message": "Why use a join?",
    })

    assert response.status_code == expected
    assert "internal server detail" not in response.text


def test_chatgpt_refreshes_and_requires_completed_sse_event(client, monkeypatch):
    test_client, _ = client
    csrf = connect_user(test_client)
    providers.save_credentials(1, "chatgpt", {
        "client_id": "oaiapp_test", "access_token": "expired-access", "refresh_token": "old-refresh",
        "expires_at": 1, "scopes": ["chatgpt.tokens.use.direct"], "email": "learner@example.test",
    }, {"email": "learner@example.test", "plan_enabled": True})
    refreshed = {}

    class TokenResponse:
        status_code = 200
        def json(self):
            return {"access_token": "fresh-access", "refresh_token": "rotated-refresh",
                    "expires_in": 3600, "scope": "chatgpt.tokens.use.direct"}

    class StreamResponse:
        status_code = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def iter_lines(self):
            yield 'data: {"type":"response.output_text.delta","delta":"A joined table "}'
            yield 'data: {"type":"response.output_text.delta","delta":"matches related rows."}'
            yield 'data: {"type":"response.completed","response":{}}'

    def refresh(url, **kwargs):
        refreshed.update(url=url, **kwargs)
        return TokenResponse()

    def stream(method, url, **kwargs):
        refreshed["inference"] = {"method": method, "url": url, **kwargs}
        return StreamResponse()

    monkeypatch.setattr(providers.httpx, "post", refresh)
    monkeypatch.setattr(assistant.httpx, "stream", stream)
    response = test_client.post("/api/assistant/respond", headers={**ORIGIN, "x-csrf-token": csrf}, json={
        "provider": "chatgpt", "model": "account-model", "lesson_slug": "05-joins",
        "exercise_slug": "05-joins", "action": "hint",
    })
    assert response.status_code == 200
    assert response.json()["answer"] == "A joined table matches related rows."
    assert refreshed["data"]["grant_type"] == "refresh_token"
    assert refreshed["inference"]["url"] == f"{providers.OPENAI_RESOURCE}/responses"
    assert refreshed["inference"]["json"]["store"] is False
    assert refreshed["inference"]["json"]["stream"] is True
    saved = providers.load_credentials(1, "chatgpt")
    assert saved["access_token"] == "fresh-access" and saved["refresh_token"] == "rotated-refresh"


def test_chatgpt_stream_without_completed_event_is_not_success(client, monkeypatch):
    test_client, _ = client
    csrf = connect_user(test_client)
    providers.save_credentials(1, "chatgpt", {
        "client_id": "oaiapp_test", "access_token": "valid-access", "refresh_token": "valid-refresh",
        "expires_at": int(time.time()) + 3600, "scopes": ["chatgpt.tokens.use.direct"],
    }, {"plan_enabled": True})

    class StreamResponse:
        status_code = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def iter_lines(self):
            yield 'data: {"type":"response.output_text.delta","delta":"partial"}'
            yield "data: [DONE]"

    monkeypatch.setattr(assistant.httpx, "stream", lambda *args, **kwargs: StreamResponse())
    response = test_client.post("/api/assistant/respond", headers={**ORIGIN, "x-csrf-token": csrf}, json={
        "provider": "chatgpt", "model": "account-model", "lesson_slug": "05-joins", "action": "ask",
        "message": "Why use a join?",
    })
    assert response.status_code == 502
    assert "before completing" in response.json()["detail"]


def test_assistant_provider_errors_are_sanitized(client, monkeypatch):
    test_client, _ = client
    csrf = connect_user(test_client)
    providers.save_credentials(1, "openai", {"api_key": "openai-test-api-key-123456"}, {})

    class Limited:
        status_code = 429
        text = "provider internals"

    monkeypatch.setattr(assistant.httpx, "post", lambda *args, **kwargs: Limited())
    response = test_client.post("/api/assistant/respond", headers={**ORIGIN, "x-csrf-token": csrf}, json={
        "provider": "openai", "model": "gpt-test-1", "lesson_slug": "05-joins", "action": "ask",
        "message": "Explain this join.",
    })
    assert response.status_code == 429
    assert "provider internals" not in response.text


def test_opencode_go_connection_uses_go_base_and_stable_session(client, monkeypatch):
    test_client, _ = client
    csrf = connect_user(test_client)
    go_base = "https://opencode.ai/inference/go"
    monkeypatch.setattr(providers, "validate_api_key", lambda provider, key: go_base)
    connected = test_client.post("/api/providers/opencode/key", headers={**ORIGIN, "x-csrf-token": csrf},
                                 json={"api_key": "opencode-go-test-key-123456"})
    assert connected.status_code == 200
    assert providers.load_credentials(1, "opencode")["api_base"] == go_base
    calls = []

    class Completion:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "A join matches related rows."}}]}

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Completion()

    monkeypatch.setattr(assistant.httpx, "post", post)
    response = test_client.post("/api/assistant/respond", headers={**ORIGIN, "x-csrf-token": csrf}, json={
        "provider": "opencode", "model": "gpt-test-1", "lesson_slug": "05-joins", "action": "ask",
        "message": "What does a join do?", "session_id": "ses_1234567890abcdef",
    })
    assert response.status_code == 200
    assert calls[0][0] == f"{go_base}/openai/v1/chat/completions"
    assert calls[0][1]["headers"]["x-opencode-session"] == "ses_1234567890abcdef"


def test_opencode_go_model_list_key_is_detected(monkeypatch):
    calls = []

    class Denied:
        status_code = 403
    class Allowed:
        status_code = 200
        def json(self):
            return {"data": [{"id": "go-model"}]}

    def get(url, **kwargs):
        calls.append(url)
        return Denied() if len(calls) == 1 else Allowed()

    monkeypatch.setattr(providers.httpx, "get", get)
    base = providers.validate_api_key("opencode", "opencode-go-test-key-123456")
    assert base == "https://opencode.ai/inference/go"
    assert calls == ["https://opencode.ai/inference/v1/models", "https://opencode.ai/inference/go/v1/models"]

