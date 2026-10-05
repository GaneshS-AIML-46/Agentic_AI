from fastapi import APIRouter

from app.api import catalog, decisions, health, live, whatif

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(catalog.router, tags=["catalog"])
api_router.include_router(decisions.router, tags=["decisions"])
api_router.include_router(whatif.router, tags=["what-if"])
api_router.include_router(live.router, tags=["live"])
