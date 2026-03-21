"""
Conversational Image Edit Service - 对话式图片编辑服务

使用 Google Chat SDK 的 chats.create() 和 chat.send_message() API
实现多轮对话式图片编辑。
"""

import logging
import uuid
import time
import base64
import re
import json
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ..common.sdk_initializer import SDKInitializer
from ..common.chat_session_manager import ChatSessionManager
from ..common.file_handler import FileHandler
from ...common.model_capabilities import get_google_capabilities

logger = logging.getLogger(__name__)


class ConversationalImageEditService:
    """
    对话式图片编辑服务
    
    使用 Google Chat SDK 实现多轮对话式图片编辑：
    - create_chat_session: 创建新的 Chat 会话
    - send_edit_message: 发送编辑消息
    - get_chat_history: 获取会话历史
    - delete_chat_session: 删除会话
    """
    _ENHANCE_PROMPT_FALLBACK_MODEL = "gemini-2.5-pro"
    _NON_MULTIMODAL_ENHANCE_KEYWORDS = (
        "imagen",
        "veo",
        "sora",
        "luma",
        "segmentation",
        "try-on",
        "tryon",
        "recontext",
        "upscale",
        "wanx",
        "wan2",
        "dall",
        "flux",
        "midjourney",
        "z-image",
        "-t2i",
        "automl",
        "earth-ai",
        "embedding",
        "aqa",
        "native-audio",
        "computer-use",
        "image-generation",
        "-image",
        "customtools",
    )
    
    def __init__(
        self,
        sdk_initializer: SDKInitializer,
        chat_session_manager: ChatSessionManager,
        file_handler: Optional[FileHandler] = None
    ):
        """
        初始化对话式图片编辑服务
        
        Args:
            sdk_initializer: SDK 初始化器
            chat_session_manager: Chat 会话管理器
            file_handler: 文件处理器（可选，用于处理图片）
        """
        self.sdk_initializer = sdk_initializer
        self.chat_session_manager = chat_session_manager
        self.file_handler = file_handler

    def _supports_thinking(self, model_name: str) -> bool:
        """
        检查模型是否支持 ThinkingConfig

        根据 API 测试结果：
        - gemini-3-pro-image-preview: 支持 thinking + 图片输出 ✅
        - gemini-3-flash-preview: 支持 thinking（但不能生成图片）
        - gemini-2.5-flash-image: 不支持 thinking（400 error）❌
        - gemini-2.0-flash-exp: 不支持 thinking ❌

        安全策略：只对 gemini-3 系列模型启用 thinking
        """
        if not model_name:
            return False
        return 'gemini-3' in model_name.lower()

    def _is_multimodal_enhance_model(self, model_name: str) -> bool:
        """
        判断模型是否适合用于增强提示词（多模态理解）。
        目标：允许 Gemini 多模态理解模型，排除专用媒体生成流水线模型。
        """
        if not model_name:
            return False
        lower_name = model_name.lower()
        if "gemini" not in lower_name:
            return False
        if any(keyword in lower_name for keyword in self._NON_MULTIMODAL_ENHANCE_KEYWORDS):
            return False
        caps = get_google_capabilities(model_name)
        return bool(caps.vision)

    def _resolve_enhance_prompt_model(self, model_hint: Optional[str]) -> str:
        """
        解析增强提示词模型：
        - 优先使用用户指定且满足多模态理解能力的模型
        - 否则回退到默认多模态模型
        """
        hint = str(model_hint or "").strip()
        if hint and self._is_multimodal_enhance_model(hint):
            return hint
        if hint:
            logger.info(
                f"[ConversationalImageEdit] Enhance model '{hint}' is not multimodal-friendly, "
                f"fallback to {self._ENHANCE_PROMPT_FALLBACK_MODEL}"
            )
        return self._ENHANCE_PROMPT_FALLBACK_MODEL

    def _build_enhance_image_part(
        self,
        reference_images: Optional[List[Dict[str, Any]]],
        genai_types: Any
    ) -> Optional[Any]:
        """
        为提示词增强构建参考图 Part（仅取第一张）。
        支持 google_file_uri / data URL。
        """
        if not reference_images:
            return None

        first_image = reference_images[0]
        if not isinstance(first_image, dict):
            return None

        file_uri = str(first_image.get("google_file_uri") or "").strip()
        if file_uri:
            return genai_types.Part(file_data=genai_types.FileData(
                file_uri=file_uri,
                mime_type=first_image.get("mime_type", "image/png"),
            ))

        raw_url = first_image.get("url")
        if not isinstance(raw_url, str) or not raw_url.startswith("data:"):
            return None

        match = re.match(r"^data:(.*?);base64,(.*)$", raw_url)
        if not match:
            return None

        mime_type = match.group(1) or first_image.get("mime_type", "image/png")
        try:
            image_bytes = base64.b64decode(match.group(2))
        except Exception:
            return None

        try:
            return genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        except AttributeError:
            return genai_types.Part(inline_data=genai_types.Blob(
                data=image_bytes,
                mime_type=mime_type,
            ))

    async def _enhance_prompt_two_stage(
        self,
        prompt: str,
        model_hint: Optional[str] = None,
        reference_images: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """
        两段式提示词增强：先用文本模型改写，再用于图片编辑。

        Args:
            prompt: 原始提示词
            model_hint: 可选模型提示（用于选择文本模型）
            reference_images: 参考图片（可选，用于多模态理解）

        Returns:
            增强后的提示词，失败时返回 None
        """
        self.sdk_initializer.ensure_initialized()
        client = self.sdk_initializer.client

        # 选择增强模型（优先使用用户选择的多模态模型）
        text_model = self._resolve_enhance_prompt_model(model_hint)

        system_prompt = (
            "You are a professional edit prompt enhancer. "
            "Return ONLY the enhanced prompt text, no explanations."
        )
        user_prompt = (
            "Rewrite the following image edit instruction to be more direct, "
            "specific, and visually actionable while preserving the intent:\n\n"
            f"{prompt}"
        )
        if reference_images:
            user_prompt += (
                "\n\nUse the attached reference image context to keep subject identity, "
                "product details, and scene constraints consistent."
            )

        try:
            from google.genai import types as genai_types
        except ImportError:
            genai_types = None

        try:
            if genai_types:
                request_parts: List[Any] = []
                image_part = self._build_enhance_image_part(reference_images, genai_types)
                if image_part is not None:
                    request_parts.append(image_part)
                request_parts.append(
                    genai_types.Part.from_text(text=f"{system_prompt}\n\n{user_prompt}")
                )
                response = client.models.generate_content(
                    model=text_model,
                    contents=request_parts,
                )
            else:
                response = client.models.generate_content(
                    model=text_model,
                    contents=f"{system_prompt}\n\n{user_prompt}",
                )

            # 取文本输出
            enhanced = None
            if hasattr(response, 'text') and response.text:
                enhanced = response.text.strip()
            elif hasattr(response, 'parts') and response.parts:
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        enhanced = part.text.strip()
                        break

            if enhanced:
                logger.info(f"[ConversationalImageEdit] Enhanced prompt generated (len={len(enhanced)})")
                return enhanced

        except Exception as e:
            logger.warning(f"[ConversationalImageEdit] Enhance prompt failed: {e}")

        return None

    async def create_chat_session(
        self,
        user_id: str,
        frontend_session_id: str,
        model: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建新的 Chat 会话
        
        Args:
            user_id: 用户 ID
            frontend_session_id: 前端会话 ID
            model: 模型名称
            config: Chat 配置（可选）
        
        Returns:
            包含 chat_id 的字典
        """
        self.sdk_initializer.ensure_initialized()
        client = self.sdk_initializer.client
        
        # 生成 Chat ID
        chat_id = str(uuid.uuid4())
        
        # 创建 Google Chat 对象
        try:
            # 导入 Google SDK 类型
            try:
                from google.genai import types as genai_types
            except ImportError:
                genai_types = None
            
            # 构建 Chat 配置
            # 注意：只提取 GenerateContentConfig 支持的有效字段（image_aspect_ratio, image_resolution）
            # thinking 开关：默认跟随模型能力，若 config 显式关闭则禁用
            enable_thinking = True
            if config and 'enable_thinking' in config:
                enable_thinking = bool(config.get('enable_thinking'))

            if genai_types:
                # 使用官方 SDK 类型
                # 注意：图像生成/编辑这类请求，通常不需要 google_search
                # ✅ 修复：只在显式提供 aspect_ratio 时设置，避免不支持该参数的模型报错
                image_config_dict = {}
                if config and config.get('image_aspect_ratio'):
                    image_config_dict['aspect_ratio'] = config['image_aspect_ratio']
                if config and config.get('image_resolution'):
                    image_config_dict['image_size'] = config['image_resolution']
                
                # ✅ 根据模型判断是否开启思考过程（仅 gemini-3 系列支持）
                thinking_cfg = genai_types.ThinkingConfig(include_thoughts=True) if enable_thinking and self._supports_thinking(model) else None
                # ✅ 修复：只在有参数时创建 ImageConfig，避免空参数导致的问题
                image_config = genai_types.ImageConfig(**image_config_dict) if image_config_dict else None
                # ✅ 禁用安全策略，避免 IMAGE_RECITATION 错误
                safety_settings = [
                    genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                ]
                chat_config = genai_types.GenerateContentConfig(
                    response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
                    thinking_config=thinking_cfg,
                    image_config=image_config,
                    safety_settings=safety_settings,
                    temperature=1.0,  # ✅ 设置较高的 temperature 减少 IMAGE_RECITATION 错误
                    # ✅ 禁用自动函数调用，避免 MALFORMED_FUNCTION_CALL 错误
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True)
                )
            else:
                # 回退到字典格式
                # ✅ 修复：只在显式提供参数时设置 image_config，避免不支持该参数的模型报错
                image_config_dict = {}
                if config and config.get('image_aspect_ratio'):
                    image_config_dict['aspect_ratio'] = config['image_aspect_ratio']
                if config and config.get('image_resolution'):
                    image_config_dict['image_size'] = config['image_resolution']

                chat_config = {
                    'response_modalities': ['TEXT', 'IMAGE'],
                    # ✅ 禁用自动函数调用，避免 MALFORMED_FUNCTION_CALL 错误
                    'automatic_function_calling': {'disable': True}
                }
                if image_config_dict:
                    chat_config['image_config'] = image_config_dict
                if enable_thinking and self._supports_thinking(model):
                    chat_config['thinking_config'] = {'include_thoughts': True}
            
            # 创建 Chat 对象
            # 注意：Google SDK 的 chats.create() 可能需要历史记录
            # 如果有历史，从数据库重建；否则创建新会话
            history = self.chat_session_manager.get_chat_history_for_rebuild(
                frontend_session_id=frontend_session_id,
                mode='image-chat-edit'
            )
            
            if history and genai_types:
                # 从历史重建 Chat
                history_contents = []
                for msg in history:
                    parts = []
                    # 处理文本
                    if msg.get('parts'):
                        for part in msg['parts']:
                            if 'text' in part:
                                parts.append(genai_types.Part.from_text(text=part['text']))
                            elif 'file_data' in part:
                                parts.append(genai_types.Part(file_data=genai_types.FileData(
                                    file_uri=part['file_data']['file_uri'],
                                    mime_type=part['file_data']['mime_type']
                                )))
                            elif 'inline_data' in part:
                                parts.append(genai_types.Part(inline_data=genai_types.Blob(
                                    data=base64.b64decode(part['inline_data']['data']),
                                    mime_type=part['inline_data']['mime_type']
                                )))
                    history_contents.append(genai_types.Content(
                        role=msg.get('role', 'user'),
                        parts=parts
                    ))
                
                chat = client.aio.chats.create(
                    model=model,
                    config=chat_config if genai_types else None,
                    history=history_contents if history_contents else None
                )
            else:
                # 创建新的 Chat 会话
                chat = client.aio.chats.create(
                    model=model,
                    config=chat_config if genai_types else None
                )
            
            # 保存到数据库
            chat_session = self.chat_session_manager.create_chat_session(
                chat_id=chat_id,
                user_id=user_id,
                frontend_session_id=frontend_session_id,
                model_name=model,
                config=config,
                chat_object=chat
            )
            
            logger.info(
                f"[ConversationalImageEdit] Created chat session: "
                f"chat_id={chat_id}, user_id={user_id}, model={model}"
            )
            
            return {
                'chat_id': chat_id,
                'frontend_session_id': frontend_session_id,
                'model': model
            }
            
        except Exception as e:
            logger.error(f"[ConversationalImageEdit] Failed to create chat session: {e}", exc_info=True)
            raise
    
    async def send_edit_message(
        self,
        chat_id: str,
        prompt: str,
        reference_images: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        frontend_session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        发送编辑消息到 Chat 会话
        
        注意：Google Chat SDK 的 chat 对象会自动维护历史记录。
        我们只需要使用同一个 chat 对象多次调用 send_message() 即可实现多轮对话。
        
        Args:
            chat_id: Chat ID
            prompt: 编辑提示词
            reference_images: 参考图片列表（可选）
            config: 可选的配置覆盖（例如更新图片尺寸、宽高比等）
            user_id: 用户 ID（用于生成附件元数据）
            frontend_session_id: 前端会话 ID（用于生成附件元数据）
        
        Returns:
            编辑后的图片列表（包含完整的附件元数据）
        """
        self.sdk_initializer.ensure_initialized()
        client = self.sdk_initializer.client
        
        # ✅ 预先获取 chat_session 元数据（用于获取 model_name 等，构建 send_config 时需要）
        chat_session = self.chat_session_manager.get_chat_session(chat_id)
        model_name = chat_session.model_name if chat_session else None

        # 判断是否需要传递图片
        # 根据官方示例（intro_gemini_3_image_gen.ipynb），多轮对话中应该传递上一轮生成的图片
        # 如果前端通过 CONTINUITY LOGIC 传递了图片，就使用它（更安全，即使 Chat SDK 有历史记录）
        should_include_image = reference_images is not None and len(reference_images) > 0

        # ✅ 重试机制：如果遇到 MALFORMED_FUNCTION_CALL 错误，清除缓存并重建 chat 对象
        # 这是因为缓存的 chat 对象可能包含有问题的历史（function_call/function_response）
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self._send_edit_message_internal(
                    chat_id=chat_id,
                    prompt=prompt,
                    reference_images=reference_images,
                    config=config,
                    chat_session=chat_session,
                    model_name=model_name,
                    should_include_image=should_include_image,
                    client=client,
                    skip_cache=(attempt > 0),  # 第二次尝试时跳过缓存
                    user_id=user_id,
                    frontend_session_id=frontend_session_id
                )
            except ValueError as e:
                error_msg = str(e)
                if 'MALFORMED_FUNCTION_CALL' in error_msg and attempt < max_retries - 1:
                    # 遇到 MALFORMED_FUNCTION_CALL 错误，清除缓存并重试
                    logger.warning(
                        f"[ConversationalImageEdit] MALFORMED_FUNCTION_CALL detected, "
                        f"clearing cache and retrying (attempt {attempt + 1}/{max_retries})"
                    )
                    # 清除缓存中的 chat 对象
                    if chat_id in self.chat_session_manager._chat_cache:
                        del self.chat_session_manager._chat_cache[chat_id]
                    last_error = e
                    continue
                else:
                    raise
        
        # 如果所有重试都失败，抛出最后一个错误
        if last_error:
            raise last_error

    async def _send_edit_message_internal(
        self,
        chat_id: str,
        prompt: str,
        reference_images: Optional[List[Dict[str, Any]]],
        config: Optional[Dict[str, Any]],
        chat_session,
        model_name: Optional[str],
        should_include_image: bool,
        client,
        skip_cache: bool = False,
        user_id: Optional[str] = None,
        frontend_session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        内部方法：发送编辑消息到 Chat 会话
        
        Args:
            skip_cache: 如果为 True，跳过缓存并重建 chat 对象（不带历史）
            user_id: 用户 ID（用于生成附件元数据）
            frontend_session_id: 前端会话 ID（用于生成附件元数据）
        """
        # 获取 Chat 对象（从缓存）
        # 注意：Chat 对象会自动维护历史记录，不需要手动重建
        chat = None if skip_cache else self.chat_session_manager.get_chat_object_from_cache(chat_id)
        
        if skip_cache:
            logger.info(
                f"[ConversationalImageEdit] Skipping cache due to previous MALFORMED_FUNCTION_CALL error, "
                f"will create fresh chat object without history"
            )

        if not chat:
            # 如果缓存中没有，说明这是第一次调用，应该先创建 chat 会话
            if not chat_session:
                raise ValueError(f"Chat session not found: {chat_id}. Please create a chat session first.")
            
            # 从数据库重建 Chat 对象（仅第一次调用时）
            # 导入 Google SDK 类型
            try:
                from google.genai import types as genai_types
            except ImportError:
                genai_types = None
            
            # 重建 Chat 配置
            # 注意：只提取 GenerateContentConfig 支持的有效字段
            chat_config = None
            if chat_session.config_json:
                try:
                    config_dict = json.loads(chat_session.config_json)
                    # 只提取 GenerateContentConfig 支持的有效字段
                    # ⚠️ 向后兼容：同时检查 camelCase（旧数据）和 snake_case（新数据）
                    valid_config = {}
                    # image_aspect_ratio / imageAspectRatio
                    if 'image_aspect_ratio' in config_dict:
                        valid_config['image_aspect_ratio'] = config_dict['image_aspect_ratio']
                    elif 'imageAspectRatio' in config_dict:
                        valid_config['image_aspect_ratio'] = config_dict['imageAspectRatio']
                    # image_resolution / imageResolution
                    if 'image_resolution' in config_dict:
                        valid_config['image_resolution'] = config_dict['image_resolution']
                    elif 'imageResolution' in config_dict:
                        valid_config['image_resolution'] = config_dict['imageResolution']
                    
                    # thinking 开关：默认跟随模型能力，若 config 显式关闭则禁用
                    # ⚠️ 向后兼容：同时检查 camelCase（旧数据）和 snake_case（新数据）
                    enable_thinking = True
                    if 'enable_thinking' in config_dict:
                        enable_thinking = bool(config_dict.get('enable_thinking'))
                    elif 'enableThinking' in config_dict:
                        enable_thinking = bool(config_dict.get('enableThinking'))

                    if genai_types and valid_config:
                        # 构建 ImageConfig
                        image_config_dict = {}
                        if 'image_aspect_ratio' in valid_config:
                            image_config_dict['aspect_ratio'] = valid_config['image_aspect_ratio']
                        if 'image_resolution' in valid_config:
                            image_config_dict['image_size'] = valid_config['image_resolution']

                        # ✅ 根据模型判断是否开启思考过程
                        thinking_cfg = genai_types.ThinkingConfig(include_thoughts=True) if enable_thinking and self._supports_thinking(chat_session.model_name) else None
                        # ✅ 禁用安全策略，避免 IMAGE_RECITATION 错误
                        safety_settings = [
                            genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                            genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                            genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                            genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                        ]
                        chat_config = genai_types.GenerateContentConfig(
                            response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
                            thinking_config=thinking_cfg,
                            image_config=genai_types.ImageConfig(**image_config_dict) if image_config_dict else None,
                            safety_settings=safety_settings,
                            temperature=1.0,  # ✅ 设置较高的 temperature 减少 IMAGE_RECITATION 错误
                            # ✅ 禁用自动函数调用，避免 MALFORMED_FUNCTION_CALL 错误
                            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True)
                        )
                        logger.debug(f"[DEBUG] chat_config 创建成功 (genai_types 路径): response_modalities=[TEXT, IMAGE], image_config={image_config_dict}, enable_thinking={enable_thinking}")
                    elif valid_config:
                        chat_config = {
                            'response_modalities': ['TEXT', 'IMAGE'],
                            'image_config': {},
                            # ✅ 禁用自动函数调用，避免 MALFORMED_FUNCTION_CALL 错误
                            'automatic_function_calling': {'disable': True}
                        }
                        if enable_thinking and self._supports_thinking(chat_session.model_name):
                            chat_config['thinking_config'] = {'include_thoughts': True}
                        if 'image_aspect_ratio' in valid_config:
                            chat_config['image_config']['aspect_ratio'] = valid_config['image_aspect_ratio']
                        if 'image_resolution' in valid_config:
                            chat_config['image_config']['image_size'] = valid_config['image_resolution']
                        logger.debug(f"[DEBUG] chat_config 创建成功 (字典路径): response_modalities={chat_config['response_modalities']}, image_config={chat_config['image_config']}, enable_thinking={enable_thinking}")
                except Exception as e:
                    logger.warning(f"[ConversationalImageEdit] Failed to parse config_json: {e}")

            # ✅ 确保 chat_config 至少包含基本配置（response_modalities + thinking_config）
            # 当 config_json 为空或解析失败时，chat_config 仍为 None，需要兜底
            if chat_config is None:
                if genai_types:
                    enable_thinking = True
                    if chat_session.config_json:
                        try:
                            cfg = json.loads(chat_session.config_json)
                            if 'enable_thinking' in cfg:
                                enable_thinking = bool(cfg.get('enable_thinking'))
                        except Exception:
                            pass
                    thinking_cfg = genai_types.ThinkingConfig(include_thoughts=True) if enable_thinking and self._supports_thinking(chat_session.model_name) else None
                    # ✅ 禁用安全策略，避免 IMAGE_RECITATION 错误
                    safety_settings = [
                        genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                        genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                        genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                        genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                    ]
                    chat_config = genai_types.GenerateContentConfig(
                        response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
                        thinking_config=thinking_cfg,
                        safety_settings=safety_settings,
                        temperature=1.0,  # ✅ 设置较高的 temperature 减少 IMAGE_RECITATION 错误
                        # ✅ 禁用自动函数调用，避免 MALFORMED_FUNCTION_CALL 错误
                        automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True)
                    )
                    logger.debug(f"[DEBUG] chat_config 创建成功 (兜底逻辑 genai_types): response_modalities=[TEXT, IMAGE], enable_thinking={enable_thinking}")
                else:
                    chat_config = {
                        'response_modalities': ['TEXT', 'IMAGE'],
                        # ✅ 禁用自动函数调用，避免 MALFORMED_FUNCTION_CALL 错误
                        'automatic_function_calling': {'disable': True}
                    }
                    enable_thinking = True
                    if chat_session.config_json:
                        try:
                            cfg = json.loads(chat_session.config_json)
                            # ⚠️ 向后兼容：同时检查 camelCase（旧数据）和 snake_case（新数据）
                            if 'enable_thinking' in cfg:
                                enable_thinking = bool(cfg.get('enable_thinking'))
                            elif 'enableThinking' in cfg:
                                enable_thinking = bool(cfg.get('enableThinking'))
                        except Exception:
                            pass
                    if enable_thinking and self._supports_thinking(chat_session.model_name):
                        chat_config['thinking_config'] = {'include_thoughts': True}
                    logger.debug(f"[DEBUG] chat_config 创建成功 (兜底逻辑 字典): response_modalities={chat_config['response_modalities']}, enable_thinking={enable_thinking}")

            # ✅ 简化设计：不加载历史记录
            # 原因：每次编辑都是独立的，前端传什么图片 AI 就编辑什么图片
            # 图片来源由前端控制（用户上传的 或 上一轮生成的），不需要 AI 从历史中"记住"
            # 这样可以避免：
            # 1. 不必要的数据库查询
            # 2. 重复的图片数据传递给 API
            # 3. token 浪费和延迟
            
            # 创建新的 Chat 对象（无历史）
            chat = client.aio.chats.create(
                model=chat_session.model_name,
                config=chat_config
            )
            logger.info(f"[ConversationalImageEdit] Created fresh chat object (no history) for chat_id={chat_id}")
            
            # 缓存 Chat 对象
            if chat:
                self.chat_session_manager.cache_chat_object(chat_id, chat)
            else:
                raise ValueError(f"Failed to create chat object for chat_id={chat_id}")
        else:
            # Chat 对象已存在，说明不是第一轮
            logger.debug(f"[ConversationalImageEdit] Using existing chat object for chat_id={chat_id}")
        
        # 构建消息内容
        # 参考：chat.send_message(message) 可以接受字符串或 Part 对象/列表
        # 根据官方示例（intro_gemini_3_image_gen.ipynb Cell 33），多轮对话中应该传递上一轮生成的图片
        # 如果前端通过 CONTINUITY LOGIC 传递了图片，就使用它（更安全，即使 Chat SDK 有历史记录）
        
        # 导入 Google SDK 类型
        try:
            from google.genai import types as genai_types
        except ImportError:
            genai_types = None
        
        # 构建消息 parts
        message_parts = []

        # ✅ AI 增强提示词（两段式稳定方案）
        enhance_prompt = bool(config.get('enhance_prompt')) if config else False
        enhanced_prompt_text = None
        if enhance_prompt:
            enhance_model = config.get('enhance_prompt_model') if config else None
            enhanced_prompt_text = await self._enhance_prompt_two_stage(
                prompt,
                model_hint=enhance_model or model_name,
                reference_images=reference_images
            )
            if enhanced_prompt_text:
                prompt = enhanced_prompt_text
        
        # 添加参考图片（如果前端传递了图片）
        # 注意：根据官方示例，多轮对话中应该传递上一轮生成的图片数据
        # 即使 Chat SDK 会自动维护历史记录，显式传递图片也是安全的
        if should_include_image and reference_images:
            # ✅ 记录 reference_images 的键和数量，但不记录完整的 BASE64 内容
            ref_img_keys = list(reference_images.keys()) if isinstance(reference_images, dict) else []
            ref_img_count = len(reference_images) if isinstance(reference_images, list) else len(ref_img_keys)
            logger.debug(f"[ConversationalImageEdit] First round: including reference images (count: {ref_img_count}, keys: {ref_img_keys})")
            for ref_img in reference_images:
                # 处理图片
                if ref_img.get('google_file_uri'):
                    # 使用 Google File URI
                    if genai_types:
                        message_parts.append(genai_types.Part(file_data=genai_types.FileData(
                            file_uri=ref_img['google_file_uri'],
                            mime_type=ref_img.get('mime_type', 'image/png')
                        )))
                    else:
                        message_parts.append({
                            'file_data': {
                                'file_uri': ref_img['google_file_uri'],
                                'mime_type': ref_img.get('mime_type', 'image/png')
                            }
                        })
                elif ref_img.get('url'):
                    url = ref_img['url']
                    if url.startswith('data:'):
                        # Base64 Data URL
                        match = re.match(r'^data:(.*?);base64,(.*)$', url)
                        if match:
                            mime_type = match.group(1) or ref_img.get('mime_type', 'image/png')
                            base64_str = match.group(2)
                            # ✅ 记录 BASE64 长度，但不记录完整内容
                            logger.debug(f"[ConversationalImageEdit] 处理 Base64 Data URL: mime_type={mime_type}, base64_length={len(base64_str)} 字符")
                            image_bytes = base64.b64decode(base64_str)
                            
                            if genai_types:
                                # 使用官方示例的方式：Part.from_bytes()
                                # 参考：intro_gemini_3_image_gen.ipynb Cell 33
                                try:
                                    message_parts.append(genai_types.Part.from_bytes(
                                        data=image_bytes,
                                        mime_type=mime_type
                                    ))
                                except AttributeError:
                                    # 如果 from_bytes 不存在，回退到 inline_data 方式
                                    message_parts.append(genai_types.Part(inline_data=genai_types.Blob(
                                        data=image_bytes,
                                        mime_type=mime_type
                                    )))
                            else:
                                # ✅ 注意：这里存储 base64_str 到字典中，但不会在日志中输出完整内容
                                message_parts.append({
                                    'inline_data': {
                                        'mime_type': mime_type,
                                        'data': base64_str  # 仅用于 API 调用，不会记录到日志
                                    }
                                })
                    elif url.startswith('http://') or url.startswith('https://'):
                        # HTTP URL：需要下载图片
                        logger.info(f"[ConversationalImageEdit] 下载 HTTP URL 图片: {url[:60]}...")
                        try:
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                                    if response.status == 200:
                                        image_bytes = await response.read()
                                        mime_type = ref_img.get('mime_type') or response.headers.get('Content-Type', 'image/png')
                                        
                                        if genai_types:
                                            # 使用官方示例的方式：Part.from_bytes()
                                            try:
                                                message_parts.append(genai_types.Part.from_bytes(
                                                    data=image_bytes,
                                                    mime_type=mime_type
                                                ))
                                                logger.info(f"[ConversationalImageEdit] ✅ HTTP URL 下载成功，大小: {len(image_bytes)} bytes")
                                            except AttributeError:
                                                # 如果 from_bytes 不存在，回退到 inline_data 方式
                                                message_parts.append(genai_types.Part(inline_data=genai_types.Blob(
                                                    data=image_bytes,
                                                    mime_type=mime_type
                                                )))
                                        else:
                                            # 回退到字典格式
                                            base64_str = base64.b64encode(image_bytes).decode('utf-8')
                                            message_parts.append({
                                                'inline_data': {
                                                    'mime_type': mime_type,
                                                    'data': base64_str
                                                }
                                            })
                                    else:
                                        raise ValueError(f"HTTP {response.status}: Failed to download image from {url[:60]}...")
                        except Exception as e:
                            logger.error(f"[ConversationalImageEdit] ❌ HTTP URL 下载失败: {e}")
                            raise ValueError(f"Failed to download image from URL: {str(e)}")
        else:
            if not should_include_image:
                logger.info(
                    f"[ConversationalImageEdit] No reference images provided. "
                    f"Will send text prompt only (Chat SDK will use history if available)."
                )
        
        # 添加文本提示
        if genai_types:
            message_parts.append(genai_types.Part.from_text(text=prompt))
        else:
            message_parts.append({'text': prompt})
        
        # ✅ 调试日志：记录 message_parts 的内容
        logger.debug(f"[DEBUG] message_parts 数量: {len(message_parts)}")
        for i, part in enumerate(message_parts):
            part_type = type(part).__name__
            if hasattr(part, 'inline_data') and part.inline_data:
                logger.debug(f"[DEBUG] message_parts[{i}]: type={part_type}, has_inline_data=True, mime_type={getattr(part.inline_data, 'mime_type', 'unknown')}")
            elif hasattr(part, 'text') and part.text:
                logger.debug(f"[DEBUG] message_parts[{i}]: type={part_type}, has_text=True, text_preview={part.text[:50]}...")
            elif hasattr(part, 'file_data') and part.file_data:
                logger.debug(f"[DEBUG] message_parts[{i}]: type={part_type}, has_file_data=True")
            else:
                logger.debug(f"[DEBUG] message_parts[{i}]: type={part_type}, attrs={dir(part)[:5]}...")
        
        # 构建要发送的消息
        # 如果只有一个 part（只有文本），直接使用文本字符串；否则使用列表
        if len(message_parts) == 1 and genai_types:
            # 只有一个文本 part，可以直接使用字符串（更简洁）
            message_to_send = prompt
            logger.debug(f"[DEBUG] message_to_send: 使用纯文本字符串")
        elif len(message_parts) == 1:
            # 回退到 part 对象
            message_to_send = message_parts[0]
            logger.debug(f"[DEBUG] message_to_send: 使用单个 part 对象")
        else:
            # 多个 parts（图片 + 文本），使用列表
            message_to_send = message_parts
            logger.debug(f"[DEBUG] message_to_send: 使用 {len(message_parts)} 个 parts 的列表")
        
        # 发送消息
        if not chat:
            raise ValueError(f"Chat object is None for chat_id={chat_id}. Cannot send message.")
        
        try:
            # 导入 Google SDK 类型
            try:
                from google.genai import types as genai_types
            except ImportError:
                genai_types = None
            
            # 构建可选的配置覆盖（例如更新图片尺寸、宽高比）
            # ⚠️ 重要：Google SDK chat.send_message(config=...) 会完全替换 chats.create() 的默认 config
            # 因此 send_config 必须包含所有必要字段（response_modalities, thinking_config, image_config）
            # 参考 SDK 源码 chats.py: config=config if config else self._config
            send_config = None
            if genai_types:
                # ✅ 始终创建 send_config 以确保 safety_settings 被应用
                # 如果提供了配置覆盖，构建完整的配置（不能只传 image_config，否则会丢失其他配置）
                image_config_dict = {}
                if config:
                    if config.get('image_aspect_ratio'):
                        image_config_dict['aspect_ratio'] = config['image_aspect_ratio']
                    if config.get('image_resolution'):
                        image_config_dict['image_size'] = config['image_resolution']

                # ✅ 获取模型名以判断是否支持 thinking
                model_name = chat_session.model_name if chat_session else ''
                thinking_cfg = genai_types.ThinkingConfig(include_thoughts=True) if self._supports_thinking(model_name) else None
                # ✅ 禁用安全策略，避免 IMAGE_RECITATION 错误
                safety_settings = [
                    genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                ]
                send_config = genai_types.GenerateContentConfig(
                    response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
                    thinking_config=thinking_cfg,
                    image_config=genai_types.ImageConfig(**image_config_dict) if image_config_dict else None,
                    safety_settings=safety_settings,
                    temperature=1.0,  # ✅ 设置较高的 temperature 减少 IMAGE_RECITATION 错误
                    # ✅ 禁用自动函数调用，避免 MALFORMED_FUNCTION_CALL 错误
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=True)
                )
                logger.debug(f"[DEBUG] send_config 创建成功: response_modalities=[TEXT, IMAGE], image_config={image_config_dict if image_config_dict else 'None'}, safety_settings=已禁用")

            # 调用 chat.send_message()（非流式）
            # 注意：Chat 对象会自动维护历史记录，所以直接调用即可
            # 如果提供了配置覆盖，使用它；否则使用创建 chat 时的默认配置
            logger.debug(f"[DEBUG] 发送消息: send_config={'存在' if send_config else '不存在（使用 chat 默认配置）'}")
            logger.debug(f"[DEBUG] 开始调用 chat.send_message()...")
            import time as _time
            _start_time = _time.time()
            try:
                # 使用非流式响应，因为这里需要返回完整的图片+文本+思考过程
                if send_config:
                    response = await chat.send_message(message=message_to_send, config=send_config)
                else:
                    response = await chat.send_message(message=message_to_send)
                
                _elapsed = _time.time() - _start_time
                logger.debug(f"[DEBUG] chat.send_message() 完成，耗时: {_elapsed:.2f}秒")
            except Exception as e:
                _elapsed = _time.time() - _start_time
                logger.error(f"[DEBUG] chat.send_message() 失败，耗时: {_elapsed:.2f}秒, 错误: {e}")
                raise
            
            # 检查 finish_reason（参考官方示例 Cell 17）
            # 如果 finish_reason 不是 STOP，说明可能有错误
            if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    try:
                        from google.genai import types as genai_types
                        if hasattr(genai_types, 'FinishReason'):
                            if candidate.finish_reason != genai_types.FinishReason.STOP:
                                reason = candidate.finish_reason
                                error_msg = f"Prompt Content Error: {reason}"
                                logger.error(f"[ConversationalImageEdit] {error_msg}")
                                raise ValueError(error_msg)
                    except (ImportError, AttributeError):
                        # 如果无法导入 FinishReason，跳过检查
                        pass
            
            # 提取编辑后的图片、文本和思考过程
            results = []
            text_responses = []  # 收集文本响应
            thoughts = []  # 收集思考过程（thoughts）

            def _extract_image_from_part(part) -> Optional[Dict[str, str]]:
                """
                尝试从 part 中提取图片
                
                ✅ 按照官方 SDK 示例模式：
                   if part.inline_data is not None:
                       image = part.as_image()
                       
                注意：使用 `is not None` 而不是 `hasattr`，因为 SDK 使用属性描述符，
                hasattr 会返回 True 即使值为 None
                """
                import io
                
                # 检查 inline_data 是否存在且不为 None（官方 SDK 模式）
                inline_data = getattr(part, 'inline_data', None)
                
                # ✅ 详细调试日志：记录 part 的所有属性
                part_attrs = [attr for attr in dir(part) if not attr.startswith('_')]
                logger.info(f"[ConversationalImageEdit] _extract_image_from_part: part type={type(part).__name__}, attrs={part_attrs[:10]}...")
                
                # ✅ 详细调试日志：记录 inline_data 的实际类型和内容
                if inline_data is not None:
                    inline_data_type = type(inline_data).__name__
                    inline_data_data = getattr(inline_data, 'data', None)
                    inline_data_mime = getattr(inline_data, 'mime_type', None)
                    data_type = type(inline_data_data).__name__ if inline_data_data is not None else 'None'
                    data_len = len(inline_data_data) if inline_data_data is not None and hasattr(inline_data_data, '__len__') else 'N/A'
                    logger.info(f"[ConversationalImageEdit] _extract_image_from_part: inline_data type={inline_data_type}, data type={data_type}, data len={data_len}, mime={inline_data_mime}")
                else:
                    logger.info(f"[ConversationalImageEdit] _extract_image_from_part: inline_data=None")
                
                if inline_data is not None:
                    # 方法1: 优先使用 as_image()（官方推荐方式）
                    try:
                        logger.info(f"[ConversationalImageEdit] Trying as_image() method...")
                        img = part.as_image()
                        logger.info(f"[ConversationalImageEdit] as_image() returned: type={type(img).__name__}, is_none={img is None}")
                        if img is not None:
                            img_bytes_io = io.BytesIO()
                            img.save(img_bytes_io, format='PNG')
                            img_bytes_io.seek(0)
                            image_bytes = img_bytes_io.read()
                            base64_str = base64.b64encode(image_bytes).decode('utf-8')
                            logger.info(f"[ConversationalImageEdit] ✅ Extracted image via as_image(), size={len(image_bytes)} bytes")
                            return {
                                'url': f"data:image/png;base64,{base64_str}",
                                'mime_type': 'image/png',
                                'size': len(image_bytes)  # 文件大小（bytes）
                            }
                        else:
                            logger.warning(f"[ConversationalImageEdit] as_image() returned None, trying inline_data.data")
                    except Exception as e:
                        logger.warning(f"[ConversationalImageEdit] as_image() failed: {e}, trying inline_data.data")
                    
                    # 方法2: 回退到直接读取 inline_data.data
                    try:
                        logger.info(f"[ConversationalImageEdit] Trying inline_data.data fallback...")
                        image_bytes = getattr(inline_data, 'data', None)
                        logger.info(f"[ConversationalImageEdit] inline_data.data: type={type(image_bytes).__name__ if image_bytes is not None else 'None'}")
                        # 兼容 data 为 str/base64 的情况
                        if isinstance(image_bytes, str):
                            data_str = image_bytes
                            if data_str.startswith('data:'):
                                _, data_str = data_str.split(',', 1)
                            try:
                                image_bytes = base64.b64decode(data_str)
                            except Exception as e:
                                logger.warning(f"[ConversationalImageEdit] inline_data base64 decode failed: {e}")
                                image_bytes = None
                        elif isinstance(image_bytes, memoryview):
                            image_bytes = image_bytes.tobytes()
                        elif isinstance(image_bytes, bytearray):
                            image_bytes = bytes(image_bytes)
                        elif isinstance(image_bytes, list):
                            try:
                                image_bytes = bytes(image_bytes)
                            except Exception as e:
                                logger.warning(f"[ConversationalImageEdit] inline_data list->bytes failed: {e}")
                                image_bytes = None
                        mime_type = getattr(inline_data, 'mime_type', None) or 'image/png'
                        if image_bytes:
                            base64_str = base64.b64encode(image_bytes).decode('utf-8')
                            logger.info(f"[ConversationalImageEdit] ✅ Extracted image via inline_data.data, size={len(image_bytes)} bytes, mime={mime_type}")
                            return {
                                'url': f"data:{mime_type};base64,{base64_str}",
                                'mime_type': mime_type,
                                'size': len(image_bytes)  # 文件大小（bytes）
                            }
                    except Exception as e:
                        logger.warning(f"[ConversationalImageEdit] inline_data.data extraction failed: {e}")

                # 记录 file_data 供诊断（某些响应可能使用 file_uri 返回图片）
                file_data = getattr(part, 'file_data', None)
                file_uri = getattr(file_data, 'file_uri', None) if file_data else None
                if file_uri:
                    logger.info(f"[ConversationalImageEdit] _extract_image_from_part: file_data uri={file_uri}")

                logger.info(f"[ConversationalImageEdit] _extract_image_from_part: no image found")
                return None
            
            # 记录响应结构用于调试
            logger.debug(f"[ConversationalImageEdit] Response structure: has_candidates={hasattr(response, 'candidates')}, has_parts={hasattr(response, 'parts')}, candidates_count={len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")
            
            # 按照官方示例的模式：
            # - Cell 19, 23: 使用 response.parts 来获取 thoughts（包含所有 parts）
            # - Cell 17, 25, 29, 31, 33, 37: 使用 response.candidates[0].content.parts 来获取最终内容（不包括 thoughts）
            # 我们需要同时使用两者：
            # 1. response.parts 用于获取 thoughts
            # 2. response.candidates[0].content.parts 用于获取最终的图片和文本
            
            # 首先从 response.parts 获取 thoughts（参考官方示例 Cell 19, 23）
            all_parts = None
            if hasattr(response, 'parts') and response.parts:
                all_parts = response.parts
                logger.info(f"[ConversationalImageEdit] Using response.parts for all content, count={len(all_parts)}")
            
            # 然后从 response.candidates[0].content.parts 获取最终内容（参考官方示例 Cell 17, 25, 29, 31, 33, 37）
            content_parts = None
            if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                logger.debug(f"[ConversationalImageEdit] Candidate structure: has_content={hasattr(candidate, 'content')}, has_parts={hasattr(candidate.content, 'parts') if hasattr(candidate, 'content') else False}")
                
                if hasattr(candidate, 'content') and candidate.content:
                    content_parts = getattr(candidate.content, 'parts', None)
                    if content_parts:
                        logger.info(f"[ConversationalImageEdit] Using response.candidates[0].content.parts for final content, count={len(content_parts)}")
            
            # 如果没有 content_parts，回退到 all_parts
            if not content_parts and all_parts:
                content_parts = all_parts
                logger.info(f"[ConversationalImageEdit] Falling back to response.parts for final content")
            
            # 步骤1: 从 response.parts 收集 thoughts（参考官方示例 Cell 19, 23）
            # ✅ 重要：根据官方文档，"The last image within Thinking is also the final rendered image."
            # 所以我们需要保存最后一个 thought 图片，以便在没有非 thought 图片时使用
            last_thought_image = None  # 保存最后一个 thought 图片
            
            if all_parts:
                logger.info(f"[ConversationalImageEdit] Processing {len(all_parts)} parts from response.parts for thoughts")
                for idx, part in enumerate(all_parts):
                    # 跳过 function_call 和 function_response
                    if getattr(part, 'function_call', None) is not None or getattr(part, 'function_response', None) is not None:
                        logger.debug(f"[ConversationalImageEdit] Skipping function_call/function_response in response.parts[{idx}]")
                        continue

                    # ✅ 使用 getattr 检查 thought 属性（官方 SDK 模式）
                    thought_value = getattr(part, 'thought', None)
                    inline_data_value = getattr(part, 'inline_data', None)
                    text_value = getattr(part, 'text', None)
                    logger.info(f"[ConversationalImageEdit] Part {idx}: thought={thought_value}, has_inline_data={inline_data_value is not None}, has_text={text_value is not None}")

                    # 收集思考过程（thoughts）- 参考官方示例 Cell 19, 23
                    # ✅ 使用 `is True` 或 truthy 检查，因为 thought 可能是 True/False/None
                    if thought_value:
                        thought_content = None
                        thought_type = None
                        
                        thought_image = _extract_image_from_part(part)
                        if thought_image:
                            thought_content = thought_image['url']
                            thought_type = 'image'
                            # ✅ 保存最后一个 thought 图片（根据官方文档，这也是最终图片）
                            last_thought_image = thought_image
                            logger.info(f"[ConversationalImageEdit] ✅ Saved thought image as potential final image (part {idx})")
                        elif text_value:
                            thought_content = text_value
                            thought_type = 'text'
                            logger.info(f"[ConversationalImageEdit] Part {idx} is text thought: {thought_content[:50] if thought_content else ''}...")
                        
                        if thought_content:
                            thoughts.append({
                                'type': thought_type,
                                'content': thought_content
                            })
                            logger.debug(f"[ConversationalImageEdit] Part {idx} is a thought (type={thought_type}), collected for frontend display")
                
                # ✅ 添加思考处理总结日志
                logger.info(f"[ConversationalImageEdit] Thought processing complete: collected {len(thoughts)} thoughts, last_thought_image={'Yes' if last_thought_image else 'No'}")
            
            # 步骤2: 从 response.parts 提取最终的图片和文本（参考官方示例）
            # 官方示例: for part in response.parts: if part.text is not None: ... elif part.inline_data is not None: image = part.as_image() ...
            if content_parts:
                logger.debug(f"[DEBUG] 响应包含 {len(content_parts)} 个 parts")
                for idx, part in enumerate(content_parts):
                    # ✅ 使用 getattr 获取属性值（官方 SDK 模式）
                    thought_value = getattr(part, 'thought', None)
                    inline_data_value = getattr(part, 'inline_data', None)
                    text_value = getattr(part, 'text', None)
                    
                    logger.debug(f"[DEBUG] Part {idx} 结构分析: thought={thought_value}, has_inline_data={inline_data_value is not None}, has_text={text_value is not None}")

                    # 跳过 thoughts（参考官方示例 Cell 17）
                    if thought_value:
                        logger.debug(f"[ConversationalImageEdit] Skipping thought part {idx} (already collected from response.parts)")
                        continue

                    # 跳过 function_call 和 function_response（避免处理工具调用）
                    if getattr(part, 'function_call', None) is not None or getattr(part, 'function_response', None) is not None:
                        logger.debug(f"[ConversationalImageEdit] Skipping function_call/function_response part {idx}")
                        continue
                    
                    # ✅ 按照官方 SDK 模式：先检查 inline_data，再检查 text
                    # 官方示例: if part.inline_data is not None: image = part.as_image()
                    if inline_data_value is not None:
                        image_result = _extract_image_from_part(part)
                        if image_result:
                            # ✅ 为图片添加完整的附件元数据
                            attachment_id = str(uuid.uuid4())
                            message_id = str(uuid.uuid4())  # AI 响应消息 ID
                            timestamp = int(time.time() * 1000)
                            
                            # 生成文件名
                            mime_type = image_result.get('mime_type', 'image/png')
                            ext = 'png' if 'png' in mime_type else 'jpeg' if 'jpeg' in mime_type or 'jpg' in mime_type else 'png'
                            filename = f"edited-{attachment_id[:8]}.{ext}"
                            
                            # 添加完整元数据
                            image_result['attachment_id'] = attachment_id
                            image_result['message_id'] = message_id
                            image_result['session_id'] = frontend_session_id
                            image_result['user_id'] = user_id
                            image_result['filename'] = filename
                            image_result['upload_status'] = 'pending'  # AI 生成的图片初始状态为 pending
                            image_result['upload_task_id'] = None  # 尚未提交上传任务
                            image_result['cloud_url'] = None  # 尚未上传到云存储
                            image_result['created_at'] = timestamp
                            
                            logger.info(f"[ConversationalImageEdit] ✅ Part {idx} extracted as final image with metadata: "
                                        f"attachment_id={attachment_id}, filename={filename}, size={image_result.get('size', 'N/A')} bytes")
                            
                            results.append(image_result)
                            continue

                    # 如果没有图片数据，处理文本响应
                    # 官方示例: if part.text is not None: print(part.text)
                    if text_value is not None:
                        text_responses.append(text_value)
                        logger.info(f"[ConversationalImageEdit] Part {idx} contains text: {text_value[:100] if text_value else ''}...")
            
            # ✅ 如果没有从非 thought parts 中提取到图片，使用最后一个 thought 图片
            # 根据官方文档："The last image within Thinking is also the final rendered image."
            if not results and last_thought_image:
                logger.info(f"[ConversationalImageEdit] No non-thought images found, using last thought image as final result")
                
                # ✅ 为 thought 图片也添加完整的附件元数据
                attachment_id = str(uuid.uuid4())
                message_id = str(uuid.uuid4())
                timestamp = int(time.time() * 1000)
                
                mime_type = last_thought_image.get('mime_type', 'image/png')
                ext = 'png' if 'png' in mime_type else 'jpeg' if 'jpeg' in mime_type or 'jpg' in mime_type else 'png'
                filename = f"edited-{attachment_id[:8]}.{ext}"
                
                last_thought_image['attachment_id'] = attachment_id
                last_thought_image['message_id'] = message_id
                last_thought_image['session_id'] = frontend_session_id
                last_thought_image['user_id'] = user_id
                last_thought_image['filename'] = filename
                last_thought_image['upload_status'] = 'pending'
                last_thought_image['upload_task_id'] = None
                last_thought_image['cloud_url'] = None
                last_thought_image['created_at'] = timestamp
                
                logger.info(f"[ConversationalImageEdit] ✅ Using thought image with metadata: "
                            f"attachment_id={attachment_id}, filename={filename}, size={last_thought_image.get('size', 'N/A')} bytes")
                
                results.append(last_thought_image)
            
            if not results:
                # 提供更详细的错误信息
                error_msg = "Model returned no edited image. "
                
                # 检查是否有文本响应
                if text_responses:
                    error_msg += f"Model returned text instead of image: {text_responses[0][:200]}... "
                elif content_parts:
                    error_msg += f"Model returned {len(content_parts)} parts, but none contained images. "
                else:
                    error_msg += "Model returned no parts. "
                
                error_msg += "Ensure the prompt describes a visual change."
                logger.error(f"[ConversationalImageEdit] {error_msg}")
                raise ValueError(error_msg)
            
            # 记录文本响应和思考过程（如果有）
            if text_responses:
                logger.info(
                    f"[ConversationalImageEdit] Model also returned text responses: "
                    f"{len(text_responses)} text parts"
                )
            if thoughts:
                logger.info(
                    f"[ConversationalImageEdit] Model returned thoughts: "
                    f"{len(thoughts)} thought parts"
                )
            
            logger.info(
                f"[ConversationalImageEdit] Sent edit message: "
                f"chat_id={chat_id}, prompt_length={len(prompt)}, "
                f"images={len(results)}, text_responses={len(text_responses)}, thoughts={len(thoughts)}"
            )
            
            # 返回结果，包含图片、文本响应和思考过程
            # 为了保持向后兼容，我们返回一个字典，包含 images 和其他元数据
            return {
                'images': results,
                'text': text_responses[0] if text_responses else None,  # 第一个文本响应
                'thoughts': thoughts,  # 思考过程列表
                'enhanced_prompt': enhanced_prompt_text
            }
            
        except Exception as e:
            # ✅ 避免在异常日志中输出完整的 BASE64 内容
            # 只记录错误信息，不记录完整的堆栈跟踪（可能包含 BASE64 数据）
            error_msg = str(e)
            # 如果错误信息中包含 BASE64 数据，截断它
            if 'data:image' in error_msg or 'base64' in error_msg.lower():
                # 截断 BASE64 部分（re 已在模块顶部导入）
                error_msg = re.sub(r'data:image[^,]+,\s*[A-Za-z0-9+/]{100,}', 'data:image/...base64...[TRUNCATED]', error_msg)
            logger.error(f"[ConversationalImageEdit] Failed to send edit message: {error_msg}")
            raise
    
    async def get_chat_history(
        self,
        chat_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取 Chat 会话历史
        
        Args:
            chat_id: Chat ID
        
        Returns:
            消息历史列表
        """
        chat_session = self.chat_session_manager.get_chat_session(chat_id)
        if not chat_session:
            raise ValueError(f"Chat session not found: {chat_id}")
        
        # 从数据库获取历史
        history = self.chat_session_manager.get_chat_history_for_rebuild(
            chat_session.frontend_session_id,
            mode='image-chat-edit'  # 使用正确的模式名称
        )
        
        return history
    
    async def delete_chat_session(self, chat_id: str) -> bool:
        """
        删除 Chat 会话
        
        Args:
            chat_id: Chat ID
        
        Returns:
            是否删除成功
        """
        return self.chat_session_manager.delete_chat_session(chat_id)
    
    def _convert_reference_images(self, reference_images: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        将 reference_images 字典格式转换为列表格式

        Args:
            reference_images: 参考图片字典 {'raw': image_data, ...}
                - image_data 可以是：字符串、字典、或字典/字符串的列表（多图）

        Returns:
            参考图片列表
        """
        reference_images_list = []
        if 'raw' in reference_images:
            raw_img = reference_images['raw']

            # ✅ 处理单个图片项（字符串或字典）
            def process_single_image(img_item) -> Optional[Dict[str, Any]]:
                """处理单个图片项，返回标准化的字典格式"""
                if isinstance(img_item, str):
                    text = img_item.strip()
                    if not text:
                        return None

                    def convert_local_image_path_to_data_url(path_text: str) -> Optional[Dict[str, Any]]:
                        parsed_path = path_text
                        if path_text.startswith("file://"):
                            parsed_path = path_text[7:]
                        candidate = Path(parsed_path).expanduser()
                        if not candidate.exists() or not candidate.is_file():
                            return None
                        guessed_mime = str(mimetypes.guess_type(str(candidate))[0] or "").lower()
                        if guessed_mime and not guessed_mime.startswith("image/"):
                            logger.warning(
                                f"[ConversationalImageEdit] 本地路径不是图片文件: {candidate} ({guessed_mime})"
                            )
                            return None
                        mime_type = guessed_mime or "image/png"
                        raw = candidate.read_bytes()
                        encoded = base64.b64encode(raw).decode("ascii")
                        return {"url": f"data:{mime_type};base64,{encoded}", "mime_type": mime_type}

                    # 字符串格式：根据 URL 类型处理
                    if text.startswith('http://') or text.startswith('https://'):
                        return {'url': text, 'mime_type': 'image/png'}
                    if text.startswith('data:'):
                        return {'url': text, 'mime_type': 'image/png'}

                    # 本地路径（绝对路径、file://、相对路径但存在）
                    if text.startswith('/') or text.startswith('file://') or Path(text).expanduser().exists():
                        local_converted = convert_local_image_path_to_data_url(text)
                        if local_converted:
                            return local_converted

                    # 纯 base64：仅在明显是 base64 串时才兜底，避免把本地路径误判为 base64
                    compact = text.replace('\n', '').replace('\r', '')
                    if (
                        len(compact) >= 64
                        and len(compact) % 4 == 0
                        and re.fullmatch(r"[A-Za-z0-9+/=]+", compact)
                    ):
                        return {'url': f"data:image/png;base64,{compact}", 'mime_type': 'image/png'}

                    logger.warning(
                        f"[ConversationalImageEdit] 未识别的图片字符串输入，已跳过: preview={text[:80]}"
                    )
                    return None

                elif isinstance(img_item, dict):
                    # 字典格式（包含 attachment_id 和 url）
                    processed_img = {}

                    # 优先级 1: google_file_uri (snake_case，中间件已转换)
                    if img_item.get('google_file_uri'):
                        processed_img['google_file_uri'] = img_item['google_file_uri']
                        processed_img['mime_type'] = img_item.get('mime_type', 'image/png')

                    # 优先级 2: url 字段
                    elif img_item.get('url'):
                        url = img_item['url']
                        if url.startswith('http://') or url.startswith('https://'):
                            processed_img['url'] = url
                            processed_img['mime_type'] = img_item.get('mime_type', 'image/png')
                        elif url.startswith('data:'):
                            processed_img['url'] = url
                            processed_img['mime_type'] = img_item.get('mime_type', 'image/png')
                        elif url.startswith('/') or url.startswith('file://') or Path(url).expanduser().exists():
                            local_path = url[7:] if url.startswith('file://') else url
                            candidate = Path(local_path).expanduser()
                            if candidate.exists() and candidate.is_file():
                                guessed_mime = str(mimetypes.guess_type(str(candidate))[0] or "").lower()
                                if not guessed_mime or guessed_mime.startswith("image/"):
                                    mime_type = guessed_mime or img_item.get('mime_type', 'image/png')
                                    raw = candidate.read_bytes()
                                    encoded = base64.b64encode(raw).decode("ascii")
                                    processed_img['url'] = f"data:{mime_type};base64,{encoded}"
                                    processed_img['mime_type'] = mime_type

                    # 优先级 3: base64_data (snake_case)
                    elif img_item.get('base64_data'):
                        processed_img['url'] = img_item['base64_data']
                        processed_img['mime_type'] = img_item.get('mime_type', 'image/png')

                    # 优先级 4: temp_url (snake_case)
                    elif img_item.get('temp_url'):
                        processed_img['url'] = img_item['temp_url']
                        processed_img['mime_type'] = img_item.get('mime_type', 'image/png')

                    # 传递 attachment_id（用于日志和调试）
                    if 'attachment_id' in img_item:
                        processed_img['attachment_id'] = img_item['attachment_id']
                        logger.info(f"[ConversationalImageEdit] 处理附件: attachment_id={img_item['attachment_id']}")

                    if processed_img:
                        return processed_img
                    else:
                        logger.warning(
                            f"[ConversationalImageEdit] Failed to extract image data from Attachment object: "
                            f"keys={list(img_item.keys())}"
                        )

                return None

            # ✅ 支持多图：raw_img 可能是列表
            if isinstance(raw_img, list):
                logger.info(f"[ConversationalImageEdit] 处理多张参考图片，数量: {len(raw_img)}")
                for idx, img_item in enumerate(raw_img):
                    processed = process_single_image(img_item)
                    if processed:
                        reference_images_list.append(processed)
                        logger.debug(f"[ConversationalImageEdit] 图片 {idx + 1}/{len(raw_img)} 处理成功")
            else:
                # 单图：字符串或字典
                processed = process_single_image(raw_img)
                if processed:
                    reference_images_list.append(processed)

        logger.info(f"[ConversationalImageEdit] 转换完成，共 {len(reference_images_list)} 张参考图片")
        return reference_images_list
    
    async def edit_image(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        user_id: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        统一的图片编辑接口 - 处理会话管理和参数转换
        
        Args:
            prompt: 编辑提示词
            model: 模型名称
            reference_images: 参考图片字典 {'raw': image_data, ...}
            user_id: 用户 ID（必需）
            **kwargs: 额外参数：
                - frontend_session_id: 前端会话 ID（必需）
                - image_aspect_ratio: 图片比例
                - image_resolution: 图片分辨率
        
        Returns:
            编辑后的图片列表
        """
        if not user_id:
            raise ValueError("user_id is required for conversational image editing")
        
        # 从 kwargs 中获取 frontend_session_id
        frontend_session_id = kwargs.get('frontend_session_id') or kwargs.get('session_id')
        if not frontend_session_id:
            raise ValueError("frontend_session_id is required for image-chat-edit mode. Please provide it in options.")
        
        # 获取或创建 Chat 会话
        existing_sessions = self.chat_session_manager.list_user_chat_sessions(
            user_id=user_id,
            frontend_session_id=frontend_session_id
        )
        
        chat_id = None
        if existing_sessions:
            # 使用现有的 Chat 会话（取最新的活跃会话）
            active_session = next((s for s in existing_sessions if s.is_active), existing_sessions[0])
            
            # ✅ 检查模型是否一致：如果用户切换了模型，需要关闭旧 session 并创建新的
            if active_session.model_name and active_session.model_name != model:
                logger.info(
                    f"[ConversationalImageEdit] Model mismatch detected: "
                    f"session model={active_session.model_name}, requested model={model}. "
                    f"Closing old session and creating new one."
                )
                # 关闭旧 session
                try:
                    await self.delete_chat_session(active_session.chat_id)
                except Exception as e:
                    logger.warning(f"[ConversationalImageEdit] Failed to delete old session: {e}")
                # 清除缓存中的旧 chat 对象
                if active_session.chat_id in self.chat_session_manager._chat_cache:
                    del self.chat_session_manager._chat_cache[active_session.chat_id]
                # 标记为需要创建新 session
                existing_sessions = None
            else:
                chat_id = active_session.chat_id
                logger.info(f"[ConversationalImageEdit] Using existing chat session: {chat_id}")
        if not existing_sessions:
            # 创建新的 Chat 会话（包括模型切换后的重建）
            session_info = await self.create_chat_session(
                user_id=user_id,
                frontend_session_id=frontend_session_id,
                model=model,
                config=kwargs
            )
            chat_id = session_info['chat_id']
            logger.info(f"[ConversationalImageEdit] Created new chat session: {chat_id}")
        
        # 转换 reference_images 格式
        reference_images_list = self._convert_reference_images(reference_images)
        
        # 提取图片相关配置（用于单轮覆盖，例如改变分辨率）
        edit_config = {}
        if 'image_aspect_ratio' in kwargs:
            edit_config['image_aspect_ratio'] = kwargs['image_aspect_ratio']
        if 'image_resolution' in kwargs:
            edit_config['image_resolution'] = kwargs['image_resolution']
        if 'enhance_prompt' in kwargs:
            edit_config['enhance_prompt'] = kwargs['enhance_prompt']
        if 'enhance_prompt_model' in kwargs:
            edit_config['enhance_prompt_model'] = kwargs['enhance_prompt_model']
        if 'enable_thinking' in kwargs:
            edit_config['enable_thinking'] = kwargs['enable_thinking']
        
        # 发送编辑消息
        results = await self.send_edit_message(
            chat_id=chat_id,
            prompt=prompt,
            reference_images=reference_images_list if reference_images_list else None,
            config=edit_config if edit_config else None,
            user_id=user_id,
            frontend_session_id=frontend_session_id
        )
        
        # 处理返回结果：如果返回的是字典（包含 images, thoughts, text），提取并附加元数据
        if isinstance(results, dict) and 'images' in results:
            # 新格式：包含 thoughts 和 text
            images = results.get('images', [])
            thoughts = results.get('thoughts', [])
            text = results.get('text')
            enhanced_prompt = results.get('enhanced_prompt')

            # 将 thoughts 和 text 附加到每个图片结果中（用于前端访问）
            for img in images:
                if thoughts:
                    img['thoughts'] = thoughts
                if text:
                    img['text'] = text
                if enhanced_prompt:
                    img['enhanced_prompt'] = enhanced_prompt

            return images
        else:
            # 旧格式：直接返回图片列表（向后兼容）
            return results
