# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Type definitions for Google Gen AI SDK."""

from typing import Any, Dict, List, Optional, Union
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from ._common import BaseModel as CommonBaseModel, CaseInSensitiveEnum


# ============================================================================
# Core Content Types
# ============================================================================

class Part(CommonBaseModel):
    """A part of content that can contain text, images, or other data."""
    
    text: Optional[str] = None
    inline_data: Optional['Blob'] = None
    file_data: Optional['FileData'] = None
    function_call: Optional['FunctionCall'] = None
    function_response: Optional['FunctionResponse'] = None
    
    @classmethod
    def from_text(cls, text: str) -> 'Part':
        """Create a Part from text."""
        return cls(text=text)
    
    @classmethod
    def from_uri(cls, file_uri: str, mime_type: str) -> 'Part':
        """Create a Part from a file URI."""
        return cls(file_data=FileData(file_uri=file_uri, mime_type=mime_type))


class Blob(CommonBaseModel):
    """Binary data with MIME type."""
    
    mime_type: str
    data: bytes
    display_name: Optional[str] = None


class FileData(CommonBaseModel):
    """Reference to a file stored in the service."""
    
    file_uri: str
    mime_type: str
    display_name: Optional[str] = None


class Content(CommonBaseModel):
    """A piece of content with a role and parts."""
    
    role: str
    parts: List[Part]


# ============================================================================
# Function Calling Types
# ============================================================================

class FunctionCall(CommonBaseModel):
    """A function call from the model."""
    
    name: str
    args: Dict[str, Any]
    id: Optional[str] = None


class FunctionResponse(CommonBaseModel):
    """Response from a function call."""
    
    name: str
    response: Dict[str, Any]


class FunctionDeclaration(CommonBaseModel):
    """Declaration of a function that can be called by the model."""
    
    name: str
    description: str
    parameters: Optional[Dict[str, Any]] = None


class Tool(CommonBaseModel):
    """A tool that contains function declarations."""
    
    function_declarations: List[FunctionDeclaration]


class FunctionCallingConfig(CommonBaseModel):
    """Configuration for function calling."""
    
    mode: str = 'AUTO'  # 'AUTO', 'ANY', 'NONE'
    allowed_function_names: Optional[List[str]] = None


class ToolConfig(CommonBaseModel):
    """Configuration for tools."""
    
    function_calling_config: Optional[FunctionCallingConfig] = None


# ============================================================================
# Generation Configuration Types
# ============================================================================

class SafetySetting(CommonBaseModel):
    """Safety setting for content generation."""
    
    category: str
    threshold: str


class GenerateContentConfig(CommonBaseModel):
    """Configuration for content generation."""
    
    # Generation parameters
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    candidate_count: Optional[int] = None
    max_output_tokens: Optional[int] = None
    stop_sequences: Optional[List[str]] = None
    
    # Response configuration
    response_mime_type: Optional[str] = None
    response_schema: Optional[Union[Dict[str, Any], type]] = None
    
    # System and tools
    system_instruction: Optional[Union[str, Content]] = None
    tools: Optional[List[Tool]] = None
    tool_config: Optional[ToolConfig] = None
    
    # Safety settings
    safety_settings: Optional[List[SafetySetting]] = None


# ============================================================================
# Response Types
# ============================================================================

class Candidate(CommonBaseModel):
    """A candidate response from the model."""
    
    content: Optional[Content] = None
    finish_reason: Optional[str] = None
    safety_ratings: Optional[List[Dict[str, Any]]] = None
    token_count: Optional[int] = None
    index: Optional[int] = None


class GenerateContentResponse(CommonBaseModel):
    """Response from content generation."""
    
    candidates: List[Candidate]
    usage_metadata: Optional[Dict[str, Any]] = None
    
    @property
    def text(self) -> str:
        """Get the text from the first candidate."""
        if self.candidates and self.candidates[0].content:
            for part in self.candidates[0].content.parts:
                if part.text:
                    return part.text
        return ""
    
    @property
    def parts(self) -> List[Part]:
        """Get the parts from the first candidate."""
        if self.candidates and self.candidates[0].content:
            return self.candidates[0].content.parts
        return []
    
    @classmethod
    def _from_response(cls, response: dict, kwargs: dict = None) -> 'GenerateContentResponse':
        """Create GenerateContentResponse from API response."""
        candidates = []
        
        if 'candidates' in response:
            for candidate_data in response['candidates']:
                content = None
                if 'content' in candidate_data:
                    content_data = candidate_data['content']
                    parts = []
                    if 'parts' in content_data:
                        for part_data in content_data['parts']:
                            parts.append(Part(**part_data))
                    content = Content(
                        role=content_data.get('role', 'model'),
                        parts=parts
                    )
                
                candidate = Candidate(
                    content=content,
                    finish_reason=candidate_data.get('finishReason'),
                    token_count=candidate_data.get('tokenCount'),
                    index=candidate_data.get('index')
                )
                candidates.append(candidate)
        
        return cls(
            candidates=candidates,
            usage_metadata=response.get('usageMetadata')
        )


# ============================================================================
# HTTP and Client Types
# ============================================================================

class HttpRetryOptions(CommonBaseModel):
    """HTTP retry configuration."""
    
    attempts: Optional[int] = None
    initial_delay: Optional[float] = None
    max_delay: Optional[float] = None


class HttpOptions(CommonBaseModel):
    """HTTP client configuration."""
    
    api_version: Optional[str] = None
    base_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: Optional[int] = None
    retry_options: Optional[HttpRetryOptions] = None


# ============================================================================
# TypedDict Versions
# ============================================================================

class GenerateContentConfigDict(TypedDict, total=False):
    """Dictionary version of GenerateContentConfig."""
    
    temperature: float
    top_p: float
    top_k: int
    max_output_tokens: int
    system_instruction: Union[str, Dict[str, Any]]
    tools: List[Dict[str, Any]]


class HttpOptionsDict(TypedDict, total=False):
    """Dictionary version of HttpOptions."""
    
    base_url: str
    headers: Dict[str, str]
    timeout: int


# Update forward references
Part.model_rebuild()
Content.model_rebuild()
GenerateContentConfig.model_rebuild()


# ============================================================================
# Parameter Types for API Calls
# ============================================================================

class _GenerateContentParameters(CommonBaseModel):
    """Parameters for generate_content API calls."""
    
    model: str
    contents: Union[str, Content, List[Content]]
    config: Optional[GenerateContentConfig] = None
    
    def model_dump(self) -> dict:
        """Convert to dictionary."""
        return {
            'model': self.model,
            'contents': self.contents,
            'config': self.config
        }


class _CountTokensParameters(CommonBaseModel):
    """Parameters for count_tokens API calls."""
    
    model: str
    contents: Union[str, Content, List[Content]]
    config: Optional[GenerateContentConfig] = None
    
    def model_dump(self) -> dict:
        """Convert to dictionary."""
        return {
            'model': self.model,
            'contents': self.contents,
            'config': self.config
        }