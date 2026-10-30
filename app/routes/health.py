"""Operational health endpoint."""

from fastapi import APIRouter

from app.config import settings


router = APIRouter(tags=["health"])


@router.get("/health", summary="Check that CivicLens is running")
async def health_check() -> dict[str, str]:
    """Return a small machine-readable liveness response."""

    return {"status": "ok", "service": settings.app_name}
