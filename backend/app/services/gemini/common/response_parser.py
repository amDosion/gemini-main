"""
Response Parser Module

Handles parsing of Google API responses to unified format.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ResponseParser:
    """
    Parses Google API responses to unified format.
    
    Handles extraction of:
    - Content text
    - Token usage information
    - Finish reasons
    """
    
    @staticmethod
    def parse_generate_content_response(response: Any, model: str) -> Dict[str, Any]:
        """
        Parse google-genai SDK's generate_content response to unified format.
        
        Args:
            response: google-genai SDK response object
            model: Model name used for generation
        
        Returns:
            Unified response format:
            {
                "content": str,
                "role": "assistant",
                "usage": {
                    "prompt_tokens": int,
                    "completion_tokens": int,
                    "total_tokens": int
                },
                "model": str,
                "finish_reason": str
            }
        
        Raises:
            ValueError: If response is None or invalid
        
        Note:
            Finish reasons are mapped from Google's enum to standard format:
            - 1 (STOP) -> "stop"
            - 2 (MAX_TOKENS) -> "length"
            - 3 (SAFETY) -> "safety"
            - 4 (RECITATION) -> "recitation"
            - 5 (OTHER) -> "other"
        """
        if response is None:
            raise ValueError("Response is None")
        
        # 提取 content
        content = ResponseParser._extract_content(response)
        
        # 提取 usage 信息
        usage = ResponseParser._extract_usage(response)
        
        # 提取 finish_reason
        finish_reason = ResponseParser._extract_finish_reason(response)
        
        return {
            "content": content,
            "role": "assistant",
            "usage": usage,
            "model": model,
            "finish_reason": finish_reason
        }
    
    @staticmethod
    def _extract_content(response: Any) -> str:
        """Extract content text from response."""
        content = ""
        try:
            if hasattr(response, 'text'):
                content = response.text
            elif hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    parts = candidate.content.parts
                    if parts and hasattr(parts[0], 'text'):
                        content = parts[0].text
        except Exception as e:
            logger.warning(f"[Response Parser] Failed to extract content: {e}")
            content = ""
        
        return content
    
    @staticmethod
    def _extract_usage(response: Any) -> Dict[str, int]:
        """Extract token usage information from response."""
        usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        try:
            if hasattr(response, 'usage_metadata'):
                metadata = response.usage_metadata
                if hasattr(metadata, 'prompt_token_count'):
                    usage["prompt_tokens"] = metadata.prompt_token_count
                if hasattr(metadata, 'candidates_token_count'):
                    usage["completion_tokens"] = metadata.candidates_token_count
                if hasattr(metadata, 'total_token_count'):
                    usage["total_tokens"] = metadata.total_token_count
        except Exception as e:
            logger.warning(f"[Response Parser] Failed to extract usage: {e}")
        
        return usage
    
    @staticmethod
    def _extract_finish_reason(response: Any) -> str:
        """Extract finish reason from response."""
        finish_reason = "stop"
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    reason = candidate.finish_reason
                    # 转换为标准格式
                    reason_map = {
                        1: "stop",  # STOP
                        2: "length",  # MAX_TOKENS
                        3: "safety",  # SAFETY
                        4: "recitation",  # RECITATION
                        5: "other"  # OTHER
                    }
                    finish_reason = reason_map.get(reason, "stop")
        except Exception as e:
            logger.warning(f"[Response Parser] Failed to extract finish_reason: {e}")
        
        return finish_reason
