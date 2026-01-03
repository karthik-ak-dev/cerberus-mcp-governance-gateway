"""
Logging Middleware

Request/response logging for observability.
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import logger, log_context, clear_log_context


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])

        # Add context for all logs in this request
        log_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # Log request
        logger.info(
            "Request started",
            query_params=str(request.query_params),
        )

        # Time the request
        start_time = time.time()

        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log response
            logger.info(
                "Request completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Request failed",
                error=str(e),
                duration_ms=duration_ms,
            )
            raise

        finally:
            clear_log_context()
