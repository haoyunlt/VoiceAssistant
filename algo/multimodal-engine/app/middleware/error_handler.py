"""
Error handling middleware
"""

import logging
import traceback
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import MultimodalEngineException

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handling middleware"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response

        except MultimodalEngineException as e:
            # Known exceptions - log and return structured error
            logger.warning(
                f"Multimodal Engine exception: {e.error_code}",
                extra={
                    "error_code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                    "path": request.url.path,
                },
            )

            return JSONResponse(
                status_code=self._get_status_code(e.error_code),
                content=e.to_dict(),
            )

        except Exception as e:
            # Unexpected exceptions - log full traceback, return generic error
            logger.error(
                f"Unexpected error: {str(e)}",
                extra={
                    "path": request.url.path,
                    "traceback": traceback.format_exc(),
                },
                exc_info=True,
            )

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An unexpected error occurred",
                        "details": {},
                    }
                },
            )

    def _get_status_code(self, error_code: str) -> int:
        """Map error codes to HTTP status codes"""
        mapping = {
            "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
            "RESOURCE_ERROR": status.HTTP_400_BAD_REQUEST,
            "RATE_LIMIT_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
            "OCR_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "VISION_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "VIDEO_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "EXTERNAL_SERVICE_ERROR": status.HTTP_502_BAD_GATEWAY,
            "INTERNAL_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        }
        return mapping.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
