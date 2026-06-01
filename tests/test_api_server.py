from fastapi.testclient import TestClient

import api_server
from src.core.gemini_provider import GeminiProvider


class FakeLLM:
    def __init__(self, provider, model_name):
        self.provider = provider
        self.model_name = model_name or "fake-model"
        self.calls = 0

    def generate(self, prompt, system_prompt=None):
        self.calls += 1
        content = (
            f"baseline from {self.provider}"
            if self.calls == 1
            else f"Final Answer: react from {self.provider}"
        )
        return {
            "content": content,
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            "latency_ms": 1,
            "provider": self.provider,
        }

    def stream(self, prompt, system_prompt=None):
        yield f"stream from {self.provider}"


def reset_api_state():
    api_server._llm_cache.clear()
    api_server._sessions.clear()
    api_server._api_events.clear()
    api_server._tools = []
    api_server._provider = "openai"


def test_compare_uses_requested_local_provider(monkeypatch):
    reset_api_state()
    calls = []

    def fake_get_llm(provider, *, model_name=None, quiet=False):
        calls.append((provider, model_name))
        return FakeLLM(provider, model_name)

    monkeypatch.setattr(api_server, "get_llm", fake_get_llm)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/compare",
        json={
            "message": "tim ban phim",
            "provider": "local",
            "model": "Phi-3-mini-4k-instruct-q4",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["baseline"]["content"] == "baseline from local"
    assert payload["react"]["content"] == "react from local"
    assert calls == [("local", "Phi-3-mini-4k-instruct-q4")]
    assert payload["telemetry"][0]["provider"] == "local"


def test_local_load_failure_does_not_fallback_to_openai(monkeypatch):
    reset_api_state()
    api_server._llm_cache["openai:gpt-4o"] = FakeLLM("openai", "gpt-4o")

    def fake_get_llm(provider, *, model_name=None, quiet=False):
        raise FileNotFoundError("local model missing")

    monkeypatch.setattr(api_server, "get_llm", fake_get_llm)
    client = TestClient(api_server.app)

    response = client.post(
        "/api/compare",
        json={
            "message": "tim ban phim",
            "provider": "local",
            "model": "Phi-3-mini-4k-instruct-q4",
        },
    )

    assert response.status_code == 503
    assert "Failed to load local model Phi-3-mini-4k-instruct-q4" in response.json()["detail"]


def test_compare_stream_emits_baseline_before_react(monkeypatch):
    reset_api_state()

    def fake_get_llm(provider, *, model_name=None, quiet=False):
        return FakeLLM(provider, model_name)

    monkeypatch.setattr(api_server, "get_llm", fake_get_llm)
    client = TestClient(api_server.app)

    with client.stream(
        "POST",
        "/api/compare/stream",
        json={
            "message": "tim ban phim",
            "provider": "local",
            "model": "Phi-3-mini-4k-instruct-q4",
        },
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert body.index("event: baseline") < body.index("event: react")
    assert body.index("event: react") < body.index("event: done")
    assert "baseline from local" in body
    assert "react from local" in body


def test_old_gemini_models_are_rejected():
    try:
        GeminiProvider(model_name="gemini-1.5-flash", api_key="fake-key")
    except ValueError as exc:
        assert "Unsupported Gemini model: gemini-1.5-flash" in str(exc)
        assert "gemini-2.5-flash" in str(exc)
    else:
        raise AssertionError("Expected old Gemini model to be rejected")
