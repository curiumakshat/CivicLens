
"""Operational health and database endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Check whether CivicLens is running."""
    return {"status": "ok", "service": settings.app_name}


@router.get("/health/db")
def database_health_check():
    """Check whether CivicLens can connect to its database."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": engine.dialect.name,
            "connection": "successful",
        }

    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "connection": "failed",
                "message": "Database connection unavailable.",
            },
        )
