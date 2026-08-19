"""OpenAI SDK integration: key handling, startup check, and connection test."""

import os

import pytest

from orchestration.llm import (
    CONNECTED_MARKER,
    HostedLanguageModel,
    ModelConfig,
    model_status,
    openai_configured,
    resolve_config,
    test_openai_connection as connect_to_openai,
)

# Captured before the autouse fixture below wipes it, for the live smoke test.
_REAL_OPENAI_KEY = os.getenv("OPENAI_API_KEY")


@pytest.fixture(autouse=True)
def _clean_openai_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)


# -- the key is read from the environment only, never hard-coded -----------


def test_no_key_means_not_configured():
    assert openai_configured() is False
    assert resolve_config() is None
    assert "keyword router" in model_status()


def test_a_placeholder_key_is_not_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "your_openai_api_key_here")
    assert openai_configured() is False
    assert resolve_config() is None


def test_a_real_key_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-value")
    assert openai_configured() is True
    config = resolve_config()
    assert config.provider == "openai"
    assert config.api_key == "sk-real-value"


def test_status_never_contains_the_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-appear")
    assert "sk-should-never-appear" not in model_status()


def test_openai_configured_check_never_raises_or_prints(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-anything")
    openai_configured()
    captured = capsys.readouterr()
    assert "sk-anything" not in captured.out
    assert "sk-anything" not in captured.err


# -- connection test ---------------------------------------------------


def test_connection_test_fails_closed_with_no_key():
    with pytest.raises(RuntimeError, match="not configured"):
        connect_to_openai()


def test_connection_test_error_never_contains_the_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-must-not-leak-12345")
    with pytest.raises(RuntimeError) as excinfo:
        connect_to_openai()
    assert "sk-must-not-leak-12345" not in str(excinfo.value)


def test_a_mocked_successful_call_returns_the_connected_marker(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")

    class FakeResponse:
        output_text = "ok"

    class FakeResponses:
        def create(self, **kwargs):
            assert kwargs["model"]
            assert "input" in kwargs
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.responses = FakeResponses()

    import orchestration.llm as llm_module

    monkeypatch.setattr(llm_module.openai_sdk, "OpenAI", FakeClient)
    assert connect_to_openai() == CONNECTED_MARKER


def test_an_empty_response_is_treated_as_a_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")

    class EmptyResponse:
        output_text = ""

    class FakeResponses:
        def create(self, **kwargs):
            return EmptyResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.responses = FakeResponses()

    import orchestration.llm as llm_module

    monkeypatch.setattr(llm_module.openai_sdk, "OpenAI", FakeClient)
    with pytest.raises(RuntimeError, match="empty response"):
        connect_to_openai()


# -- routing never exposes the key, and degrades cleanly --------------------


def test_route_degrades_to_none_on_an_sdk_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    import httpx2
    import orchestration.llm as llm_module

    fake_request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    fake_response = httpx2.Response(401, request=fake_request, json={"error": {"message": "bad key"}})

    class FakeResponses:
        def create(self, **kwargs):
            raise llm_module.openai_sdk.AuthenticationError(
                message="bad key", response=fake_response, body=None
            )

    class FakeClient:
        def __init__(self, api_key):
            self.responses = FakeResponses()

    monkeypatch.setattr(llm_module.openai_sdk, "OpenAI", FakeClient)
    model = HostedLanguageModel(ModelConfig("openai", "gpt-4o", "sk-fake"))
    assert model.route("find nuclear strategies", history=[], intents=["generate"]) is None


def test_route_uses_the_responses_api_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    import json

    import orchestration.llm as llm_module

    captured = {}

    class FakeResponse:
        output_text = json.dumps({"intent": "generate", "args": {"query": "nuclear"}})

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeClient:
        def __init__(self, api_key):
            self.responses = FakeResponses()

    monkeypatch.setattr(llm_module.openai_sdk, "OpenAI", FakeClient)
    model = HostedLanguageModel(ModelConfig("openai", "gpt-4o", "sk-fake"))
    intent = model.route("find nuclear strategies", history=[], intents=["generate"])

    assert intent.name == "generate"
    assert intent.args["query"] == "nuclear"
    assert captured["model"] == "gpt-4o"
    assert captured["text"] == {"format": {"type": "json_object"}}
    assert "sk-fake" not in json.dumps(captured, default=str)


# -- optional live smoke test, skipped unless a real key is present ---------


@pytest.mark.skipif(not _REAL_OPENAI_KEY, reason="requires a real OPENAI_API_KEY")
def test_live_connection_against_the_real_api(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", _REAL_OPENAI_KEY)
    assert connect_to_openai() == CONNECTED_MARKER
