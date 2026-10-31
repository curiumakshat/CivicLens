"""Runtime configuration for CivicLens."""

from dataclasses import dataclass, field
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


def default_google_redirect_uri() -> str:
    """Build the Google OAuth callback URI from the environment.

    Priority:
      1. Explicit GOOGLE_REDIRECT_URI env-var
      2. Vercel VERCEL_URL (auto-set by Vercel on every deployment)
      3. Localhost fallback
    """
    explicit = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    vercel_url = os.getenv("VERCEL_URL", "").strip()
    if vercel_url:
        return f"https://{vercel_url}/auth/google/callback"
    return "http://localhost:8000/auth/google/callback"


@dataclass(frozen=True)
class Settings:
    app_name: str = "CivicLens"
    database_url: str = field(default_factory=default_database_url)

    # Session Secret
    session_secret: str = field(default_factory=lambda: os.getenv(
        "SESSION_SECRET",
        os.getenv("CIVICLENS_SESSION_SECRET", "civiclens-session-secret-key-32chars-min!")
    ))
    otp_pepper: str = field(default_factory=lambda: os.getenv("CIVICLENS_OTP_PEPPER", "civiclens-otp-pepper-salt"))

    # Google OAuth 2.0 / OpenID Connect
    google_client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_ID", "").strip())
    google_client_secret: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_SECRET", "").strip())
    google_redirect_uri: str = field(default_factory=default_google_redirect_uri)

    # Optional Gmail SMTP
    smtp_email: str = field(default_factory=lambda: os.getenv("SMTP_EMAIL", "").strip())
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", "").strip().replace(" ", ""))
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "smtp.gmail.com").strip())
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))

    # Demo mode allows graceful testing when external services are unreachable
    demo_mode: bool = field(default_factory=lambda: os.getenv("CIVICLENS_DEMO_MODE", "true").lower() == "true")
    admin_email: str = field(default_factory=lambda: os.getenv("CIVICLENS_ADMIN_EMAIL", "akshat.raj25@st.niituniversity.in").strip().lower())
    priority_window_days: int = field(default_factory=lambda: int(os.getenv("CIVICLENS_PRIORITY_WINDOW_DAYS", "30")))
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", "").strip().rstrip("/"))
    supabase_jwks_url: str = field(default_factory=lambda: os.getenv("SUPABASE_JWKS_URL", "").strip())
    # Server-only Supabase Storage credentials. Never expose this to Vite.
    supabase_secret_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SECRET_KEY", "").strip())
    supabase_reports_bucket: str = field(default_factory=lambda: os.getenv("SUPABASE_REPORTS_BUCKET", "civiclens-reports").strip())

    @property
    def has_google_oauth(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


settings = Settings()
