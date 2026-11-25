from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.errors import ServiceUnavailable


@dataclass(frozen=True)
class Completion:
    text: str
    tokens: int
    neurons: float


def is_enabled() -> bool:
    """True when a real provider is configured (not the deterministic mock)."""
    return settings.ai_provider.lower() in {"openai", "cloudflare"} and bool(
        settings.ai_api_key
    )


def provider_base_url() -> str:
    """Resolve the chat-completions URL for the configured provider."""
    if settings.ai_provider.lower() == "cloudflare":
        if not settings.cloudflare_account_id:
            raise ServiceUnavailable("CLOUDFLARE_ACCOUNT_ID is not configured")
        account = settings.cloudflare_account_id.strip().strip("/")
        return f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1"
    return settings.ai_base_url


def estimate_neurons(tokens: int) -> float:
    """Approximate Neurons when the provider does not report them."""
    rate = max(settings.ai_neurons_per_1k_tokens, 0.0)
    return max(tokens, 0) * rate / 1000


async def complete_with_usage(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> Completion:
    """Call the provider and return text plus real or estimated usage."""
    if not settings.ai_api_key:
        raise ServiceUnavailable("AI API key is not configured")

    payload = {
        "model": settings.ai_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens if max_tokens is not None else settings.ai_max_tokens,
    }
    url = f"{provider_base_url().rstrip('/')}/chat/completions"

    async def post(http: httpx.AsyncClient) -> httpx.Response:
        return await http.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
        )

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=120) as http:
                response = await post(http)
        else:
            response = await post(client)
        response.raise_for_status()
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]
        if raw_text is None:
            raise ServiceUnavailable(
                "AI provider returned no answer (increase AI_MAX_TOKENS for reasoning models)"
            )
        text = str(raw_text).strip()
        usage = data.get("usage") or {}
        tokens = int(usage.get("total_tokens", 0) or 0)
        reported = usage.get("neurons")
        neurons = float(reported) if reported else estimate_neurons(tokens)
    except (httpx.HTTPError, KeyError, IndexError, AttributeError, TypeError, ValueError) as exc:
        raise ServiceUnavailable("AI provider is temporarily unavailable") from exc

    if not text:
        raise ServiceUnavailable("AI provider returned an empty response")
    return Completion(text=text, tokens=tokens, neurons=neurons)


async def complete(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, int]:
    """Backward-compatible wrapper returning only text and tokens."""
    result = await complete_with_usage(
        messages, temperature=temperature, max_tokens=max_tokens, client=client
    )
    return result.text, result.tokens
