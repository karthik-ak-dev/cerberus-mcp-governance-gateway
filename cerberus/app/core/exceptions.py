"""
Custom Exceptions

Application-specific exceptions with HTTP status codes.
"""

from typing import Any, Optional


class CerberusException(Exception):
    """Base exception for all Cerberus errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


class AuthenticationError(CerberusException):
    """Authentication failed error."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            details=details,
        )


class AuthorizationError(CerberusException):
    """Authorization failed error."""

    def __init__(
        self,
        message: str = "Access denied",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            details=details,
        )


class NotFoundError(CerberusException):
    """Resource not found error."""

    def __init__(
        self,
        resource: str,
        resource_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id '{resource_id}' not found"
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            details=details,
        )


class ValidationError(CerberusException):
    """Validation error."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class RateLimitExceededError(CerberusException):
    """Rate limit exceeded error."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        extra_details = details or {}
        if retry_after:
            extra_details["retry_after_seconds"] = retry_after
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details=extra_details,
        )


class PolicyViolationError(CerberusException):
    """Policy violation error (guardrail triggered)."""

    def __init__(
        self,
        message: str,
        guardrail_type: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        extra_details = details or {}
        extra_details["guardrail_type"] = guardrail_type
        super().__init__(
            message=message,
            status_code=403,
            error_code="POLICY_VIOLATION",
            details=extra_details,
        )


class OrganisationNotFoundError(NotFoundError):
    """Organisation not found error."""

    def __init__(self, organisation_id: str) -> None:
        super().__init__(resource="Organisation", resource_id=organisation_id)


class McpServerWorkspaceNotFoundError(NotFoundError):
    """MCP Server Workspace not found error."""

    def __init__(self, mcp_server_workspace_id: str) -> None:
        super().__init__(
            resource="MCP Server Workspace", resource_id=mcp_server_workspace_id
        )


class UserNotFoundError(NotFoundError):
    """User not found error."""

    def __init__(self, user_id: str) -> None:
        super().__init__(resource="User", resource_id=user_id)


class PolicyNotFoundError(NotFoundError):
    """Policy not found error."""

    def __init__(self, policy_id: str) -> None:
        super().__init__(resource="Policy", resource_id=policy_id)


class AgentAccessNotFoundError(NotFoundError):
    """Agent Access not found error."""

    def __init__(self, agent_access_id: str) -> None:
        super().__init__(resource="Agent Access", resource_id=agent_access_id)


class InvalidAgentAccessKeyError(AuthenticationError):
    """Invalid agent access key error."""

    def __init__(self, message: str = "Invalid or expired agent access key") -> None:
        super().__init__(message=message)


class ServiceUnavailableError(CerberusException):
    """Service temporarily unavailable error."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            details=details,
        )


class ConflictError(CerberusException):
    """Resource conflict error."""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            details=details,
        )


# =============================================================================
# Governance Plane Exceptions
# =============================================================================


class GuardrailError(CerberusException):
    """Base exception for guardrail errors."""

    def __init__(
        self,
        message: str,
        guardrail_type: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        extra_details = details or {}
        extra_details["guardrail_type"] = guardrail_type
        super().__init__(
            message=message,
            status_code=500,
            error_code="GUARDRAIL_ERROR",
            details=extra_details,
        )
        self.guardrail_type = guardrail_type


class GuardrailConfigurationError(GuardrailError):
    """Guardrail configuration is invalid."""

    def __init__(
        self,
        message: str,
        guardrail_type: str,
        config_key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        extra_details = details or {}
        if config_key:
            extra_details["config_key"] = config_key
        super().__init__(
            message=message,
            guardrail_type=guardrail_type,
            details=extra_details,
        )
        self.error_code = "GUARDRAIL_CONFIG_ERROR"


class GuardrailExecutionError(GuardrailError):
    """Guardrail execution failed."""

    def __init__(
        self,
        message: str,
        guardrail_type: str,
        original_error: Optional[Exception] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        extra_details = details or {}
        if original_error:
            extra_details["original_error"] = str(original_error)
            extra_details["error_type"] = type(original_error).__name__
        super().__init__(
            message=message,
            guardrail_type=guardrail_type,
            details=extra_details,
        )
        self.original_error = original_error
        self.error_code = "GUARDRAIL_EXECUTION_ERROR"


class GuardrailNotFoundError(CerberusException):
    """Guardrail type not registered."""

    def __init__(self, guardrail_type: str) -> None:
        super().__init__(
            message=f"Guardrail '{guardrail_type}' is not registered",
            status_code=500,
            error_code="GUARDRAIL_NOT_FOUND",
            details={"guardrail_type": guardrail_type},
        )


class UpstreamError(CerberusException):
    """Upstream MCP server error."""

    def __init__(
        self,
        message: str,
        upstream_url: Optional[str] = None,
        upstream_status: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        extra_details = details or {}
        if upstream_url:
            extra_details["upstream_url"] = upstream_url
        if upstream_status:
            extra_details["upstream_status"] = upstream_status
        super().__init__(
            message=message,
            status_code=502,
            error_code="UPSTREAM_ERROR",
            details=extra_details,
        )
