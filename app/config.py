"""Application configuration for the first local/offline build slice."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings with safe SQLite defaults for local development."""

    app_name: str = "CivicLens"
    database_url: str = os.getenv("CIVICLENS_DATABASE_URL", "sqlite:///./civiclens.db")


settings = Settings()
