from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas import ProductOut
from app.services import catalog

router = APIRouter(tags=["public"])


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/catalog", response_model=list[ProductOut])
async def catalog_list(
    kind: str | None = None, session: AsyncSession = Depends(get_session)
) -> list[ProductOut]:
    products = await catalog.list_products(session, kind=kind, active_only=True)
    return [ProductOut.model_validate(product) for product in products]


@router.get("/catalog/{slug}", response_model=ProductOut)
async def catalog_detail(
    slug: str, session: AsyncSession = Depends(get_session)
) -> ProductOut:
    product = await catalog.get_product_by_slug(session, slug)
    return ProductOut.model_validate(product)
