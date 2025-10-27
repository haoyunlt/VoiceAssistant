"""
Custom exceptions for Multimodal Engine
"""

from typing import Any, Dict, Optional


class MultimodalEngineException(Exception):
    """Base exception for Multimodal Engine"""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary"""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


class OCRException(MultimodalEngineException):
    """OCR related exceptions"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code="OCR_ERROR", details=details)


class VisionException(MultimodalEngineException):
    """Vision related exceptions"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code="VISION_ERROR", details=details)


class VideoException(MultimodalEngineException):
    """Video analysis related exceptions"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code="VIDEO_ERROR", details=details)


class ValidationException(MultimodalEngineException):
    """Input validation exceptions"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code="VALIDATION_ERROR", details=details)


class ResourceException(MultimodalEngineException):
    """Resource related exceptions (file size, format, etc.)"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code="RESOURCE_ERROR", details=details)


class ExternalServiceException(MultimodalEngineException):
    """External service call exceptions"""

    def __init__(
        self,
        message: str,
        service: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        details["service"] = service
        super().__init__(
            message, error_code="EXTERNAL_SERVICE_ERROR", details=details
        )


class RateLimitException(MultimodalEngineException):
    """Rate limit exceeded"""

    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED", details=details)
