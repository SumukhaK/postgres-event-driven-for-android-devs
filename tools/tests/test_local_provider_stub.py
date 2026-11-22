"""The deterministic stub must speak the protocol the app expects, without a live model."""
import json
import threading
from http.server import ThreadingHTTPServer

import httpx
import pytest

from tools import local_provider_stub


@pytest.fixture
def stub_base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), local_provider_stub.Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()
    server.server_close()


def test_stub_lists_only_the_scripted_models(stub_base_url):
    response = httpx.get(f"{stub_base_url}/models", timeout=5)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert ids == ["stub-clear-sql", "stub-sql-warning", "stub-no-sql", "stub-fail-midstream"]


def test_stub_streams_a_complete_chat_answer(stub_base_url):
    with httpx.stream("POST", f"{stub_base_url}/chat/completions", timeout=10,
                      json={"model": "stub-clear-sql", "messages": []}) as response:
        assert response.status_code == 200
        text, completed = "", False
        for line in response.iter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                completed = completed or line == "data: [DONE]"
                continue
            event = json.loads(line[6:])
            choice = event["choices"][0]
            text += choice["delta"].get("content", "")
            if choice.get("finish_reason") == "stop":
                completed = True
    assert completed
    assert "SELECT name, price FROM products" in text
    assert "is_active" in text


def test_stub_sql_warning_reply_references_an_unknown_column(stub_base_url):
    with httpx.stream("POST", f"{stub_base_url}/chat/completions", timeout=10,
                      json={"model": "stub-sql-warning", "messages": []}) as response:
        text = ""
        for line in response.iter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                text += json.loads(line[6:])["choices"][0]["delta"].get("content", "")
    assert "SELECT name, active FROM products" in text


def test_stub_midstream_model_drops_the_transport(stub_base_url):
    received = []
    with pytest.raises(httpx.HTTPError):
        with httpx.stream("POST", f"{stub_base_url}/chat/completions", timeout=10,
                          json={"model": "stub-fail-midstream", "messages": []}) as response:
            for line in response.iter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    received.append(json.loads(line[6:])["choices"][0]["delta"].get("content", ""))
    assert received == ["The answer starts here. ", "Only part of the text arrives, "]
