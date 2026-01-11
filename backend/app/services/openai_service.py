"""
OpenAI Provider Service

This module implements the OpenAI provider service using the official OpenAI Python SDK.
It supports chat completions, image generation, and speech synthesis.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import logging
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from .base_provider import BaseProviderService

logger = logging.getLogger(__name__)


class OpenAIService(BaseProviderService):
    """
    OpenAI Provider Service implementation.
    
    This service uses the official OpenAI Python SDK to interact with OpenAI's API.
    It also supports OpenAI-compatible APIs by allowing custom base URLs.
    
    Supported features:
    - Chat completions (streaming and non-streaming)
    - Image generation (DALL-E)
    - Speech synthesis (TTS)
    - Model listing
    """
    
    def __init__(self, api_key: str, api_url: Optional[str] = None, **kwargs):
        """
        Initialize OpenAI service.
        
        Args:
            api_key: OpenAI API key
            api_url: Optional custom API URL (for OpenAI-compatible APIs)
            **kwargs: Additional parameters:
                - timeout (float): Request timeout in seconds (default: 120.0)
                - max_retries (int): Maximum number of retries (default: 3)
        """
        super().__init__(api_key, api_url, **kwargs)
        
        # Create AsyncOpenAI client
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_url or "https://api.openai.com/v1",
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3)
        )
        
        logger.info(f"[OpenAI Service] Initialized with base_url={api_url or 'default'}")
    
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a chat request and get a complete response (non-streaming).
        
        Args:
            messages: List of message objects with 'role' and 'content'
            model: Model identifier (e.g., 'gpt-4', 'gpt-3.5-turbo')
            **kwargs: Additional parameters:
                - temperature (float): Sampling temperature (0.0-2.0)
                - max_tokens (int): Maximum tokens to generate
                - top_p (float): Nucleus sampling parameter
                - frequency_penalty (float): Frequency penalty (-2.0 to 2.0)
                - presence_penalty (float): Presence penalty (-2.0 to 2.0)
        
        Returns:
            Dict containing:
                - content: The response text
                - role: 'assistant'
                - usage: Token usage information
                - model: The model used
                - finish_reason: Why the generation stopped
        """
        try:
            logger.info(f"[OpenAI Service] Chat request: model={model}, messages={len(messages)}")
            
            # Call OpenAI API
            response: ChatCompletion = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            
            # Convert to unified format
            result = {
                "content": response.choices[0].message.content or "",
                "role": "assistant",
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                },
                "model": response.model,
                "finish_reason": response.choices[0].finish_reason or "stop"
            }
            
            logger.info(
                f"[OpenAI Service] Chat response: "
                f"tokens={result['usage']['total_tokens']}, "
                f"finish_reason={result['finish_reason']}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"[OpenAI Service] Chat error: {e}", exc_info=True)
            raise
    
    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        model: str, 
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a chat request and stream the response.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            model: Model identifier (e.g., 'gpt-4', 'gpt-3.5-turbo')
            **kwargs: Additional parameters (same as chat())
        
        Yields:
            Dict containing:
                - content: Incremental response text
                - chunk_type: 'content' | 'done' | 'error'
                - prompt_tokens: (in done chunk) Number of prompt tokens
                - completion_tokens: (in done chunk) Number of completion tokens
                - total_tokens: (in done chunk) Total tokens used
                - finish_reason: (in done chunk) Why the generation stopped
        """
        try:
            logger.info(f"[OpenAI Service] Stream chat request: model={model}, messages={len(messages)}")
            
            # Call OpenAI API with streaming
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                **kwargs
            )
            
            # Stream chunks
            async for chunk in stream:
                # Skip empty chunks
                if not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                
                # Content chunk
                if delta.content:
                    yield {
                        "content": delta.content,
                        "chunk_type": "content"
                    }
                
                # Done chunk (last chunk with usage info)
                if hasattr(chunk, 'usage') and chunk.usage:
                    yield {
                        "content": "",
                        "chunk_type": "done",
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                        "finish_reason": chunk.choices[0].finish_reason or "stop"
                    }
                    
                    logger.info(
                        f"[OpenAI Service] Stream completed: "
                        f"tokens={chunk.usage.total_tokens}, "
                        f"finish_reason={chunk.choices[0].finish_reason}"
                    )
        
        except Exception as e:
            logger.error(f"[OpenAI Service] Stream error: {e}", exc_info=True)
            # Yield error chunk
            yield {
                "content": "",
                "chunk_type": "error",
                "error": str(e)
            }
    
    async def get_available_models(self) -> List["ModelConfig"]:
        """
        Get list of available models.
        
        Returns:
            List of ModelConfig objects
        """
        from .model_capabilities import ModelConfig, Capabilities
        
        try:
            logger.info("[OpenAI Service] Fetching available models")
            
            # Get models from OpenAI API
            models = await self.client.models.list()
            
            result = []
            for model in models.data:
                model_id = model.id
                lower_id = model_id.lower()
                
                # 推断能力
                vision = any(kw in lower_id for kw in ["vision", "gpt-4o", "gpt-4-turbo"])
                reasoning = any(kw in lower_id for kw in ["o1", "o3"])
                coding = any(kw in lower_id for kw in ["code", "codex"])
                
                result.append(ModelConfig(
                    id=model_id,
                    name=model_id,
                    description=f"OpenAI model: {model_id}",
                    capabilities=Capabilities(
                        vision=vision,
                        search=False,
                        reasoning=reasoning,
                        coding=coding
                    ),
                    context_window=None
                ))
            
            logger.info(f"[OpenAI Service] Found {len(result)} models")
            
            return result
        
        except Exception as e:
            logger.error(f"[OpenAI Service] Error fetching models: {e}", exc_info=True)
            raise
    
    def get_provider_name(self) -> str:
        """
        Get the name of this provider.
        
        Returns:
            'OpenAI'
        """
        return "OpenAI"
    
    async def generate_image(
        self, 
        prompt: str, 
        model: str = "dall-e-3", 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate an image using DALL-E.
        
        Args:
            prompt: Text description of the image to generate
            model: Model to use ('dall-e-2' or 'dall-e-3')
            **kwargs: Additional parameters:
                - size (str): Image size ('1024x1024', '1792x1024', '1024x1792')
                - quality (str): Image quality ('standard' or 'hd')
                - style (str): Image style ('vivid' or 'natural')
                - n (int): Number of images to generate (1-10)
        
        Returns:
            Dict containing:
                - url: URL of the generated image
                - revised_prompt: Revised prompt used by DALL-E
        """
        try:
            logger.info(f"[OpenAI Service] Image generation: model={model}, prompt={prompt[:50]}...")
            
            # Call DALL-E API
            response = await self.client.images.generate(
                model=model,
                prompt=prompt,
                **kwargs
            )
            
            # Extract result
            result = {
                "url": response.data[0].url,
                "revised_prompt": response.data[0].revised_prompt if hasattr(response.data[0], 'revised_prompt') else None
            }
            
            logger.info(f"[OpenAI Service] Image generated: url={result['url']}")
            
            return result
        
        except Exception as e:
            logger.error(f"[OpenAI Service] Image generation error: {e}", exc_info=True)
            raise
    
    async def generate_speech(
        self, 
        text: str, 
        voice: str = "alloy", 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate speech audio from text using TTS.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use ('alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer')
            **kwargs: Additional parameters:
                - model (str): TTS model ('tts-1' or 'tts-1-hd')
                - speed (float): Speech speed (0.25-4.0)
                - response_format (str): Audio format ('mp3', 'opus', 'aac', 'flac')
        
        Returns:
            Dict containing:
                - audio: Audio content as bytes
                - format: Audio format
        """
        try:
            logger.info(f"[OpenAI Service] Speech generation: voice={voice}, text={text[:50]}...")
            
            # Get model and format
            model = kwargs.pop("model", "tts-1")
            audio_format = kwargs.pop("response_format", "mp3")
            
            # Call TTS API
            response = await self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format=audio_format,
                **kwargs
            )
            
            # Read audio content
            audio_content = response.content
            
            result = {
                "audio": audio_content,
                "format": audio_format
            }
            
            logger.info(f"[OpenAI Service] Speech generated: size={len(audio_content)} bytes")
            
            return result
        
        except Exception as e:
            logger.error(f"[OpenAI Service] Speech generation error: {e}", exc_info=True)
            raise
