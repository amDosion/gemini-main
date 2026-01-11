"""
SDK Initializer Module

Handles lazy initialization of the google-genai SDK client.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# 使用新版 google-genai SDK
try:
    from google import genai as google_genai
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False


class SDKInitializer:
    """
    Manages lazy initialization of the google-genai SDK client.
    
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
        location: str = "us-central1"
    ):
        """
        Initialize the SDK initializer.
        
        Args:
            api_key: Google API key for Gemini API authentication
            use_vertex_ai: Whether to use Vertex AI instead of Gemini API
            project_id: Google Cloud project ID (required for Vertex AI)
            location: Google Cloud location (default: us-central1)
        
        Note:
            If environment variables are set, they will be used automatically:
            - GOOGLE_GENAI_USE_VERTEXAI=true -> enables Vertex AI mode
            - GOOGLE_CLOUD_PROJECT -> project ID
            - GOOGLE_CLOUD_LOCATION -> location
            - GEMINI_API_KEY or GOOGLE_API_KEY -> API key
        """
        # Check environment variables for Vertex AI configuration
        env_use_vertex = os.environ.get('GOOGLE_GENAI_USE_VERTEXAI', '').lower() == 'true'
        env_project = os.environ.get('GOOGLE_CLOUD_PROJECT')
        env_location = os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-central1')
        
        # Use environment variables if not explicitly provided
        self.use_vertex_ai = use_vertex_ai or env_use_vertex
        self.project_id = project_id or env_project
        self.location = location if location != "us-central1" else env_location
        self.api_key = api_key
        
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
        
        # 初始化新版 google-genai SDK
        if not GOOGLE_GENAI_AVAILABLE:
            raise RuntimeError(
                "google-genai SDK is not available. "
                "Please install: pip install google-genai>=1.55.0"
            )
        
        # ✅ 临时清除环境变量 GEMINI_API_KEY，确保只使用数据库中的 API Key
        original_env_key = os.environ.get('GEMINI_API_KEY')
        if original_env_key and not self.use_vertex_ai:
            logger.warning(
                "[SDK Initializer] Detected GEMINI_API_KEY environment variable. "
                "Temporarily clearing it to ensure database API key is used."
            )
            del os.environ['GEMINI_API_KEY']
        
        try:
            if self.use_vertex_ai:
                # Vertex AI 模式
                if self.api_key:
                    # ✅ 使用 API Key 模式（推荐）
                    logger.info("[SDK Initializer] Initializing Vertex AI with API Key")
                    self._genai_client = google_genai.Client(
                        vertexai=True,
                        api_key=self.api_key
                        # ❌ 不传递 project 和 location，避免触发 ADC 认证
                    )
                    logger.info("[SDK Initializer] Vertex AI SDK initialized with API Key (lazy loading)")
                else:
                    # 传统 Vertex AI 模式（需要 ADC 认证）
                    if not self.project_id:
                        raise ValueError("project_id is required for Vertex AI ADC mode")
                    
                    logger.info(
                        f"[SDK Initializer] Initializing Vertex AI with ADC: "
                        f"project={self.project_id}, location={self.location}"
                    )
                    self._genai_client = google_genai.Client(
                        vertexai=True,
                        project=self.project_id,
                        location=self.location
                    )
                    logger.info("[SDK Initializer] Vertex AI SDK initialized with ADC (lazy loading)")
            else:
                # Gemini API 模式
                if not self.api_key:
                    raise ValueError("api_key is required for Gemini API mode")
                
                logger.info("[SDK Initializer] Initializing Gemini API mode")
                self._genai_client = google_genai.Client(api_key=self.api_key)
                logger.info("[SDK Initializer] Gemini API SDK initialized (lazy loading)")
            
            self._sdk_initialized = True
        except Exception as e:
            logger.error(f"[SDK Initializer] Failed to init google-genai SDK: {e}")
            raise RuntimeError(f"Failed to initialize Google SDK: {e}")
        finally:
            # ✅ 恢复原始环境变量（如果存在）
            if original_env_key and not self.use_vertex_ai:
                os.environ['GEMINI_API_KEY'] = original_env_key
    
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
