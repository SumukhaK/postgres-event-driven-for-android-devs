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

from learning_app import providers
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

