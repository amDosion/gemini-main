"""
Simple Image Edit Service - 使用 generateContent() 进行图片编辑

将前端 generateContent() 调用逻辑迁移到后端，实现简单图片编辑。
支持 Google Files API 优化，自动模型路由等功能。
"""

import logging
import base64
import io
import re
import time
import tempfile
import os
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import aiohttp

from .sdk_initializer import SDKInitializer
from .file_handler import FileHandler

logger = logging.getLogger(__name__)


class SimpleImageEditService:
    """
    使用 generateContent() 进行简单图片编辑的服务
    
    特点：
    - 支持 Google Files API 优化（减少数据传输）
    - 自动模型路由（文本模型 → 图像模型）
    - 支持 Virtual Try-On 模式
    - 处理多种图片输入格式（Base64、URL、Google File URI）
    """
    
    def __init__(self, sdk_initializer: SDKInitializer, file_handler: FileHandler):
        """
        初始化简单图片编辑服务
        
        Args:
            sdk_initializer: SDK 初始化器
            file_handler: 文件处理器（用于 Google Files API 上传）
        """
        self.sdk_initializer = sdk_initializer
        self.file_handler = file_handler
    
    def _route_model(self, model: str) -> str:
        """
        模型路由：自动切换到图像模型
        
        Args:
            model: 原始模型 ID
            
        Returns:
            路由后的模型 ID
        """
        target_model = model
        
        # 如果用户选择了纯文本模型，自动切换到图像模型
        if target_model == 'gemini-3-pro-preview':
            target_model = 'gemini-3-pro-image-preview'
        elif (
            'image' not in target_model and 
            'veo' not in target_model and 
            'vision' not in target_model and 
            'pro-image' not in target_model
        ):
            # 回退到默认图像模型
            target_model = 'gemini-2.5-flash-image'
        
        if target_model != model:
            logger.info(f"[SimpleImageEdit] Model routed: {model} → {target_model}")
        
        return target_model
    
    async def _process_reference_image(
        self,
        reference_image: Dict[str, Any],
        use_google_files_api: bool = True
    ) -> Dict[str, Any]:
        """
        处理参考图片，转换为 Google API 格式
        
        优先级：
        1. Google File URI（已上传，未过期）
        2. Base64 数据（inlineData）
        3. HTTP URL（需要下载）
        
        Args:
            reference_image: 参考图片字典，包含：
                - url: 图片 URL（Base64 Data URL 或 HTTP URL）
                - mimeType: MIME 类型
                - googleFileUri: Google Files API URI（可选）
                - googleFileExpiry: Google File URI 过期时间（可选）
                - base64Data: Base64 数据（可选）
            use_google_files_api: 是否使用 Google Files API
            
        Returns:
            包含 part 信息的字典：{'type': 'fileData'|'inlineData', 'data': {...}}
        """
        # 优先级 1：使用已有的 Google File URI（未过期）
        if reference_image.get('googleFileUri'):
            expiry = reference_image.get('googleFileExpiry')
            if expiry and expiry > (int(time.time() * 1000)):
                logger.debug("[SimpleImageEdit] Using existing Google File URI")
                return {
                    'type': 'fileData',
                    'data': {
                        'mimeType': reference_image.get('mimeType', 'image/png'),
                        'fileUri': reference_image['googleFileUri']
                    }
                }
        
        # 优先级 2：Base64 数据
        base64_data = reference_image.get('base64Data') or reference_image.get('url', '')
        if base64_data and isinstance(base64_data, str) and base64_data.startswith('data:'):
            match = re.match(r'^data:(.*?);base64,(.*)$', base64_data)
            if match:
                mime_type = match.group(1) or reference_image.get('mimeType', 'image/png')
                base64_str = match.group(2)
                
                # 如果启用 Google Files API，尝试上传
                if use_google_files_api:
                    try:
                        # 解码 Base64 并上传
                        image_bytes = base64.b64decode(base64_str)
                        file_uri = await self._upload_bytes_to_google_files(
                            image_bytes,
                            mime_type
                        )
                        return {
                            'type': 'fileData',
                            'data': {
                                'mimeType': mime_type,
                                'fileUri': file_uri
                            }
                        }
                    except Exception as e:
                        logger.warning(f"[SimpleImageEdit] Google Files API upload failed, using Base64: {e}")
                
                # 回退到 Base64
                return {
                    'type': 'inlineData',
                    'data': {
                        'mimeType': mime_type,
                        'data': base64_str
                    }
                }
        
        # 优先级 3：HTTP URL（需要下载）
        url = reference_image.get('url', '')
        if url and url.startswith('http'):
            try:
                # 下载图片
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            image_bytes = await response.read()
                            mime_type = reference_image.get('mimeType') or response.headers.get('Content-Type', 'image/png')
                            
                            # 如果启用 Google Files API，尝试上传
                            if use_google_files_api:
                                try:
                                    file_uri = await self._upload_bytes_to_google_files(
                                        image_bytes,
                                        mime_type
                                    )
                                    return {
                                        'type': 'fileData',
                                        'data': {
                                            'mimeType': mime_type,
                                            'fileUri': file_uri
                                        }
                                    }
                                except Exception as e:
                                    logger.warning(f"[SimpleImageEdit] Google Files API upload failed: {e}")
                            
                            # 回退到 Base64
                            base64_str = base64.b64encode(image_bytes).decode('utf-8')
                            return {
                                'type': 'inlineData',
                                'data': {
                                    'mimeType': mime_type,
                                    'data': base64_str
                                }
                            }
            except Exception as e:
                logger.error(f"[SimpleImageEdit] Failed to download image from URL: {e}")
                raise ValueError(f"无法下载图片: {url}")
        
        raise ValueError("无法处理参考图片：缺少有效的图片数据")
    
    async def _upload_bytes_to_google_files(
        self,
        image_bytes: bytes,
        mime_type: str
    ) -> str:
        """
        将字节数据上传到 Google Files API
        
        Args:
            image_bytes: 图片字节数据
            mime_type: MIME 类型
            
        Returns:
            Google File URI
        """
        # 创建临时文件
        suffix = '.png'
        if 'jpeg' in mime_type or 'jpg' in mime_type:
            suffix = '.jpg'
        elif 'webp' in mime_type:
            suffix = '.webp'
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(image_bytes)
            tmp_path = tmp_file.name
        
        try:
            # 上传文件
            file_info = await self.file_handler.upload_file(
                tmp_path,
                display_name=f"image_edit_{int(time.time())}",
                mime_type=mime_type
            )
            return file_info['uri']
        finally:
            # 清理临时文件
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
    
    
    async def edit_with_generate_content(
        self,
        model: str,
        prompt: str,
        reference_images: List[Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        使用 generateContent() 进行简单图片编辑
        
        Args:
            model: 模型 ID
            prompt: 编辑提示词
            reference_images: 参考图片列表（每个图片是一个字典）
            config: 配置选项，包含：
                - imageAspectRatio: 图片比例（默认 '1:1'）
                - imageResolution: 图片分辨率
                - enableSearch: 是否启用搜索工具
                - virtualTryOnTarget: Virtual Try-On 目标
                - useGoogleFilesApi: 是否使用 Google Files API（默认 True）
        
        Returns:
            编辑后的图片列表，每个图片包含：
                - url: Base64 Data URL
                - mimeType: MIME 类型
        """
        config = config or {}
        
        # 1. 模型路由
        target_model = self._route_model(model)
        
        # 2. 导入 Google SDK 类型
        try:
            from google.genai import types as genai_types
        except ImportError:
            # 如果官方 SDK 不可用，使用字典格式
            genai_types = None
        
        # 3. 构建请求配置
        if genai_types:
            # 使用官方 SDK 类型
            image_config_dict = {
                'aspect_ratio': config.get('imageAspectRatio', '1:1')
            }
            if config.get('imageResolution'):
                image_config_dict['image_size'] = config['imageResolution']
            
            generate_config = genai_types.GenerateContentConfig(
                response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
                image_config=genai_types.ImageConfig(**image_config_dict)
            )
            
            # 注入搜索工具
            if config.get('enableSearch'):
                generate_config.tools = [genai_types.Tool(google_search={})]
        else:
            # 回退到字典格式
            generate_config = {
                'response_modalities': ['TEXT', 'IMAGE'],
                'image_config': {
                    'aspect_ratio': config.get('imageAspectRatio', '1:1')
                }
            }
            if config.get('imageResolution'):
                generate_config['image_config']['image_size'] = config['imageResolution']
            if config.get('enableSearch'):
                generate_config['tools'] = [{'google_search': {}}]
        
        # 4. 处理参考图片
        parts = []
        use_google_files_api = config.get('useGoogleFilesApi', True)
        
        for ref_img in reference_images:
            part_info = await self._process_reference_image(ref_img, use_google_files_api)
            if part_info['type'] == 'fileData':
                if genai_types:
                    # 使用官方 SDK Part 类型
                    parts.append(genai_types.Part(file_data=genai_types.FileData(
                        file_uri=part_info['data']['fileUri'],
                        mime_type=part_info['data']['mimeType']
                    )))
                else:
                    parts.append({'file_data': part_info['data']})
            else:
                if genai_types:
                    # 使用官方 SDK Part 类型
                    parts.append(genai_types.Part(inline_data=genai_types.Blob(
                        data=base64.b64decode(part_info['data']['data']),
                        mime_type=part_info['data']['mimeType']
                    )))
                else:
                    parts.append({'inline_data': part_info['data']})
        
        # 5. 构建提示词（支持 Virtual Try-On）
        final_prompt = prompt.strip()
        if config.get('virtualTryOnTarget'):
            target = config['virtualTryOnTarget']
            final_prompt = (
                f"Perform a virtual try-on editing task. "
                f"Identify the {target} in the image. "
                f"Replace strictly the {target} with: {prompt}. "
                f"Maintain the rest of the image exactly as is."
            )
        
        if genai_types:
            parts.append(genai_types.Part.from_text(text=final_prompt))
        else:
            parts.append({'text': final_prompt})
        
        # 6. 调用 generateContent()
        try:
            await self.sdk_initializer.ensure_initialized()
            client = self.sdk_initializer.client
            
            logger.info(f"[SimpleImageEdit] Calling generateContent: model={target_model}, parts={len(parts)}")
            
            # 构建 contents（官方 SDK 格式）
            if genai_types:
                contents = genai_types.Content(role='user', parts=parts)
                # 使用异步 API
                response = await client.aio.models.generate_content(
                    model=target_model,
                    contents=[contents],
                    config=generate_config
                )
            else:
                # 回退格式
                response = await client.aio.models.generate_content(
                    model=target_model,
                    contents={'parts': parts},
                    config=generate_config
                )
            
            # 7. 提取编辑后的图片
            results = []
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        # 处理 inline_data（字节数据）
                        if hasattr(part, 'inline_data') and part.inline_data:
                            image_bytes = part.inline_data.data
                            mime_type = part.inline_data.mime_type or 'image/png'
                            # 转换为 Base64 Data URL
                            base64_str = base64.b64encode(image_bytes).decode('utf-8')
                            results.append({
                                'url': f"data:{mime_type};base64,{base64_str}",
                                'mimeType': mime_type
                            })
            
            if not results:
                raise ValueError("Model returned no edited image. Ensure the prompt describes a visual change.")
            
            logger.info(f"[SimpleImageEdit] Successfully edited image: {len(results)} result(s)")
            return results
            
        except Exception as e:
            logger.error(f"[SimpleImageEdit] Edit failed: {e}", exc_info=True)
            raise
    
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
                    # HTTP URL：直接传递，后端会下载
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
                # 字典格式（包含 url、mimeType 等）
                reference_images_list.append(raw_img)
        
        return reference_images_list
    
    async def edit_image(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        统一的图片编辑接口 - 处理参数转换
        
        Args:
            prompt: 编辑提示词
            model: 模型 ID
            reference_images: 参考图片字典 {'raw': image_data, ...}
            **kwargs: 额外参数：
                - imageAspectRatio: 图片比例（默认 '1:1'）
                - imageResolution: 图片分辨率
                - enableSearch: 是否启用搜索工具
                - virtualTryOnTarget: Virtual Try-On 目标
                - useGoogleFilesApi: 是否使用 Google Files API（默认 True）
        
        Returns:
            编辑后的图片列表
        """
        # 转换 reference_images 格式
        reference_images_list = self._convert_reference_images(reference_images)
        
        # 构建配置
        config = {
            'imageAspectRatio': kwargs.get('aspect_ratio', kwargs.get('imageAspectRatio', '1:1')),
            'imageResolution': kwargs.get('image_size', kwargs.get('imageResolution')),
            'enableSearch': kwargs.get('enableSearch', False),
            'virtualTryOnTarget': kwargs.get('virtualTryOnTarget'),
            'useGoogleFilesApi': kwargs.get('useGoogleFilesApi', True)
        }
        
        # 调用编辑方法
        return await self.edit_with_generate_content(
            model=model,
            prompt=prompt,
            reference_images=reference_images_list,
            config=config
        )
