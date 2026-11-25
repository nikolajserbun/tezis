"""Sync .env with the current Cloudflare quick tunnel URL.

Usage:
    python scripts/refresh_tunnel.py

Quick tunnels get a new address every time the container restarts. This script
reads the address from the running container and rewrites only FRONTEND_URL,
PUBLIC_BASE_URL and CORS_ORIGINS in .env. It never prints or rewrites secrets.
After running it, recreate api/bot and restart frontend with the printed
commands.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
CONTAINER = "tezis-tunnel"
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def tunnel_url() -> str:
    result = subprocess.run(
        ["docker", "logs", CONTAINER],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"Не удалось прочитать логи контейнера {CONTAINER}")
    urls = URL_PATTERN.findall(result.stdout + result.stderr)
    if not urls:
        raise SystemExit(f"В логах {CONTAINER} нет адреса trycloudflare.com")
    return urls[-1]


def rewrite_env(url: str) -> None:
    if not ENV_PATH.exists():
        raise SystemExit("Файл .env не найден")
    replacements = {
        "FRONTEND_URL": url,
        "PUBLIC_BASE_URL": url,
        "CORS_ORIGINS": f"http://localhost:5173,http://localhost:8000,{url}",
    }
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    updated: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in replacements:
            updated.append(f"{key}={replacements[key]}")
            seen.add(key)
        else:
            updated.append(line)
    for key, value in replacements.items():
        if key not in seen:
            updated.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(updated) + "\n", encoding="utf-8")


def check(url: str) -> None:
    try:
        with urlopen(f"{url}/app", timeout=10) as response:
            print(f"Проверка /app: HTTP {response.status}")
    except OSError as error:
        print(f"Проверка /app не удалась: {error}", file=sys.stderr)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    url = tunnel_url()
    rewrite_env(url)
    check(url)
    print(f"Адрес туннеля записан в .env: {url}")
    print("Выполните в PowerShell в корне проекта:")
    print("$env:COMPOSE_PROJECT_NAME='tezis'")
    print("docker compose --profile polling up -d --force-recreate api bot")
    print("docker compose --profile polling restart frontend")


if __name__ == "__main__":
    main()
