"""
Application Constants

Centralized constants used throughout the application.
"""

import re
from enum import Enum


class FailMode(str, Enum):
    """Gateway fail mode when governance service is unreachable."""

    OPEN = "open"  # Allow requests when service is down
    CLOSED = "closed"  # Block requests when service is down


class Direction(str, Enum):
    """Message direction for governance decisions."""

    REQUEST = "request"
    RESPONSE = "response"


class Transport(str, Enum):
    """Transport protocol for MCP communication."""

    HTTP = "http"
    STDIO = "stdio"


class DecisionAction(str, Enum):
    """Possible decision actions."""

    ALLOW = "allow"
    BLOCK_REQUEST = "block_request"
    BLOCK_RESPONSE = "block_response"
    MODIFY = "modify"
    LOG_ONLY = "log_only"
    THROTTLE = "throttle"


class Severity(str, Enum):
    """Event severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class UserRole(str, Enum):
    """
    User roles for dashboard access.

    Simplified for MVP:
    - super_admin: Platform admin (system administrators)
    - org_admin: Full admin for their organisation (manage workspaces, agents, policies)
    - org_viewer: Read-only access to view dashboards and logs
    """

    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    ORG_VIEWER = "org_viewer"


class EnvironmentType(str, Enum):
    """MCP Server Workspace environment types."""

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"


class SubscriptionTier(str, Enum):
    """Organisation subscription tiers."""

    DEFAULT = "default"


class LogLevel(str, Enum):
    """Logging verbosity levels."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    VERBOSE = "verbose"


class SortOrder(str, Enum):
    """Sort order for queries."""

    ASC = "asc"
    DESC = "desc"


class ScanDirection(str, Enum):
    """Direction to scan for guardrail checks."""

    REQUEST = "request"
    RESPONSE = "response"
    BOTH = "both"


# =============================================================================
# GUARDRAIL TYPES (MVP - Per PRD)
# =============================================================================


class GuardrailType(str, Enum):
    """
    Available guardrail types (MVP only).

    4 Categories with granular guardrails:
    1. RBAC - Agent Tool Access Control
    2. PII Detection - Granular per PII type
    3. Content Filter - Block large/structured content
    4. Rate Limiting - Per minute/hour limits
    """

    # RBAC (Agent Tool Access Control)
    RBAC = "rbac"

    # PII Detection (Granular - only types with reliable patterns)
    PII_CREDIT_CARD = "pii_credit_card"
    PII_SSN = "pii_ssn"
    PII_EMAIL = "pii_email"
    PII_PHONE = "pii_phone"
    PII_IP_ADDRESS = "pii_ip_address"

    # Content Filter (Allow/Block Request & Response Content)
    CONTENT_LARGE_DOCUMENTS = "content_large_documents"
    CONTENT_STRUCTURED_DATA = "content_structured_data"
    CONTENT_SOURCE_CODE = "content_source_code"

    # Rate Limiting (Tool Usage Rate Limiting)
    RATE_LIMIT_PER_MINUTE = "rate_limit_per_minute"
    RATE_LIMIT_PER_HOUR = "rate_limit_per_hour"


class GuardrailCategory(str, Enum):
    """Guardrail categories for grouping."""

    RBAC = "rbac"
    PII = "pii"
    CONTENT = "content"
    RATE_LIMIT = "rate_limit"


# Mapping of guardrail types to categories
GUARDRAIL_CATEGORIES: dict[GuardrailType, GuardrailCategory] = {
    GuardrailType.RBAC: GuardrailCategory.RBAC,
    GuardrailType.PII_CREDIT_CARD: GuardrailCategory.PII,
    GuardrailType.PII_SSN: GuardrailCategory.PII,
    GuardrailType.PII_EMAIL: GuardrailCategory.PII,
    GuardrailType.PII_PHONE: GuardrailCategory.PII,
    GuardrailType.PII_IP_ADDRESS: GuardrailCategory.PII,
    GuardrailType.CONTENT_LARGE_DOCUMENTS: GuardrailCategory.CONTENT,
    GuardrailType.CONTENT_STRUCTURED_DATA: GuardrailCategory.CONTENT,
    GuardrailType.CONTENT_SOURCE_CODE: GuardrailCategory.CONTENT,
    GuardrailType.RATE_LIMIT_PER_MINUTE: GuardrailCategory.RATE_LIMIT,
    GuardrailType.RATE_LIMIT_PER_HOUR: GuardrailCategory.RATE_LIMIT,
}


class PolicyAction(str, Enum):
    """Action to take when a policy/guardrail is triggered."""

    BLOCK = "block"
    REDACT = "redact"
    ALERT = "alert"
    AUDIT_ONLY = "audit_only"


class PolicyLevel(str, Enum):
    """Policy hierarchy levels."""

    ORGANISATION = "organisation"
    WORKSPACE = "workspace"
    AGENT = "agent"


class AnalyticsPeriod(str, Enum):
    """Valid analytics period values."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


# =============================================================================
# TIER DEFAULTS
# =============================================================================

# Tier configuration with all settings and allowed guardrails
# When an organisation is created with a tier, these defaults are applied
TIER_DEFAULTS: dict[SubscriptionTier, dict] = {
    SubscriptionTier.DEFAULT: {
        "max_mcp_server_workspaces": 10,
        "max_users": 50,
        "max_agent_accesses_per_workspace": 100,
        "data_retention_days": 90,
        "default_fail_mode": FailMode.CLOSED.value,
        "allowed_guardrails": [gt.value for gt in GuardrailType],
    },
}


def get_tier_defaults(tier: SubscriptionTier) -> dict:
    """Get the default settings for a subscription tier."""
    return TIER_DEFAULTS.get(tier, TIER_DEFAULTS[SubscriptionTier.DEFAULT]).copy()


# =============================================================================
# GUARDRAIL DEFAULT CONFIGURATIONS
# =============================================================================

# Default configurations for each guardrail type
GUARDRAIL_DEFAULTS: dict[GuardrailType, dict] = {
    # RBAC
    GuardrailType.RBAC: {
        "default_action": "deny",
        "allowed_tools": [],
        "denied_tools": [],
    },
    # PII Detection
    GuardrailType.PII_CREDIT_CARD: {
        "direction": "both",
        "redaction_pattern": "[REDACTED:CREDIT_CARD]",
    },
    GuardrailType.PII_SSN: {
        "direction": "both",
        "redaction_pattern": "[REDACTED:SSN]",
    },
    GuardrailType.PII_EMAIL: {
        "direction": "both",
        "redaction_pattern": "[REDACTED:EMAIL]",
    },
    GuardrailType.PII_PHONE: {
        "direction": "both",
        "redaction_pattern": "[REDACTED:PHONE]",
    },
    GuardrailType.PII_IP_ADDRESS: {
        "direction": "both",
        "redaction_pattern": "[REDACTED:IP]",
    },
    # Content Filter
    GuardrailType.CONTENT_LARGE_DOCUMENTS: {
        "direction": "both",
        "max_chars": 10000,
    },
    GuardrailType.CONTENT_STRUCTURED_DATA: {
        "direction": "both",
        "max_rows": 50,
    },
    GuardrailType.CONTENT_SOURCE_CODE: {
        "direction": "both",
        "max_chars": 5000,
    },
    # Rate Limiting
    GuardrailType.RATE_LIMIT_PER_MINUTE: {
        "limit": 60,
    },
    GuardrailType.RATE_LIMIT_PER_HOUR: {
        "limit": 1000,
    },
}


# Guardrail display names and descriptions for seeding
GUARDRAIL_METADATA: dict[GuardrailType, dict] = {
    GuardrailType.RBAC: {
        "display_name": "Agent Tool Access Control",
        "description": "Configure which Tools & Resources are allowed for which Agent",
    },
    GuardrailType.PII_CREDIT_CARD: {
        "display_name": "PII - Credit Card",
        "description": "Detect and handle credit/debit card numbers",
    },
    GuardrailType.PII_SSN: {
        "display_name": "PII - Social Security Number",
        "description": "Detect and handle Social Security Numbers",
    },
    GuardrailType.PII_EMAIL: {
        "display_name": "PII - Email Address",
        "description": "Detect and handle email addresses",
    },
    GuardrailType.PII_PHONE: {
        "display_name": "PII - Phone Number",
        "description": "Detect and handle phone numbers",
    },
    GuardrailType.PII_IP_ADDRESS: {
        "display_name": "PII - IP Address",
        "description": "Detect and handle IP addresses",
    },
    GuardrailType.CONTENT_LARGE_DOCUMENTS: {
        "display_name": "Content - Large Documents",
        "description": "Block documents exceeding size threshold",
    },
    GuardrailType.CONTENT_STRUCTURED_DATA: {
        "display_name": "Content - Structured Data",
        "description": "Block tables/CSVs exceeding row threshold",
    },
    GuardrailType.CONTENT_SOURCE_CODE: {
        "display_name": "Content - Source Code",
        "description": "Block code blocks exceeding size threshold",
    },
    GuardrailType.RATE_LIMIT_PER_MINUTE: {
        "display_name": "Rate Limit - Per Minute",
        "description": "Limit requests per minute",
    },
    GuardrailType.RATE_LIMIT_PER_HOUR: {
        "display_name": "Rate Limit - Per Hour",
        "description": "Limit requests per hour",
    },
}


# =============================================================================
# GUARDRAIL CONFIG SCHEMAS
# =============================================================================
# Defines allowed config keys and their types for each guardrail type.
# Used for validation during guardrail and policy creation/updates.

# Config field definitions: (type, required, allowed_values)
# type: str, int, list, bool
# required: True/False
# allowed_values: None or list of allowed values

GUARDRAIL_CONFIG_SCHEMAS: dict[GuardrailType, dict[str, tuple]] = {
    # RBAC: Control which tools agents can access
    GuardrailType.RBAC: {
        "default_action": (str, False, ["allow", "deny"]),
        "allowed_tools": (list, False, None),  # List of tool patterns
        "denied_tools": (list, False, None),  # List of tool patterns
    },
    # PII Detection: All PII types share same schema
    GuardrailType.PII_CREDIT_CARD: {
        "direction": (str, False, ["request", "response", "both"]),
        "redaction_pattern": (str, False, None),
    },
    GuardrailType.PII_SSN: {
        "direction": (str, False, ["request", "response", "both"]),
        "redaction_pattern": (str, False, None),
    },
    GuardrailType.PII_EMAIL: {
        "direction": (str, False, ["request", "response", "both"]),
        "redaction_pattern": (str, False, None),
    },
    GuardrailType.PII_PHONE: {
        "direction": (str, False, ["request", "response", "both"]),
        "redaction_pattern": (str, False, None),
    },
    GuardrailType.PII_IP_ADDRESS: {
        "direction": (str, False, ["request", "response", "both"]),
        "redaction_pattern": (str, False, None),
    },
    # Content filters
    GuardrailType.CONTENT_LARGE_DOCUMENTS: {
        "direction": (str, False, ["request", "response", "both"]),
        "max_chars": (int, False, None),
    },
    GuardrailType.CONTENT_STRUCTURED_DATA: {
        "direction": (str, False, ["request", "response", "both"]),
        "max_rows": (int, False, None),
    },
    GuardrailType.CONTENT_SOURCE_CODE: {
        "direction": (str, False, ["request", "response", "both"]),
        "max_chars": (int, False, None),
    },
    # Rate limiting
    GuardrailType.RATE_LIMIT_PER_MINUTE: {
        "limit": (int, False, None),
    },
    GuardrailType.RATE_LIMIT_PER_HOUR: {
        "limit": (int, False, None),
    },
}


def validate_guardrail_config(
    guardrail_type: GuardrailType,
    config: dict,
    strict: bool = True,
) -> tuple[bool, str | None]:
    """Validate config against the schema for a guardrail type.

    Args:
        guardrail_type: The guardrail type to validate against
        config: The config dict to validate
        strict: If True, reject unknown keys. If False, only validate known keys.

    Returns:
        Tuple of (is_valid, error_message)
        If valid, returns (True, None)
        If invalid, returns (False, "error description")
    """
    schema = GUARDRAIL_CONFIG_SCHEMAS.get(guardrail_type)
    if not schema:
        # Unknown guardrail type - allow any config
        return True, None

    # Check for unknown keys in strict mode
    if strict:
        unknown_keys = set(config.keys()) - set(schema.keys())
        if unknown_keys:
            return False, (
                f"Unknown config keys for guardrail type '{guardrail_type.value}': "
                f"{sorted(unknown_keys)}. Allowed keys: {sorted(schema.keys())}"
            )

    # Validate each provided key
    for key, value in config.items():
        if key not in schema:
            continue  # Skip unknown keys in non-strict mode

        expected_type, _required, allowed_values = schema[key]

        # Type validation
        if expected_type == str and not isinstance(value, str):
            return False, (
                f"Config key '{key}' must be a string, got {type(value).__name__}"
            )
        if expected_type == int and not isinstance(value, int):
            return False, (
                f"Config key '{key}' must be an integer, got {type(value).__name__}"
            )
        if expected_type == bool and not isinstance(value, bool):
            return False, (
                f"Config key '{key}' must be a boolean, got {type(value).__name__}"
            )
        if expected_type == list and not isinstance(value, list):
            return False, (
                f"Config key '{key}' must be a list, got {type(value).__name__}"
            )

        # Value validation (if allowed_values specified)
        if allowed_values is not None and value not in allowed_values:
            return False, (
                f"Config key '{key}' has invalid value '{value}'. "
                f"Allowed values: {allowed_values}"
            )

    # Check required fields
    for key, (_, required, _) in schema.items():
        if required and key not in config:
            return False, f"Required config key '{key}' is missing"

    return True, None


# =============================================================================
# RUNTIME GUARDRAIL CONFIG VALIDATION
# =============================================================================
# Used by the governance plane at runtime to validate effective configurations
# with additional checks like regex pattern compilation.


def validate_regex_pattern(pattern: str, field_name: str = "pattern") -> tuple[bool, str | None]:
    """Validate a regex pattern can be compiled.

    Args:
        pattern: The regex pattern string
        field_name: Name of the field for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        re.compile(pattern)
        return True, None
    except re.error as e:
        return False, f"Invalid regex {field_name}: '{pattern}' - {e}"


def _validate_rbac_config(config: dict) -> tuple[bool, str | None] | None:
    """Validate RBAC configuration.

    Args:
        config: RBAC guardrail configuration

    Returns:
        Error tuple if invalid, None if valid
    """
    # Validate allowed_tools is a list of strings
    allowed_tools = config.get("allowed_tools", [])
    if not isinstance(allowed_tools, list):
        return False, "allowed_tools must be a list"
    for idx, tool in enumerate(allowed_tools):
        if not isinstance(tool, str):
            return False, f"allowed_tools[{idx}] must be a string"

    # Validate denied_tools is a list of strings
    denied_tools = config.get("denied_tools", [])
    if not isinstance(denied_tools, list):
        return False, "denied_tools must be a list"
    for idx, tool in enumerate(denied_tools):
        if not isinstance(tool, str):
            return False, f"denied_tools[{idx}] must be a string"

    # Validate default_action
    default_action = config.get("default_action", "deny")
    if default_action not in ("allow", "deny"):
        return False, f"default_action must be 'allow' or 'deny', got '{default_action}'"

    return None


def validate_runtime_guardrail_config(
    guardrail_type: str,
    config: dict,
) -> tuple[bool, str | None]:
    """Validate guardrail config at runtime with additional checks.

    This is used by the governance plane when initializing guardrails.
    It performs additional validation beyond schema checks, such as:
    - Compiling regex patterns
    - Validating positive integers for limits
    - Checking required runtime fields

    Args:
        guardrail_type: The guardrail type name (e.g., "rbac", "pii_detection")
        config: The configuration dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    if guardrail_type == "content_filter":
        # Validate regex patterns
        regex_patterns = config.get("regex_patterns", [])
        for idx, pattern_config in enumerate(regex_patterns):
            pattern = pattern_config.get("pattern")
            if pattern:
                is_valid, error = validate_regex_pattern(
                    pattern, f"regex_patterns[{idx}].pattern"
                )
                if not is_valid:
                    return False, error

    elif guardrail_type == "rbac":
        # Validate RBAC config
        result = _validate_rbac_config(config)
        if result:
            return result

    elif guardrail_type == "rate_limit":
        # Validate limits are positive
        default_limits = config.get("default_limits", {})
        for key in ["requests_per_minute", "requests_per_hour", "requests_per_day"]:
            if key in default_limits:
                limit = default_limits[key]
                if not isinstance(limit, int) or limit <= 0:
                    return False, f"default_limits.{key} must be a positive integer"

        per_tool_limits = config.get("per_tool_limits", {})
        for tool, tool_config in per_tool_limits.items():
            for key in ["requests_per_minute", "requests_per_hour", "requests_per_day"]:
                if key in tool_config:
                    limit = tool_config[key]
                    if not isinstance(limit, int) or limit <= 0:
                        return False, f"per_tool_limits.{tool}.{key} must be a positive integer"

    elif guardrail_type.startswith("pii_"):
        # Validate redaction pattern if provided
        redaction_pattern = config.get("redaction_pattern")
        if redaction_pattern and "{type}" not in redaction_pattern.lower():
            return False, "redaction_pattern must contain '{type}' placeholder"

    return True, None
