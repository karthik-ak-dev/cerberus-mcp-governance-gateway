"""
Base Model Classes

This module provides the foundational classes for all SQLAlchemy models in Cerberus.
It includes the declarative base and common mixins for timestamps and soft deletion.

These base classes ensure consistency across all models and reduce code duplication.
"""

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from sqlalchemy import DateTime, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.functions import now


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    This is the declarative base that all models inherit from. It provides:
    - Automatic table name generation
    - Type annotation support for columns
    - JSON type mapping for PostgreSQL JSONB columns

    All models in the application should inherit from this class either
    directly or through one of the mixin classes.
    """

    # Map Python dict type to PostgreSQL JSONB for flexible JSON storage
    type_annotation_map = {
        dict[str, Any]: "JSONB",
    }


class TimestampMixin:
    """
    Mixin that adds automatic timestamp tracking to models.

    Provides two timestamp columns that are automatically managed:
    - created_at: Set when the record is first inserted
    - updated_at: Updated whenever the record is modified

    Usage:
        class MyModel(Base, TimestampMixin):
            __tablename__ = "my_table"
            id: Mapped[int] = mapped_column(primary_key=True)

    Example values:
        created_at: 2024-01-15T10:30:00Z (when record was created)
        updated_at: 2024-01-16T14:45:30Z (last modification time)
    """

    # Timestamp when the record was created
    # Automatically set by the database on INSERT using server_default
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),      # Store with timezone info for global apps
        server_default=now(),         # Database sets this on INSERT
        nullable=False,
    )

    # Timestamp when the record was last updated
    # Automatically updated by SQLAlchemy on UPDATE using onupdate
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),      # Store with timezone info
        server_default=now(),         # Initial value on INSERT
        onupdate=now(),               # SQLAlchemy updates this on UPDATE
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Mixin that adds soft delete capability to models.

    Instead of permanently deleting records, soft delete marks them
    as deleted by setting a timestamp. This allows:
    - Data recovery if needed
    - Audit trail preservation
    - Referential integrity maintenance

    Usage:
        class MyModel(Base, TimestampMixin, SoftDeleteMixin):
            __tablename__ = "my_table"
            id: Mapped[int] = mapped_column(primary_key=True)

    Example values:
        deleted_at: None              (record is active)
        deleted_at: 2024-01-20T09:00:00Z  (record was soft-deleted)

    Note: Queries should filter out soft-deleted records:
        query.where(MyModel.deleted_at.is_(None))
    """

    # Timestamp when the record was soft-deleted
    # NULL means the record is active; a timestamp means it's deleted
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,                # NULL = not deleted
        default=None,                 # Records start as not deleted
    )

    @property
    def is_deleted(self) -> bool:
        """
        Check if the record has been soft deleted.

        Returns:
            True if deleted_at is set (record is deleted)
            False if deleted_at is None (record is active)
        """
        return self.deleted_at is not None


class EnumValidationMixin:
    """
    Mixin that provides automatic enum validation for model fields.

    Models using this mixin should define an `_enum_fields` class variable
    that maps field names to their corresponding Enum classes.

    Example:
        from app.config.constants import UserRole, SubscriptionTier

        class User(Base, EnumValidationMixin):
            _enum_fields: ClassVar[dict[str, type[Enum]]] = {
                "role": UserRole,
            }

            role: Mapped[str] = mapped_column(String(50), default="developer")

    The validation is triggered automatically before insert/update operations,
    ensuring invalid enum values cannot be written to the database.
    """

    # Subclasses should override this with their enum field mappings
    _enum_fields: ClassVar[dict[str, type[Enum]]] = {}

    def validate_enum_fields(self) -> None:
        """
        Validate all enum fields have valid values.

        Raises:
            ValueError: If any enum field has an invalid value
        """
        for field_name, enum_class in self._enum_fields.items():
            value = getattr(self, field_name, None)
            if value is not None:
                # Get valid values from enum
                valid_values = {e.value for e in enum_class}
                if value not in valid_values:
                    raise ValueError(
                        f"Invalid value '{value}' for field '{field_name}'. "
                        f"Must be one of: {', '.join(sorted(valid_values))}"
                    )

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register validation event listeners when subclass is created."""
        super().__init_subclass__(**kwargs)

        # Only register events for classes that have _enum_fields defined
        if cls._enum_fields:
            # Register before_insert event
            # Signature: (mapper, connection, target) - we only need target
            @event.listens_for(cls, "before_insert", propagate=True)
            def validate_before_insert(*args: Any) -> None:
                target = args[2]
                target.validate_enum_fields()

            # Register before_update event
            # Signature: (mapper, connection, target) - we only need target
            @event.listens_for(cls, "before_update", propagate=True)
            def validate_before_update(*args: Any) -> None:
                target = args[2]
                target.validate_enum_fields()
