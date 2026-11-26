"""Prepare a local .env for production without printing secret values.

The script is safe to run repeatedly: random secrets are generated only when
the current value is still a known placeholder.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path

PLACEHOLDERS = ("change-me", "replace-with", "test-password", "tezis-dev-2026")


def main() -> None:
    path = Path(".env")
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

    public_url = values.get("PUBLIC_BASE_URL", "").strip()
    updates: dict[str, str] = {
        "APP_ENV": "prod",
        "DEBUG": "false",
        "DEV_PAYMENTS_ENABLED": "false",
        "BOT_MODE": "webhook",
    }
    if public_url:
        updates["WEBHOOK_BASE_URL"] = public_url

    for key in ("SECRET_KEY", "JWT_SECRET", "WEBHOOK_SECRET"):
        if values.get(key, "").startswith(PLACEHOLDERS) or not values.get(key):
            updates[key] = secrets.token_urlsafe(48)
    dev_password = values.get("DEV_ADMIN_PASSWORD", "")
    if not dev_password or dev_password.startswith(PLACEHOLDERS):
        updates["DEV_ADMIN_PASSWORD"] = secrets.token_urlsafe(24)

    result: list[str] = []
    for line in lines:
        match = re.match(r"^([A-Z0-9_]+)=", line)
        if match and match.group(1) in updates:
            key = match.group(1)
            result.append(f"{key}={updates[key]}")
        else:
            result.append(line)
    path.write_text("\n".join(result) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
