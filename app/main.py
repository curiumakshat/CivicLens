from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import init_db
from app.routes.health import router as health_router


ROOT = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=ROOT / "templates")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Prepare the local database before serving requests."""

    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Civic issue reporting and resolution tracker",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.include_router(health_router)


@app.get("/", include_in_schema=False)
async def public_tracker(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")
