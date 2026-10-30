"""Database engine and session helpers.

The engine is configured now so the domain models in Quest 2 can use it
without changing application wiring. SQLite is the default for the offline
hackathon demo; the URL can later point to PostgreSQL.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class for CivicLens SQLAlchemy models."""


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one request-scoped database session and always close it."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all registered tables for the local prototype database.

    Importing the models here ensures SQLAlchemy has registered them before
    metadata creation, while keeping the database module independent from
    model definitions at import time.
    """

    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
