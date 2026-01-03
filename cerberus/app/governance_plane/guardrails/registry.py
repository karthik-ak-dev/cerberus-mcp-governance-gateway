"""
Guardrail Registry

Central registry for all available guardrails.

Design Notes:
- Registry explicitly imports and registers guardrails (no decorator pattern)
- Guardrail classes are imported from loader module to keep this module clean
- This avoids cyclic imports: guardrails don't need to import registry
- Registration happens at module load time (eager loading)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.exceptions import GuardrailNotFoundError
from app.governance_plane.guardrails.loader import GUARDRAIL_CLASSES

if TYPE_CHECKING:
    from app.governance_plane.guardrails.base import BaseGuardrail

logger = logging.getLogger(__name__)


class GuardrailRegistry:
    """Registry for guardrail implementations.

    Thread-safe registry that holds all registered guardrail classes.
    Uses explicit registration to avoid import cycles.
    """

    def __init__(self) -> None:
        self._guardrails: dict[str, type[BaseGuardrail]] = {}

    def register(self, guardrail_class: type[BaseGuardrail]) -> None:
        """Register a guardrail class.

        Args:
            guardrail_class: Guardrail class to register

        Raises:
            ValueError: If a guardrail with the same name is already registered
        """
        name = guardrail_class.name
        if name in self._guardrails:
            existing = self._guardrails[name]
            if existing is not guardrail_class:
                raise ValueError(
                    f"Guardrail '{name}' already registered by {existing.__name__}"
                )
            return

        self._guardrails[name] = guardrail_class
        logger.debug("Registered guardrail: %s", name)

    def get(self, name: str) -> type[BaseGuardrail] | None:
        """Get a guardrail class by name.

        Args:
            name: Guardrail name

        Returns:
            Guardrail class or None if not found
        """
        return self._guardrails.get(name)

    def get_or_raise(self, name: str) -> type[BaseGuardrail]:
        """Get a guardrail class by name, raising if not found.

        Args:
            name: Guardrail name

        Returns:
            Guardrail class

        Raises:
            GuardrailNotFoundError: If guardrail is not registered
        """
        guardrail = self.get(name)
        if guardrail is None:
            raise GuardrailNotFoundError(name)
        return guardrail

    def list_all(self) -> list[str]:
        """List all registered guardrail names.

        Returns:
            List of guardrail names
        """
        return list(self._guardrails.keys())

    def get_all(self) -> dict[str, type[BaseGuardrail]]:
        """Get all registered guardrails.

        Returns:
            Dictionary of name -> class
        """
        return self._guardrails.copy()

    def is_registered(self, name: str) -> bool:
        """Check if a guardrail is registered.

        Args:
            name: Guardrail name

        Returns:
            True if registered
        """
        return name in self._guardrails

    def count(self) -> int:
        """Get the number of registered guardrails.

        Returns:
            Number of guardrails
        """
        return len(self._guardrails)


def _create_registry() -> GuardrailRegistry:
    """Create and populate the guardrail registry."""
    registry = GuardrailRegistry()
    for guardrail_class in GUARDRAIL_CLASSES:
        registry.register(guardrail_class)
    logger.info(
        "Loaded %d guardrails: %s",
        registry.count(),
        registry.list_all(),
    )
    return registry


# Global registry instance - populated at module load time
guardrail_registry = _create_registry()
