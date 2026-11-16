"""Resource and failure guards for the opt-in benchmark (no real model calls)."""
import json

import httpx
import pytest

from tools import evaluate_t26 as trial


class FakeOllama:
    def __init__(self, resident=None):
        self.resident = resident or []
        self.posts = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, path):
        data = {"/api/tags": {"models": [{"name": "qwen2.5:7b-instruct"}]},
                "/api/ps": {"models": self.resident}, "/api/version": {"version": "test"}}[path]
        return httpx.Response(200, json=data, request=httpx.Request("GET", "http://localhost" + path))

    def post(self, path, json):
        self.posts.append(json)
        return httpx.Response(200, json={}, request=httpx.Request("POST", "http://localhost" + path))

    def stream(self, *args, **kwargs):
        raise httpx.ReadTimeout("simulated inference failure")


@pytest.mark.parametrize("free,resident", [(3 * 1024**3, []), (8 * 1024**3, [{"name": "another-model"}])])
def test_preflight_never_loads_or_unloads_when_resources_unavailable(monkeypatch, tmp_path, free, resident):
    fake = FakeOllama(resident)
    monkeypatch.setattr(trial.httpx, "Client", lambda **kwargs: fake)
    monkeypatch.setattr(trial, "free_ram", lambda: free)
    with pytest.raises(RuntimeError):
        trial.run("qwen2.5:7b-instruct", tmp_path / "result.json")
    assert fake.posts == []
    assert not (tmp_path / "result.json").exists()


def test_inference_failure_is_saved_and_model_is_unloaded(monkeypatch, tmp_path):
    fake = FakeOllama()
    monkeypatch.setattr(trial.httpx, "Client", lambda **kwargs: fake)
    monkeypatch.setattr(trial, "free_ram", lambda: 8 * 1024**3)
    result = tmp_path / "result.json"
    with pytest.raises(RuntimeError, match="inference failure"):
        trial.run("qwen2.5:7b-instruct", result)
    saved = json.loads(result.read_text())
    assert saved["records"][0]["outcome"] == "failed"
    assert saved["records"][0]["error_type"] == "ReadTimeout"
    assert saved["metadata"]["resident_after_unload"] == []
    assert len(fake.posts) == 2
    assert all(body["keep_alive"] == 0 for body in fake.posts)
