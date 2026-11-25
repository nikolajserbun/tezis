from __future__ import annotations

import httpx

from app.core.config import settings
from app.services import websearch


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class _FakeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, *args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(self.payload)


def test_from_searx_maps_results() -> None:
    result = websearch._from_searx(
        {
            "results": [
                {
                    "title": "Первый",
                    "url": "https://example.com/1",
                    "content": "Коротко",
                },
                {"title": "Битый", "url": "http:///go/1", "content": ""},
                {
                    "title": "Второй",
                    "url": "https://example.com/2",
                    "content": "x" * 800,
                },
                {"title": "Третий", "url": "https://example.com/3", "content": ""},
                {"title": "Четвёртый", "url": "https://example.com/4", "content": ""},
            ]
        }
    )

    assert result.demo is False
    assert [item.title for item in result.items] == ["Первый", "Второй", "Третий"]
    assert result.items[0].url == "https://example.com/1"
    assert len(result.items[1].snippet) == 600


async def test_search_uses_searxng_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "searxng_url", "http://searxng:8080")
    monkeypatch.setattr(
        websearch.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeClient(
            {
                "results": [
                    {
                        "title": "Свежий материал",
                        "url": "https://example.com/news",
                        "content": "Актуальная информация",
                    }
                ]
            }
        ),
    )

    result = await websearch.search("последние новости")

    assert result.demo is False
    assert result.items[0].url == "https://example.com/news"
    assert result.note == ""


async def test_search_falls_back_when_searxng_fails(monkeypatch) -> None:
    class _BrokenClient(_FakeClient):
        async def get(self, *args: object, **kwargs: object) -> _FakeResponse:
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(settings, "searxng_url", "http://searxng:8080")
    monkeypatch.setattr(
        websearch.httpx, "AsyncClient", lambda *args, **kwargs: _BrokenClient({})
    )

    result = await websearch.search("что умеет студия")

    assert result.demo is True
    assert "Поиск недоступен" in result.note
