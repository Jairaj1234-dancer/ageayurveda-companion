import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.api.v1.router import api_router
from app.core.limiter import limiter
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.request_tracing import RequestTracingMiddleware
from app.core.logging import logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} ({settings.app_env})")

    # Auto-create tables for SQLite dev mode
    if settings.database_url.startswith("sqlite"):
        from app.database import engine, Base
        import app.models  # noqa: F401 — registers all models with Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite tables created/verified")

    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# State for rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware (order matters - last added = first executed)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)

# API routes
app.include_router(api_router, prefix=settings.api_v1_prefix)

# Static directory paths
static_dir = os.path.join(os.path.dirname(__file__), "static")
admin_dir = os.path.join(static_dir, "admin")

# Root route — serve sample landing page
from fastapi.responses import FileResponse

@app.get("/")
async def serve_landing():
    index = os.path.join(static_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "AgeAyurveda Companion API", "docs": "/docs"}

# Serve admin SPA for /admin/* routes

if os.path.isdir(admin_dir):
    from fastapi.responses import FileResponse

    @app.get("/admin/{full_path:path}")
    async def serve_admin(full_path: str = ""):
        file_path = os.path.join(admin_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(admin_dir, "index.html"))

# Static files (widget JS, etc.)
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
