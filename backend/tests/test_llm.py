import json

import httpx
import pytest

from app import agent
from app.config import Settings, settings
from app.schemas import AgentStep


def hosted(monkeypatch, handler):
    real = httpx.Client
    monkeypatch.setattr(agent.httpx, "Client", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    for key, value in {
        "llm_provider": "openai",
        "llm_base_url": "https://llm.example/v1/",
        "llm_api_key": "test-key",
        "llm_model": "test-model",
        "llm_reasoning_effort": "low",
    }.items():
        monkeypatch.setattr(settings(), key, value)


def test_hosted_provider_requests_schema_json(monkeypatch):
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), auth=request.headers["authorization"], body=json.loads(request.content))
        content = json.dumps({"rationale": "Check courier fees first.", "tool": "get_delivery_costs"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    hosted(monkeypatch, handler)
    step = agent.model_json(AgentStep, [{"role": "user", "content": "Plan the investigation."}])
    assert step.tool == "get_delivery_costs"
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == "test-model" and seen["body"]["reasoning_effort"] == "low"
    schema = seen["body"]["response_format"]["json_schema"]
    assert schema["name"] == "AgentStep" and schema["strict"] is True
    assert set(schema["schema"]["required"]) == {"rationale", "hypotheses", "tool", "query"}
    assert schema["schema"]["additionalProperties"] is False
    assert settings().model_name == "test-model"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": '{"tool": "run_sql"}'}}]}),
        httpx.Response(429, json={"error": {"message": "rate limited"}}),
    ],
)
def test_hosted_provider_failures_raise_fallback_errors(monkeypatch, response):
    hosted(monkeypatch, lambda request: response)
    with pytest.raises((ValueError, httpx.HTTPError)):
        agent.model_json(AgentStep, [{"role": "user", "content": "Plan the investigation."}])


def test_hosted_provider_waits_for_rate_limits(monkeypatch):
    responses = iter(
        [
            httpx.Response(429, headers={"retry-after": "2"}, json={"error": {"message": "rate limited"}}),
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"rationale": "Plan the next step.", "tool": "finish"}'}}]},
            ),
        ]
    )
    waits = []
    hosted(monkeypatch, lambda request: next(responses))
    monkeypatch.setattr(agent.time, "sleep", waits.append)
    assert agent.model_json(AgentStep, [{"role": "user", "content": "Plan the investigation."}]).tool == "finish"
    assert waits == [2.0]


def test_hosted_provider_configuration_is_validated():
    with pytest.raises(ValueError, match="needs llm_base_url"):
        Settings(llm_provider="openai", agent_mode="auto", llm_base_url="", llm_api_key="", llm_model="")
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(llm_provider="openai", agent_mode="auto", llm_base_url="http://x", llm_api_key="k", llm_model="m")
    with pytest.raises(ValueError, match="llm_provider"):
        Settings(llm_provider="mystery")
    assert Settings(llm_provider="openai", agent_mode="deterministic", llm_api_key="").agent_mode == "deterministic"
