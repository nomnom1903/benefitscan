"""
app/main.py — Application entry point

This file:
  1. Creates the FastAPI application
  2. Registers all route modules
  3. Initializes the database on startup
  4. Serves the frontend static files
  5. Starts the uvicorn server when run directly

Run with:
  python app/main.py
Then open: http://localhost:5000
"""

import logging
import sys
from pathlib import Path

# When running as `python app/main.py`, Python sets the script's directory
# (app/) as sys.path[0], so `from app.xxx import` fails. We fix this by
# inserting the project root (one level up from this file) into sys.path.
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routes import upload, extract, export

# ─────────────────────────────────────────────────────────────────────────────
# Logging setup
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.is_development else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Startup / shutdown lifecycle (replaces deprecated @app.on_event)
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Called once at startup (before yield) and once at shutdown (after yield)."""
    logger.info("BenefitScan starting up...")
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Database initialized: {settings.database_url}")
    logger.info(f"Upload directory: {settings.upload_dir}")
    logger.info(f"Using Claude model: {settings.claude_model}")
    logger.info(f"App running at: http://localhost:{settings.app_port}")
    yield
    # Nothing to clean up on shutdown for V1


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI application
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="BenefitScan API",
    description="AI-powered SBC extraction and plan comparison for insurance brokers",
    version="1.0.0",
    lifespan=lifespan,
    # Only show API docs in development. In production (V2 cloud), docs might be public.
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# ─────────────────────────────────────────────────────────────────────────────
# CORS — allow the frontend to call the API
# Since the frontend is served FROM the same FastAPI app (as static files),
# we don't strictly need CORS for production. But it's useful during development
# if you want to run the frontend separately (e.g. on a different port with live reload).
# ─────────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # In V2, lock this down to your specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(upload.router, tags=["Upload"])
app.include_router(extract.router, tags=["Extract & Review"])
app.include_router(export.router, tags=["Export"])


@app.get("/health")
def health_check() -> dict:
    """Health check endpoint — useful for debugging and future monitoring."""
    return {
        "status": "ok",
        "model": settings.claude_model,
        "environment": settings.app_env,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Serve the frontend
# The frontend/ directory contains index.html, styles.css, app.js.
# We mount it at /static and add a root route that serves index.html.
# ─────────────────────────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    # Mount CSS, JS, and other assets at /static
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_frontend() -> FileResponse:
        """Serve the main UI at the root URL."""
        return FileResponse(str(FRONTEND_DIR / "index.html"))
else:
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR}")

    @app.get("/")
    def no_frontend() -> dict:
        return {"message": "API is running. Frontend not found."}


# ─────────────────────────────────────────────────────────────────────────────
# Entry point — run uvicorn when this file is executed directly
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.is_development,  # auto-reload on file changes in dev mode
        log_level="debug" if settings.is_development else "info",
    )
