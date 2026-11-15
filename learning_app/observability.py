"""Local request correlation and privacy-safe diagnostic events."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
import re
import time
import uuid

from fastapi import HTTPException


_request_id = ContextVar("learning_request_id", default=None)
_logger = logging.getLogger("learning_app.diagnostics")
_SAFE_LABEL = re.compile(r"[A-Za-z0-9_.:/{}-]{1,96}\Z")
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
_STATIC_API_PATHS = {
    "/api/health", "/api/course", "/api/progress", "/api/providers",
    "/api/assistant/models", "/api/assistant/respond", "/api/assistant/respond/stream",
    "/api/providers/local", "/api/providers/chatgpt/start",
    "/api/auth/me", "/api/auth/register", "/api/auth/login", "/api/auth/logout",
}
_PROGRESS_PATH = re.compile(r"/api/progress/[a-z0-9-]{1,80}\Z")
_PROVIDER_PATH = re.compile(r"/api/providers/(?:openai|anthropic|opencode|local|chatgpt)(?:/key)?\Z")


def current_request_id():
    return _request_id.get()


@contextmanager
def request_context(value):
    token = _request_id.set(value)
    try:
        yield
    finally:
        _request_id.reset(token)


def _label(value):
    return value if isinstance(value, str) and _SAFE_LABEL.fullmatch(value) else None


def diagnostic_event(name, outcome, *, stage=None, route=None, method=None,
                     provider=None, status_code=None, duration_ms=None,
                     first_body_ms=None, error_kind=None, model=None,
                     action=None, lesson=None):
    record = {"event": _label(name), "outcome": _label(outcome)}
    request_id = current_request_id()
    if request_id:
        record["request_id"] = request_id
    for key, value in (("stage", stage), ("route", route), ("method", method),
                       ("provider", provider), ("error_kind", error_kind),
                       ("model", model), ("action", action), ("lesson", lesson)):
        safe = _label(value)
        if safe:
            record[key] = safe
    if isinstance(status_code, int) and 100 <= status_code <= 599:
        record["status_code"] = status_code
    if isinstance(duration_ms, int) and duration_ms >= 0:
        record["duration_ms"] = duration_ms
    if isinstance(first_body_ms, int) and first_body_ms >= 0:
        record["first_body_ms"] = first_body_ms
    _logger.info("%s", json.dumps(record, separators=(",", ":")))


@contextmanager
def diagnostic_stage(stage, *, provider=None, model=None, action=None, lesson=None):
    started = time.perf_counter()
    labels = {"stage": stage, "provider": provider, "model": model, "action": action, "lesson": lesson}
    diagnostic_event("stage", "started", **labels)
    try:
        yield
    except HTTPException as error:
        diagnostic_event("stage", "error", **labels,
                         status_code=error.status_code,
                         duration_ms=round((time.perf_counter() - started) * 1000),
                         error_kind="http")
        raise
    except Exception:
        diagnostic_event("stage", "error", **labels,
                         status_code=500,
                         duration_ms=round((time.perf_counter() - started) * 1000),
                         error_kind="internal")
        raise
    else:
        diagnostic_event("stage", "success", **labels,
                         duration_ms=round((time.perf_counter() - started) * 1000))


class RequestDiagnosticsMiddleware:
    """Correlate API requests through their final streamed body without logging URLs or bodies."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = _request_id.set(request_id)
        started = time.perf_counter()
        method = scope.get("method", "")
        method = method if method in _METHODS else "OTHER"
        response_started = False
        response_status = 500
        first_body_ms = None
        completed = False

        def route_name():
            route = scope.get("route")
            path = getattr(route, "path", None)
            if isinstance(path, str) and path.startswith("/api/"):
                return path
            path = scope.get("path", "")
            if path in _STATIC_API_PATHS:
                return path
            if isinstance(path, str) and _PROGRESS_PATH.fullmatch(path):
                return "/api/progress/{lesson}"
            if isinstance(path, str) and _PROVIDER_PATH.fullmatch(path):
                return re.sub(r"/(?:openai|anthropic|opencode|local|chatgpt)(?=/|$)", "/{provider}", path)
            return "unmatched"

        async def send_diagnostic(message):
            nonlocal response_started, response_status, first_body_ms, completed
            message_type = message.get("type")
            if message_type == "http.response.start":
                response_started = True
                response_status = message["status"]
                headers = [(key, value) for key, value in message.get("headers", [])
                           if key.lower() != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            elif message_type == "http.response.body":
                body = message.get("body", b"")
                if body and first_body_ms is None:
                    first_body_ms = round((time.perf_counter() - started) * 1000)
                if not message.get("more_body", False) and not completed:
                    completed = True
                    outcome = "success" if response_status < 400 else (
                        "client_error" if response_status < 500 else "server_error")
                    diagnostic_event("http_request", outcome, route=route_name(), method=method,
                                     status_code=response_status,
                                     duration_ms=round((time.perf_counter() - started) * 1000),
                                     first_body_ms=first_body_ms)
            await send(message)

        diagnostic_event("http_request", "started", route="pending", method=method)
        try:
            await self.app(scope, receive, send_diagnostic)
        except Exception:
            if not completed:
                diagnostic_event("http_request", "error", route=route_name(), method=method,
                                 status_code=response_status if response_started else 500,
                                 duration_ms=round((time.perf_counter() - started) * 1000),
                                 first_body_ms=first_body_ms, error_kind="internal")
            if not response_started:
                body = b'{"detail":"Internal server error"}'
                await send({"type": "http.response.start", "status": 500, "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"x-request-id", request_id.encode("ascii")),
                ]})
                await send({"type": "http.response.body", "body": body})
            else:
                raise
        finally:
            _request_id.reset(token)
