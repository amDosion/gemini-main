"""
Common utilities and error classes for image editing implementations.

This module provides shared functionality used by both Gemini API and Vertex AI
image editing implementations, ensuring consistent validation and error handling.
"""

import base64
from typing import Dict, Optional


# ==================== Constants ====================

VALID_EDIT_MODES = [
    "inpainting-insert",
    "inpainting-remove",
    "outpainting",
    "product-image"
]

VALID_REFERENCE_IMAGE_TYPES = [
    "raw",      # Required: Base image to edit
    "mask",     # Optional: Mask for inpainting operations
    "control",  # Optional: Control image for guided generation
    "style",    # Optional: Style reference for style transfer
    "subject",  # Optional: Subject reference for subject-aware editing
    "content"   # Optional: Content reference for content-aware editing
]

REQUIRED_REFERENCE_IMAGE_TYPES = ["raw"]

VALID_ASPECT_RATIOS = ["1:1", "3:4", "4:3", "9:16", "16:9"]

VALID_OUTPUT_MIME_TYPES = ["image/png", "image/jpeg"]

VALID_SAFETY_FILTER_LEVELS = [
    "block_most",
    "block_some",
    "block_few",
    "block_fewest"
]

VALID_PERSON_GENERATION = [
    "dont_allow",
    "allow_adult",
    "allow_all"
]


# ==================== Error Classes ====================

class NotSupportedError(Exception):
    """
    Raised when a feature is not supported by the current implementation.
    
    This is primarily used by GeminiAPIImageEditor to indicate that
    image editing is not supported by the Gemini API.
    """
    
    def __init__(self, message: str, api_type: str = "gemini_api"):
        super().__init__(message)
        self.api_type = api_type


# ==================== Validation Functions ====================

def decode_base64_image(base64_string: str) -> bytes:
    """
    Decode a Base64-encoded image string to bytes.
    
    Args:
        base64_string: Base64-encoded image string
    
    Returns:
        Decoded image bytes
    
    Raises:
        ValueError: If the Base64 string is invalid
    
    Example:
        >>> image_bytes = decode_base64_image("iVBORw0KGgoAAAANSUhEUgAAAAUA...")
    """
    try:
        return base64.b64decode(base64_string)
    except Exception as e:
        raise ValueError(f"Invalid Base64 image string: {str(e)}")


def validate_edit_mode(edit_mode: Optional[str]) -> None:
    """
    Validate edit mode parameter.
    
    Args:
        edit_mode: Edit mode string (e.g., 'inpainting-insert', 'outpainting')
    
    Raises:
        ValueError: If edit mode is invalid
    
    Example:
        >>> validate_edit_mode("inpainting-insert")  # OK
        >>> validate_edit_mode("invalid-mode")  # Raises ValueError
    """
    if edit_mode is not None and edit_mode not in VALID_EDIT_MODES:
        raise ValueError(
            f"Invalid edit_mode: {edit_mode}. "
            f"Must be one of {VALID_EDIT_MODES}"
        )


def validate_reference_images(reference_images: Dict[str, str]) -> None:
    """
    Validate reference images dictionary.
    
    Checks:
    1. Required 'raw' image is present
    2. All reference image types are valid
    3. All values are non-empty strings (Base64 data)
    
    Args:
        reference_images: Dictionary mapping reference image types to Base64 strings
    
    Raises:
        ValueError: If reference images are invalid
    
    Example:
        >>> reference_images = {
        ...     "raw": "base64_encoded_image_data",
        ...     "mask": "base64_encoded_mask_data"
        ... }
        >>> validate_reference_images(reference_images)  # OK
        
        >>> reference_images = {"mask": "base64_data"}  # Missing 'raw'
        >>> validate_reference_images(reference_images)  # Raises ValueError
    """
    if not isinstance(reference_images, dict):
        raise ValueError("reference_images must be a dictionary")
    
    # Check required 'raw' image
    if "raw" not in reference_images:
        raise ValueError(
            f"Required reference image 'raw' is missing. "
            f"Required types: {REQUIRED_REFERENCE_IMAGE_TYPES}"
        )
    
    # Validate all reference image types
    for ref_type, ref_data in reference_images.items():
        if ref_type not in VALID_REFERENCE_IMAGE_TYPES:
            raise ValueError(
                f"Invalid reference image type: {ref_type}. "
                f"Valid types: {VALID_REFERENCE_IMAGE_TYPES}"
            )
        
        if not isinstance(ref_data, str) or not ref_data:
            raise ValueError(
                f"Reference image '{ref_type}' must be a non-empty Base64 string"
            )


def validate_number_of_images(number_of_images: Optional[int]) -> None:
    """
    Validate number_of_images parameter.
    
    Args:
        number_of_images: Number of images to generate (1-4)
    
    Raises:
        ValueError: If number_of_images is invalid
    
    Example:
        >>> validate_number_of_images(2)  # OK
        >>> validate_number_of_images(5)  # Raises ValueError
    """
    if number_of_images is not None:
        if not isinstance(number_of_images, int):
            raise ValueError("number_of_images must be an integer")
        
        if number_of_images < 1 or number_of_images > 4:
            raise ValueError(
                f"Invalid number_of_images: {number_of_images}. "
                f"Must be between 1 and 4"
            )


def validate_aspect_ratio(aspect_ratio: Optional[str]) -> None:
    """
    Validate aspect ratio parameter.
    
    Args:
        aspect_ratio: Aspect ratio string (e.g., '1:1', '16:9')
    
    Raises:
        ValueError: If aspect ratio is invalid
    
    Example:
        >>> validate_aspect_ratio("1:1")  # OK
        >>> validate_aspect_ratio("21:9")  # Raises ValueError
    """
    if aspect_ratio is not None and aspect_ratio not in VALID_ASPECT_RATIOS:
        raise ValueError(
            f"Invalid aspect_ratio: {aspect_ratio}. "
            f"Must be one of {VALID_ASPECT_RATIOS}"
        )


def validate_guidance_scale(guidance_scale: Optional[int]) -> None:
    """
    Validate guidance scale parameter.
    
    Args:
        guidance_scale: Guidance scale value (0-100)
    
    Raises:
        ValueError: If guidance scale is invalid
    
    Example:
        >>> validate_guidance_scale(50)  # OK
        >>> validate_guidance_scale(150)  # Raises ValueError
    """
    if guidance_scale is not None:
        if not isinstance(guidance_scale, (int, float)):
            raise ValueError("guidance_scale must be a number")
        
        if guidance_scale < 0 or guidance_scale > 100:
            raise ValueError(
                f"Invalid guidance_scale: {guidance_scale}. "
                f"Must be between 0 and 100"
            )


def validate_output_mime_type(output_mime_type: Optional[str]) -> None:
    """
    Validate output MIME type parameter.
    
    Args:
        output_mime_type: Output MIME type (e.g., 'image/png', 'image/jpeg')
    
    Raises:
        ValueError: If output MIME type is invalid
    
    Example:
        >>> validate_output_mime_type("image/png")  # OK
        >>> validate_output_mime_type("image/gif")  # Raises ValueError
    """
    if output_mime_type is not None and output_mime_type not in VALID_OUTPUT_MIME_TYPES:
        raise ValueError(
            f"Invalid output_mime_type: {output_mime_type}. "
            f"Must be one of {VALID_OUTPUT_MIME_TYPES}"
        )


def validate_safety_filter_level(safety_filter_level: Optional[str]) -> None:
    """
    Validate safety filter level parameter.
    
    Args:
        safety_filter_level: Safety filter level (e.g., 'block_some', 'block_few')
    
    Raises:
        ValueError: If safety filter level is invalid
    
    Example:
        >>> validate_safety_filter_level("block_some")  # OK
        >>> validate_safety_filter_level("block_none")  # Raises ValueError
    """
    if safety_filter_level is not None and safety_filter_level not in VALID_SAFETY_FILTER_LEVELS:
        raise ValueError(
            f"Invalid safety_filter_level: {safety_filter_level}. "
            f"Must be one of {VALID_SAFETY_FILTER_LEVELS}"
        )


def validate_person_generation(person_generation: Optional[str]) -> None:
    """
    Validate person generation parameter.
    
    Args:
        person_generation: Person generation setting (e.g., 'allow_adult', 'dont_allow')
    
    Raises:
        ValueError: If person generation setting is invalid
    
    Example:
        >>> validate_person_generation("allow_adult")  # OK
        >>> validate_person_generation("allow_nsfw")  # Raises ValueError
    """
    if person_generation is not None and person_generation not in VALID_PERSON_GENERATION:
        raise ValueError(
            f"Invalid person_generation: {person_generation}. "
            f"Must be one of {VALID_PERSON_GENERATION}"
        )


# ==================== Utility Functions ====================

def encode_image_to_base64(image_bytes: bytes) -> str:
    """
    Encode image bytes to Base64 string.
    
    Args:
        image_bytes: Raw image bytes
    
    Returns:
        Base64-encoded string
    
    Example:
        >>> image_bytes = b"\\x89PNG\\r\\n..."
        >>> base64_string = encode_image_to_base64(image_bytes)
    """
    return base64.b64encode(image_bytes).decode('utf-8')
