"""
Database Session Management

This module configures the async SQLAlchemy engine and session factory.
It provides the core database connectivity for the entire application.

Key Concepts:
=============

1. ENGINE: The database connection manager
   - Maintains a pool of database connections
   - Handles connection lifecycle (create, reuse, close)
   - Configured once at application startup

2. SESSION: A unit of work with the database
   - One session per request (typically)
   - Tracks changes to objects (dirty, new, deleted)
   - Commits or rolls back as a transaction

3. SESSION FACTORY: Creates new sessions
   - AsyncSessionLocal() creates a new session
   - Sessions are NOT thread-safe (one per request)

Connection Pool:
================
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONNECTION POOL                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │                     SQLAlchemy Engine                        │          │
│   ├─────────────────────────────────────────────────────────────┤          │
│   │                                                              │          │
│   │   Pool of Connections:                                       │          │
│   │   ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐    pool_size = 5       │          │
│   │   │ C1 │ │ C2 │ │ C3 │ │ C4 │ │ C5 │                        │          │
│   │   └────┘ └────┘ └────┘ └────┘ └────┘                        │          │
│   │                                                              │          │
│   │   Overflow (temporary):                                      │          │
│   │   ┌────┐ ┌────┐ ┌────┐                  max_overflow = 10   │          │
│   │   │ O1 │ │ O2 │ │ O3 │ ...                                  │          │
│   │   └────┘ └────┘ └────┘                                      │          │
│   │                                                              │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
│   Total max connections = pool_size + max_overflow = 15                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Request Lifecycle:
==================
    1. Request arrives at FastAPI endpoint
    2. get_db() dependency is called
    3. New AsyncSession created from pool
    4. Session yielded to route handler
    5. Route handler uses session via repositories
    6. On success: session.commit()
    7. On exception: session.rollback()
    8. Finally: session.close() (returns connection to pool)

Configuration:
==============
    DATABASE_URL: postgresql+asyncpg://user:pass@host:5432/dbname
    DATABASE_POOL_SIZE: Number of persistent connections (default: 5)
    DATABASE_MAX_OVERFLOW: Extra connections under load (default: 10)
"""

from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import settings
from app.core.logging import logger


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
#
# The engine is the starting point for any SQLAlchemy application.
# It's a factory for database connections and manages the connection pool.
#
# Key parameters:
# - echo: Log all SQL statements (useful for debugging, disable in production)
# - pool_size: Number of connections to keep open permanently
# - max_overflow: Extra connections allowed when pool is exhausted
# - pool_pre_ping: Test connections before using (handles stale connections)

engine = create_async_engine(
    settings.DATABASE_URL,
    # Log SQL statements if DEBUG mode is enabled
    # Example output: "SELECT * FROM tenants WHERE slug = 'acme-corp'"
    echo=settings.DEBUG,
    # Number of permanent connections in the pool
    # These stay open even when idle
    # Default: 5 connections
    pool_size=settings.DATABASE_POOL_SIZE,
    # Additional connections allowed when pool is full
    # These are closed when no longer needed
    # Total max = pool_size + max_overflow
    # Default: 10 overflow connections
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    # Check if connection is still alive before using it
    # Prevents "connection closed" errors after database restarts
    # Small performance cost but worth the reliability
    pool_pre_ping=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION FACTORY
# ═══════════════════════════════════════════════════════════════════════════════
#
# async_sessionmaker creates a factory that produces AsyncSession instances.
# Each session represents a single "conversation" with the database.
#
# Key parameters:
# - expire_on_commit=False: Objects remain usable after commit
#   (otherwise accessing attributes would trigger new queries)
# - autocommit=False: We manually control when to commit
# - autoflush=False: We manually control when to flush changes

AsyncSessionLocal = async_sessionmaker(
    # Bind to our engine (connection source)
    bind=engine,
    # Create AsyncSession instances (not regular Session)
    class_=AsyncSession,
    # Don't expire objects after commit
    # This allows: commit() then still access object.name
    # Without this: commit() then access object.name → new query
    expire_on_commit=False,
    # Don't auto-commit after each statement
    # We want explicit transaction control
    autocommit=False,
    # Don't auto-flush before queries
    # Gives us more control over when SQL is executed
    autoflush=False,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI DEPENDENCY: get_db()
# ═══════════════════════════════════════════════════════════════════════════════
#
# This is a FastAPI dependency that provides a database session to route handlers.
# It handles the full lifecycle: create, yield, commit/rollback, close.
#
# Usage in routes:
#     @app.get("/tenants/{id}")
#     async def get_tenant(id: UUID, db: AsyncSession = Depends(get_db)):
#         repo = TenantRepository(db)
#         return await repo.get(id)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Creates a new session for each request and handles cleanup.

    Lifecycle:
        1. Create new session from pool
        2. Yield session to route handler
        3. If no exception: commit changes
        4. If exception: rollback changes
        5. Always: close session (return connection to pool)

    Yields:
        AsyncSession: Database session for the current request

    Example:
        @app.post("/tenants")
        async def create_tenant(
            data: TenantCreate,
            db: AsyncSession = Depends(get_db)
        ):
            repo = TenantRepository(db)
            tenant = await repo.create(**data.dict())
            return tenant  # Session auto-commits after return
    """
    # Create new session from the factory
    async with AsyncSessionLocal() as session:
        try:
            # Yield session to the route handler
            yield session

            # If we get here (no exception), commit the transaction
            # This saves all changes made during the request
            await session.commit()

        except Exception:
            # If any exception occurred, rollback all changes
            # This ensures database consistency
            await session.rollback()

            # Re-raise the exception so FastAPI can handle it
            raise

        finally:
            # Always close the session
            # This returns the connection to the pool
            await session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# LIFECYCLE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
#
# These functions are called during application startup and shutdown.
# They're typically registered in main.py:
#
#     app = FastAPI()
#
#     @app.on_event("startup")
#     async def startup():
#         await init_db()
#
#     @app.on_event("shutdown")
#     async def shutdown():
#         await close_db()


async def init_db() -> None:
    """
    Initialize database connection on application startup.

    This function:
    1. Tests the database connection
    2. Logs success or failure
    3. Raises exception if connection fails (prevents app from starting)

    Should be called during FastAPI startup event.

    Raises:
        Exception: If database connection fails
    """
    logger.info("Initializing database connection")
    try:
        # Test the connection by executing a simple query
        async with engine.begin() as conn:
            # Run a simple query to verify connection works
            await conn.execute(text("SELECT 1"))

        logger.info("Database connection established successfully")

    except Exception as e:
        # Log the error with details
        logger.error(f"Failed to connect to database: {str(e)}")

        # Re-raise to prevent application from starting
        # Better to fail fast than run without a database
        raise


async def close_db() -> None:
    """
    Close database connection on application shutdown.

    This function:
    1. Closes all connections in the pool
    2. Releases all resources
    3. Logs the shutdown

    Should be called during FastAPI shutdown event.
    Important for clean shutdown and resource cleanup.
    """
    logger.info("Closing database connection")

    # Dispose of the engine, closing all pooled connections
    await engine.dispose()

    logger.info("Database connection closed successfully")
