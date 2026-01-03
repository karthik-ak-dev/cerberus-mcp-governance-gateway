"""
Guardrail Model

Represents a guardrail definition in the system.
Guardrails are atomic security checks that can be attached to policies.

Each guardrail is a pre-defined type (RBAC, PII detection, rate limiting, etc.)
with default configuration that can be overridden per policy.

Default Config Structure (defined in app/config/constants.py -> GUARDRAIL_DEFAULTS):
- RBAC: {"default_action": "deny", "allowed_tools": [], "denied_tools": []}
- PII: {"direction": "both", "redaction_pattern": "[REDACTED:TYPE]"}
- Content: {"direction": "both", "max_chars": N} or {"max_rows": N}
- Rate Limit: {"limit": N}

Config Override Behavior:
- Policy.config OVERRIDES Guardrail.default_config (not merged)
- If policy has empty config {}, guardrail defaults are used
- If policy has partial config, only those keys are used (missing keys = defaults)
"""

from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import GuardrailCategory, GuardrailType
from app.models.base import Base, EnumValidationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.policy import Policy


class Guardrail(Base, TimestampMixin, EnumValidationMixin):
    """
    Guardrail definition model.

    Guardrails are atomic security checks that can be attached to entities
    (Organisation, MCP Server Workspace, Agent Access) via policies.

    Each guardrail type has:
    - A unique name (e.g., "pii_ssn", "rbac", "rate_limit_per_minute")
    - A display name for UI (e.g., "PII - Social Security Number")
    - A description explaining what it does
    - A category for grouping (rbac, pii, content, rate_limit)
    - Default configuration that can be overridden per policy

    Default Config Structure by Category:
    ------------------------------------
    RBAC:
        {
            "default_action": "deny",     # "allow" or "deny" when no rule matches
            "allowed_tools": ["tool/*"],  # Glob patterns for allowed tools
            "denied_tools": []            # Glob patterns for denied tools
        }

    PII Detection (all PII types):
        {
            "direction": "both",                    # "request", "response", or "both"
            "redaction_pattern": "[REDACTED:TYPE]"  # Pattern for redaction action
        }

    Content Filter:
        {
            "direction": "both",  # "request", "response", or "both"
            "max_chars": 10000,   # For large_documents, source_code
            "max_rows": 50        # For structured_data
        }

    Rate Limiting:
        {
            "limit": 60  # Max requests per time window (minute or hour)
        }

    Guardrails are seeded on application startup and represent the available
    security checks that users can enable via policies.
    """

    __tablename__ = "guardrails"

    # Enum field validation mapping
    _enum_fields: ClassVar[dict[str, type]] = {
        "guardrail_type": GuardrailType,
        "category": GuardrailCategory,
    }

    # ==========================================================================
    # PRIMARY KEY
    # ==========================================================================

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Unique identifier for the guardrail",
    )

    # ==========================================================================
    # CORE FIELDS
    # ==========================================================================

    guardrail_type: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        doc="Unique guardrail type identifier (e.g., 'pii_ssn', 'rbac')",
    )

    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Human-readable name for UI display",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed description of what this guardrail does",
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Category for grouping (rbac, pii, content, rate_limit)",
    )

    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================

    default_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Default config for this guardrail. Policy.config overrides this.",
    )

    # ==========================================================================
    # STATUS
    # ==========================================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether this guardrail is available for use",
    )

    # ==========================================================================
    # RELATIONSHIPS
    # ==========================================================================

    # Policies that use this guardrail
    policies: Mapped[list["Policy"]] = relationship(
        "Policy",
        back_populates="guardrail",
        lazy="dynamic",
    )

    # ==========================================================================
    # METHODS
    # ==========================================================================

    def __repr__(self) -> str:
        return (
            f"<Guardrail(id={self.id}, "
            f"type='{self.guardrail_type}', "
            f"category='{self.category}')>"
        )

    def get_effective_config(self, policy_config: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Get the effective configuration by merging policy overrides with defaults.

        Args:
            policy_config: Configuration overrides from the policy

        Returns:
            Merged configuration with policy values taking precedence
        """
        if not policy_config:
            return self.default_config.copy()

        # Start with defaults, then apply policy overrides
        effective = self.default_config.copy()
        effective.update(policy_config)
        return effective
