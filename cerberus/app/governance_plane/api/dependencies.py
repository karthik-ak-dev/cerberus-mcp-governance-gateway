"""
Governance Plane API Dependencies

Agent access key validation for gateway requests.
Derives all context (organisation, workspace, agent) from the key.

Access Control:
- Agent permissions are controlled by Policies and Guardrails
- No "scopes" - the RBAC guardrail controls tool access
- Rate limiting and PII guardrails control other aspects
"""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidAgentAccessKeyError
from app.core.logging import logger
from app.core.security import hash_api_key
from app.db.repositories.agent_access_repository import AgentAccessRepository
from app.db.session import get_db
from app.schemas.agent_access import AgentAccessContext


async def validate_access_key(
    authorization: Annotated[str | None, Header()] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> AgentAccessContext:
    """Validate agent access key from Authorization header.

    Derives all context from the key:
    - agent_access_id: From the key
    - mcp_server_workspace_id: From the key
    - organisation_id: From the workspace relationship
    - mcp_server_url: From the workspace
    - agent_name: From the key

    Note: No scopes - permissions are controlled by Policies and Guardrails.
    The RBAC guardrail controls tool access, rate limiting guardrail
    controls request limits, etc.

    Args:
        authorization: Authorization header value
        db: Database session

    Returns:
        AgentAccessContext with all derived values

    Raises:
        InvalidAgentAccessKeyError: If key is missing or invalid
    """
    logger.info("Validating access key", has_authorization=authorization is not None)

    if not authorization:
        logger.warning("Access key validation failed: missing authorization header")
        raise InvalidAgentAccessKeyError()

    if not authorization.startswith("Bearer "):
        logger.warning("Access key validation failed: invalid authorization format")
        raise InvalidAgentAccessKeyError()

    token = authorization[7:]  # Remove "Bearer " prefix

    # Hash the key to lookup
    key_hash = hash_api_key(token)
    logger.info("Looking up access key by hash")

    # Look up the key with relationships eagerly loaded
    repo = AgentAccessRepository(db)
    key_record = await repo.get_valid_key_with_context(key_hash)

    if not key_record:
        logger.warning("Access key validation failed: key not found or inactive")
        raise InvalidAgentAccessKeyError()

    # Validate workspace relationship is loaded
    if not key_record.mcp_server_workspace:
        logger.warning(
            "Access key validation failed: workspace not found",
            agent_access_id=str(key_record.id),
        )
        raise InvalidAgentAccessKeyError("Agent workspace not found")

    # Update usage stats
    await repo.update_usage(key_record.id)

    logger.info(
        "Access key validated successfully",
        agent_access_id=str(key_record.id),
        agent_name=key_record.name,
        organisation_id=str(key_record.mcp_server_workspace.organisation_id),
        mcp_server_workspace_id=str(key_record.mcp_server_workspace_id),
        mcp_server_url=key_record.mcp_server_workspace.mcp_server_url,
    )

    # Return context derived entirely from the key
    # Note: No scopes - permissions controlled by Policies and Guardrails
    return AgentAccessContext(
        agent_access_id=str(key_record.id),
        agent_name=key_record.name,
        mcp_server_workspace_id=str(key_record.mcp_server_workspace_id),
        organisation_id=str(key_record.mcp_server_workspace.organisation_id),
        mcp_server_url=key_record.mcp_server_workspace.mcp_server_url,
    )


# Type aliases for common dependency patterns
ValidatedAccessKey = Annotated[AgentAccessContext, Depends(validate_access_key)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
