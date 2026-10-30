from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="CivicLens", description="Civic issue reporting and resolution tracker")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


@app.get("/", include_in_schema=False)
async def public_tracker(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")
