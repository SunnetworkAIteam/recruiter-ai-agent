"""
Application entrypoint.

Run locally with: uvicorn app.main:app --reload --port 8000
Run in production with: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import asyncio
from app.api.routes import candidates, interviews, jobs
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.rate_limit import limiter
from app.logging_config import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup", environment=settings.ENVIRONMENT, app_name=settings.APP_NAME)
    from app.services.interview_service import background_sync_loop

    sync_task = asyncio.create_task(background_sync_loop())
    yield
    sync_task.cancel()
    logger.info("app_shutdown")

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
    # Never expose interactive docs in production — they reveal your entire
    # API surface (including internal/admin routes) to anyone who finds the URL.
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: exc)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "ngrok-skip-browser-warning"],
)

register_exception_handlers(app)

app.include_router(candidates.router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)
app.include_router(interviews.router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
def health_check():
    """
    Liveness/readiness probe for Koyeb. Deliberately does NOT touch the
    database — a health check that depends on the DB means a transient DB
    blip takes down your whole service via failed health checks and
    restarts, which is worse than the original blip.
    """
    return {"status": "ok", "environment": settings.ENVIRONMENT}
