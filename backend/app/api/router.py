from fastapi import APIRouter

from app.api import admin, auth, internal, me, orders, public, webhooks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(public.router)
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(orders.router)
api_router.include_router(admin.router)
api_router.include_router(internal.router)
api_router.include_router(webhooks.router)
