"""
Database Migration Runner

Runs Alembic migrations on application startup with distributed locking.
Uses PostgreSQL advisory locks to ensure only one instance runs migrations
at a time, preventing race conditions in multi-instance deployments.

Usage:
    Set RUN_MIGRATIONS_ON_STARTUP=true in environment variables.
    Migrations will run automatically during app startup.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError

from app.config.settings import settings
from app.core.logging import logger
from app.db.session import engine

# Advisory lock ID for migrations (arbitrary unique number)
# This ensures only one instance runs migrations at a time
MIGRATION_LOCK_ID = 123456789


def get_alembic_config() -> Config:
    """Get Alembic configuration.

    Returns:
        Alembic Config object pointing to the project's alembic.ini
    """
    # Find the project root (where alembic.ini lives)
    # This file is at app/db/migrations.py, so go up 3 levels
    project_root = Path(__file__).parent.parent.parent
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

    config = Config(str(alembic_ini))

    # Override the database URL from settings
    # This ensures we use the same URL as the app, including any env overrides
    # Convert async URL to sync URL for alembic (replace +asyncpg with standard driver)
    sync_url = str(settings.DATABASE_URL).replace("+asyncpg", "")
    config.set_main_option("sqlalchemy.url", sync_url)

    return config


async def acquire_migration_lock() -> bool:
    """Try to acquire PostgreSQL advisory lock for migrations.

    Advisory locks are session-level locks that don't block regular queries.
    pg_try_advisory_lock returns immediately (non-blocking).

    Returns:
        True if lock acquired, False if another process holds it
    """
    async with engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT pg_try_advisory_lock({MIGRATION_LOCK_ID})")
        )
        row = result.fetchone()
        return row[0] if row else False


async def release_migration_lock() -> None:
    """Release the PostgreSQL advisory lock."""
    async with engine.connect() as conn:
        await conn.execute(
            text(f"SELECT pg_advisory_unlock({MIGRATION_LOCK_ID})")
        )
        await conn.commit()


def _run_alembic_upgrade_sync() -> None:
    """Run alembic upgrade head synchronously in a separate thread.

    This must run in a separate thread because alembic's env.py uses
    asyncio.run(), which cannot be called from within an existing event loop.
    Running in a thread gives alembic its own event loop.
    """
    config = get_alembic_config()
    command.upgrade(config, "head")


async def run_alembic_upgrade() -> None:
    """Run alembic upgrade head in a thread pool.

    Alembic's env.py uses asyncio.run() internally, which conflicts with
    FastAPI's already-running event loop. Running in a thread pool executor
    allows alembic to create its own event loop.
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        await loop.run_in_executor(executor, _run_alembic_upgrade_sync)


async def run_migrations() -> None:
    """Run database migrations with distributed locking.

    This function:
    1. Attempts to acquire a PostgreSQL advisory lock
    2. If acquired, runs alembic upgrade head
    3. Releases the lock when done
    4. If lock not acquired, waits and retries (another instance is migrating)

    The advisory lock ensures that in a multi-instance deployment (like App Runner
    with multiple containers), only one instance runs migrations while others wait.
    """
    if not settings.RUN_MIGRATIONS_ON_STARTUP:
        logger.debug("RUN_MIGRATIONS_ON_STARTUP is disabled, skipping migrations")
        return

    logger.info("Attempting to run database migrations...")

    max_attempts = 30  # Wait up to 30 seconds for lock
    attempt = 0

    while attempt < max_attempts:
        try:
            lock_acquired = await acquire_migration_lock()

            if lock_acquired:
                logger.info("Migration lock acquired, running migrations...")
                try:
                    # Run migrations in a thread pool (alembic uses asyncio.run internally)
                    await run_alembic_upgrade()
                    logger.info("Database migrations completed successfully")
                    return
                finally:
                    await release_migration_lock()
                    logger.debug("Migration lock released")
            else:
                # Another instance is running migrations, wait and check again
                attempt += 1
                logger.info(
                    f"Migration lock held by another instance, waiting... "
                    f"(attempt {attempt}/{max_attempts})"
                )
                await asyncio.sleep(1)

        except (SQLAlchemyError, CommandError, OSError) as e:
            logger.error(f"Migration failed: {e}")
            # Try to release lock if we somehow acquired it
            try:
                await release_migration_lock()
            except SQLAlchemyError:
                pass
            raise

    logger.warning(
        "Could not acquire migration lock after max attempts. "
        "Assuming another instance completed migrations."
    )
