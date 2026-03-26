import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.router import api_router

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler.
    Everything BEFORE yield runs on startup.
    Everything AFTER yield runs on shutdown.
    """
    # ── Startup ──────────────────────────────────────────
    logger.info("Starting up Swiftex Sense API...")
    
    # We will initialize Neo4j connection here later

    logger.info("Lifespan startup phase complete. Web server ready.")

    yield  # App is now running — handle requests

    # ── Shutdown ─────────────────────────────────────────
    logger.info("Shutting down Swiftex Sense API...")
    # We will close Neo4j connection here later
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Swiftex Sense Server API",
        description="Production API for Retrieval Augmented Generation (RAG) capabilities.",
        version="1.0.0",
        lifespan=lifespan,   # ← attach the lifespan handler
    )

    # Set up CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Adjust this in production!
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(api_router, prefix="/api/v1")

    # Serve generated Excel exports — files land in app/static/exports/
    _static_dir = Path(__file__).parent / "static"
    _static_dir.mkdir(parents=True, exist_ok=True)
    (Path(__file__).parent / "static" / "exports").mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    @app.get("/health", tags=["Health"])
    def check_health():
        return {"status": "ok", "message": "Swiftex Sense API is running smoothly."}

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
