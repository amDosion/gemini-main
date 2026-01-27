"""
Parameter Validation Utilities

Provides standardized parameter validation with helpful error messages and suggestions.
"""

from typing import Any, List, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)


class ParameterValidationError(ValueError):
    """
    Enhanced parameter validation error with structured information.
    
    Provides detailed error information including:
    - Parameter name and invalid value
    - Valid options or ranges
    - Helpful suggestions for fixing the error
    - Service context for better debugging
    """
    
    def __init__(
        self,
        parameter: str,
        value: Any,
        message: str,
        valid_options: Optional[List[str]] = None,
        valid_range: Optional[str] = None,
        suggestion: Optional[str] = None,
        service: Optional[str] = None
    ):
        """
        Initialize parameter validation error.
        
        Args:
            parameter: Name of the invalid parameter
            value: The invalid value that was provided
            message: Base error message
            valid_options: List of valid options for the parameter
            valid_range: Description of valid range (e.g., "1.0 to 3.0")
            suggestion: Helpful suggestion for fixing the error
            service: Name of the service where error occurred
        """
        self.parameter = parameter
        self.value = value
        self.valid_options = valid_options
        self.valid_range = valid_range
        self.suggestion = suggestion
        self.service = service
        
        # Build comprehensive error message
        full_message = self._build_error_message(message)
        super().__init__(full_message)
    
    def _build_error_message(self, base_message: str) -> str:
        """Build comprehensive error message with all available information."""
        parts = []
        
        # Service context
        if self.service:
            parts.append(f"[{self.service}]")
        
        # Base message
        parts.append(base_message)
        
        # Valid options
        if self.valid_options:
            if len(self.valid_options) <= 5:
                options_str = ", ".join(f"'{opt}'" for opt in self.valid_options)
                parts.append(f"Valid options: {options_str}")
            else:
                # Show first few options and indicate there are more
                options_str = ", ".join(f"'{opt}'" for opt in self.valid_options[:3])
                parts.append(f"Valid options include: {options_str} (and {len(self.valid_options) - 3} more)")
        
        # Valid range
        if self.valid_range:
            parts.append(f"Valid range: {self.valid_range}")
        
        # Helpful suggestion
        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")
        
        return " | ".join(parts)


class ParameterValidator:
    """
    Standardized parameter validation utilities.
    
    Provides common validation patterns with consistent error messages
    and helpful suggestions for fixing parameter errors.
    """
    
    def __init__(self, service_name: str):
        """
        Initialize validator for a specific service.
        
        Args:
            service_name: Name of the service (for error context)
        """
        self.service_name = service_name
    
    def validate_required_string(
        self,
        parameter: str,
        value: Any,
        min_length: int = 1,
        max_length: Optional[int] = None
    ) -> None:
        """
        Validate required string parameter.
        
        Args:
            parameter: Parameter name
            value: Parameter value to validate
            min_length: Minimum required length
            max_length: Maximum allowed length (optional)
        
        Raises:
            ParameterValidationError: If validation fails
        """
        if value is None:
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Parameter '{parameter}' is required and cannot be None",
                suggestion="Provide a non-empty string value",
                service=self.service_name
            )
        
        if not isinstance(value, str):
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Parameter '{parameter}' must be a string, got {type(value).__name__}",
                suggestion=f"Convert the value to a string or provide a string directly",
                service=self.service_name
            )
        
        if len(value.strip()) < min_length:
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Parameter '{parameter}' cannot be empty or whitespace-only",
                suggestion="Provide a non-empty string value",
                service=self.service_name
            )
        
        if max_length and len(value) > max_length:
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Parameter '{parameter}' is too long ({len(value)} characters)",
                valid_range=f"1 to {max_length} characters",
                suggestion=f"Shorten the value to {max_length} characters or less",
                service=self.service_name
            )
    
    def validate_choice(
        self,
        parameter: str,
        value: Any,
        valid_options: List[str],
        case_sensitive: bool = True
    ) -> None:
        """
        Validate parameter against a list of valid options.
        
        Args:
            parameter: Parameter name
            value: Parameter value to validate
            valid_options: List of valid options
            case_sensitive: Whether comparison should be case-sensitive
        
        Raises:
            ParameterValidationError: If validation fails
        """
        if value is None:
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Parameter '{parameter}' is required",
                valid_options=valid_options,
                suggestion=f"Choose one of the valid options",
                service=self.service_name
            )
        
        # Convert to string for comparison
        value_str = str(value)
        comparison_options = valid_options
        comparison_value = value_str
        
        if not case_sensitive:
            comparison_options = [opt.lower() for opt in valid_options]
            comparison_value = value_str.lower()
        
        if comparison_value not in comparison_options:
            # Find close matches for better suggestions
            close_matches = self._find_close_matches(value_str, valid_options)
            suggestion = f"Choose one of the valid options"
            if close_matches:
                suggestion += f". Did you mean: {', '.join(close_matches)}?"
            
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Invalid value '{value}' for parameter '{parameter}'",
                valid_options=valid_options,
                suggestion=suggestion,
                service=self.service_name
            )
    
    def validate_numeric_range(
        self,
        parameter: str,
        value: Any,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        value_type: type = float,
        inclusive: bool = True
    ) -> None:
        """
        Validate numeric parameter within a range.
        
        Args:
            parameter: Parameter name
            value: Parameter value to validate
            min_value: Minimum allowed value (optional)
            max_value: Maximum allowed value (optional)
            value_type: Expected numeric type (int or float)
            inclusive: Whether range bounds are inclusive
        
        Raises:
            ParameterValidationError: If validation fails
        """
        if value is None:
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Parameter '{parameter}' is required",
                suggestion=f"Provide a {value_type.__name__} value",
                service=self.service_name
            )
        
        # Type validation
        if not isinstance(value, (int, float)):
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Parameter '{parameter}' must be a number, got {type(value).__name__}",
                suggestion=f"Provide a {value_type.__name__} value",
                service=self.service_name
            )
        
        # Convert to expected type if needed
        try:
            if value_type == int and not isinstance(value, int):
                value = int(value)
        except (ValueError, TypeError):
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Parameter '{parameter}' cannot be converted to {value_type.__name__}",
                suggestion=f"Provide a valid {value_type.__name__} value",
                service=self.service_name
            )
        
        # Range validation
        range_parts = []
        if min_value is not None:
            range_parts.append(f"{min_value}")
        if max_value is not None:
            if range_parts:
                range_parts.append("to")
            range_parts.append(f"{max_value}")
        
        range_desc = " ".join(range_parts) if range_parts else "any number"
        
        if min_value is not None:
            if (inclusive and value < min_value) or (not inclusive and value <= min_value):
                op = "greater than or equal to" if inclusive else "greater than"
                raise ParameterValidationError(
                    parameter=parameter,
                    value=value,
                    message=f"Parameter '{parameter}' must be {op} {min_value}, got {value}",
                    valid_range=range_desc,
                    suggestion=f"Use a value {op} {min_value}",
                    service=self.service_name
                )
        
        if max_value is not None:
            if (inclusive and value > max_value) or (not inclusive and value >= max_value):
                op = "less than or equal to" if inclusive else "less than"
                raise ParameterValidationError(
                    parameter=parameter,
                    value=value,
                    message=f"Parameter '{parameter}' must be {op} {max_value}, got {value}",
                    valid_range=range_desc,
                    suggestion=f"Use a value {op} {max_value}",
                    service=self.service_name
                )
    
    def validate_boolean(
        self,
        parameter: str,
        value: Any,
        required: bool = False
    ) -> None:
        """
        Validate boolean parameter.
        
        Args:
            parameter: Parameter name
            value: Parameter value to validate
            required: Whether the parameter is required
        
        Raises:
            ParameterValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ParameterValidationError(
                    parameter=parameter,
                    value=value,
                    message=f"Parameter '{parameter}' is required",
                    valid_options=["true", "false"],
                    suggestion="Provide a boolean value (True or False)",
                    service=self.service_name
                )
            return
        
        if not isinstance(value, bool):
            raise ParameterValidationError(
                parameter=parameter,
                value=value,
                message=f"Parameter '{parameter}' must be a boolean, got {type(value).__name__}",
                valid_options=["true", "false"],
                suggestion="Use True or False (boolean values)",
                service=self.service_name
            )
    
    def _find_close_matches(self, value: str, options: List[str], max_matches: int = 2) -> List[str]:
        """Find close matches for a value in a list of options."""
        value_lower = value.lower()
        matches = []
        
        # Look for partial matches
        for option in options:
            option_lower = option.lower()
            if (value_lower in option_lower or 
                option_lower in value_lower or
                self._similar_strings(value_lower, option_lower)):
                matches.append(option)
                if len(matches) >= max_matches:
                    break
        
        return matches
    
    def _similar_strings(self, s1: str, s2: str, threshold: float = 0.6) -> bool:
        """Check if two strings are similar using simple character overlap."""
        if not s1 or not s2:
            return False
        
        # Simple similarity check based on character overlap
        s1_chars = set(s1.lower())
        s2_chars = set(s2.lower())
        
        if not s1_chars or not s2_chars:
            return False
        
        overlap = len(s1_chars & s2_chars)
        total = len(s1_chars | s2_chars)
        
        return (overlap / total) >= threshold


# Common validation patterns for image services
class ImageServiceValidator(ParameterValidator):
    """Specialized validator for image services with common patterns."""
    
    # Common valid options
    UPSCALE_FACTORS = ['x2', 'x4']
    ASPECT_RATIOS = ['1:1', '3:4', '4:3', '9:16', '16:9']
    IMAGE_SIZES = ['1K', '2K', '4K']
    # PERSON_GENERATION removed - parameter no longer used
    MIME_TYPES = ['image/png', 'image/jpeg']
    MASK_MODES = ['MASK_MODE_FOREGROUND', 'MASK_MODE_BACKGROUND']
    EXPANSION_MODES = ['scale', 'offset', 'ratio']

    
    def validate_model(self, model: str, supported_models: List[str]) -> None:
        """Validate model parameter with helpful suggestions."""
        self.validate_required_string('model', model)
        
        if model not in supported_models:
            logger.warning(f"[{self.service_name}] Model '{model}' may not be optimized for this service")
            # Don't raise error, just warn - allow trying unsupported models
    
    def validate_upscale_factor(self, upscale_factor: str) -> None:
        """Validate upscale factor with specific suggestions."""
        self.validate_choice(
            'upscale_factor',
            upscale_factor,
            self.UPSCALE_FACTORS
        )
    
    def validate_aspect_ratio(self, aspect_ratio: str) -> None:
        """Validate aspect ratio with format checking."""
        self.validate_required_string('aspect_ratio', aspect_ratio)
        
        if ':' not in aspect_ratio:
            raise ParameterValidationError(
                parameter='aspect_ratio',
                value=aspect_ratio,
                message="Aspect ratio must be in format 'width:height'",
                valid_options=self.ASPECT_RATIOS,
                suggestion="Use format like '16:9' or '4:3'",
                service=self.service_name
            )
        
        try:
            width, height = aspect_ratio.split(':')
            width_num, height_num = int(width), int(height)
            if width_num <= 0 or height_num <= 0:
                raise ValueError("Dimensions must be positive")
        except ValueError:
            raise ParameterValidationError(
                parameter='aspect_ratio',
                value=aspect_ratio,
                message="Aspect ratio must contain positive integers",
                valid_options=self.ASPECT_RATIOS,
                suggestion="Use format like '16:9' with positive integers",
                service=self.service_name
            )
    
    def validate_image_size(self, image_size: str) -> None:
        """Validate image size parameter."""
        self.validate_choice('image_size', image_size, self.IMAGE_SIZES)
    
    # validate_person_generation method removed - parameter no longer used
    # The API will use its default value (allow_adult)
    
    def validate_mime_type(self, mime_type: str) -> None:
        """Validate output MIME type."""
        self.validate_choice('output_mime_type', mime_type, self.MIME_TYPES)
    
    def validate_compression_quality(self, quality: int) -> None:
        """Validate compression quality."""
        self.validate_numeric_range(
            'output_compression_quality',
            quality,
            min_value=1,
            max_value=100,
            value_type=int
        )
    
    def validate_guidance_scale(self, guidance_scale: float) -> None:
        """Validate guidance scale parameter."""
        self.validate_numeric_range(
            'guidance_scale',
            guidance_scale,
            min_value=1.0,
            max_value=20.0,
            value_type=float
        )
    
    def validate_number_of_images(self, number_of_images: int) -> None:
        """Validate number of images parameter."""
        self.validate_numeric_range(
            'number_of_images',
            number_of_images,
            min_value=1,
            max_value=4,
            value_type=int
        )