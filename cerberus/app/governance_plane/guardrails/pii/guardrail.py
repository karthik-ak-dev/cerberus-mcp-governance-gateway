"""
PII Detection Guardrail

Detects and handles personally identifiable information.
Each PII type has its own guardrail class for granular policy control.
"""

import re
from typing import Any, ClassVar

from app.config.constants import Direction, Severity
from app.core.logging import logger
from app.governance_plane.guardrails.base import BaseGuardrail, GuardrailResult
from app.governance_plane.guardrails.pii.patterns import PII_PATTERNS
from app.schemas.decision import DecisionRequest, MCPMessage


class BasePIIGuardrail(BaseGuardrail):
    """Base class for PII detection guardrails.

    Each subclass detects a specific type of PII (SSN, credit card, email, etc.).
    """

    # Subclasses must override these
    name: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    pii_type: ClassVar[str] = ""  # Key in PII_PATTERNS (e.g., "ssn", "credit_card")

    supported_directions: ClassVar[list[Direction]] = [
        Direction.REQUEST,
        Direction.RESPONSE,
    ]

    async def evaluate(
        self,
        message: MCPMessage,
        request: DecisionRequest,
    ) -> GuardrailResult:
        """Evaluate message for this specific PII type.

        Args:
            message: MCP message
            request: Decision request containing context

        Returns:
            Guardrail result
        """
        direction = request.direction.value
        config_direction = self.config.get("direction", "response")

        # Check if we should scan this direction
        if config_direction not in ("both", direction):
            logger.debug(
                "PII: Skipping - direction not configured",
                pii_type=self.pii_type,
                current_direction=direction,
                config_direction=config_direction,
            )
            return self._allow()

        # Get content to scan
        content = self._extract_content(message)
        if not content:
            logger.debug("PII: No content to scan", pii_type=self.pii_type)
            return self._allow()

        logger.debug(
            "PII: Scanning content",
            pii_type=self.pii_type,
            direction=direction,
            content_length=len(content),
        )

        # Scan for this specific PII type
        findings = self._scan_for_pii(content)

        if not findings:
            logger.debug("PII: No PII detected", pii_type=self.pii_type)
            return self._allow()

        logger.info(
            "PII: Found potential PII",
            pii_type=self.pii_type,
            findings_count=len(findings),
        )

        # Determine action based on config
        action = self.config.get("action", "redact")

        if action == "block":
            is_request = request.direction == Direction.REQUEST
            logger.info(
                "PII: BLOCKED - Sensitive PII detected",
                pii_type=self.pii_type,
                direction=direction,
                total_findings=len(findings),
            )
            return self._block(
                reason=f"Blocked due to {self.pii_type.upper()} detection",
                details={
                    "pii_type": self.pii_type,
                    "total_findings": len(findings),
                },
                is_request=is_request,
                severity=Severity.CRITICAL,
            )

        # Apply redaction
        logger.info(
            "PII: REDACTING - PII will be masked",
            pii_type=self.pii_type,
            direction=direction,
            redaction_count=len(findings),
        )
        modified_message = self._redact_pii(message, findings)
        return self._modify(
            modified_message=modified_message,
            reason=f"{self.pii_type.upper()} redacted: {len(findings)} instances",
            details={
                "pii_type": self.pii_type,
                "redaction_count": len(findings),
            },
        )

    def _scan_for_pii(self, content: str) -> list[dict[str, Any]]:
        """Scan content for this specific PII type.

        Args:
            content: Text to scan

        Returns:
            List of findings
        """
        findings = []

        pattern_info = PII_PATTERNS.get(self.pii_type)
        if not pattern_info:
            logger.warning("PII: Unknown PII type", pii_type=self.pii_type)
            return findings

        pattern = pattern_info["pattern"]
        validator = pattern_info.get("validator")

        for match in re.finditer(pattern, content, re.IGNORECASE):
            value = match.group(0)

            # Run validator if exists
            if validator and not validator(value):
                continue

            findings.append(
                {
                    "type": self.pii_type,
                    "value": value,
                    "start": match.start(),
                    "end": match.end(),
                }
            )

        return findings

    def _redact_pii(
        self, message: MCPMessage, findings: list[dict[str, Any]]
    ) -> MCPMessage:
        """Redact PII from message.

        Uses value-based replacement to avoid JSON encoding issues.
        Each finding's 'value' is replaced with the redaction pattern.

        Args:
            message: Original message
            findings: PII findings to redact

        Returns:
            Modified message with redaction
        """
        redaction_pattern = self.config.get(
            "redaction_pattern", f"[REDACTED:{self.pii_type.upper()}]"
        )

        # Create a copy of the message
        modified = message.model_copy(deep=True)

        if modified.result:
            # Build replacement mapping from findings
            replacements: dict[str, str] = {}
            for finding in findings:
                value = finding["value"]
                replacement = redaction_pattern.replace(
                    "{type}", finding["type"].upper()
                )
                replacements[value] = replacement

            # Apply replacements to the result structure
            modified.result = self._apply_redactions(modified.result, replacements)

        return modified

    def _apply_redactions(
        self, data: Any, replacements: dict[str, str]
    ) -> Any:
        """Recursively apply redactions to data structure.

        Args:
            data: Data to process (dict, list, or string)
            replacements: Mapping of PII values to redaction tokens

        Returns:
            Data with redactions applied
        """
        if isinstance(data, str):
            result = data
            for pii_value, redaction in replacements.items():
                result = result.replace(pii_value, redaction)
            return result
        elif isinstance(data, dict):
            return {k: self._apply_redactions(v, replacements) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._apply_redactions(item, replacements) for item in data]
        else:
            return data


# =============================================================================
# SPECIFIC PII GUARDRAIL CLASSES
# =============================================================================
# Each class corresponds to a GuardrailType in constants.py


class PIICreditCardGuardrail(BasePIIGuardrail):
    """Detect and handle credit card numbers."""

    name: ClassVar[str] = "pii_credit_card"
    display_name: ClassVar[str] = "PII - Credit Card"
    description: ClassVar[str] = "Detect and handle credit/debit card numbers"
    pii_type: ClassVar[str] = "credit_card"


class PIISSNGuardrail(BasePIIGuardrail):
    """Detect and handle Social Security Numbers."""

    name: ClassVar[str] = "pii_ssn"
    display_name: ClassVar[str] = "PII - Social Security Number"
    description: ClassVar[str] = "Detect and handle Social Security Numbers"
    pii_type: ClassVar[str] = "ssn"


class PIIEmailGuardrail(BasePIIGuardrail):
    """Detect and handle email addresses."""

    name: ClassVar[str] = "pii_email"
    display_name: ClassVar[str] = "PII - Email Address"
    description: ClassVar[str] = "Detect and handle email addresses"
    pii_type: ClassVar[str] = "email"


class PIIPhoneGuardrail(BasePIIGuardrail):
    """Detect and handle phone numbers."""

    name: ClassVar[str] = "pii_phone"
    display_name: ClassVar[str] = "PII - Phone Number"
    description: ClassVar[str] = "Detect and handle phone numbers"
    pii_type: ClassVar[str] = "phone"


class PIIIPAddressGuardrail(BasePIIGuardrail):
    """Detect and handle IP addresses."""

    name: ClassVar[str] = "pii_ip_address"
    display_name: ClassVar[str] = "PII - IP Address"
    description: ClassVar[str] = "Detect and handle IP addresses"
    pii_type: ClassVar[str] = "ip_address"


# List of all PII guardrail classes for registration
PII_GUARDRAIL_CLASSES = [
    PIICreditCardGuardrail,
    PIISSNGuardrail,
    PIIEmailGuardrail,
    PIIPhoneGuardrail,
    PIIIPAddressGuardrail,
]
