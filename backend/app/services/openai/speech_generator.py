"""
OpenAI 语音生成器

处理 OpenAI 的语音合成操作（TTS）。
"""
import logging
from typing import Any, Dict, Optional

from ...utils.log_sanitization import summarize_text_for_log, summarize_url_for_log
from ._shared import (
    SPEECH_ALLOWED_OPTION_KEYS,
    audio_format_to_mime_type,
    build_async_client,
    filter_allowed_kwargs,
    read_binary_response_content,
    to_data_url,
)

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
        self.client = build_async_client(
            api_key=api_key,
            base_url=self.base_url,
            timeout=kwargs.get("timeout", 120.0),
            max_retries=kwargs.get("max_retries", 3),
            client=kwargs.get("client"),
        )
        
        logger.info(
            "[OpenAI SpeechGenerator] Initialized with base_url=%s",
            summarize_url_for_log(self.base_url),
        )
    
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
                - url: Data URL 音频内容
                - mime_type: 音频 MIME 类型
                - format: 音频格式
        """
        try:
            logger.info(
                "[OpenAI SpeechGenerator] Speech generation: voice=%s, text=%s",
                voice,
                summarize_text_for_log(text, label="text"),
            )
            request_kwargs = self._normalize_generate_kwargs(kwargs)
            model = request_kwargs.pop("model")
            audio_format = request_kwargs.get("response_format", "mp3")
            
            # Call TTS API
            response = await self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                **request_kwargs
            )
            
            # Read audio content
            audio_content = await read_binary_response_content(response)
            mime_type = audio_format_to_mime_type(audio_format)
            
            result = {
                "url": to_data_url(audio_content, mime_type),
                "mime_type": mime_type,
                "format": audio_format,
            }
            
            logger.info("[OpenAI SpeechGenerator] Speech generated: size=%s bytes", len(audio_content))
            
            return result
        
        except Exception as e:
            logger.error(
                "[OpenAI SpeechGenerator] Speech generation error: %s",
                summarize_text_for_log(e, label="error"),
            )
            raise

    def _normalize_generate_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        normalized = filter_allowed_kwargs(
            kwargs,
            allowed_keys=SPEECH_ALLOWED_OPTION_KEYS,
        )

        model = str(normalized.get("model") or "tts-1").strip() or "tts-1"
        normalized["model"] = model

        response_format = str(normalized.get("response_format") or "mp3").strip().lower() or "mp3"
        if response_format not in {"mp3", "wav", "opus", "aac", "flac", "pcm"}:
            response_format = "mp3"
        normalized["response_format"] = response_format

        if "speed" in normalized:
            try:
                speed = float(normalized["speed"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Unsupported speech speed: {normalized['speed']}") from exc
            normalized["speed"] = max(0.25, min(speed, 4.0))

        return normalized
