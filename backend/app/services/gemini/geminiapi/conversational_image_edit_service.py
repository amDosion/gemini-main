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
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ..common.sdk_initializer import SDKInitializer
from ..common.chat_session_manager import ChatSessionManager
from ..common.file_handler import FileHandler

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
            # 注意：只提取 GenerateContentConfig 支持的有效字段（imageAspectRatio, imageResolution）
            if genai_types:
                # 使用官方 SDK 类型
                # 注意：图像生成/编辑这类请求，通常不需要 google_search
                image_config_dict = {
                    'aspect_ratio': config.get('imageAspectRatio', '1:1') if config else '1:1'
                }
                if config and config.get('imageResolution'):
                    image_config_dict['image_size'] = config['imageResolution']
                
                chat_config = genai_types.GenerateContentConfig(
                    response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
                    thinking_config=genai_types.ThinkingConfig(include_thoughts=True),  # ✅ 开启思考过程
                    image_config=genai_types.ImageConfig(**image_config_dict)
                )
            else:
                # 回退到字典格式
                chat_config = {
                    'response_modalities': ['TEXT', 'IMAGE'],
                    'image_config': {
                        'aspect_ratio': config.get('imageAspectRatio', '1:1') if config else '1:1'
                    }
                }
                if config and config.get('imageResolution'):
                    chat_config['image_config']['image_size'] = config['imageResolution']
            
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
        config: Optional[Dict[str, Any]] = None
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
        
        Returns:
            编辑后的图片列表
        """
        self.sdk_initializer.ensure_initialized()
        client = self.sdk_initializer.client
        
        # 获取 Chat 对象（从缓存）
        # 注意：Chat 对象会自动维护历史记录，不需要手动重建
        chat = self.chat_session_manager.get_chat_object_from_cache(chat_id)
        
        # 判断是否需要传递图片
        # 根据官方示例（intro_gemini_3_image_gen.ipynb），多轮对话中应该传递上一轮生成的图片
        # 如果前端通过 CONTINUITY LOGIC 传递了图片，就使用它（更安全，即使 Chat SDK 有历史记录）
        should_include_image = reference_images is not None and len(reference_images) > 0
        
        if not chat:
            # 如果缓存中没有，说明这是第一次调用，应该先创建 chat 会话
            chat_session = self.chat_session_manager.get_chat_session(chat_id)
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
                    valid_config = {}
                    if 'imageAspectRatio' in config_dict:
                        valid_config['imageAspectRatio'] = config_dict['imageAspectRatio']
                    if 'imageResolution' in config_dict:
                        valid_config['imageResolution'] = config_dict['imageResolution']
                    
                    if genai_types and valid_config:
                        # 构建 ImageConfig
                        image_config_dict = {}
                        if 'imageAspectRatio' in valid_config:
                            image_config_dict['aspect_ratio'] = valid_config['imageAspectRatio']
                        if 'imageResolution' in valid_config:
                            image_config_dict['image_size'] = valid_config['imageResolution']
                        
                        chat_config = genai_types.GenerateContentConfig(
                            response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
                            image_config=genai_types.ImageConfig(**image_config_dict) if image_config_dict else None
                        )
                    elif valid_config:
                        chat_config = {
                            'response_modalities': ['TEXT', 'IMAGE'],
                            'image_config': {}
                        }
                        if 'imageAspectRatio' in valid_config:
                            chat_config['image_config']['aspect_ratio'] = valid_config['imageAspectRatio']
                        if 'imageResolution' in valid_config:
                            chat_config['image_config']['image_size'] = valid_config['imageResolution']
                except Exception as e:
                    logger.warning(f"[ConversationalImageEdit] Failed to parse config_json: {e}")
            
            # 从历史重建 Chat 对象（如果有历史）
            history = self.chat_session_manager.get_chat_history_for_rebuild(
                chat_session.frontend_session_id,
                mode='image-chat-edit'
            )
            
            if history and genai_types:
                # 构建历史记录
                history_contents = []
                for msg in history:
                    parts = []
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
                    if parts:
                        history_contents.append(genai_types.Content(
                            role=msg.get('role', 'user'),
                            parts=parts
                        ))
                
                # 重建 Chat 对象（带历史）
                chat = client.aio.chats.create(
                    model=chat_session.model_name,
                    config=chat_config,
                    history=history_contents if history_contents else None
                )
            else:
                # 创建新的 Chat 对象（无历史）
                chat = client.aio.chats.create(
                    model=chat_session.model_name,
                    config=chat_config
                )
            
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
                if ref_img.get('googleFileUri'):
                    # 使用 Google File URI
                    if genai_types:
                        message_parts.append(genai_types.Part(file_data=genai_types.FileData(
                            file_uri=ref_img['googleFileUri'],
                            mime_type=ref_img.get('mimeType', 'image/png')
                        )))
                    else:
                        message_parts.append({
                            'file_data': {
                                'file_uri': ref_img['googleFileUri'],
                                'mime_type': ref_img.get('mimeType', 'image/png')
                            }
                        })
                elif ref_img.get('url'):
                    url = ref_img['url']
                    if url.startswith('data:'):
                        # Base64 Data URL
                        match = re.match(r'^data:(.*?);base64,(.*)$', url)
                        if match:
                            mime_type = match.group(1) or ref_img.get('mimeType', 'image/png')
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
                                        mime_type = ref_img.get('mimeType') or response.headers.get('Content-Type', 'image/png')
                                        
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
        
        # 构建要发送的消息
        # 如果只有一个 part（只有文本），直接使用文本字符串；否则使用列表
        if len(message_parts) == 1 and genai_types:
            # 只有一个文本 part，可以直接使用字符串（更简洁）
            message_to_send = prompt
        elif len(message_parts) == 1:
            # 回退到 part 对象
            message_to_send = message_parts[0]
        else:
            # 多个 parts（图片 + 文本），使用列表
            message_to_send = message_parts
        
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
            # 参考：response = chat.send_message(message, config=types.GenerateContentConfig(...))
            send_config = None
            if config and genai_types:
                # 如果提供了配置覆盖，构建新的配置
                image_config_dict = {}
                if config.get('imageAspectRatio'):
                    image_config_dict['aspect_ratio'] = config['imageAspectRatio']
                if config.get('imageResolution'):
                    image_config_dict['image_size'] = config['imageResolution']
                
                if image_config_dict:
                    send_config = genai_types.GenerateContentConfig(
                        image_config=genai_types.ImageConfig(**image_config_dict)
                    )
            
            # 调用 chat.send_message()
            # 注意：Chat 对象会自动维护历史记录，所以直接调用即可
            # 如果提供了配置覆盖，使用它；否则使用创建 chat 时的默认配置
            if send_config:
                response = await chat.send_message(message=message_to_send, config=send_config)
            else:
                response = await chat.send_message(message=message_to_send)
            
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
                logger.debug(f"[ConversationalImageEdit] Using response.parts for thoughts, count={len(all_parts)}")
            
            # 然后从 response.candidates[0].content.parts 获取最终内容（参考官方示例 Cell 17, 25, 29, 31, 33, 37）
            content_parts = None
            if hasattr(response, 'candidates') and response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                logger.debug(f"[ConversationalImageEdit] Candidate structure: has_content={hasattr(candidate, 'content')}, has_parts={hasattr(candidate.content, 'parts') if hasattr(candidate, 'content') else False}")
                
                if hasattr(candidate, 'content') and candidate.content:
                    content_parts = getattr(candidate.content, 'parts', None)
                    if content_parts:
                        logger.debug(f"[ConversationalImageEdit] Using response.candidates[0].content.parts for final content, count={len(content_parts)}")
            
            # 如果没有 content_parts，回退到 all_parts
            if not content_parts and all_parts:
                content_parts = all_parts
                logger.debug(f"[ConversationalImageEdit] Falling back to response.parts for final content")
            
            # 步骤1: 从 response.parts 收集 thoughts（参考官方示例 Cell 19, 23）
            if all_parts:
                logger.debug(f"[ConversationalImageEdit] Processing {len(all_parts)} parts from response.parts for thoughts")
                for idx, part in enumerate(all_parts):
                    # 收集思考过程（thoughts）- 参考官方示例 Cell 19, 23
                    if hasattr(part, 'thought') and getattr(part, 'thought', None):
                        thought_content = None
                        thought_type = None
                        
                        # 检查 thought 的内容类型（文本或图片）- 参考官方示例 Cell 19
                        if hasattr(part, 'text') and part.text:
                            thought_content = part.text
                            thought_type = 'text'
                        elif hasattr(part, 'inline_data') and part.inline_data:
                            # thoughts 也可能包含图片 - 参考官方示例 Cell 19
                            try:
                                image_bytes = part.inline_data.data
                                mime_type = getattr(part.inline_data, 'mime_type', None) or 'image/png'
                                base64_str = base64.b64encode(image_bytes).decode('utf-8')
                                thought_content = f"data:{mime_type};base64,{base64_str}"
                                thought_type = 'image'
                            except Exception as e:
                                logger.debug(f"[ConversationalImageEdit] Failed to extract thought image: {e}")
                                thought_content = "[思考过程包含图片，但提取失败]"
                                thought_type = 'text'
                        
                        if thought_content:
                            thoughts.append({
                                'type': thought_type,
                                'content': thought_content
                            })
                            logger.debug(f"[ConversationalImageEdit] Part {idx} is a thought (type={thought_type}), collected for frontend display")
            
            # 步骤2: 从 response.candidates[0].content.parts 提取最终的图片和文本（参考官方示例 Cell 17, 25, 29, 31, 33, 37）
            if content_parts:
                logger.debug(f"[ConversationalImageEdit] Processing {len(content_parts)} parts from response.candidates[0].content.parts for final content")
                for idx, part in enumerate(content_parts):
                    logger.debug(f"[ConversationalImageEdit] Part {idx}: has_thought={hasattr(part, 'thought') and getattr(part, 'thought', None)}, has_as_image={hasattr(part, 'as_image')}, has_inline_data={hasattr(part, 'inline_data')}, has_text={hasattr(part, 'text')}")
                    
                    # 跳过 thoughts（参考官方示例 Cell 17）
                    if hasattr(part, 'thought') and getattr(part, 'thought', None):
                        logger.debug(f"[ConversationalImageEdit] Skipping thought part {idx} (already collected from response.parts)")
                        continue
                    
                    # 处理文本响应（参考官方示例 Cell 25, 29, 31, 33, 37）
                    # 注意：文本和图片是独立检查的，一个 part 可以同时包含 text 和 inline_data
                    if hasattr(part, 'text') and part.text:
                        text_content = part.text
                        text_responses.append(text_content)
                        logger.info(f"[ConversationalImageEdit] Part {idx} contains text: {text_content[:100]}...")
                        # 注意：不 continue，因为同一个 part 可能同时包含 text 和 inline_data
                    
                    # 方法1：尝试使用 as_image() 方法（推荐方式）
                    try:
                        if hasattr(part, 'as_image'):
                            img = part.as_image()
                            if img:
                                logger.info(f"[ConversationalImageEdit] ✅ Extracted image using as_image() method")
                                # 将图片转换为 base64
                                import io
                                img_bytes = io.BytesIO()
                                img.save(img_bytes, format='PNG')
                                img_bytes.seek(0)
                                image_bytes = img_bytes.read()
                                base64_str = base64.b64encode(image_bytes).decode('utf-8')
                                results.append({
                                    'url': f"data:image/png;base64,{base64_str}",
                                    'mimeType': 'image/png'
                                })
                                continue
                    except Exception as e:
                        logger.debug(f"[ConversationalImageEdit] as_image() failed for part {idx}: {e}, trying inline_data")
                    
                    # 方法2：回退到 inline_data（兼容方式，参考官方示例）
                    if hasattr(part, 'inline_data') and part.inline_data:
                        try:
                            image_bytes = part.inline_data.data
                            mime_type = getattr(part.inline_data, 'mime_type', None) or 'image/png'
                            logger.info(f"[ConversationalImageEdit] ✅ Extracted image using inline_data, size={len(image_bytes)} bytes, mime_type={mime_type}")
                            # 转换为 Base64 Data URL
                            base64_str = base64.b64encode(image_bytes).decode('utf-8')
                            results.append({
                                'url': f"data:{mime_type};base64,{base64_str}",
                                'mimeType': mime_type
                            })
                            continue
                        except Exception as e:
                            logger.debug(f"[ConversationalImageEdit] inline_data extraction failed for part {idx}: {e}")
            
            if not results:
                # 提供更详细的错误信息
                error_msg = "Model returned no edited image. "
                
                # 检查是否有文本响应
                if text_responses:
                    error_msg += f"Model returned text instead of image: {text_responses[0][:200]}... "
                elif parts:
                    error_msg += f"Model returned {len(parts)} parts, but none contained images. "
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
                'thoughts': thoughts  # 思考过程列表
            }
            
        except Exception as e:
            # ✅ 避免在异常日志中输出完整的 BASE64 内容
            # 只记录错误信息，不记录完整的堆栈跟踪（可能包含 BASE64 数据）
            error_msg = str(e)
            # 如果错误信息中包含 BASE64 数据，截断它
            if 'data:image' in error_msg or 'base64' in error_msg.lower():
                # 截断 BASE64 部分
                import re
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
        
        Returns:
            参考图片列表
        """
        reference_images_list = []
        if 'raw' in reference_images:
            raw_img = reference_images['raw']
            if isinstance(raw_img, str):
                # 字符串格式：根据 URL 类型处理
                # 修复：先检查 HTTP URL，避免错误地将 HTTP URL 当作 base64 处理
                if raw_img.startswith('http://') or raw_img.startswith('https://'):
                    # HTTP URL：直接传递，后端 send_edit_message 会下载
                    reference_images_list.append({
                        'url': raw_img,
                        'mimeType': 'image/png'
                    })
                elif raw_img.startswith('data:'):
                    # Data URL：直接使用
                    reference_images_list.append({
                        'url': raw_img,
                        'mimeType': 'image/png'
                    })
                else:
                    # 其他字符串（纯 base64）：添加 data URL 前缀
                    reference_images_list.append({
                        'url': f"data:image/png;base64,{raw_img}",
                        'mimeType': 'image/png'
                    })
            elif isinstance(raw_img, dict):
                # ✅ 处理字典格式（包含 attachment_id 和 url）
                processed_img = {}
                
                # 优先级 1: googleFileUri（如果已上传到 Google Files API）
                if raw_img.get('googleFileUri'):
                    processed_img['googleFileUri'] = raw_img['googleFileUri']
                    processed_img['mimeType'] = raw_img.get('mimeType', 'image/png')
                
                # 优先级 2: url 字段（HTTP URL 优先，避免 Base64 占用空间）
                elif raw_img.get('url'):
                    url = raw_img['url']
                    if url.startswith('http://') or url.startswith('https://'):
                        processed_img['url'] = url
                        processed_img['mimeType'] = raw_img.get('mimeType', 'image/png')
                    elif url.startswith('data:'):
                        processed_img['url'] = url
                        processed_img['mimeType'] = raw_img.get('mimeType', 'image/png')
                
                # 优先级 3: base64Data
                elif raw_img.get('base64Data'):
                    processed_img['url'] = raw_img['base64Data']
                    processed_img['mimeType'] = raw_img.get('mimeType', 'image/png')
                
                # 优先级 4: tempUrl 字段（备选）
                elif raw_img.get('tempUrl'):
                    processed_img['url'] = raw_img['tempUrl']
                    processed_img['mimeType'] = raw_img.get('mimeType', 'image/png')
                
                # ✅ 如果有 attachment_id，也传递（用于日志和调试）
                if 'attachment_id' in raw_img:
                    processed_img['attachment_id'] = raw_img['attachment_id']
                    logger.info(f"[ConversationalImageEdit] 处理附件: attachment_id={raw_img['attachment_id'][:8]}...")
                
                # 如果提取到了有效数据，添加到列表
                if processed_img:
                    reference_images_list.append(processed_img)
                else:
                    logger.warning(
                        f"[ConversationalImageEdit] Failed to extract image data from Attachment object: "
                        f"keys={list(raw_img.keys())}"
                    )
        
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
                - imageAspectRatio: 图片比例
                - imageResolution: 图片分辨率
        
        Returns:
            编辑后的图片列表
        """
        if not user_id:
            raise ValueError("user_id is required for conversational image editing")
        
        # 从 kwargs 中获取 frontend_session_id
        frontend_session_id = kwargs.get('frontend_session_id') or kwargs.get('sessionId')
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
            chat_id = active_session.chat_id
            logger.info(f"[ConversationalImageEdit] Using existing chat session: {chat_id}")
        else:
            # 创建新的 Chat 会话
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
        if 'imageAspectRatio' in kwargs:
            edit_config['imageAspectRatio'] = kwargs['imageAspectRatio']
        if 'imageResolution' in kwargs:
            edit_config['imageResolution'] = kwargs['imageResolution']
        
        # 发送编辑消息
        results = await self.send_edit_message(
            chat_id=chat_id,
            prompt=prompt,
            reference_images=reference_images_list if reference_images_list else None,
            config=edit_config if edit_config else None
        )
        
        # 处理返回结果：如果返回的是字典（包含 images, thoughts, text），提取并附加元数据
        if isinstance(results, dict) and 'images' in results:
            # 新格式：包含 thoughts 和 text
            images = results.get('images', [])
            thoughts = results.get('thoughts', [])
            text = results.get('text')
            
            # 将 thoughts 和 text 附加到每个图片结果中（用于前端访问）
            for img in images:
                if thoughts:
                    img['thoughts'] = thoughts
                if text:
                    img['text'] = text
            
            return images
        else:
            # 旧格式：直接返回图片列表（向后兼容）
            return results
