"""
SDK Initializer Module

Handles lazy retrieval of unified Gemini clients from GeminiClientPool.
"""

import logging
from typing import Optional, Union

from ..client_pool import get_client_pool
from ..agent.types import HttpOptions, HttpOptionsDict

logger = logging.getLogger(__name__)


class SDKInitializer:
    """
    Manages lazy retrieval of Gemini client from unified GeminiClientPool.
    
    Supports both Gemini API and Vertex AI modes:
    - Gemini API: Uses API key authentication
    - Vertex AI: Uses project ID + location authentication
    
    This class ensures the SDK is only initialized when needed,
    avoiding unnecessary blocking and resource consumption.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        use_vertex_ai: bool = False,
        project_id: Optional[str] = None,
        location: str = "us-central1",
        http_options: Optional[Union[HttpOptions, HttpOptionsDict]] = None,
    ):
        """
        Initialize the SDK initializer.
        
        Args:
            api_key: Google API key for Gemini API authentication
            use_vertex_ai: Whether to use Vertex AI instead of Gemini API
            project_id: Google Cloud project ID (required for Vertex AI)
            location: Google Cloud location (default: us-central1)
        """
        self.use_vertex_ai = use_vertex_ai
        self.project_id = project_id
        self.location = location
        self.api_key = api_key
        self.http_options = http_options
        
        self._genai_client = None
        self._sdk_initialized = False
    
    def ensure_initialized(self):
        """
        Ensure SDK is initialized (lazy loading).
        
        Only initializes the SDK when first called.
        Subsequent calls return immediately.
        
        Raises:
            RuntimeError: If google-genai SDK is not available or initialization fails
        """
        if self._sdk_initialized:
            return
        
        try:
            pool = get_client_pool()

            if self.use_vertex_ai:
                if not self.project_id:
                    raise ValueError("project_id is required for Vertex AI mode")
                logger.info(
                    "[SDK Initializer] Retrieving Vertex AI client from unified pool: "
                    f"project={self.project_id}, location={self.location}"
                )
                self._genai_client = pool.get_client(
                    api_key=self.api_key,
                    vertexai=True,
                    project=self.project_id,
                    location=self.location,
                    http_options=self.http_options,
                )
            else:
                if not self.api_key:
                    raise ValueError("api_key is required for Gemini API mode")

                logger.info("[SDK Initializer] Retrieving Gemini API client from unified pool")
                self._genai_client = pool.get_client(
                    api_key=self.api_key,
                    vertexai=False,
                    http_options=self.http_options,
                )
            
            self._sdk_initialized = True
        except Exception as e:
            logger.error(f"[SDK Initializer] Failed to init google-genai SDK: {e}")
            raise RuntimeError(f"Failed to initialize Google SDK: {e}")
    
    @property
    def client(self):
        """
        Get the initialized SDK client.
        
        Returns:
            google_genai.Client instance
        
        Raises:
            RuntimeError: If SDK is not initialized
        """
        if not self._sdk_initialized:
            raise RuntimeError("SDK not initialized. Call ensure_initialized() first.")
        return self._genai_client
    
    @property
    def is_initialized(self) -> bool:
        """Check if SDK is initialized."""
        return self._sdk_initialized
    
    @property
    def api_type(self) -> str:
        """Get the API type being used."""
        return "vertex_ai" if self.use_vertex_ai else "gemini_api"
