"""Set the public HTTPS URL used by the Mini App, API and Telegram webhook.

Usage:
    python scripts/set_public_url.py https://example.ts.net

Only URL-related keys are rewritten; secrets are never read or printed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

URL_KEYS = ("FRONTEND_URL", "PUBLIC_BASE_URL", "WEBHOOK_BASE_URL")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/set_public_url.py https://example.ts.net")
        return 2
    url = sys.argv[1].strip().rstrip("/")
    if not url.startswith("https://") or "." not in url:
        print("URL must be an absolute https:// address")
        return 2

    path = Path(".env")
    lines = path.read_text(encoding="utf-8").splitlines()
    updates = {
        "FRONTEND_URL": url,
        "PUBLIC_BASE_URL": url,
        "WEBHOOK_BASE_URL": url,
        "CORS_ORIGINS": f"http://localhost:5173,http://localhost:8000,{url}",
    }
    result: list[str] = []
    seen: set[str] = set()
    for line in lines:
        match = re.match(r"^([A-Z0-9_]+)=", line)
        if match and match.group(1) in updates:
            key = match.group(1)
            result.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            result.append(line)
    for key, value in updates.items():
        if key not in seen:
            result.append(f"{key}={value}")
    path.write_text("\n".join(result) + "\n", encoding="utf-8")
    print(f"Public URL updated: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
