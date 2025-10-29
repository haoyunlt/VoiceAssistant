"""
Input validation utilities
"""

import logging

from fastapi import UploadFile

from app.core.exceptions import ResourceException, ValidationException

logger = logging.getLogger(__name__)

# Maximum file sizes (in bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB

# Allowed MIME types
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/bmp",
    "image/tiff",
    "image/webp",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
}


async def validate_image_file(file: UploadFile) -> bytes:
    """
    Validate and read image file

    Args:
        file: Uploaded file

    Returns:
        File content as bytes

    Raises:
        ValidationException: If file validation fails
        ResourceException: If file size exceeds limit
    """
    # Check content type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationException(
            f"Unsupported image type: {file.content_type}",
            details={
                "allowed_types": list(ALLOWED_IMAGE_TYPES),
                "provided_type": file.content_type,
            },
        )

    # Read file content
    content = await file.read()

    # Check file size
    file_size = len(content)
    if file_size > MAX_IMAGE_SIZE:
        raise ResourceException(
            f"Image file too large: {file_size} bytes (max: {MAX_IMAGE_SIZE} bytes)",
            details={
                "file_size": file_size,
                "max_size": MAX_IMAGE_SIZE,
            },
        )

    if file_size == 0:
        raise ValidationException("Image file is empty")

    logger.debug(
        f"Image file validated: {file.filename}, "
        f"type: {file.content_type}, size: {file_size} bytes"
    )

    return content


async def validate_video_file(file: UploadFile) -> bytes:
    """
    Validate and read video file

    Args:
        file: Uploaded file

    Returns:
        File content as bytes

    Raises:
        ValidationException: If file validation fails
        ResourceException: If file size exceeds limit
    """
    # Check content type
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise ValidationException(
            f"Unsupported video type: {file.content_type}",
            details={
                "allowed_types": list(ALLOWED_VIDEO_TYPES),
                "provided_type": file.content_type,
            },
        )

    # Read file content
    content = await file.read()

    # Check file size
    file_size = len(content)
    if file_size > MAX_VIDEO_SIZE:
        raise ResourceException(
            f"Video file too large: {file_size} bytes (max: {MAX_VIDEO_SIZE} bytes)",
            details={
                "file_size": file_size,
                "max_size": MAX_VIDEO_SIZE,
            },
        )

    if file_size == 0:
        raise ValidationException("Video file is empty")

    logger.debug(
        f"Video file validated: {file.filename}, "
        f"type: {file.content_type}, size: {file_size} bytes"
    )

    return content


def validate_language(language: str | None) -> str:
    """
    Validate language parameter

    Args:
        language: Language code

    Returns:
        Validated language code

    Raises:
        ValidationException: If language is invalid
    """
    if not language:
        return "auto"

    language = language.lower().strip()

    # Common language codes
    valid_languages = {
        "auto", "en", "zh", "ja", "ko", "fr", "de", "es", "it", "pt", "ru",
        "ar", "hi", "th", "vi", "id", "ms", "tl", "nl", "tr", "pl", "uk"
    }

    if language not in valid_languages:
        raise ValidationException(
            f"Unsupported language: {language}",
            details={
                "provided": language,
                "valid_languages": list(valid_languages),
            },
        )

    return language


def validate_detect_type(detect_type: str) -> str:
    """
    Validate detection type

    Args:
        detect_type: Detection type

    Returns:
        Validated detection type

    Raises:
        ValidationException: If detection type is invalid
    """
    valid_types = {"objects", "faces", "scenes", "text"}

    detect_type = detect_type.lower().strip()

    if detect_type not in valid_types:
        raise ValidationException(
            f"Unsupported detect type: {detect_type}",
            details={
                "provided": detect_type,
                "valid_types": list(valid_types),
            },
        )

    return detect_type


def validate_analysis_type(analysis_type: str) -> str:
    """
    Validate video analysis type

    Args:
        analysis_type: Analysis type

    Returns:
        Validated analysis type

    Raises:
        ValidationException: If analysis type is invalid
    """
    valid_types = {"summary", "keyframes", "objects", "speech"}

    analysis_type = analysis_type.lower().strip()

    if analysis_type not in valid_types:
        raise ValidationException(
            f"Unsupported analysis type: {analysis_type}",
            details={
                "provided": analysis_type,
                "valid_types": list(valid_types),
            },
        )

    return analysis_type
