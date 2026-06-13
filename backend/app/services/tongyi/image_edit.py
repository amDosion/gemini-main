"""
图像编辑服务层
封装 DashScope 图像编辑 API 调用逻辑

支持的模型:
- qwen-image-edit-plus (及其变体)
- wan2.6-image
- wan2.5-i2i-preview (向后兼容)

增强功能:
- 编辑 Prompt 智能优化（可选）
- 基于 Qwen-VL-Max 图像理解
"""
from typing import List, Optional
from dataclasses import dataclass, field
import httpx
import logging
import mimetypes
import time
from pathlib import Path
from urllib.parse import unquote

from .file_upload import upload_bytes_to_dashscope_async, upload_to_dashscope_async
from .base import (
    WAN27_STANDARD_MAX_IMAGES,
    clamp_image_count,
    get_qwen_image_max_output_count,
    get_wan27_size,
    is_wan27_image_model,
)
from ..storage.local_provider import DEFAULT_LOCAL_URL_PREFIX, resolve_local_public_file_path
from ...utils.log_sanitization import summarize_text_for_log, summarize_url_for_log

logger = logging.getLogger(__name__)

# DashScope 官方 API 地址
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com"


def _summarize_response_shape_for_log(response_data: object) -> str:
    if not isinstance(response_data, dict):
        return summarize_text_for_log(response_data, label="response")

    parts = [f"dict_keys={len(response_data)}"]
    output = response_data.get("output")
    if isinstance(output, dict):
        parts.append(f"output_keys={len(output)}")
        choices = output.get("choices")
        if isinstance(choices, list):
            parts.append(f"choices={len(choices)}")
        results = output.get("results")
        if isinstance(results, list):
            parts.append(f"results={len(results)}")
    return "; ".join(parts)


@dataclass
class ImageEditResult:
    """图像编辑结果"""
    success: bool
    url: Optional[str] = None
    urls: List[str] = field(default_factory=list)
    mime_type: str = "image/png"
    error: Optional[str] = None
    # 新增: Prompt 优化信息
    optimized_prompt: Optional[str] = None
    original_prompt: Optional[str] = None


@dataclass
class ImageEditOptions:
    """图像编辑选项"""
    n: int = 1
    negative_prompt: Optional[str] = None
    size: Optional[str] = None
    aspect_ratio: str = "1:1"
    watermark: bool = False
    seed: Optional[int] = None
    prompt_extend: bool = False
    # 新增: Prompt 优化参数
    enable_prompt_optimize: bool = False  # 是否启用编辑 Prompt 智能优化
    prompt_optimize_model: Optional[str] = None  # Prompt 优化使用的额外模型


class ImageEditService:
    """图像编辑服务"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._edit_optimizer = None  # 延迟加载

    @property
    def edit_optimizer(self):
        """懒加载编辑 Prompt 优化器"""
        if self._edit_optimizer is None:
            from .prompt_optimizer import EditPromptOptimizer
            self._edit_optimizer = EditPromptOptimizer(self.api_key)
        return self._edit_optimizer

    async def process_reference_image(
        self,
        image_url: str,
        model: str
    ) -> str:
        """
        处理参考图片,统一转换为 oss:// URL

        Args:
            image_url: 图片URL (支持 https://, oss://, data:image/...)
            model: 模型名称（用于获取上传凭证）

        Returns:
            oss:// 格式的URL
        """
        # 情况 1: 已经是 oss:// URL - 直接使用
        if image_url.startswith('oss://'):
            logger.info("[Image Edit] 使用现有 OSS URL: %s", summarize_url_for_log(image_url))
            return image_url

        local_path = self._resolve_local_public_image_path(image_url)
        if local_path:
            logger.info("[Image Edit] 上传本地存储图片到 OSS: %s", summarize_url_for_log(image_url))
            mime_type = mimetypes.guess_type(local_path.name)[0] or "image/png"
            extension = mimetypes.guess_extension(mime_type) or ".png"
            result = await upload_bytes_to_dashscope_async(
                local_path.read_bytes(),
                f"image-edit-{int(time.time() * 1000)}{extension}",
                self.api_key,
                model=model,
            )
            if not result.success:
                raise Exception(f"图片上传失败: {result.error}")
            logger.info("[Image Edit] ✅ 本地图片上传成功: %s", summarize_url_for_log(result.oss_url))
            return result.oss_url

        # 情况 2 & 3: HTTPS URL 或 Base64 data URI
        logger.info("[Image Edit] 上传图片到 OSS: %s", summarize_url_for_log(image_url))
        logger.info(f"[Image Edit] 使用模型获取上传凭证: {model}")

        # Use the async httpx variant from this async context so we do not
        # block the event loop on the DashScope policy + OSS upload calls.
        result = await upload_to_dashscope_async(
            image_url=image_url,
            api_key=self.api_key,
            model=model,
        )

        if not result.success:
            raise Exception(f"图片上传失败: {result.error}")

        logger.info("[Image Edit] ✅ 上传成功: %s", summarize_url_for_log(result.oss_url))
        return result.oss_url

    def _resolve_local_public_image_path(self, image_url: str) -> Optional[Path]:
        if not isinstance(image_url, str):
            return None
        if not image_url.startswith(f"{DEFAULT_LOCAL_URL_PREFIX}/"):
            return None
        local_path = resolve_local_public_file_path(image_url) or resolve_local_public_file_path(unquote(image_url))
        if local_path and local_path.exists() and local_path.is_file():
            return local_path
        raise FileNotFoundError(f"本地存储图片不存在: {summarize_url_for_log(image_url)}")

    def _resolve_optimizer_image_input(self, image_url: str):
        local_path = self._resolve_local_public_image_path(image_url)
        if local_path:
            return local_path.read_bytes()
        return image_url

    def build_qwen_payload(
        self,
        model: str,
        prompt: str,
        image_url: str,
        options: ImageEditOptions
    ) -> dict:
        """构建 Qwen Image Edit 请求 payload"""
        content = [{"image": image_url}]
        if prompt:
            content.append({"text": prompt})
        n = clamp_image_count(options.n, get_qwen_image_max_output_count(model))

        payload = {
            "model": model,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": content
                }]
            },
            "parameters": {
                "n": n,
                "watermark": options.watermark,
                "prompt_extend": options.prompt_extend
            }
        }

        if options.negative_prompt:
            payload["parameters"]["negative_prompt"] = options.negative_prompt
        if options.seed is not None:
            payload["parameters"]["seed"] = options.seed
        if options.size and n == 1:
            payload["parameters"]["size"] = options.size

        return payload

    def build_wan26_image_payload(
        self,
        model: str,
        prompt: str,
        image_url: str,
        options: ImageEditOptions
    ) -> dict:
        """构建 wan2.6-image 模型请求 payload"""
        content = []
        if prompt:
            content.append({"text": prompt})
        content.append({"image": image_url})

        payload = {
            "model": model,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": content
                }]
            },
            "parameters": {
                "n": options.n,
                "watermark": options.watermark,
                "prompt_extend": options.prompt_extend,
                "enable_interleave": False
            }
        }

        if options.negative_prompt:
            payload["parameters"]["negative_prompt"] = options.negative_prompt
        if options.seed is not None:
            payload["parameters"]["seed"] = options.seed
        if options.size:
            payload["parameters"]["size"] = options.size

        return payload

    def build_wan27_payload(
        self,
        model: str,
        prompt: str,
        image_url: str,
        options: ImageEditOptions
    ) -> dict:
        """构建 wan2.7-image / wan2.7-image-pro 图像编辑请求 payload"""
        content = [{"image": image_url}]
        if prompt:
            content.append({"text": prompt})

        n = clamp_image_count(options.n, WAN27_STANDARD_MAX_IMAGES)
        size = get_wan27_size(
            options.aspect_ratio,
            options.size or "2K",
            model,
            has_image_input=True,
            image_count=n,
        )
        parameters = {
            "size": size,
            "n": n,
            "watermark": options.watermark,
        }
        if options.seed is not None:
            parameters["seed"] = options.seed

        return {
            "model": model,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": content
                }]
            },
            "parameters": parameters
        }

    def build_wan_legacy_payload(
        self,
        model: str,
        prompt: str,
        image_url: str,
        options: ImageEditOptions
    ) -> dict:
        """构建旧版通义万相模型请求 payload"""
        payload = {
            "model": model,
            "input": {
                "prompt": prompt,
                "images": [image_url]
            },
            "parameters": {
                "n": options.n,
                "watermark": options.watermark
            }
        }

        if options.negative_prompt:
            payload["parameters"]["negative_prompt"] = options.negative_prompt
        if options.seed is not None:
            payload["parameters"]["seed"] = options.seed
        if options.size:
            payload["parameters"]["size"] = options.size

        return payload

    async def call_api(
        self,
        endpoint: str,
        payload: dict,
        use_oss_resolve: bool = True
    ) -> dict:
        """调用 DashScope API"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        if use_oss_resolve:
            headers['X-DashScope-OssResourceResolve'] = 'enable'
            logger.info("[Image Edit] 添加 X-DashScope-OssResourceResolve: enable")

        logger.info(f"[Image Edit] 调用 DashScope API: {endpoint}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers=headers
            )

            if response.status_code != 200:
                error_text = response.text
                safe_error = summarize_text_for_log(error_text, label="dashscope_error")
                logger.error("[Image Edit] API 错误 (%s): %s", response.status_code, safe_error)
                raise Exception(f"DashScope API 错误: {safe_error}")

            result = response.json()
            logger.info("[Image Edit] ✅ API 调用成功")
            return result

    def extract_image_urls(self, response_data: dict, model: str) -> List[str]:
        """从 API 响应中提取全部图片 URL"""
        urls: List[str] = []

        # 检查是否误用了视觉理解模型
        if 'output' in response_data and 'choices' in response_data.get('output', {}):
            choices = response_data['output']['choices']
            has_text_content = False
            for choice in choices or []:
                content = choice.get('message', {}).get('content', [])
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get('image'):
                        urls.append(item['image'])
                    elif item.get('text'):
                        has_text_content = True
            if urls:
                return urls
            if choices and has_text_content:
                raise Exception(
                    f"模型错误: '{model}' 是视觉理解模型，不支持图像编辑。\n"
                    f"请使用图像编辑模型如: qwen-image-edit-plus, wan2.6-image"
                )

        # Qwen 和 Wan multimodal-generation 模型响应格式
        if model.startswith('qwen-') or model == 'wan2.6-image' or is_wan27_image_model(model):
            if 'output' in response_data and 'choices' in response_data['output']:
                choices = response_data['output']['choices']
                for choice in choices or []:
                    content = choice.get('message', {}).get('content', [])
                    for item in content:
                        if isinstance(item, dict) and item.get('image'):
                            urls.append(item['image'])
                if urls:
                    return urls

        # 旧版通义万相响应格式
        if model.startswith('wan') and model != 'wan2.6-image':
            if 'output' in response_data and 'results' in response_data['output']:
                results = response_data['output']['results']
                for item in results or []:
                    if item.get('url'):
                        urls.append(item['url'])
                if urls:
                    return urls

        # 通用格式尝试
        if 'output' in response_data:
            output = response_data['output']
            for field in ['url', 'output_image_url', 'image_url']:
                if field in output:
                    return [output[field]]

        logger.error(
            "[Image Edit] 无法从响应中提取图片 URL: %s",
            _summarize_response_shape_for_log(response_data),
        )
        raise Exception("API 返回成功但未找到图片 URL")

    def extract_image_url(self, response_data: dict, model: str) -> str:
        """从 API 响应中提取第一张图片 URL（兼容旧调用方）"""
        return self.extract_image_urls(response_data, model)[0]

    async def edit(
        self,
        model: str,
        prompt: str,
        image_url: str,
        options: Optional[ImageEditOptions] = None
    ) -> ImageEditResult:
        """
        执行图像编辑

        Args:
            model: 模型名称
            prompt: 编辑提示词
            image_url: 参考图片 URL
            options: 编辑选项

        Returns:
            ImageEditResult

        增强功能:
        - 可选编辑 Prompt 智能优化
        """
        if options is None:
            options = ImageEditOptions()

        # ========== Prompt 优化（如果启用）==========
        original_prompt = prompt
        optimized_prompt = None

        if options.enable_prompt_optimize:
            logger.info(f"[Image Edit] 🔄 [Prompt优化] 开始优化编辑 Prompt...")
            try:
                optimizer_image = self._resolve_optimizer_image_input(image_url)
                optimizer = self.edit_optimizer
                logger.info(
                    "[Image Edit] [Prompt优化] 使用模型: %s",
                    options.prompt_optimize_model or getattr(optimizer, "model", "qwen-vl-max-latest"),
                )
                optimize_result = await optimizer.optimize(
                    prompt=prompt,
                    image=optimizer_image,
                    enable_rewrite=True,
                    model=options.prompt_optimize_model,
                )
                if optimize_result.success:
                    prompt = optimize_result.optimized_prompt
                    optimized_prompt = optimize_result.optimized_prompt
                    logger.info(f"[Image Edit] ✅ [Prompt优化] 优化成功")
                    logger.info(
                        "[Image Edit]     - 原始: %s",
                        summarize_text_for_log(original_prompt, label="original_prompt"),
                    )
                    logger.info(
                        "[Image Edit]     - 优化后: %s",
                        summarize_text_for_log(optimized_prompt, label="optimized_prompt"),
                    )
                else:
                    logger.warning(f"[Image Edit] ⚠️ [Prompt优化] 优化失败，使用原始 Prompt: {optimize_result.error}")
            except Exception as e:
                logger.error(f"[Image Edit] ❌ [Prompt优化] 异常: {str(e)}")

        try:
            # 步骤 1: 处理参考图片
            oss_url = await self.process_reference_image(image_url, model)

            # 步骤 2: 根据模型类型构建 payload 和 endpoint
            if model.startswith('qwen-'):
                endpoint = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/multimodal-generation/generation"
                payload = self.build_qwen_payload(model, prompt, oss_url, options)
            elif is_wan27_image_model(model):
                endpoint = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/multimodal-generation/generation"
                payload = self.build_wan27_payload(model, prompt, oss_url, options)
                logger.info(f"[Image Edit] {model} 使用 multimodal-generation 端点")
            elif model == 'wan2.6-image':
                endpoint = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/multimodal-generation/generation"
                payload = self.build_wan26_image_payload(model, prompt, oss_url, options)
                logger.info(f"[Image Edit] wan2.6-image 使用 multimodal-generation 端点")
            elif model.startswith('wan'):
                endpoint = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/image-generation/generation"
                payload = self.build_wan_legacy_payload(model, prompt, oss_url, options)
            else:
                return ImageEditResult(success=False, error=f"不支持的模型: {model}")

            # 步骤 3: 调用 API
            result = await self.call_api(endpoint, payload, use_oss_resolve=True)

            # 步骤 4: 提取图片 URL
            result_urls = self.extract_image_urls(result, model)
            result_url = result_urls[0]

            logger.info(
                "[Image Edit] ✅ 图像编辑完成: %s 张，首图=%s",
                len(result_urls),
                summarize_url_for_log(result_url),
            )

            return ImageEditResult(
                success=True,
                url=result_url,
                urls=result_urls,
                original_prompt=original_prompt,
                optimized_prompt=optimized_prompt
            )

        except Exception as e:
            logger.error(f"[Image Edit] ❌ 图像编辑失败: {str(e)}")
            return ImageEditResult(
                success=False,
                error=str(e),
                original_prompt=original_prompt,
                optimized_prompt=optimized_prompt
            )

    async def close(self):
        """关闭服务（预留接口）"""
        pass
