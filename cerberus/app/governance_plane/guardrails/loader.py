"""
Guardrail Loader

Loads and registers all guardrail implementations.
This module is separate from registry to keep imports clean.
"""

from app.governance_plane.guardrails.content.guardrail import ContentFilterGuardrail
from app.governance_plane.guardrails.pii.guardrail import PII_GUARDRAIL_CLASSES
from app.governance_plane.guardrails.rate_limit.guardrail import (
    RATE_LIMIT_GUARDRAIL_CLASSES,
)
from app.governance_plane.guardrails.rbac.guardrail import RBACGuardrail

# All guardrail classes to be registered
# PII and Rate Limit guardrails are registered individually for granular policy control
GUARDRAIL_CLASSES = [
    RBACGuardrail,
    *PII_GUARDRAIL_CLASSES,  # pii_ssn, pii_credit_card, pii_email, etc.
    ContentFilterGuardrail,
    *RATE_LIMIT_GUARDRAIL_CLASSES,  # rate_limit_per_minute, rate_limit_per_hour
]
