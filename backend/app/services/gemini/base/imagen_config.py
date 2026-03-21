"""
Configuration models for Imagen API selection.

This module defines Pydantic models for configuring and validating
Imagen API settings (Gemini API vs Vertex AI).
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
import os


class ImagenAPIConfig(BaseModel):
    """
    Configuration for Imagen API selection.
    
    This model validates that the required credentials are present
    for the selected API mode.
    """
    
    api_mode: Literal['gemini_api', 'vertex_ai'] = Field(
        default='gemini_api',
        description="API mode to use for image generation"
    )
    
    # Gemini API configuration
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Gemini API key"
    )
    
    # Vertex AI configuration
    vertex_ai_project_id: Optional[str] = Field(
        default=None,
        description="Google Cloud project ID"
    )
    vertex_ai_location: Optional[str] = Field(
        default='us-central1',
        description="Vertex AI location/region"
    )
    vertex_ai_credentials_path: Optional[str] = Field(
        default=None,
        description="Path to service account credentials JSON"
    )
    
    @field_validator('api_mode')
    @classmethod
    def validate_api_mode(cls, v):
        """Validate API mode value."""
        if v not in ['gemini_api', 'vertex_ai']:
            raise ValueError(f"Invalid api_mode: {v}. Must be 'gemini_api' or 'vertex_ai'")
        return v
    
    def validate_config(self) -> None:
        """
        Validate that required credentials are present for the selected API mode.
        
        Raises:
            ValueError: If required credentials are missing
        """
        if self.api_mode == 'gemini_api':
            if not self.gemini_api_key:
                raise ValueError("gemini_api_key is required for Gemini API mode")
        
        elif self.api_mode == 'vertex_ai':
            if not self.vertex_ai_project_id:
                raise ValueError("vertex_ai_project_id is required for Vertex AI mode")
            if not self.vertex_ai_location:
                raise ValueError("vertex_ai_location is required for Vertex AI mode")
            if not self.vertex_ai_credentials_path:
                raise ValueError("vertex_ai_credentials_path is required for Vertex AI mode")
            
            # Validate credentials file exists
            if not os.path.exists(self.vertex_ai_credentials_path):
                raise ValueError(f"Credentials file not found: {self.vertex_ai_credentials_path}")
    
    @classmethod
    def from_env(cls) -> 'ImagenAPIConfig':
        """
        Load configuration from environment variables.
        
        Returns:
            ImagenAPIConfig instance
        """
        use_vertex_ai = os.getenv('GOOGLE_GENAI_USE_VERTEXAI', 'false').lower() == 'true'
        
        return cls(
            api_mode='vertex_ai' if use_vertex_ai else 'gemini_api',
            gemini_api_key=os.getenv('GEMINI_API_KEY'),
            vertex_ai_project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
            vertex_ai_location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            vertex_ai_credentials_path=os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        )


class ImagenAPIConfigUpdate(BaseModel):
    """
    Model for updating Imagen API configuration.
    
    All fields are optional to allow partial updates.
    """
    
    api_mode: Optional[Literal['gemini_api', 'vertex_ai']] = None
    gemini_api_key: Optional[str] = None
    vertex_ai_project_id: Optional[str] = None
    vertex_ai_location: Optional[str] = None
    vertex_ai_credentials_path: Optional[str] = None


class ImagenCapabilitiesResponse(BaseModel):
    """Response model for API capabilities."""
    
    api_type: Literal['gemini_api', 'vertex_ai']
    max_images: int
    aspect_ratios: list[str]
    image_sizes: list[str]
    person_generation: list[str]
    supports_allow_all: bool


class ImagenConfigResponse(BaseModel):
    """Response model for configuration endpoint."""
    
    api_mode: Literal['gemini_api', 'vertex_ai']
    capabilities: ImagenCapabilitiesResponse
    has_gemini_api_key: bool
    has_vertex_ai_config: bool


class TestConnectionRequest(BaseModel):
    """Request model for testing API connection."""
    
    api_mode: Literal['gemini_api', 'vertex_ai']
    gemini_api_key: Optional[str] = None
    vertex_ai_project_id: Optional[str] = None
    vertex_ai_location: Optional[str] = None
    vertex_ai_credentials_path: Optional[str] = None


class TestConnectionResponse(BaseModel):
    """Response model for connection test."""
    
    success: bool
    message: str
    api_type: Optional[str] = None
    details: Optional[dict] = None
