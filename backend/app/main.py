"""FastAPI application entrypoint for the MVP.

Serves the /recommendations API (app.api.recommendations) and a minimal
static single-page frontend (app/static/index.html) from the same origin.

Run with: uvicorn app.main:app --reload --port 8000  (from backend/)
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

from app.api.favorites import router as favorites_router
from app.api.organizations import router as organizations_router
from app.api.recommendations import router as recommendations_router

app = FastAPI(title="NYC Activity Discovery Engine (MVP)")

# Needed once the frontend runs on the Vite dev server (5173) instead of
# being served from this same FastAPI origin. Restricted to the known dev
# server origin, not a wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendations_router)
app.include_router(favorites_router)
app.include_router(organizations_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
static_app = StaticFiles(directory=STATIC_DIR, html=True)


@app.middleware("http")
async def disable_static_caching(request: Request, call_next):
    """The MVP's frontend changes frequently during development; a cached
    stale index.html (browser or preview panel) is a confusing failure
    mode ("I edited it but nothing changed"). Static assets are small and
    local, so always-revalidate is the right tradeoff here.
    """
    response: Response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


app.mount("/", static_app, name="static")
