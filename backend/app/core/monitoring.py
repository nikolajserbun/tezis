from __future__ import annotations

import time

import sentry_sdk

from app.core.config import settings

# Avoid flooding the owner chat when the same failure repeats every request.
ALERT_COOLDOWN_SECONDS = 300
_last_alert: dict[str, float] = {}


def init_sentry() -> None:
    """Initialise Sentry once per process (no-op without a DSN)."""
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )


def capture_exception(exc: BaseException) -> None:
    """Send an exception to Sentry when monitoring is configured."""
    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exc)


def should_alert(key: str) -> bool:
    """Return True at most once per cooldown window for a given alert key."""
    now = time.monotonic()
    last = _last_alert.get(key, 0.0)
    if now - last < ALERT_COOLDOWN_SECONDS:
        return False
    _last_alert[key] = now
    return True
