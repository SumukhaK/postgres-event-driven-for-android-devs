"""Provider OAuth, encrypted API-key, and local endpoint connections."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import ipaddress
import json
import logging
import os
import secrets
import threading
import time
import uuid
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from learning_app.auth import current_session, verify_csrf
from learning_app.credentials import CredentialEncryptionUnavailable, cipher, decrypt, encrypt
from learning_app.storage import database


router = APIRouter()
API_PROVIDERS = {"openai", "anthropic", "opencode"}
LOCAL_PROVIDER = "local"
COPILOT_PROVIDER = "copilot"
ALL_PROVIDERS = API_PROVIDERS | {"chatgpt", COPILOT_PROVIDER, LOCAL_PROVIDER}
PROVIDER_CATALOG = (
    {"id": "chatgpt", "name": "ChatGPT", "protocol": "openai_responses",
     "billing": "ChatGPT plan usage", "auth_methods": [{"id": "account_oauth", "label": "Continue with ChatGPT"}]},
    {"id": "openai", "name": "OpenAI API", "protocol": "openai_responses",
     "billing": "OpenAI API account", "auth_methods": [{"id": "api_key", "label": "Connect API key"}]},
    {"id": "anthropic", "name": "Claude API", "protocol": "anthropic_messages",
     "billing": "Claude Console credits or billing", "auth_methods": [{"id": "api_key", "label": "Connect Console API key"}]},
    {"id": "opencode", "name": "OpenCode Console", "protocol": "opencode_chat",
     "billing": "OpenCode Console plan or budget", "auth_methods": [{"id": "api_key", "label": "Connect API key"}]},
    {"id": COPILOT_PROVIDER, "name": "GitHub Copilot", "protocol": "github_copilot_sdk",
     "billing": "Your GitHub Copilot subscription", "auth_methods": [{"id": "oauth_device", "label": "Sign in with GitHub Copilot"}]},
    {"id": LOCAL_PROVIDER, "name": "Local model", "protocol": "openai_compatible_or_native_ollama",
     "billing": "Your device or model host", "auth_methods": [{"id": "local_endpoint", "label": "Connect local endpoint"}]},
)
LOCAL_MODEL_HOSTS = {"localhost", "host.docker.internal"}
OPENAI_ISSUER = "https://auth.openai.com"
OPENAI_AUTHORIZE = f"{OPENAI_ISSUER}/api/accounts/authorize"
OPENAI_TOKEN = f"{OPENAI_ISSUER}/api/accounts/oauth/token"
OPENAI_RESOURCE = "https://api.openai.com/v1"
OPENAI_MODEL_URL = f"{OPENAI_RESOURCE}/models"
HOST_SETTING = "chatgpt_ext_agent_host_id"
CLIENT_SETTING_PREFIX = "chatgpt_client_id:"
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
_pending = {}
_pending_lock = threading.Lock()
_pending_copilot = {}
_pending_copilot_lock = threading.Lock()
_callback_server = None
_logger = logging.getLogger(__name__)


class ApiKeyPayload(BaseModel):
    api_key: str = Field(min_length=8, max_length=2048)


class LocalEndpointPayload(BaseModel):
    base_url: str = Field(min_length=8, max_length=512)
    api_key: str = Field(default="", max_length=2048)


class CopilotPollPayload(BaseModel):
    state: str = Field(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


def encryption_ready():
    try:
        cipher()
        return True
    except CredentialEncryptionUnavailable:
        return False


def save_credentials(user_id, provider, credentials, metadata):
    sealed = encrypt(credentials)
    with database() as db:
        db.execute("""
            INSERT INTO provider_connections(user_id, provider, encrypted_credentials, metadata)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, provider) DO UPDATE SET
              encrypted_credentials = excluded.encrypted_credentials,
              metadata = excluded.metadata,
              connected_at = CURRENT_TIMESTAMP
        """, (user_id, provider, sealed, json.dumps(metadata, separators=(",", ":"))))


def load_credentials(user_id, provider):
    with database() as db:
        row = db.execute("SELECT encrypted_credentials FROM provider_connections WHERE user_id = ? AND provider = ?",
                          (user_id, provider)).fetchone()
    return decrypt(row["encrypted_credentials"]) if row else None


def chatgpt_access_token(user_id, credentials):
    if "chatgpt.tokens.use.direct" not in credentials.get("scopes", []):
        raise HTTPException(status_code=403, detail="Enable ChatGPT plan use in AI connections first.")
    if credentials.get("access_token") and credentials.get("expires_at", 0) > int(time.time()) + 60:
        return credentials["access_token"]
    if not credentials.get("refresh_token"):
        raise HTTPException(status_code=401, detail="Reconnect ChatGPT to continue.")
    try:
        response = httpx.post(OPENAI_TOKEN, data={
            "grant_type": "refresh_token", "client_id": credentials["client_id"],
            "refresh_token": credentials["refresh_token"], "resource": OPENAI_RESOURCE,
        }, headers={"accept": "application/json"}, timeout=15)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="ChatGPT is temporarily unavailable. Try again.")
    try:
        tokens = response.json()
    except ValueError:
        tokens = {}
    if not isinstance(tokens, dict):
        tokens = {}
    if response.status_code != 200:
        if tokens.get("error") in {"invalid_grant", "invalid_refresh_token", "token_expired", "refresh_token_expired", "refresh_token_invalidated", "refresh_token_reused"}:
            with database() as db:
                db.execute("DELETE FROM provider_connections WHERE user_id = ? AND provider = 'chatgpt'", (user_id,))
            raise HTTPException(status_code=401, detail="Reconnect ChatGPT to continue.")
        raise HTTPException(status_code=503, detail="ChatGPT could not refresh your connection. Try again.")
    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="ChatGPT returned an incomplete refresh response.")
    granted_scopes = tokens.get("scope") or " ".join(credentials.get("scopes", []))
    scopes = set(granted_scopes.split())
    if "chatgpt.tokens.use.direct" not in scopes:
        raise HTTPException(status_code=403, detail="Enable ChatGPT plan use in AI connections first.")
    try:
        expires_in = max(1, int(tokens.get("expires_in", 3600)))
    except (TypeError, ValueError):
        expires_in = 3600
    refreshed = {**credentials, **tokens, "scopes": sorted(scopes), "expires_at": int(time.time()) + expires_in}
    save_credentials(user_id, "chatgpt", refreshed,
                     {"email": refreshed.get("email"), "plan_enabled": True})
    return access_token


def validate_api_key(provider, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    if provider == "openai":
        url = OPENAI_MODEL_URL
    elif provider == "anthropic":
        url = "https://api.anthropic.com/v1/models"
        headers = {"x-api-key": api_key, "anthropic-version": "2026-10-21"}
    elif provider == "opencode":
        unreachable = False
        for base in ("https://opencode.ai/inference", "https://opencode.ai/inference/go"):
            try:
                response = httpx.get(f"{base}/v1/models", headers=headers, timeout=10)
            except httpx.HTTPError:
                unreachable = True
                continue
            if response.status_code == 200:
                try:
                    models = response.json().get("data")
                except (ValueError, AttributeError):
                    models = None
                if not isinstance(models, list):
                    raise HTTPException(status_code=502, detail="The provider returned an unexpected response.")
                return base
            if response.status_code not in (401, 403):
                raise HTTPException(status_code=502, detail="The provider could not validate this key right now.")
        if unreachable:
            raise HTTPException(status_code=502, detail="The provider could not be reached. Try again.")
        raise HTTPException(status_code=422, detail="The provider rejected this key or the account does not allow API access.")
    else:
        raise HTTPException(status_code=404, detail="That provider is not supported.")
    try:
        response = httpx.get(url, headers=headers, timeout=10)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="The provider could not be reached. Try again.")
    if response.status_code in (401, 403):
        raise HTTPException(status_code=422, detail="The provider rejected this key or the account does not allow API access.")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="The provider could not validate this key right now.")
    try:
        models = response.json().get("data")
    except (ValueError, AttributeError):
        models = None
    if not isinstance(models, list):
        raise HTTPException(status_code=502, detail="The provider returned an unexpected response.")


def validate_local_base_url(value):
    try:
        parsed = urlsplit(value.strip())
        parsed.port
    except (AttributeError, ValueError):
        raise HTTPException(status_code=422, detail="Enter a valid local model URL.")
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = False
    if (parsed.scheme.lower() not in {"http", "https"} or not host
            or (host not in LOCAL_MODEL_HOSTS and not is_loopback)
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment):
        raise HTTPException(status_code=422, detail="Use a loopback or host.docker.internal URL without credentials, query, or fragment.")
    path = parsed.path.rstrip("/")
    segments = path.strip("/").split("/") if path else []
    if any(segment in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._~-]+", segment) for segment in segments):
        raise HTTPException(status_code=422, detail="The local model URL path is invalid.")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, "", "")).rstrip("/")


def validate_local_model_endpoint(base_url, api_key):
    base_url = validate_local_base_url(base_url)
    headers = {"accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = httpx.get(f"{base_url}/models", headers=headers, timeout=10,
                             follow_redirects=False, trust_env=False)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="The local model server did not respond in time.")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="The local model server could not be reached.")
    if response.status_code in (401, 403):
        raise HTTPException(status_code=422, detail="The local model server rejected this API key.")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="The local server did not return an OpenAI-compatible model list.")
    try:
        models = response.json().get("data")
    except (ValueError, AttributeError):
        models = None
    if not isinstance(models, list):
        raise HTTPException(status_code=502, detail="The local server returned an unexpected model list.")
    return base_url


def is_ollama_endpoint(base_url, api_key=""):
    parsed = urlsplit(base_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    root = urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")
    headers = {"accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = httpx.get(f"{root}/api/version", headers=headers, timeout=3,
                             follow_redirects=False, trust_env=False)
        body = response.json() if response.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        return False
    return isinstance(body, dict) and isinstance(body.get("version"), str)


def _loopback(value):
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return value.lower() == "localhost"


def is_local_runtime(request):
    host = urlsplit(str(request.base_url)).hostname or ""
    client = request.client.host if request.client else ""
    return _loopback(host) and _loopback(client)


def copilot_client_id():
    return os.getenv("GITHUB_COPILOT_CLIENT_ID", "").strip()


def start_copilot_device_flow(user_id):
    client_id = copilot_client_id()
    if not client_id:
        raise HTTPException(status_code=503, detail="Configure GITHUB_COPILOT_CLIENT_ID to enable GitHub Copilot sign-in.")
    try:
        response = httpx.post(GITHUB_DEVICE_CODE_URL, data={
            "client_id": client_id, "scope": "read:user offline_access",
        }, headers={"accept": "application/json"}, timeout=15)
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="GitHub sign-in could not be started. Try again.")
    if response.status_code != 200 or not isinstance(data, dict):
        raise HTTPException(status_code=503, detail="GitHub sign-in could not be started. Check the OAuth app configuration.")
    if data.get("error") == "device_flow_disabled":
        raise HTTPException(status_code=503, detail="Enable device flow in the GitHub OAuth app settings, then try again.")
    try:
        expires_in = min(1800, max(60, int(data["expires_in"])))
        interval = min(60, max(1, int(data["interval"])))
        device_code = data["device_code"]
        user_code = data["user_code"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="GitHub returned an incomplete sign-in response.")
    if (not isinstance(device_code, str) or len(device_code) > 256
            or not isinstance(user_code, str) or not re.fullmatch(r"[A-Z0-9-]{4,16}", user_code)
            or data.get("verification_uri") != "https://github.com/login/device"):
        raise HTTPException(status_code=502, detail="GitHub returned an invalid sign-in response.")
    state = secrets.token_urlsafe(32)
    now = int(time.time())
    with _pending_copilot_lock:
        for expired, attempt in list(_pending_copilot.items()):
            if attempt["expires_at"] <= now or attempt["user_id"] == user_id:
                _pending_copilot.pop(expired, None)
        _pending_copilot[state] = {
            "user_id": user_id, "client_id": client_id, "device_code": device_code, "interval": interval,
            "last_poll": 0, "expires_at": now + expires_in,
        }
    return {"state": state, "user_code": user_code, "verification_uri": data["verification_uri"],
            "interval": interval, "expires_in": expires_in}


def poll_copilot_device_flow(user_id, state):
    now = int(time.time())
    with _pending_copilot_lock:
        attempt = _pending_copilot.get(state)
        if not attempt or attempt["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="This GitHub sign-in has expired. Start again.")
        if attempt["expires_at"] <= now:
            _pending_copilot.pop(state, None)
            return {"status": "expired"}
        wait = attempt["interval"] - (now - attempt["last_poll"])
        if wait > 0:
            return {"status": "pending", "retry_after": wait}
        attempt["last_poll"] = now
        device_code = attempt["device_code"]
        client_id = attempt["client_id"]
        interval = attempt["interval"]
    try:
        response = httpx.post(GITHUB_TOKEN_URL, data={
            "client_id": client_id, "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }, headers={"accept": "application/json"}, timeout=15)
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="GitHub sign-in could not be checked. Try again.")
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="GitHub returned an unexpected sign-in response.")
    error = data.get("error")
    if error == "authorization_pending":
        return {"status": "pending", "retry_after": interval}
    if error == "slow_down":
        with _pending_copilot_lock:
            if state in _pending_copilot:
                _pending_copilot[state]["interval"] = min(60, interval + 5)
                interval = _pending_copilot[state]["interval"]
        return {"status": "pending", "retry_after": interval}
    if error in {"access_denied", "expired_token"}:
        with _pending_copilot_lock:
            _pending_copilot.pop(state, None)
        return {"status": "denied" if error == "access_denied" else "expired"}
    access_token = data.get("access_token")
    if response.status_code != 200 or not isinstance(access_token, str) or not access_token.startswith(("gho_", "ghu_")):
        _logger.warning("GitHub Copilot token exchange failed (%s)", error or "unexpected response")
        with _pending_copilot_lock:
            _pending_copilot.pop(state, None)
        return {"status": "error", "message": "GitHub could not complete sign-in. Check that device flow is enabled."}
    try:
        profile = httpx.get(GITHUB_USER_URL, headers={"Authorization": f"Bearer {access_token}",
                               "accept": "application/vnd.github+json"}, timeout=15)
        account = profile.json()
    except (httpx.HTTPError, ValueError):
        with _pending_copilot_lock:
            _pending_copilot.pop(state, None)
        raise HTTPException(status_code=503, detail="GitHub authorized the connection, but the account could not be verified.")
    if profile.status_code != 200 or not isinstance(account, dict) or not isinstance(account.get("login"), str):
        with _pending_copilot_lock:
            _pending_copilot.pop(state, None)
        raise HTTPException(status_code=502, detail="GitHub authorized the connection, but the account could not be verified.")
    try:
        if not isinstance(data.get("refresh_token"), str) or not data["refresh_token"].startswith("ghr_"):
            raise ValueError("missing refresh token")
        expires_at = now + max(1, int(data["expires_in"]))
        refresh_expires_at = now + max(1, int(data["refresh_token_expires_in"]))
    except (TypeError, ValueError):
        with _pending_copilot_lock:
            _pending_copilot.pop(state, None)
        raise HTTPException(status_code=502, detail="GitHub returned an invalid token lifetime.")
    credentials = {
        "client_id": client_id, "login": account["login"], "access_token": access_token,
        "refresh_token": data.get("refresh_token"), "expires_at": expires_at,
        "refresh_expires_at": refresh_expires_at,
    }
    try:
        save_credentials(user_id, COPILOT_PROVIDER, credentials,
                         {"login": account["login"], "credential_type": "github_oauth"})
    finally:
        with _pending_copilot_lock:
            _pending_copilot.pop(state, None)
    return {"status": "connected", "login": account["login"]}


def copilot_access_token(user_id, credentials):
    now = int(time.time())
    expires_at = credentials.get("expires_at")
    if not expires_at or expires_at > now + 60:
        return credentials["access_token"]
    refresh_token = credentials.get("refresh_token")
    if not refresh_token or (credentials.get("refresh_expires_at") or 0) <= now:
        with database() as db:
            db.execute("DELETE FROM provider_connections WHERE user_id = ? AND provider = ?", (user_id, COPILOT_PROVIDER))
        raise HTTPException(status_code=401, detail="Reconnect GitHub Copilot to continue.")
    try:
        response = httpx.post(GITHUB_TOKEN_URL, data={
            "client_id": credentials.get("client_id") or copilot_client_id(),
            "grant_type": "refresh_token", "refresh_token": refresh_token,
        }, headers={"accept": "application/json"}, timeout=15)
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="GitHub Copilot sign-in could not be refreshed. Try again.")
    if response.status_code != 200:
        if isinstance(data, dict) and data.get("error") in {
            "invalid_grant", "invalid_refresh_token", "token_expired", "refresh_token_expired",
            "refresh_token_invalidated", "refresh_token_reused",
        }:
            with database() as db:
                db.execute("DELETE FROM provider_connections WHERE user_id = ? AND provider = ?", (user_id, COPILOT_PROVIDER))
            raise HTTPException(status_code=401, detail="Reconnect GitHub Copilot to continue.")
        raise HTTPException(status_code=503, detail="GitHub Copilot could not refresh your connection. Try again.")
    if not isinstance(data, dict) or not isinstance(data.get("access_token"), str) or not data["access_token"].startswith(("gho_", "ghu_")):
        raise HTTPException(status_code=502, detail="GitHub returned an invalid refresh response.")
    try:
        if not isinstance(data.get("refresh_token"), str) or not data["refresh_token"].startswith("ghr_"):
            raise ValueError("missing refresh token")
        refreshed = {**credentials, **data}
        refreshed["expires_at"] = now + int(data["expires_in"])
        refreshed["refresh_expires_at"] = now + int(data["refresh_token_expires_in"])
    except (TypeError, ValueError, KeyError):
        raise HTTPException(status_code=502, detail="GitHub returned an invalid token lifetime.")
    save_credentials(user_id, COPILOT_PROVIDER, refreshed,
                     {"login": credentials.get("login"), "credential_type": "github_oauth"})
    return refreshed["access_token"]


def is_local_app_url(request):
    return _loopback(urlsplit(str(request.base_url)).hostname or "")


def host_id():
    with database() as db:
        row = db.execute("SELECT setting_value FROM runtime_settings WHERE setting_key = ?", (HOST_SETTING,)).fetchone()
        if row:
            return row["setting_value"]
        value = f"urn:uuid:{uuid.uuid4()}"
        db.execute("INSERT INTO runtime_settings(setting_key, setting_value) VALUES (?, ?)", (HOST_SETTING, value))
        return value


def registration_client_id(user_id):
    with database() as db:
        row = db.execute("SELECT setting_value FROM runtime_settings WHERE setting_key = ?",
                         (f"{CLIENT_SETTING_PREFIX}{user_id}",)).fetchone()
    return row["setting_value"] if row else None


def save_registration_client_id(user_id, client_id):
    with database() as db:
        db.execute("INSERT INTO runtime_settings(setting_key, setting_value) VALUES (?, ?) "
                   "ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
                   (f"{CLIENT_SETTING_PREFIX}{user_id}", client_id))


def callback_uri():
    global _callback_server
    if _callback_server is None:
        try:
            _callback_server = ThreadingHTTPServer(("127.0.0.1", 0), ChatGPTCallback)
            _callback_server.daemon_threads = True
            threading.Thread(target=_callback_server.serve_forever, daemon=True, name="chatgpt-oauth-callback").start()
        except OSError as error:
            raise HTTPException(status_code=503, detail="A local sign-in callback could not start.") from error
    return f"http://127.0.0.1:{_callback_server.server_port}/auth/callback"


def begin_chatgpt_signin(user_id, app_url, existing=None):
    redirect_uri = callback_uri()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode("ascii")
    issued_client = existing.get("client_id") if existing else None
    params = {
        "client_id": issued_client or "dynamic_agent_client",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct",
        "resource": OPENAI_RESOURCE,
        "state": state,
        "nonce": nonce,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "ext_agent_host_id": host_id(),
    }
    if existing:
        if existing.get("id_token"):
            params["id_token_hint"] = existing["id_token"]
        if existing.get("email"):
            params["login_hint"] = existing["email"]
    else:
        params["agent_name_hint"] = "Postgres Lab Developer Studio"
    with _pending_lock:
        now = int(time.time())
        for expired in [key for key, item in _pending.items() if item["expires_at"] < now]:
            _pending.pop(expired, None)
        _pending[state] = {
            "user_id": user_id, "state": state, "nonce": nonce, "verifier": verifier,
            "redirect_uri": redirect_uri, "client_id": issued_client,
            "app_url": app_url.rstrip("/"), "host_id": params["ext_agent_host_id"],
            "expires_at": now + 600,
        }
    return f"{OPENAI_AUTHORIZE}?{urlencode(params)}"


def _b64url_json(segment):
    return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))


def verify_openai_id_token(token, client_id, nonce):
    try:
        encoded_header, encoded_claims, encoded_signature = token.split(".")
        header = _b64url_json(encoded_header)
        claims = _b64url_json(encoded_claims)
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise ValueError("Unsupported signing key.")
        response = httpx.get(f"{OPENAI_ISSUER}/.well-known/jwks.json", timeout=10)
        response.raise_for_status()
        key = next(item for item in response.json()["keys"] if item.get("kid") == header["kid"] and item.get("kty") == "RSA")
        modulus = int.from_bytes(base64.urlsafe_b64decode(key["n"] + "=" * (-len(key["n"]) % 4)), "big")
        exponent = int.from_bytes(base64.urlsafe_b64decode(key["e"] + "=" * (-len(key["e"]) % 4)), "big")
        public_key = rsa.RSAPublicNumbers(exponent, modulus).public_key()
        if public_key.key_size < 2048:
            raise ValueError("Signing key is too small.")
        signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        now = int(time.time())
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if claims.get("iss") != OPENAI_ISSUER or client_id not in audiences:
            raise ValueError("Issuer or audience did not match.")
        if not isinstance(claims.get("exp"), int) or claims["exp"] <= now:
            raise ValueError("Identity token expired.")
        if claims.get("nbf", 0) > now or claims.get("nonce") != nonce or not claims.get("sub"):
            raise ValueError("Identity token claims did not match.")
        return claims
    except (httpx.HTTPError, KeyError, StopIteration, TypeError, ValueError, InvalidSignature, json.JSONDecodeError) as error:
        _logger.warning("ChatGPT identity token validation failed (%s)", type(error).__name__)
        raise ValueError("ChatGPT sign-in could not be verified.") from error


def complete_chatgpt_signin(state, code, issued_client_id, error=None):
    with _pending_lock:
        attempt = _pending.pop(state, None) if state else None
    if not attempt or attempt["expires_at"] < int(time.time()) or attempt["state"] != state:
        _logger.warning("ChatGPT sign-in failed: missing or expired OAuth state")
        return False
    if error or not code:
        _logger.warning("ChatGPT sign-in was denied or returned no authorization code")
        return False
    client_id = attempt["client_id"] or issued_client_id
    if not client_id or client_id == "dynamic_agent_client":
        _logger.warning("ChatGPT sign-in failed: authorization response had no issued client ID")
        return False
    if attempt["client_id"] and issued_client_id and issued_client_id != attempt["client_id"]:
        _logger.warning("ChatGPT sign-in failed: callback client ID did not match pending connection")
        return False
    if issued_client_id:
        save_registration_client_id(attempt["user_id"], client_id)
    try:
        response = httpx.post(OPENAI_TOKEN, data={
            "grant_type": "authorization_code", "client_id": client_id, "code": code,
            "code_verifier": attempt["verifier"], "redirect_uri": attempt["redirect_uri"],
            "resource": OPENAI_RESOURCE,
        }, headers={"accept": "application/json"}, timeout=15)
        if response.status_code != 200:
            try:
                payload = response.json()
                oauth_error = payload.get("error")
                description = payload.get("error_description", "")
            except (ValueError, AttributeError):
                oauth_error = None
                description = ""
            _logger.warning("ChatGPT token exchange failed: HTTP %s (%s; %s)", response.status_code,
                            oauth_error or "no error code", description[:160])
            return False
        tokens = response.json()
        identity_token = tokens.get("id_token")
        if not identity_token:
            _logger.warning("ChatGPT token response did not include an identity token")
            return False
        identity = verify_openai_id_token(identity_token, client_id, attempt["nonce"])
        scopes = set(tokens.get("scope", "").split())
        plan_enabled = "chatgpt.tokens.use.direct" in scopes and bool(tokens.get("access_token"))
        credentials = {
            "client_id": client_id, "host_id": attempt["host_id"], "email": identity.get("email"),
            "subject": identity["sub"], "id_token": identity_token,
            "access_token": tokens.get("access_token"), "refresh_token": tokens.get("refresh_token"),
            "scopes": sorted(scopes), "expires_at": int(time.time()) + int(tokens.get("expires_in", 0)),
        }
        save_credentials(attempt["user_id"], "chatgpt", credentials,
                         {"email": identity.get("email"), "plan_enabled": plan_enabled})
        return True
    except (httpx.HTTPError, ValueError, KeyError, TypeError, CredentialEncryptionUnavailable) as error:
        _logger.warning("ChatGPT sign-in failed during token handling (%s)", type(error).__name__)
        return False


class ChatGPTCallback(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path != "/auth/callback":
            self.send_error(404)
            return
        query = parse_qs(parsed.query)
        state = query.get("state", [None])[0]
        with _pending_lock:
            attempt = _pending.get(state)
        success = complete_chatgpt_signin(
            state, query.get("code", [None])[0],
            query.get("client_id", [None])[0], query.get("error", [None])[0],
        )
        app_url = attempt["app_url"] if attempt else "http://127.0.0.1:8000"
        destination = urljoin(app_url + "/", f"playground?chatgpt={'connected' if success else 'error'}")
        self.send_response(302)
        self.send_header("Location", destination)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def log_message(self, format, *args):
        return


def revoke_chatgpt(credentials):
    refresh_token = credentials.get("refresh_token")
    if not refresh_token:
        return False
    try:
        discovery = httpx.get(f"{OPENAI_ISSUER}/.well-known/openid-configuration", timeout=10)
        endpoint = discovery.json()["revocation_endpoint"]
        response = httpx.post(endpoint, data={
            "token": refresh_token, "token_type_hint": "refresh_token", "client_id": credentials["client_id"],
        }, timeout=10)
        return response.status_code == 200
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return False


@router.get("")
def provider_status(request: Request):
    session = current_session(request)
    with database() as db:
        rows = db.execute("SELECT provider, metadata FROM provider_connections WHERE user_id = ?", (session.user_id,)).fetchall()
    saved = {row["provider"]: json.loads(row["metadata"]) for row in rows}
    return {
        "credential_storage_ready": encryption_ready(),
        "chatgpt_local_available": is_local_runtime(request) and encryption_ready(),
        "copilot_local_available": is_local_runtime(request) and encryption_ready() and bool(copilot_client_id()),
        "catalog": [
            {**provider, "available": (
                provider["id"] not in {"chatgpt", COPILOT_PROVIDER}
                or (is_local_runtime(request) and encryption_ready()
                    and (provider["id"] != COPILOT_PROVIDER or bool(copilot_client_id())))
            )}
            for provider in PROVIDER_CATALOG
        ],
        "connections": [
            {"provider": provider, "connected": provider in saved,
             "email": saved.get(provider, {}).get("email"),
             "plan_enabled": bool(saved.get(provider, {}).get("plan_enabled")) if provider == "chatgpt" else None,
             **({"login": saved[provider].get("login")} if provider == COPILOT_PROVIDER and provider in saved else {}),
             **({"api_base": saved[provider].get("api_base")} if provider == LOCAL_PROVIDER and provider in saved else {})}
            for provider in ("chatgpt", "openai", "anthropic", "opencode", COPILOT_PROVIDER, LOCAL_PROVIDER)
        ],
    }


@router.post("/local")
def connect_local_model(payload: LocalEndpointPayload, request: Request):
    session = current_session(request)
    verify_csrf(request, session)
    if not is_local_app_url(request):
        raise HTTPException(status_code=403, detail="Local models can only be connected from the local app.")
    if not encryption_ready():
        raise HTTPException(status_code=503, detail="Secure credential storage is not configured on this server.")
    api_key = payload.api_key.strip()
    base_url = validate_local_model_endpoint(payload.base_url, api_key)
    credentials = {"api_base": base_url}
    if api_key:
        credentials["api_key"] = api_key
    if is_ollama_endpoint(base_url, api_key):
        credentials["runtime"] = "ollama"
    save_credentials(session.user_id, LOCAL_PROVIDER, credentials,
                     {"credential_type": "openai_compatible", "api_base": base_url})
    return {"provider": LOCAL_PROVIDER, "connected": True}


@router.post("/{provider}/key")
def connect_api_key(provider: str, payload: ApiKeyPayload, request: Request):
    session = current_session(request)
    verify_csrf(request, session)
    if provider not in API_PROVIDERS:
        raise HTTPException(status_code=404, detail="That API-key provider is not supported.")
    if not encryption_ready():
        raise HTTPException(status_code=503, detail="Secure credential storage is not configured on this server.")
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=422, detail="Enter an API key.")
    api_base = validate_api_key(provider, api_key)
    credentials = {"api_key": api_key}
    if api_base:
        credentials["api_base"] = api_base
    save_credentials(session.user_id, provider, credentials, {"credential_type": "api_key"})
    return {"provider": provider, "connected": True}


@router.post("/chatgpt/start")
def start_chatgpt(request: Request):
    session = current_session(request)
    verify_csrf(request, session)
    if not is_local_runtime(request):
        raise HTTPException(status_code=403, detail="ChatGPT plan sign-in is available only in the local app.")
    if not encryption_ready():
        raise HTTPException(status_code=503, detail="Secure credential storage is not configured on this server.")
    existing = load_credentials(session.user_id, "chatgpt")
    if not existing:
        client_id = registration_client_id(session.user_id)
        if client_id:
            existing = {"client_id": client_id}
    return {"authorization_url": begin_chatgpt_signin(session.user_id, str(request.base_url), existing)}


@router.post("/copilot/start")
def start_copilot(request: Request):
    session = current_session(request)
    verify_csrf(request, session)
    if not is_local_runtime(request):
        raise HTTPException(status_code=403, detail="GitHub Copilot sign-in is available only in the local app.")
    if not encryption_ready():
        raise HTTPException(status_code=503, detail="Secure credential storage is not configured on this server.")
    return start_copilot_device_flow(session.user_id)


@router.post("/copilot/poll")
def poll_copilot(payload: CopilotPollPayload, request: Request):
    session = current_session(request)
    verify_csrf(request, session)
    if not is_local_runtime(request):
        raise HTTPException(status_code=403, detail="GitHub Copilot sign-in is available only in the local app.")
    return poll_copilot_device_flow(session.user_id, payload.state)


@router.post("/copilot/cancel")
def cancel_copilot(payload: CopilotPollPayload, request: Request):
    session = current_session(request)
    verify_csrf(request, session)
    with _pending_copilot_lock:
        attempt = _pending_copilot.get(payload.state)
        if attempt and attempt["user_id"] == session.user_id:
            _pending_copilot.pop(payload.state, None)
    return {"cancelled": True}


@router.delete("/{provider}")
def disconnect_provider(provider: str, request: Request):
    session = current_session(request)
    verify_csrf(request, session)
    if provider not in ALL_PROVIDERS:
        raise HTTPException(status_code=404, detail="That provider is not supported.")
    revoked = None
    if provider == "chatgpt":
        try:
            credentials = load_credentials(session.user_id, provider)
            revoked = revoke_chatgpt(credentials) if credentials else False
        except CredentialEncryptionUnavailable:
            revoked = False
    with database() as db:
        db.execute("DELETE FROM provider_connections WHERE user_id = ? AND provider = ?", (session.user_id, provider))
    result = {"provider": provider, "connected": False}
    if provider == "chatgpt":
        result["remote_revocation_confirmed"] = revoked
    return result
