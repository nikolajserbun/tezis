from __future__ import annotations

from datetime import timedelta

from app.core.utils import utcnow
from app.models import Generation
from app.services import ai


async def test_mock_story_contains_full_plan_and_author_material(session, user) -> None:
    brand = None
    result = await ai.MockProvider().generate(
        kind="story",
        platform="telegram",
        topic="Почему клиенты выбирают экспертов",
        brand=brand,
    )
    assert "<b>Тема</b>" in result.text
    assert "<b>Креативный план</b>" in result.text
    assert "<b>Материал по теме автора</b>" in result.text
    assert "Сцена «до»" in result.text
    assert "вопрос" in result.text.lower()


async def test_generation_escapes_dynamic_html(session, user) -> None:
    result = await ai.generate(
        session,
        user=user,
        brand=None,
        kind="post",
        platform="telegram",
        topic="<script>alert(1)</script>",
    )
    assert "<script>" not in result.result
    assert "&lt;script&gt;" in result.result
    assert "<b>Тема</b>" in result.result


async def test_mock_post_is_enriched_with_author_blocks(session, user) -> None:
    result = await ai.MockProvider().generate(
        kind="post",
        platform="telegram",
        topic="Позиционирование эксперта",
        brand=None,
    )
    assert "🧭 <b>Тема</b>" in result.text
    assert "🗺 <b>Креативный план</b>" in result.text
    assert "📚 <b>Материал по теме автора</b>" in result.text


def test_openai_prompt_requests_author_focused_blocks() -> None:
    messages = ai.build_messages(
        kind="story",
        platform="telegram",
        topic="Почему клиенты выбирают экспертов",
        brand=None,
    )
    system = messages[0]["content"]
    user_prompt = messages[1]["content"]
    assert "«Тема»" in system
    assert "«Креативный план»" in system
    assert "«Материал по теме автора»" in system
    assert "полный рассказ" in user_prompt
    assert "креативный план" in user_prompt


async def test_cleanup_old_generations(session, user) -> None:
    stale = Generation(
        user_id=user.id,
        kind="post",
        platform="telegram",
        topic="старая",
        result="старый текст",
        tokens=10,
        cost_minor=1,
    )
    stale.created_at = utcnow() - timedelta(days=31)
    fresh = Generation(
        user_id=user.id,
        kind="story",
        platform="telegram",
        topic="свежая",
        result="свежий текст",
        tokens=10,
        cost_minor=1,
    )
    session.add_all([stale, fresh])
    await session.commit()

    removed = await ai.cleanup_old_generations(session)

    assert removed == 1
    remaining = await ai.list_generations(session, user.id)
    assert [item.topic for item in remaining] == ["свежая"]
