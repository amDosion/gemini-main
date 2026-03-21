"""
Common Utilities for Gemini Service

This module provides utility functions used across both the official compatibility layer
and the legacy implementation. It includes MIME type detection, validation, error handling,
and retry mechanisms.
"""

import mimetypes
import asyncio
import random
import time
import re
import base64
import hashlib
from typing import Optional, Any, Callable, TypeVar, Union, Dict, List
from pathlib import Path
import logging

# Optional: python-magic for better MIME type detection
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

logger = logging.getLogger(__name__)

T = TypeVar('T')


def detect_mime_type(file_path: Union[str, Path]) -> Optional[str]:
    """
    Detect MIME type of a file.
    
    Uses multiple methods for accurate detection:
    1. python-magic library (if available)
    2. mimetypes module based on file extension
    3. Manual detection for common types
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string or None if detection fails
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        logger.warning(f"File does not exist: {file_path}")
        return None
    
    # Try python-magic first (most accurate)
    if MAGIC_AVAILABLE:
        try:
            mime_type = magic.from_file(str(file_path), mime=True)
            if mime_type and mime_type != 'application/octet-stream':
                return mime_type
        except Exception as e:
            logger.debug(f"python-magic detection failed: {e}")
    
    # Fallback to mimetypes module
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type:
        return mime_type
    
    # Manual detection for common file types
    extension = file_path.suffix.lower()
    extension_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.csv': 'text/csv',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.html': 'text/html',
        '.md': 'text/markdown',
        '.wav': 'audio/wav',
        '.mp3': 'audio/mpeg',
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
    }
    
    return extension_map.get(extension, 'application/octet-stream')


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key format.
    
    Args:
        api_key: API key to validate
        
    Returns:
        True if API key format is valid
    """
    if not api_key or not isinstance(api_key, str):
        return False
    
    # Basic format validation
    # Google API keys typically start with 'AIza' and are 39 characters long
    if api_key.startswith('AIza') and len(api_key) == 39:
        return True
    
    # Allow other formats for flexibility
    if len(api_key) >= 20 and api_key.replace('-', '').replace('_', '').isalnum():
        return True
    
    return False


def validate_file_size(file_path: Union[str, Path], max_size_mb: int = 20) -> bool:
    """
    Validate file size against maximum allowed size.
    
    Args:
        file_path: Path to the file
        max_size_mb: Maximum allowed size in MB
        
    Returns:
        True if file size is within limits
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            return False
        
        size_mb = file_path.stat().st_size / (1024 * 1024)
        return size_mb <= max_size_mb
    except Exception as e:
        logger.error(f"Error validating file size: {e}")
        return False


def validate_mime_type(mime_type: str, allowed_types: List[str]) -> bool:
    """
    Validate MIME type against allowed types.
    
    Args:
        mime_type: MIME type to validate
        allowed_types: List of allowed MIME types (supports wildcards)
        
    Returns:
        True if MIME type is allowed
    """
    if not mime_type or not allowed_types:
        return False
    
    for allowed in allowed_types:
        if allowed == mime_type:
            return True
        
        # Support wildcard matching (e.g., 'image/*')
        if '*' in allowed:
            pattern = allowed.replace('*', '.*')
            if re.match(pattern, mime_type):
                return True
    
    return False


def format_error_message(error: Exception, context: Optional[str] = None) -> str:
    """
    Format error message with context.
    
    Args:
        error: Exception to format
        context: Optional context information
        
    Returns:
        Formatted error message
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    if context:
        return f"{context}: {error_type}: {error_msg}"
    else:
        return f"{error_type}: {error_msg}"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing whitespace and dots
    filename = filename.strip(' .')
    
    # Ensure filename is not empty
    if not filename:
        filename = 'unnamed_file'
    
    # Limit length
    if len(filename) > 255:
        name, ext = Path(filename).stem, Path(filename).suffix
        max_name_len = 255 - len(ext)
        filename = name[:max_name_len] + ext
    
    return filename


def calculate_file_hash(file_path: Union[str, Path], algorithm: str = 'sha256') -> str:
    """
    Calculate hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256', etc.)
        
    Returns:
        Hex digest of the file hash
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def encode_base64(data: bytes) -> str:
    """
    Encode bytes to base64 string.
    
    Args:
        data: Bytes to encode
        
    Returns:
        Base64 encoded string
    """
    return base64.b64encode(data).decode('utf-8')


def decode_base64(data: str) -> bytes:
    """
    Decode base64 string to bytes.
    
    Args:
        data: Base64 encoded string
        
    Returns:
        Decoded bytes
    """
    return base64.b64decode(data)


async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exp_base: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[List[type]] = None,
    **kwargs
) -> T:
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        *args: Positional arguments for the function
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exp_base: Exponential base for backoff
        jitter: Whether to add random jitter
        retry_on: List of exception types to retry on
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function call
        
    Raises:
        Last exception if all attempts fail
    """
    if retry_on is None:
        retry_on = [Exception]
    
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # Check if we should retry on this exception
            if not any(isinstance(e, exc_type) for exc_type in retry_on):
                raise e
            
            # Don't sleep on the last attempt
            if attempt == max_attempts - 1:
                break
            
            # Calculate delay
            delay = min(initial_delay * (exp_base ** attempt), max_delay)
            
            # Add jitter
            if jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            logger.debug(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}")
            await asyncio.sleep(delay)
    
    # All attempts failed
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("All retry attempts failed")


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        lst: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def is_url(text: str) -> bool:
    """
    Check if text is a URL.
    
    Args:
        text: Text to check
        
    Returns:
        True if text appears to be a URL
    """
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(text))


def extract_model_name(model_identifier: str) -> str:
    """
    Extract clean model name from various identifier formats.
    
    Args:
        model_identifier: Model identifier (may include prefixes)
        
    Returns:
        Clean model name
    """
    # Remove common prefixes
    prefixes = [
        'models/',
        'publishers/google/models/',
        'projects/',
    ]
    
    clean_name = model_identifier
    for prefix in prefixes:
        if clean_name.startswith(prefix):
            clean_name = clean_name[len(prefix):]
            break
    
    # Extract model name from full path
    if '/' in clean_name:
        parts = clean_name.split('/')
        # Look for the actual model name (usually after 'models')
        if 'models' in parts:
            model_index = parts.index('models')
            if model_index + 1 < len(parts):
                clean_name = parts[model_index + 1]
        else:
            clean_name = parts[-1]
    
    return clean_name