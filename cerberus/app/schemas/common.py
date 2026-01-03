"""
Common Schemas

Shared schemas used across the application.
"""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.config.constants import SortOrder


DataT = TypeVar("DataT")


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class PaginationParams(BaseModel):
    """Pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        """Get limit for database query."""
        return self.per_page


class PaginationMeta(BaseModel):
    """Pagination metadata in response."""

    page: int
    per_page: int
    total: int
    total_pages: int

    @classmethod
    def create(cls, page: int, per_page: int, total: int) -> "PaginationMeta":
        """Create pagination meta from parameters."""
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        )


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Generic paginated response."""

    data: list[DataT]
    pagination: PaginationMeta


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
    success: bool = True


class ErrorDetail(BaseModel):
    """Error detail in response."""

    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: ErrorDetail


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    service: str = "cerberus"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields in responses."""

    created_at: datetime
    updated_at: datetime


class IDMixin(BaseModel):
    """Mixin for ID field in responses."""

    id: str


class SortParams(BaseModel):
    """Sorting query parameters."""

    sort_by: str = "created_at"
    sort_order: SortOrder = Field(default=SortOrder.DESC)
