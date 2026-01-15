"""
OpenAI 语音生成器

处理 OpenAI 的语音合成操作（TTS）。
"""
from typing import Dict, Any, Optional
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class SpeechGenerator:
    """
    OpenAI 语音生成器
    
    负责处理所有语音合成相关的操作。
    """
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, **kwargs):
        """
        初始化语音生成器
        
        Args:
            api_key: OpenAI API key
            base_url: Optional custom API URL
            **kwargs: Additional parameters (timeout, max_retries, etc.)
        """
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        
        # Create AsyncOpenAI client
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3)
        )
        
        logger.info(f"[OpenAI SpeechGenerator] Initialized with base_url={self.base_url}")
    
    async def generate_speech(
        self,
        text: str,
        voice: str = "alloy",
        **kwargs
    ) -> Dict[str, Any]:
        """
        使用 TTS 从文本生成语音
        
        Args:
            text: 要转换的文本
            voice: 使用的语音 ('alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer')
            **kwargs: 额外参数:
                - model (str): TTS 模型 ('tts-1' 或 'tts-1-hd')
                - speed (float): 语音速度 (0.25-4.0)
                - response_format (str): 音频格式 ('mp3', 'opus', 'aac', 'flac')
        
        Returns:
            包含以下字段的字典:
                - audio: 音频内容（字节）
                - format: 音频格式
        """
        try:
            logger.info(f"[OpenAI SpeechGenerator] Speech generation: voice={voice}, text={text[:50]}...")
            
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
            
            logger.info(f"[OpenAI SpeechGenerator] Speech generated: size={len(audio_content)} bytes")
            
            return result
        
        except Exception as e:
            logger.error(f"[OpenAI SpeechGenerator] Speech generation error: {e}", exc_info=True)
            raise
