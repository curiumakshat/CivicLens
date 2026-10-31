"""Database engine and session management for CivicLens."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # The legacy column migration is SQLite-specific. PostgreSQL deployments
    # receive the complete schema above and should use a real migration tool
    # for future schema changes.
    if not settings.database_url.startswith("sqlite"):
        return

    # Safe SQLite column migration
    with engine.begin() as conn:
        try:
            existing_cols = [
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()
            ]
            if existing_cols:
                if "google_sub" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN google_sub VARCHAR(255)")
                    conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_sub ON users (google_sub)")
                if "email" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
                if "avatar_url" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)")
                if "auth_provider" not in existing_cols:
                    conn.exec_driver_sql("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(40) DEFAULT 'otp'")
        except Exception:
            pass
