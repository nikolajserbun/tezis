"""Подставить CLOUDFLARE_ACCOUNT_ID в .env по текущему API-токену."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from app.core.config import settings

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


async def main() -> None:
    if not settings.ai_api_key:
        print("AI_API_KEY is empty — put your Cloudflare API token into .env first.")
        return

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            "https://api.cloudflare.com/client/v4/accounts",
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
        )
    if response.status_code != 200:
        print(f"FAIL: Cloudflare answered {response.status_code}: {response.text[:300]}")
        return

    accounts = response.json().get("result") or []
    if not accounts:
        print("FAIL: no Cloudflare accounts available for this token.")
        return

    account = accounts[0]
    account_id = str(account["id"])
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("CLOUDFLARE_ACCOUNT_ID="):
            lines[index] = f"CLOUDFLARE_ACCOUNT_ID={account_id}"
            break
    else:
        lines.append(f"CLOUDFLARE_ACCOUNT_ID={account_id}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: account {account.get('name', '')!r} -> {account_id} written to .env")


if __name__ == "__main__":
    asyncio.run(main())
