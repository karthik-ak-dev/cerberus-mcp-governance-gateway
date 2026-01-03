"""
Database Module

This module provides database connectivity and session management for Cerberus.

Architecture Overview:
======================
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DATABASE LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   FastAPI Route                                                             │
│       │                                                                     │
│       │  Dependency Injection: get_db()                                     │
│       ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │              AsyncSession (from session.py)                 │          │
│   │                                                             │          │
│   │  - One session per request                                  │          │
│   │  - Auto-commit on success                                   │          │
│   │  - Auto-rollback on exception                               │          │
│   │  - Auto-close when request ends                             │          │
│   └─────────────────────────────────────────────────────────────┘          │
│       │                                                                     │
│       │  Passed to Repository                                               │
│       ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │              Repository (from repositories/)                │          │
│   │                                                             │          │
│   │  - OrganisationRepository                                   │          │
│   │  - McpServerWorkspaceRepository                             │          │
│   │  - UserRepository                                           │          │
│   │  - PolicyRepository                                         │          │
│   │  - GuardrailRepository                                      │          │
│   │  - AgentAccessRepository                                    │          │
│   │  - AuditLogRepository                                       │          │
│   └─────────────────────────────────────────────────────────────┘          │
│       │                                                                     │
│       │  SQL Queries                                                        │
│       ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────┐          │
│   │              PostgreSQL Database                            │          │
│   └─────────────────────────────────────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Components:
===========
- session.py: Database engine, session factory, and lifecycle functions
- repositories/: Repository pattern implementations for each model

Usage in FastAPI:
=================
    from fastapi import Depends
    from app.db import get_db
    from app.db.repositories import OrganisationRepository

    @app.get("/organisations/{slug}")
    async def get_organisation(slug: str, db: AsyncSession = Depends(get_db)):
        repo = OrganisationRepository(db)
        organisation = await repo.get_by_slug(slug)
        return organisation
"""

from app.db.session import (
    get_db,
    init_db,
    close_db,
    AsyncSessionLocal,
)

__all__ = [
    # Session management
    "get_db",  # FastAPI dependency for getting a database session
    "init_db",  # Initialize database on app startup
    "close_db",  # Close database on app shutdown
    "AsyncSessionLocal",  # Session factory for manual session creation
]
