"""
Tongyi Provider 协调者服务

作为 Tongyi Provider 的统一入口，协调所有子服务：
- QwenNativeProvider: 聊天服务
- ImageGenerationService: 图片生成服务
- ImageEditService: 图片编辑服务
- ImageExpandService: 图片扩展服务
- ModelManager: 模型管理服务

架构说明：
- TongyiService 作为协调者，仅负责请求分发，不包含业务逻辑
- 所有子服务延迟加载，避免循环导入和减少初始化开销
- 遵循"路由与逻辑分离"架构原则

Updated: 2026-01-14 - 移除 TongyiImageService 中间层，直接委托给 ImageGenerationService
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
from sqlalchemy.orm import Session
import logging

from ..common.base_provider import BaseProviderService
from ..common.model_capabilities import ModelConfig

logger = logging.getLogger(__name__)


class TongyiService(BaseProviderService):
    """
    Tongyi Provider 协调者服务
    
    统一协调所有 Tongyi 子服务，使用委托模式分发请求。
    """
    
    def __init__(
        self,
        api_key: str,
        api_url: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
        **kwargs
    ):
        """
        初始化 TongyiService 协调者
        
        Args:
            api_key: DashScope API Key
            api_url: API URL（可选，Tongyi 通常不使用）
            user_id: 用户 ID（可选）
            db: 数据库会话（可选）
            **kwargs: 额外参数
        """
        super().__init__(api_key, api_url, **kwargs)
        self.user_id = user_id
        self.db = db
        
        # 子服务延迟加载（避免循环导入和减少初始化开销）
        self._chat_provider = None
        self._image_generation_service = None  # 直接使用 ImageGenerationService
        self._image_edit_service = None
        self._image_expand_service = None
        self._model_manager = None
        
        logger.info(f"[TongyiService] 协调者初始化完成: api_key={api_key[:10]}...")
    
    # ==================== 必需方法（BaseProviderService） ====================
    
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        非流式聊天（委托给 QwenNativeProvider）
        
        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
            
        Returns:
            聊天响应字典
        """
        if self._chat_provider is None:
            from .chat import QwenNativeProvider
            self._chat_provider = QwenNativeProvider(
                api_key=self.api_key,
                api_url=self.api_url,
                connection_mode=kwargs.get("connection_mode", "official"),
                **{k: v for k, v in kwargs.items() if k != "connection_mode"}
            )
        
        return await self._chat_provider.chat(messages, model, **kwargs)
    
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天（委托给 QwenNativeProvider）
        
        Args:
            messages: 消息列表
            model: 模型名称
            **kwargs: 额外参数
            
        Yields:
            流式响应块
        """
        if self._chat_provider is None:
            from .chat import QwenNativeProvider
            self._chat_provider = QwenNativeProvider(
                api_key=self.api_key,
                api_url=self.api_url,
                connection_mode=kwargs.get("connection_mode", "official"),
                **{k: v for k, v in kwargs.items() if k != "connection_mode"}
            )
        
        async for chunk in self._chat_provider.stream_chat(messages, model, **kwargs):
            yield chunk
    
    async def get_available_models(self) -> List[ModelConfig]:
        """
        获取可用模型列表（委托给 ModelManager）
        
        Returns:
            模型配置列表
        """
        if self._model_manager is None:
            from .model_manager import ModelManager
            self._model_manager = ModelManager(
                api_key=self.api_key,
                api_url=self.api_url
            )
        
        return await self._model_manager.get_available_models()
    
    def get_provider_name(self) -> str:
        """获取提供商名称"""
        return "Tongyi"
    
    # ==================== 可选方法（图片相关） ====================
    
    async def generate_image(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        生成图片（直接委托给 ImageGenerationService）

        Args:
            prompt: 提示词
            model: 模型名称
            **kwargs: 额外参数
                - aspect_ratio: 宽高比（如 "1:1", "16:9"）
                - resolution: 分辨率（如 "1.25K", "2K"）
                - num_images: 生成数量（1-4）
                - negative_prompt: 负向提示词
                - seed: 随机种子
                - style: 风格

        Returns:
            图片生成结果列表
        """
        import time
        start_time = time.time()
        
        logger.info(f"[TongyiService] ========== 开始图片生成 ==========")
        logger.info(f"[TongyiService] 📥 请求参数:")
        logger.info(f"[TongyiService]     - model: {model}")
        logger.info(f"[TongyiService]     - prompt: {prompt[:100] + '...' if len(prompt) > 100 else prompt}")
        logger.info(f"[TongyiService]     - prompt长度: {len(prompt)}")
        for key, value in kwargs.items():
            if key in ['aspectRatio', 'aspect_ratio', 'imageResolution', 'resolution', 'numberOfImages', 'num_images', 'imageStyle', 'style']:
                logger.info(f"[TongyiService]     - {key}: {value}")
        
        logger.info(f"[TongyiService] 🔄 [步骤1] 初始化 ImageGenerationService...")
        if self._image_generation_service is None:
            from .image_generation import ImageGenerationService, ImageGenerationRequest
            self._image_generation_service = ImageGenerationService(self.api_key)
            logger.info(f"[TongyiService] ✅ [步骤1] ImageGenerationService 已初始化")
        else:
            logger.info(f"[TongyiService] ✅ [步骤1] ImageGenerationService 已存在，复用实例")

        # 构建请求参数
        logger.info(f"[TongyiService] 🔄 [步骤2] 构建 ImageGenerationRequest...")
        from .image_generation import ImageGenerationRequest
        
        # 处理 promptExtend -> enable_prompt_optimize
        enable_prompt_optimize = kwargs.get("promptExtend") or kwargs.get("enable_prompt_optimize", False)
        # 处理 addMagicSuffix -> add_magic_suffix
        add_magic_suffix = kwargs.get("addMagicSuffix") if kwargs.get("addMagicSuffix") is not None else kwargs.get("add_magic_suffix", True)
        
        request = ImageGenerationRequest(
            model_id=model,
            prompt=prompt,
            aspect_ratio=kwargs.get("aspectRatio") or kwargs.get("aspect_ratio", "1:1"),
            resolution=kwargs.get("imageResolution") or kwargs.get("resolution", "1.25K"),
            num_images=kwargs.get("numberOfImages") or kwargs.get("num_images", 1),
            negative_prompt=kwargs.get("negativePrompt") or kwargs.get("negative_prompt"),
            seed=kwargs.get("seed"),
            style=kwargs.get("imageStyle") or kwargs.get("style"),
            enable_prompt_optimize=enable_prompt_optimize,
            add_magic_suffix=add_magic_suffix
        )
        logger.info(f"[TongyiService] ✅ [步骤2] 请求参数构建完成:")
        logger.info(f"[TongyiService]     - model_id: {request.model_id}")
        logger.info(f"[TongyiService]     - aspect_ratio: {request.aspect_ratio}")
        logger.info(f"[TongyiService]     - resolution: {request.resolution}")
        logger.info(f"[TongyiService]     - num_images: {request.num_images}")

        # 直接调用 ImageGenerationService
        logger.info(f"[TongyiService] 🔄 [步骤3] 调用 ImageGenerationService.generate()...")
        service_start = time.time()
        results = await self._image_generation_service.generate(request)
        service_time = (time.time() - service_start) * 1000
        logger.info(f"[TongyiService] ✅ [步骤3] ImageGenerationService 调用完成 (耗时: {service_time:.2f}ms)")
        logger.info(f"[TongyiService]     - 返回结果数量: {len(results)}")

        # 转换为统一格式
        logger.info(f"[TongyiService] 🔄 [步骤4] 转换结果格式...")
        formatted_results = []
        for idx, result in enumerate(results):
            # 获取优化后的提示词（TongYi 使用 optimized_prompt，映射为前端期望的 enhancedPrompt）
            enhanced_prompt = getattr(result, "optimized_prompt", None)
            
            formatted_result = {
                "url": result.url,
                "enhancedPrompt": enhanced_prompt,  # ✅ 使用前端期望的字段名
                "mime_type": getattr(result, "mime_type", "image/png")
            }
            formatted_results.append(formatted_result)
            url_type = "HTTP" if result.url and result.url.startswith('http') else "其他"
            logger.info(f"[TongyiService]     - 第 {idx+1} 张图片: URL类型={url_type}, mime_type={formatted_result['mime_type']}")
            if enhanced_prompt:
                logger.info(f"[TongyiService]     - 增强后提示词: {enhanced_prompt[:80]}...")
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[TongyiService] ✅ [步骤4] 格式转换完成 (耗时: {total_time:.2f}ms)")
        logger.info(f"[TongyiService] ========== 图片生成完成 (总耗时: {total_time:.2f}ms) ==========")
        logger.info(f"[TongyiService]     - 最终返回图片数量: {len(formatted_results)}")

        return formatted_results
    
    async def edit_image(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        mode: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        编辑图片（委托给 ImageEditService）
        
        Args:
            prompt: 编辑提示词
            model: 模型名称
            reference_images: 参考图片字典 {'raw': image_url, 'mask': mask_url, ...}
            mode: 编辑模式（可选，Tongyi 目前不支持多种编辑模式，但保留接口一致性）
            **kwargs: 额外参数
                - edit_mode: 编辑模式（Tongyi 内部使用）
                - number_of_images: 生成数量
                - negative_prompt: 负向提示词
                - seed: 随机种子
        
        Returns:
            编辑结果列表
        """
        if self._image_edit_service is None:
            from .image_edit import ImageEditService, ImageEditOptions
            self._image_edit_service = ImageEditService(api_key=self.api_key)
        
        # 获取原始图片 URL
        raw_image = reference_images.get("raw")
        if not raw_image:
            raise ValueError("reference_images must contain 'raw' key with image URL")
        
        # ✅ 处理字典格式（包含 attachment_id 和 url）
        if isinstance(raw_image, dict):
            image_url = raw_image.get("url")
            if not image_url:
                raise ValueError("reference_images['raw'] dict must contain 'url' key")
            # 记录 attachment_id（如果存在）
            if "attachment_id" in raw_image:
                logger.info(f"[TongyiService.edit_image] 处理附件: attachment_id={raw_image['attachment_id'][:8]}...")
        else:
            # 向后兼容：字符串格式
            image_url = raw_image
        
        # 构建编辑选项
        from .image_edit import ImageEditOptions
        
        # 处理 promptExtend -> enable_prompt_optimize
        enable_prompt_optimize = kwargs.get("promptExtend") or kwargs.get("enable_prompt_optimize", False)
        
        options = ImageEditOptions(
            n=kwargs.get("number_of_images") or kwargs.get("numberOfImages", 1),
            negative_prompt=kwargs.get("negative_prompt") or kwargs.get("negativePrompt"),
            size=kwargs.get("size"),
            watermark=kwargs.get("watermark", False),
            seed=kwargs.get("seed"),
            prompt_extend=kwargs.get("prompt_extend", True),
            enable_prompt_optimize=enable_prompt_optimize
        )
        
        # 调用编辑服务
        result = await self._image_edit_service.edit(
            model=model,
            prompt=prompt,
            image_url=image_url,
            options=options
        )
        
        # 转换为统一格式
        if result.success:
            return [{
                "url": result.url,
                "mime_type": result.mime_type
            }]
        else:
            raise Exception(f"Image editing failed: {result.error}")
    
    async def expand_image(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        扩展图片（委托给 ImageExpandService）
        
        Args:
            prompt: 扩展提示词（可选）
            model: 模型名称（可选）
            reference_images: 参考图片字典 {'raw': image_url}
            **kwargs: 额外参数
                - mode: 扩展模式（scale/offset/ratio）
                - x_scale, y_scale: 缩放比例（scale 模式）
                - left_offset, right_offset, top_offset, bottom_offset: 偏移量（offset 模式）
                - angle: 角度（ratio 模式）
                - output_ratio: 输出比例（ratio 模式）
        
        Returns:
            扩展结果列表
        """
        if self._image_expand_service is None:
            from .image_expand import ImageExpandService
            self._image_expand_service = ImageExpandService()
        
        # 获取原始图片 URL
        raw_image = reference_images.get("raw")
        if not raw_image:
            raise ValueError("reference_images must contain 'raw' key with image URL")
        
        # ✅ 处理字典格式（包含 attachment_id 和 url）
        if isinstance(raw_image, dict):
            image_url = raw_image.get("url")
            if not image_url:
                raise ValueError("reference_images['raw'] dict must contain 'url' key")
            # 记录 attachment_id（如果存在）
            if "attachment_id" in raw_image:
                logger.info(f"[TongyiService.expand_image] 处理附件: attachment_id={raw_image['attachment_id'][:8]}...")
        else:
            # 向后兼容：字符串格式
            image_url = raw_image
        
        # 构建扩展参数
        from .image_expand import ImageExpandService
        expand_mode = kwargs.get("mode", "scale")
        parameters = ImageExpandService.build_parameters(
            mode=expand_mode,
            x_scale=kwargs.get("x_scale", 2.0),
            y_scale=kwargs.get("y_scale", 2.0),
            left_offset=kwargs.get("left_offset", 0),
            right_offset=kwargs.get("right_offset", 0),
            top_offset=kwargs.get("top_offset", 0),
            bottom_offset=kwargs.get("bottom_offset", 0),
            angle=kwargs.get("angle", 0),
            output_ratio=kwargs.get("output_ratio", "16:9")
        )
        
        # 调用扩展服务
        result = self._image_expand_service.execute_with_fallback(
            image_url=image_url,
            api_key=self.api_key,
            parameters=parameters
        )
        
        # 转换为统一格式
        if result.success:
            return [{
                "url": result.output_url,
                "task_id": result.task_id
            }]
        else:
            raise Exception(f"Image expansion failed: {result.error}")
    
    async def generate_video(
        self,
        prompt: str,
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成视频（Tongyi 暂不支持，抛出 NotImplementedError）
        
        Args:
            prompt: 提示词
            model: 模型名称
            **kwargs: 额外参数
        
        Raises:
            NotImplementedError: Tongyi 暂不支持视频生成
        """
        raise NotImplementedError("Tongyi does not support video generation yet")
    
    async def generate_speech(
        self,
        text: str,
        voice: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成语音（Tongyi 暂不支持，抛出 NotImplementedError）
        
        Args:
            text: 文本
            voice: 语音名称
            **kwargs: 额外参数
        
        Raises:
            NotImplementedError: Tongyi 暂不支持语音生成
        """
        raise NotImplementedError("Tongyi does not support speech generation yet")

    async def layered_design(
        self,
        prompt: str,
        model: str,
        reference_images: Dict[str, Any],
        mode: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        分层设计（委托给 LayeredDesignService）

        与 GoogleService 保持一致的接口，使用共享的 LayeredDesignService。

        Args:
            prompt: 设计目标描述
            model: 模型名称（用于布局建议时的 LLM 调用）
            reference_images: 参考图片字典 {'raw': image_url, ...}
            mode: 分层设计模式:
                - image-layered-suggest: 布局建议
                - image-layered-decompose: 图层分解
                - image-layered-vectorize: Mask 矢量化
                - image-layered-render: 渲染合成
            **kwargs: 额外参数
                - canvasW, canvasH: 画布尺寸
                - layers: 分解图层数
                - layerDoc: 渲染用的 LayerDoc

        Returns:
            根据 mode 返回不同结构的结果字典
        """
        from ..common.layered_design_service import LayeredDesignService

        logger.info(f"[TongyiService] Delegating layered design to LayeredDesignService: mode={mode}")

        # 创建 LayeredDesignService 实例
        # 注意：Tongyi 使用 OpenAI 兼容格式的 LLM 客户端
        llm_client = None
        if self._chat_provider is None:
            from .chat import QwenNativeProvider
            self._chat_provider = QwenNativeProvider(
                api_key=self.api_key,
                api_url=self.api_url,
            )
        llm_client = self._chat_provider

        service = LayeredDesignService(
            llm_client=llm_client,
            llm_model=model
        )

        return await service.process(
            mode=mode,
            prompt=prompt,
            reference_images=reference_images,
            **kwargs
        )
