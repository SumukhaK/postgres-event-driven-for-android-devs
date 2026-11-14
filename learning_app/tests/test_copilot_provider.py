import sys
from types import SimpleNamespace

from learning_app import copilot_provider


def test_copilot_adapter_uses_only_explicit_token_and_tool_free_session(monkeypatch):
    calls = {}

    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def send_and_wait(self, prompt):
            calls["prompt"] = prompt
            return SimpleNamespace(data=SimpleNamespace(content="A join combines related rows."))

    class Client:
        def __init__(self, **kwargs): calls["client"] = kwargs
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def list_models(self): return [SimpleNamespace(id="gpt-test", name="GPT test")]
        async def create_session(self, **kwargs): calls["session"] = kwargs; return Session()

    monkeypatch.setitem(sys.modules, "copilot", SimpleNamespace(CopilotClient=Client))
    monkeypatch.setenv("GH_TOKEN", "ambient-token-must-not-be-forwarded")
    models = copilot_provider.list_models("gho_user-token")
    answer = copilot_provider.generate("gho_user-token", "gpt-test", "Tutor instructions", [
        {"role": "user", "content": "Why use a join?"},
    ])

    assert models[0].id == "gpt-test"
    assert answer == "A join combines related rows."
    assert calls["client"]["github_token"] == "gho_user-token"
    assert calls["client"]["use_logged_in_user"] is False
    assert calls["client"]["mode"] == "empty"
    assert "GH_TOKEN" not in calls["client"]["env"]
    assert calls["session"]["available_tools"] == []
    assert calls["session"]["enable_session_telemetry"] is False
    assert calls["session"]["system_message"] == {"mode": "append", "content": "Tutor instructions"}
    assert "Tutor instructions" not in calls["prompt"]
    assert "User: Why use a join?" in calls["prompt"]
