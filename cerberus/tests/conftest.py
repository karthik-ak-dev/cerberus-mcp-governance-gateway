"""
Pytest Fixtures for Integration Testing

Provides fixtures for testing with real PostgreSQL database and HTTP client.

Usage:
    Run tests against the Docker Compose test database:

    1. Start test services:
       docker compose -f docker/docker-compose.test.yml up -d

    2. Run tests:
       pytest tests/integration/ -v

    Or use the default SQLite for quick local tests:
       TEST_USE_SQLITE=true pytest tests/ -v
"""

# pylint: disable=redefined-outer-name,import-outside-toplevel

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.constants import (
    GUARDRAIL_CATEGORIES,
    GUARDRAIL_DEFAULTS,
    GUARDRAIL_METADATA,
    GuardrailType,
    SubscriptionTier,
    UserRole,
    get_tier_defaults,
)
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.base import Base


# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# Use PostgreSQL for integration tests, SQLite for quick unit tests
USE_SQLITE = os.getenv("TEST_USE_SQLITE", "false").lower() == "true"

if USE_SQLITE:
    TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
else:
    # PostgreSQL test database (use docker-compose.test.yml)
    TEST_DATABASE_URL = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/cerberus_test",
    )


# =============================================================================
# EVENT LOOP
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with fresh schema.

    Creates all tables before test, drops them after.
    Each test gets a clean database state.
    """
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    test_session_local = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with test_session_local() as session:
        yield session

    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with database session override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================================
# SEED DATA FIXTURES
# =============================================================================


@pytest_asyncio.fixture
async def seeded_guardrails(test_db: AsyncSession) -> list:
    """Seed all guardrail definitions into the test database."""
    from app.db.repositories import GuardrailRepository

    repo = GuardrailRepository(test_db)
    guardrails = []

    for guardrail_type in GuardrailType:
        metadata = GUARDRAIL_METADATA.get(guardrail_type, {})
        default_config = GUARDRAIL_DEFAULTS.get(guardrail_type, {})
        category = GUARDRAIL_CATEGORIES.get(guardrail_type)

        if not category:
            continue

        guardrail = await repo.create(
            guardrail_type=guardrail_type.value,
            display_name=metadata.get("display_name", guardrail_type.value),
            description=metadata.get("description"),
            category=category.value,
            default_config=default_config,
            is_active=True,
        )
        guardrails.append(guardrail)

    await test_db.commit()
    return guardrails


@pytest_asyncio.fixture
async def test_organisation(test_db: AsyncSession):
    """Create a test organisation."""
    from app.db.repositories import OrganisationRepository

    repo = OrganisationRepository(test_db)
    tier_defaults = get_tier_defaults(SubscriptionTier.DEFAULT)

    org = await repo.create(
        name="Test Organization",
        subscription_tier=SubscriptionTier.DEFAULT.value,
        settings=tier_defaults,
    )
    await test_db.commit()
    return org


@pytest_asyncio.fixture
async def test_workspace(test_db: AsyncSession, test_organisation):
    """Create a test MCP server workspace."""
    from app.db.repositories import McpServerWorkspaceRepository

    repo = McpServerWorkspaceRepository(test_db)

    workspace = await repo.create(
        organisation_id=test_organisation.id,
        name="Test Workspace",
        slug="test-workspace",
        environment="development",
        mcp_endpoint_url="http://localhost:8080/mcp",
    )
    await test_db.commit()
    return workspace


@pytest_asyncio.fixture
async def test_agent_access(test_db: AsyncSession, test_workspace):
    """Create a test agent access."""
    from app.db.repositories import AgentAccessRepository

    repo = AgentAccessRepository(test_db)

    agent_access, _key = await repo.create(
        mcp_server_workspace_id=test_workspace.id,
        name="Test Agent",
        description="Test agent for integration tests",
    )
    await test_db.commit()
    return agent_access


# =============================================================================
# USER & AUTH FIXTURES
# =============================================================================


@pytest_asyncio.fixture
async def super_admin_user(test_db: AsyncSession):
    """Create a super admin user."""
    from app.db.repositories import UserRepository

    repo = UserRepository(test_db)

    user = await repo.create(
        email="superadmin@test.com",
        password_hash=hash_password("testpassword123"),
        display_name="Super Admin",
        role=UserRole.SUPER_ADMIN.value,
        organisation_id=None,  # Super admin has no org
    )
    await test_db.commit()
    return user


@pytest_asyncio.fixture
async def org_admin_user(test_db: AsyncSession, test_organisation):
    """Create an org admin user."""
    from app.db.repositories import UserRepository

    repo = UserRepository(test_db)

    user = await repo.create(
        email="orgadmin@test.com",
        password_hash=hash_password("testpassword123"),
        display_name="Org Admin",
        role=UserRole.ORG_ADMIN.value,
        organisation_id=test_organisation.id,
    )
    await test_db.commit()
    return user


@pytest_asyncio.fixture
async def org_viewer_user(test_db: AsyncSession, test_organisation):
    """Create an org viewer user."""
    from app.db.repositories import UserRepository

    repo = UserRepository(test_db)

    user = await repo.create(
        email="orgviewer@test.com",
        password_hash=hash_password("testpassword123"),
        display_name="Org Viewer",
        role=UserRole.ORG_VIEWER.value,
        organisation_id=test_organisation.id,
    )
    await test_db.commit()
    return user


@pytest_asyncio.fixture
async def other_org_admin_user(test_db: AsyncSession):
    """Create an admin user for a different organisation."""
    from app.db.repositories import OrganisationRepository, UserRepository

    # Create different org
    org_repo = OrganisationRepository(test_db)
    tier_defaults = get_tier_defaults(SubscriptionTier.DEFAULT)

    other_org = await org_repo.create(
        name="Other Organization",
        subscription_tier=SubscriptionTier.DEFAULT.value,
        settings=tier_defaults,
    )

    # Create user for that org
    user_repo = UserRepository(test_db)
    user = await user_repo.create(
        email="otheradmin@test.com",
        password_hash=hash_password("testpassword123"),
        display_name="Other Org Admin",
        role=UserRole.ORG_ADMIN.value,
        organisation_id=other_org.id,
    )
    await test_db.commit()
    return user


# =============================================================================
# AUTH TOKEN FIXTURES
# =============================================================================


def _create_auth_headers(user) -> dict[str, str]:
    """Create authorization headers for a user."""
    token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "organisation_id": str(user.organisation_id) if user.organisation_id else None,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def super_admin_headers(super_admin_user) -> dict[str, str]:
    """Get auth headers for super admin."""
    return _create_auth_headers(super_admin_user)


@pytest.fixture
def org_admin_headers(org_admin_user) -> dict[str, str]:
    """Get auth headers for org admin."""
    return _create_auth_headers(org_admin_user)


@pytest.fixture
def org_viewer_headers(org_viewer_user) -> dict[str, str]:
    """Get auth headers for org viewer."""
    return _create_auth_headers(org_viewer_user)


@pytest.fixture
def other_org_admin_headers(other_org_admin_user) -> dict[str, str]:
    """Get auth headers for other org admin."""
    return _create_auth_headers(other_org_admin_user)


# =============================================================================
# HELPER FIXTURES
# =============================================================================


@pytest.fixture
def make_uuid():
    """Factory to create UUIDs."""
    return lambda: str(uuid4())


@pytest.fixture
def future_datetime():
    """Get a datetime 1 hour in the future."""
    return datetime.now(timezone.utc) + timedelta(hours=1)


@pytest.fixture
def past_datetime():
    """Get a datetime 1 hour in the past."""
    return datetime.now(timezone.utc) - timedelta(hours=1)
