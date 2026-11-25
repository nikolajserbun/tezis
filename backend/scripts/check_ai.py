"""Проверка настроенного AI-провайдера одним коротким запросом."""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.errors import ServiceUnavailable
from app.services.llm import complete, provider_base_url


async def main() -> None:
    if not settings.ai_api_key:
        print("AI_API_KEY is empty — fill it in .env (see .env.example).")
        return

    print(
        f"provider={settings.ai_provider} "
        f"model={settings.ai_model} "
        f"base_url={provider_base_url()}"
    )
    try:
        text, tokens = await complete(
            [{"role": "user", "content": "Ответь одним словом: готов"}],
            max_tokens=512,
        )
    except ServiceUnavailable as exc:
        print(f"FAIL: {exc.message}")
        return
    print(f"OK: {text[:200]!r}, tokens={tokens}")


if __name__ == "__main__":
    asyncio.run(main())
