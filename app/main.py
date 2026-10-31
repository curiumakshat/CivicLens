from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db
from app.routes.auth import router as auth_router
from app.routes.admin import router as admin_router
from app.routes.health import router as health_router
from app.routes.reports import router as reports_router


ROOT = Path(__file__).resolve().parent.parent
REACT_DIST = ROOT / "frontend" / "dist"
templates = Jinja2Templates(directory=ROOT / "templates")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize database tables and migrations on startup."""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="CivicLens Civic Issue Reporting and Resolution Tracker with Google OAuth2 Authentication",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
if (REACT_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=REACT_DIST / "assets"), name="react-assets")

# Mount API Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(reports_router)

# Secure Session Middleware for OAuth state & user session
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=False,  # Set to False for local development on http://localhost:8000
    max_age=86400 * 7,  # 7 days
)


@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    """Resident Login Portal."""
    if (REACT_DIST / "index.html").exists():
        return FileResponse(REACT_DIST / "index.html")
    user_id = request.session.get("user_id")
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "google_client_id": settings.google_client_id,
            "has_google_oauth": settings.has_google_oauth,
            "is_logged_in": bool(user_id),
            "user_name": request.session.get("name"),
            "user_email": request.session.get("email"),
            "error": error,
        },
    )


@app.get("/tracker", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
@app.get("/report", include_in_schema=False)
@app.get("/admin", include_in_schema=False)
async def public_tracker(request: Request):
    """CivicLens Public Tracker & Issue Resolution Dashboard."""
    if (REACT_DIST / "index.html").exists():
        return FileResponse(REACT_DIST / "index.html")
    user_id = request.session.get("user_id")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user_id": user_id,
            "user_name": request.session.get("name", "Anushka K."),
            "user_email": request.session.get("email", "anushka.k@gmail.com"),
            "user_avatar": request.session.get("avatar_url"),
            "auth_provider": request.session.get("auth_provider", "demo"),
            "is_logged_in": bool(user_id),
        },
    )


@app.get("/{path:path}", include_in_schema=False)
async def react_spa_fallback(path: str):
    """Serve the React shell for client-side frontend routes."""
    if path.startswith(("api/", "auth/")):
        raise HTTPException(status_code=404, detail="Not Found")
    if (REACT_DIST / "index.html").exists():
        return FileResponse(REACT_DIST / "index.html")
    raise HTTPException(status_code=404, detail="Not Found")
