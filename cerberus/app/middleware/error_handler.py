"""
Error Handler Middleware

Global exception handling for the API.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.exceptions import CerberusException
from app.core.logging import logger


def setup_exception_handlers(app: FastAPI) -> None:
    """Set up global exception handlers.

    Args:
        app: FastAPI application
    """

    @app.exception_handler(CerberusException)
    async def cerberus_exception_handler(
        _request: Request, exc: CerberusException
    ) -> JSONResponse:
        """Handle Cerberus-specific exceptions."""
        logger.warning(
            "Application error",
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        _request: Request, exc: ValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        logger.warning("Validation error", errors=exc.errors())
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.error(
            "Unexpected error",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )
