"""Runtime configuration for CivicLens."""

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def default_database_url() -> str:
    """Choose a writable local default while allowing hosted databases."""

    configured = os.getenv("CIVICLENS_DATABASE_URL") or os.getenv("DATABASE_URL")
    if configured:
        return configured
    if os.getenv("VERCEL") == "1" or os.getenv("VERCEL_ENV"):
        # Vercel deployments have a read-only bundle; /tmp is writable but
        # ephemeral. Use Postgres/Supabase for persistent production data.
        temp_db = Path(tempfile.gettempdir()) / "civiclens.db"
        return f"sqlite:///{temp_db.as_posix()}"
    return "sqlite:///./civiclens.db"


@dataclass(frozen=True)
class Settings:
    app_name: str = "CivicLens"
    database_url: str = default_database_url()
    
    # Session Secret
    session_secret: str = os.getenv(
        "SESSION_SECRET",
        os.getenv("CIVICLENS_SESSION_SECRET", "civiclens-session-secret-key-32chars-min!")
    )
    otp_pepper: str = os.getenv("CIVICLENS_OTP_PEPPER", "civiclens-otp-pepper-salt")

    # Google OAuth 2.0 / OpenID Connect
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback").strip()

    # Optional Gmail SMTP
    smtp_email: str = os.getenv("SMTP_EMAIL", "").strip()
    smtp_password: str = os.getenv("SMTP_PASSWORD", "").strip().replace(" ", "")
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))

    # Demo mode allows graceful testing when external services are unreachable
    demo_mode: bool = os.getenv("CIVICLENS_DEMO_MODE", "true").lower() == "true"
    admin_email: str = os.getenv("CIVICLENS_ADMIN_EMAIL", "akshat.raj25@st.niitunversity.in").strip().lower()
    priority_window_days: int = int(os.getenv("CIVICLENS_PRIORITY_WINDOW_DAYS", "30"))

    @property
    def has_google_oauth(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


settings = Settings()
