"""Vercel serverless entrypoint for the CivicLens FastAPI application.

Vercel Python runtime expects an ASGI or WSGI application in `api/index.py`.
All `/auth/*`, `/api/*`, and `/health*` routes are forwarded here via
the rewrites in `vercel.json`.
"""

import sys
from pathlib import Path

# Ensure the project root is on the Python path so that `from app.…` imports
# resolve correctly in the Vercel serverless environment.
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.main import app  # noqa: E402

# Vercel looks for an `app` variable by default.
__all__ = ["app"]
