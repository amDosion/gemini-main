"""
Common utilities and error classes for Imagen implementations.

This module provides shared functionality used by both Gemini API and Vertex AI
implementations, ensuring consistent validation and error handling.
"""

import base64
from typing import Optional, List


# ==================== Constants ====================

VALID_ASPECT_RATIOS = ["1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9"]
VALID_IMAGE_SIZES = ["1K", "2K"]


# ==================== Error Classes ====================

class ImagenError(Exception):
    """Base exception for all Imagen-related errors."""
    pass


class ConfigurationError(ImagenError):
    """Raised when configuration is invalid or missing."""
    pass


class ParameterValidationError(ImagenError):
    """Raised when generation parameters are invalid."""
    pass


class APIError(ImagenError):
    """Raised when API calls fail."""
    
    def __init__(self, message: str, api_type: str, original_error: Exception = None):
        super().__init__(message)
        self.api_type = api_type
        self.original_error = original_error


class QuotaExceededError(APIError):
    """Raised when API quota is exceeded."""
    pass


class ContentPolicyError(ImagenError):
    """Raised when image generation is blocked by safety/content policy."""
    pass


# ==================== Validation Functions ====================

def validate_aspect_ratio(aspect_ratio: str) -> None:
    """
    Validate aspect ratio parameter.
    
    Args:
        aspect_ratio: Aspect ratio string (e.g., '1:1', '16:9')
    
    Raises:
        ParameterValidationError: If aspect ratio is invalid
    """
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise ParameterValidationError(
            f"Invalid aspect_ratio: {aspect_ratio}. "
            f"Must be one of {VALID_ASPECT_RATIOS}"
        )


def validate_image_size(image_size: Optional[str]) -> None:
    """
    Validate image size parameter.
    
    Args:
        image_size: Image size string (e.g., '1K', '2K') or None
    
    Raises:
        ParameterValidationError: If image size is invalid
    """
    if image_size is not None and image_size not in VALID_IMAGE_SIZES:
        raise ParameterValidationError(
            f"Invalid image_size: {image_size}. "
            f"Must be one of {VALID_IMAGE_SIZES}"
        )


# Note: person_generation parameter has been removed.
# The API will use its default value (allow_adult), which allows
# normal adult and children images without NSFW content.


# ==================== Utility Functions ====================

def encode_image_to_base64(image_bytes: bytes) -> str:
    """
    Encode image bytes to base64 string.
    
    Args:
        image_bytes: Raw image bytes
    
    Returns:
        Base64-encoded string
    """
    return base64.b64encode(image_bytes).decode('utf-8')
