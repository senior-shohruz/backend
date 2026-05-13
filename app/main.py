"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import settings
from app.db.session import AsyncSessionLocal, init_db
from app.db.seed import run_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown hooks."""
    # In production use Alembic migrations instead of init_db()
    await init_db()
    async with AsyncSessionLocal() as db:
        await run_seed(db)
    yield
    # Cleanup if needed


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", tags=["health"])
    async def root() -> dict:
        return {
            "app": settings.APP_NAME,
            "status": "ok",
            "docs": "/docs",
            "api_prefix": settings.API_V1_PREFIX,
        }

    @app.get("/health", tags=["health"])
    async def health() -> dict:
        return {"status": "healthy"}

    return app


app = create_app()
