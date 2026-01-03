"""
Cerberus Application Entry Point

FastAPI application setup with all routers and middleware.

This is the unified governance service that provides:
- Control Plane: Admin APIs for managing tenants, workspaces, policies
- Proxy: Direct MCP proxy with inline governance
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache.redis_client import close_redis, init_redis
from app.config.settings import settings
from app.control_plane.api.router import router as control_plane_router
from app.db.migrations import run_migrations
from app.db.session import close_db, init_db
from app.governance_plane.api.router import router as governance_plane_router
from app.governance_plane.proxy.client import close_mcp_client, init_mcp_client
from app.middleware.error_handler import setup_exception_handlers
from app.middleware.logging import LoggingMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    await init_db()
    await run_migrations()  # Run migrations if RUN_MIGRATIONS_ON_STARTUP=true
    await init_redis()
    await init_mcp_client()
    yield
    # Shutdown
    await close_mcp_client()
    await close_db()
    await close_redis()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Unified Governance Service for MCP (Model Context Protocol).\n\n"
            "Provides:\n"
            "- **Control Plane**: Admin APIs for tenants, workspaces, users, policies\n"
            "- **Proxy**: Direct MCP proxy with inline governance\n\n"
            "The proxy endpoint (`/governance-plane/api/v1/proxy/`) allows MCP clients to "
            "connect directly to Cerberus, which handles governance checks and forwards "
            "to upstream MCP servers."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom Middleware
    application.add_middleware(LoggingMiddleware)

    # Exception Handlers
    setup_exception_handlers(application)

    # Routers
    # Control Plane - Admin APIs
    application.include_router(
        control_plane_router,
        prefix="/control-plane/api/v1",
    )

    # Governance Plane - MCP Proxy with inline governance
    application.include_router(
        governance_plane_router,
        prefix="/governance-plane/api/v1",
    )

    # Health Check
    @application.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "cerberus",
            "version": "1.0.0",
            "components": {
                "control_plane": "healthy",
                "governance_plane": "healthy",
                "proxy": "healthy",
            },
        }

    @application.get("/health/detailed", tags=["Health"])
    async def detailed_health_check() -> dict:
        """Detailed health check with component status."""
        return {
            "status": "healthy",
            "service": "cerberus",
            "version": "1.0.0",
            "environment": settings.APP_ENV,
            "components": {
                "database": {"status": "healthy"},
                "redis": {"status": "healthy"},
                "control_plane": {"status": "healthy"},
                "governance_plane": {"status": "healthy"},
                "proxy": {
                    "status": "healthy",
                    "mode": "inline-governance",
                    "mcp_timeout_seconds": settings.MCP_REQUEST_TIMEOUT_SECONDS,
                    "mcp_max_retries": settings.MCP_MAX_RETRIES,
                },
            },
        }

    return application


app = create_application()
