"""CivicLens FastAPI application.

Locally: serves both the API and the React SPA from `frontend/dist`.
On Vercel: only handles `/auth/*`, `/api/*`, and `/health*` routes;
           the React SPA is served as static files by Vercel CDN.
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db
from app.routes.auth import router as auth_router
from app.routes.admin import router as admin_router
from app.routes.health import router as health_router
from app.routes.reports import router as reports_router


ROOT = Path(__file__).resolve().parent.parent
REACT_DIST = ROOT / "frontend" / "dist"
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize database tables and migrations on startup."""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="CivicLens Civic Issue Reporting and Resolution Tracker",
    lifespan=lifespan,
)

# ── Session Middleware (MUST be added before routers) ──────────────────
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=IS_VERCEL,          # HTTPS on Vercel, HTTP locally
    max_age=86400 * 7,             # 7 days
)

# ── CORS (needed when Vite dev server proxies to the API on a different port) ─
allowed_origins = ["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:8000"]
vercel_url = os.getenv("VERCEL_URL")
if vercel_url:
    allowed_origins.append(f"https://{vercel_url}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(reports_router)


# ── Local-only: serve React SPA & static assets ───────────────────────
# On Vercel the CDN serves these; locally FastAPI does it.
if not IS_VERCEL:
    # Mount built React assets (JS/CSS chunks)
    if (REACT_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=REACT_DIST / "assets"), name="react-assets")

    # Legacy static directory (if any templates need it)
    if (ROOT / "static").exists():
        app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str):
        """Serve the React SPA shell for any unmatched path (client-side routing)."""
        if path.startswith(("api/", "auth/", "health")):
            raise HTTPException(status_code=404, detail="Not Found")
        spa_index = REACT_DIST / "index.html"
        if spa_index.exists():
            return FileResponse(spa_index)
        raise HTTPException(status_code=404, detail="Frontend not built. Run: cd frontend && npm ci && npm run build")
