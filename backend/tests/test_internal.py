from __future__ import annotations

import pytest

from app.api import internal
from app.core.config import settings
from app.core.errors import Forbidden, ServiceUnavailable


def test_cron_secret_missing_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cron_secret", "")

    with pytest.raises(ServiceUnavailable):
        internal._require_cron_secret(None)


def test_cron_secret_placeholder_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "cron_secret", "change-me-cron-secret")

    with pytest.raises(ServiceUnavailable):
        internal._require_cron_secret("Bearer change-me-cron-secret")


def test_wrong_cron_secret_is_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cron_secret", "s3cret")

    with pytest.raises(Forbidden):
        internal._require_cron_secret("Bearer wrong")


def test_valid_cron_secret_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cron_secret", "s3cret")

    internal._require_cron_secret("Bearer s3cret")
