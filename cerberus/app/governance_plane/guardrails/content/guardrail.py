"""
Content Filter Guardrail

Blocks or flags content based on keywords and patterns.
"""

import re
from typing import Any, ClassVar, Pattern

from app.config.constants import Direction, Severity, validate_runtime_guardrail_config
from app.core.exceptions import GuardrailConfigurationError
from app.core.logging import logger
from app.governance_plane.guardrails.base import BaseGuardrail, GuardrailResult
from app.schemas.decision import DecisionRequest, MCPMessage


class ContentFilterGuardrail(BaseGuardrail):
    """Content filtering guardrail.

    Filters content based on:
    - Keyword blocklists and warning lists
    - Regex patterns for more complex matching

    Regex patterns are compiled at initialization to catch
    configuration errors early.
    """

    name: ClassVar[str] = "content_filter"
    display_name: ClassVar[str] = "Content Filter"
    description: ClassVar[str] = "Block or flag content based on keywords and patterns"
    supported_directions: ClassVar[list[Direction]] = [
        Direction.REQUEST,
        Direction.RESPONSE,
    ]

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize content filter with validated configuration.

        Args:
            config: Guardrail configuration

        Raises:
            GuardrailConfigurationError: If configuration is invalid
        """
        super().__init__(config)

        # Validate config using centralized validation
        is_valid, error = validate_runtime_guardrail_config(self.name, config)
        if not is_valid:
            raise GuardrailConfigurationError(
                message=error or "Invalid configuration",
                guardrail_type=self.name,
            )

        self._compiled_patterns: list[tuple[Pattern[str], str, str]] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns at initialization time.

        Patterns have already been validated by validate_runtime_guardrail_config,
        so this should not fail. We still catch errors defensively.
        """
        regex_patterns = self.config.get("regex_patterns", [])

        for idx, pattern_config in enumerate(regex_patterns):
            pattern = pattern_config.get("pattern")
            if not pattern:
                logger.warning(
                    "Skipping empty regex pattern",
                    guardrail=self.name,
                    pattern_index=idx,
                )
                continue

            action = pattern_config.get("action", "block")
            name = pattern_config.get("name", pattern)

            # Pattern was already validated, but compile defensively
            compiled = re.compile(pattern, re.IGNORECASE)
            self._compiled_patterns.append((compiled, action, name))

    async def evaluate(
        self,
        message: MCPMessage,
        request: DecisionRequest,
    ) -> GuardrailResult:
        """Evaluate message content against filters.

        Args:
            message: MCP message
            request: Decision request containing context

        Returns:
            Guardrail result
        """
        direction = request.direction.value
        config_direction = self.config.get("direction", "both")

        if config_direction not in ("both", direction):
            logger.debug(
                "ContentFilter: Skipping - direction not configured",
                current_direction=direction,
                config_direction=config_direction,
            )
            return self._allow()

        content = self._extract_content(message)
        if not content:
            logger.debug("ContentFilter: No content to check")
            return self._allow()

        logger.debug(
            "ContentFilter: Checking content",
            direction=direction,
            content_length=len(content),
            keywords_configured=bool(self.config.get("keywords")),
            patterns_configured=len(self._compiled_patterns),
        )

        # Check keywords first (fast path)
        keyword_result = self._check_keywords(content, request)
        if keyword_result:
            return keyword_result

        # Check regex patterns
        return self._check_patterns(content, request)

    def _check_keywords(
        self, content: str, request: DecisionRequest
    ) -> GuardrailResult | None:
        """Check content against keyword lists.

        Args:
            content: Text content to check
            request: Decision request for context

        Returns:
            Block result if blocked, None otherwise
        """
        keywords_config = self.config.get("keywords", {})
        block_keywords = keywords_config.get("block", [])
        content_lower = content.lower()

        logger.debug(
            "ContentFilter: Checking block keywords",
            block_keywords_count=len(block_keywords),
        )

        # Check for blocked keywords
        blocked = [kw for kw in block_keywords if kw.lower() in content_lower]

        if blocked:
            logger.info(
                "ContentFilter: BLOCKED - Prohibited keywords detected",
                direction=request.direction.value,
                matched_keywords=blocked,
            )
            return self._block(
                reason="Blocked content: prohibited keywords detected",
                details={"matched_keywords": blocked},
                is_request=(request.direction == Direction.REQUEST),
                severity=Severity.WARNING,
            )

        return None

    def _check_patterns(
        self, content: str, request: DecisionRequest
    ) -> GuardrailResult:
        """Check content against compiled regex patterns.

        Args:
            content: Text content to check
            request: Decision request for context

        Returns:
            Guardrail result
        """
        pattern_matches = []
        warned_keywords = []

        # Check warning keywords
        keywords_config = self.config.get("keywords", {})
        warn_keywords = keywords_config.get("warn", [])
        content_lower = content.lower()

        warned_keywords = [kw for kw in warn_keywords if kw.lower() in content_lower]

        if warned_keywords:
            logger.debug(
                "ContentFilter: Warning keywords detected",
                warned_keywords=warned_keywords,
            )

        # Check compiled regex patterns
        logger.debug(
            "ContentFilter: Checking regex patterns",
            patterns_count=len(self._compiled_patterns),
        )

        for compiled, action, name in self._compiled_patterns:
            if compiled.search(content):
                if action == "block":
                    logger.info(
                        "ContentFilter: BLOCKED - Pattern matched",
                        direction=request.direction.value,
                        pattern_name=name,
                    )
                    return self._block(
                        reason=f"Blocked content: pattern '{name}' matched",
                        details={"pattern": name},
                        is_request=(request.direction == Direction.REQUEST),
                        severity=Severity.WARNING,
                    )
                pattern_matches.append(name)

        # If only warnings, log them
        if warned_keywords or pattern_matches:
            logger.debug(
                "ContentFilter: Content flagged for review (warnings only)",
                warned_keywords=warned_keywords,
                pattern_matches=pattern_matches,
            )
            return self._log_only(
                reason="Content flagged for review",
                details={
                    "warned_keywords": warned_keywords,
                    "pattern_matches": pattern_matches,
                },
            )

        logger.debug("ContentFilter: ALLOWED - No violations found")
        return self._allow()
