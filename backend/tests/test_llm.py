from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import settings
from app.core.errors import ServiceUnavailable
from app.services import llm


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_complete_uses_configured_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(
        settings,
        "ai_base_url",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )
    monkeypatch.setattr(settings, "ai_model", "gemini-3.5-flash-lite")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["json"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "  Готово  "}}],
                "usage": {"total_tokens": 123},
            },
        )

    async with _mock_client(handler) as client:
        text, tokens = await llm.complete(
            [{"role": "user", "content": "Привет"}], client=client
        )

    assert text == "Готово"
    assert tokens == 123
    assert seen["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    )
    assert seen["auth"] == "Bearer test-key"
    assert seen["json"]["model"] == "gemini-3.5-flash-lite"
    assert seen["json"]["messages"] == [{"role": "user", "content": "Привет"}]


async def test_cloudflare_base_url_uses_account_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_provider", "cloudflare")
    monkeypatch.setattr(settings, "cloudflare_account_id", "abc123")

    assert llm.provider_base_url() == (
        "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1"
    )


async def test_complete_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_api_key", "")

    with pytest.raises(ServiceUnavailable):
        await llm.complete([{"role": "user", "content": "Привет"}])


async def test_complete_maps_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    async with _mock_client(handler) as client:
        with pytest.raises(ServiceUnavailable):
            await llm.complete([{"role": "user", "content": "Привет"}], client=client)


async def test_complete_rejects_empty_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})

    async with _mock_client(handler) as client:
        with pytest.raises(ServiceUnavailable):
            await llm.complete([{"role": "user", "content": "Привет"}], client=client)


async def test_complete_rejects_reasoning_without_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": None, "reasoning": "thinking..."}}
                ]
            },
        )

    async with _mock_client(handler) as client:
        with pytest.raises(ServiceUnavailable, match="AI_MAX_TOKENS"):
            await llm.complete([{"role": "user", "content": "Привет"}], client=client)


async def test_complete_with_usage_reads_reported_neurons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Ответ"}}],
                "usage": {"total_tokens": 100, "neurons": 1.25},
            },
        )

    async with _mock_client(handler) as client:
        result = await llm.complete_with_usage(
            [{"role": "user", "content": "Привет"}], client=client
        )

    assert result.tokens == 100
    assert result.neurons == 1.25


async def test_complete_with_usage_estimates_missing_neurons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_neurons_per_1k_tokens", 25.0)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Ответ"}}],
                "usage": {"total_tokens": 200},
            },
        )

    async with _mock_client(handler) as client:
        result = await llm.complete_with_usage(
            [{"role": "user", "content": "Привет"}], client=client
        )

    assert result.neurons == 5.0
