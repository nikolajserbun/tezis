from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.errors import ServiceUnavailable


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


async def complete(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, int]:
    """Call the configured OpenAI-compatible provider and return (text, tokens)."""
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
        tokens = int(data.get("usage", {}).get("total_tokens", 0) or 0)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ServiceUnavailable("AI provider is temporarily unavailable") from exc

    if not text:
        raise ServiceUnavailable("AI provider returned an empty response")
    return text, tokens
