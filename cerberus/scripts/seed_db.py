#!/usr/bin/env python3
"""
Database Seeder

Creates initial data for development and testing.
Cleans existing seed data before inserting fresh data.

Run from project root:
    python -m scripts.seed_db
"""

import asyncio

from sqlalchemy import text

from app.db.session import AsyncSessionLocal, init_db
from app.db.repositories import (
    GuardrailRepository,
    OrganisationRepository,
    McpServerWorkspaceRepository,
    UserRepository,
)
from app.core.security import hash_password
from app.core.logging import logger
from app.config.constants import (
    GUARDRAIL_CATEGORIES,
    GUARDRAIL_DEFAULTS,
    GUARDRAIL_METADATA,
    GuardrailType,
    SubscriptionTier,
    get_tier_defaults,
)


async def clean_seed_data(session) -> None:
    """Remove existing seed data before reseeding."""
    logger.info("Cleaning existing seed data...")

    # Delete in correct order due to foreign key constraints
    tables = [
        "audit_logs",
        "agent_accesses",
        "policies",
        "users",
        "mcp_server_workspaces",
        "organisations",
        "guardrails",
    ]

    for table in tables:
        await session.execute(text(f"DELETE FROM {table}"))
        logger.info("Cleared table: %s", table)

    await session.commit()
    logger.info("Seed data cleaned successfully")


async def seed_database() -> None:
    """Seed the database with initial data."""
    logger.info("Starting database seeding...")

    await init_db()

    async with AsyncSessionLocal() as session:
        # Clean existing data first
        await clean_seed_data(session)

        # Create repositories
        guardrail_repo = GuardrailRepository(session)
        org_repo = OrganisationRepository(session)
        workspace_repo = McpServerWorkspaceRepository(session)
        user_repo = UserRepository(session)

        # Seed guardrails using constants (GUARDRAIL_CATEGORIES, DEFAULTS, METADATA)
        logger.info("Seeding guardrails...")
        for guardrail_type in GuardrailType:
            metadata = GUARDRAIL_METADATA.get(guardrail_type, {})
            default_config = GUARDRAIL_DEFAULTS.get(guardrail_type, {})
            category = GUARDRAIL_CATEGORIES.get(guardrail_type)

            if not category:
                logger.warning(
                    "No category defined for guardrail type: %s", guardrail_type.value
                )
                continue

            guardrail = await guardrail_repo.create(
                guardrail_type=guardrail_type.value,
                display_name=metadata.get("display_name", guardrail_type.value),
                description=metadata.get("description"),
                category=category.value,
                default_config=default_config,
                is_active=True,
            )
            logger.info("Created guardrail: %s", guardrail.display_name)

        # Create demo organisation with DEFAULT tier settings
        org = await org_repo.create(
            name="Demo Organization",
            slug="demo",
            description="Demo organisation for testing",
            subscription_tier=SubscriptionTier.DEFAULT.value,
            settings=get_tier_defaults(SubscriptionTier.DEFAULT),
        )
        logger.info("Created organisation: %s", org.name)

        # Create workspaces
        prod_workspace = await workspace_repo.create(
            organisation_id=org.id,
            name="Production",
            slug="prod",
            mcp_server_url="http://localhost:3000",
            environment_type="production",
            settings={"fail_mode": "closed", "log_level": "verbose"},
        )
        logger.info("Created workspace: %s", prod_workspace.name)

        dev_workspace = await workspace_repo.create(
            organisation_id=org.id,
            name="Development",
            slug="dev",
            mcp_server_url="http://localhost:3001",
            environment_type="development",
            settings={"fail_mode": "open", "log_level": "standard"},
        )
        logger.info("Created workspace: %s", dev_workspace.name)

        # Create super admin user (platform-level, no organisation)
        super_admin = await user_repo.create(
            organisation_id=None,  # SuperAdmins don't belong to any org
            email="superadmin@cerberus.com",
            display_name="Super Admin",
            role="super_admin",
            password_hash=hash_password("superadmin123"),
        )
        logger.info("Created super admin: %s (no org)", super_admin.display_name)

        # Create org admin user
        admin = await user_repo.create(
            organisation_id=org.id,
            email="admin@demo.com",
            display_name="Admin User",
            role="org_admin",
            password_hash=hash_password("admin123"),
        )
        logger.info("Created user: %s", admin.display_name)

        # Create viewer user
        viewer = await user_repo.create(
            organisation_id=org.id,
            email="viewer@demo.com",
            display_name="Viewer User",
            role="org_viewer",
            password_hash=hash_password("viewer123"),
        )
        logger.info("Created user: %s", viewer.display_name)

        await session.commit()

    logger.info("Database seeding completed!")


if __name__ == "__main__":
    asyncio.run(seed_database())
