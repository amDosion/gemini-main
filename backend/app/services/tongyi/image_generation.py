"""
通义图像服务 - 文生图实现
支持 Z-Image、Qwen-Image、WanV2 系列模型
"""
import httpx
import logging
from typing import List, Optional
from dataclasses import dataclass

from .base import get_endpoint, get_pixel_resolution, QWEN_RESOLUTIONS

logger = logging.getLogger(__name__)


@dataclass
class ImageGenerationResult:
    """图像生成结果"""
    url: str
    mime_type: str = "image/png"
    filename: Optional[str] = None


@dataclass
class ImageGenerationRequest:
    """图像生成请求"""
    model_id: str
    prompt: str
    aspect_ratio: str = "1:1"
    resolution: str = "1.25K"
    num_images: int = 1
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    style: Optional[str] = None


class ImageGenerationService:
    """
    文生图服务 - 服务层实现

    支持的模型:
    - Z-Image 系列: z-image-turbo, z-image, z-image-omni-base
    - Qwen 系列: qwen-image-plus
    - WanV2 系列: wan2.6-t2i, wan2.5-t2i-preview, wan2.2-t2i-plus, etc.
    """

    def __init__(self, api_key: str, timeout: float = 300.0):
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """懒加载 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def generate(self, request: ImageGenerationRequest) -> List[ImageGenerationResult]:
        """
        生成图像 - 根据模型路由到对应的生成方法
        """
        model_id = request.model_id.lower()

        # Z-Image 系列
        if "z-image" in model_id:
            return await self._generate_z_image(request)

        # Qwen-Image-Plus
        if "qwen" in model_id:
            return await self._generate_qwen_image(request)

        # WanV2 系列 (包含 -t2i 后缀的模型)
        if "-t2i" in model_id:
            return await self._generate_wan_v2_image(request)

        # wan2.6-image 模型不支持纯文生图
        if model_id == "wan2.6-image":
            raise ValueError(
                "wan2.6-image 模型的纯文生图模式需要流式输出，当前暂不支持。\n"
                "请使用以下替代方案：\n"
                "- 文生图：使用 wan2.6-t2i 或其他 -t2i 系列模型\n"
                "- 图像编辑：使用 /api/image-edit/edit 端点"
            )

        raise ValueError(f"不支持的图像生成模型: {request.model_id}。请使用 wan2.x-t2i 系列模型。")

    async def _generate_z_image(self, request: ImageGenerationRequest) -> List[ImageGenerationResult]:
        """Z-Image 系列生成"""
        endpoint = get_endpoint("image-generation")
        size = get_pixel_resolution(request.aspect_ratio, request.resolution, request.model_id)

        # Z-Image-Turbo 只支持 1 张图
        num_images = 1 if "turbo" in request.model_id.lower() else min(request.num_images, 4)

        payload = {
            "model": request.model_id,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": [{"text": request.prompt}]
                }]
            },
            "parameters": {
                "size": size,
                "n": num_images,
            }
        }

        if request.negative_prompt:
            payload["parameters"]["negative_prompt"] = request.negative_prompt
        if request.seed is not None:
            payload["parameters"]["seed"] = request.seed

        logger.info(f"[ImageGeneration] Z-Image 请求: model={request.model_id}, size={size}, n={num_images}")
        response = await self._call_api(endpoint, payload)
        return self._parse_image_response(response)

    async def _generate_qwen_image(self, request: ImageGenerationRequest) -> List[ImageGenerationResult]:
        """Qwen-Image-Plus 生成"""
        endpoint = get_endpoint("image-generation")
        size = QWEN_RESOLUTIONS.get(request.aspect_ratio, "1328*1328")

        payload = {
            "model": request.model_id,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": [{"text": request.prompt}]
                }]
            },
            "parameters": {
                "size": size,
                "n": min(request.num_images, 4),
                "prompt_extend": True,
                "watermark": False,
            }
        }

        if request.negative_prompt:
            payload["parameters"]["negative_prompt"] = request.negative_prompt

        logger.info(f"[ImageGeneration] Qwen 请求: model={request.model_id}, size={size}")
        response = await self._call_api(endpoint, payload)
        return self._parse_image_response(response)

    async def _generate_wan_v2_image(self, request: ImageGenerationRequest) -> List[ImageGenerationResult]:
        """WanV2 系列文生图"""
        endpoint = get_endpoint("image-generation")
        size = get_pixel_resolution(request.aspect_ratio, request.resolution, request.model_id)

        payload = {
            "model": request.model_id,
            "input": {
                "messages": [{
                    "role": "user",
                    "content": [{"text": request.prompt}]
                }]
            },
            "parameters": {
                "size": size,
                "n": min(request.num_images, 4),
                "prompt_extend": True,
                "watermark": False,
            }
        }

        if request.negative_prompt:
            payload["parameters"]["negative_prompt"] = request.negative_prompt
        if request.seed is not None:
            payload["parameters"]["seed"] = request.seed

        logger.info(f"[ImageGeneration] WanV2 请求: model={request.model_id}, size={size}")
        response = await self._call_api(endpoint, payload)
        return self._parse_image_response(response)

    async def _call_api(self, endpoint: str, payload: dict) -> dict:
        """调用 DashScope API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-OssResourceResolve": "enable",
        }

        logger.info(f"[ImageGeneration] 调用 API: {endpoint}")

        try:
            response = await self.client.post(endpoint, json=payload, headers=headers)

            if not response.is_success:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", str(response.status_code))
                    error_code = error_data.get("code", "Unknown")
                except Exception:
                    error_msg = response.text
                    error_code = str(response.status_code)

                logger.error(f"[ImageGeneration] API 错误: code={error_code}, message={error_msg}")
                raise Exception(f"DashScope API Error [{error_code}]: {error_msg}")

            return response.json()

        except httpx.TimeoutException:
            logger.error("[ImageGeneration] API 调用超时")
            raise Exception("DashScope API 调用超时")
        except httpx.RequestError as e:
            logger.error(f"[ImageGeneration] API 请求失败: {str(e)}")
            raise Exception(f"无法连接到 DashScope API: {str(e)}")

    def _parse_image_response(self, response: dict) -> List[ImageGenerationResult]:
        """解析图像响应"""
        results = []
        output = response.get("output", {})

        # 主要路径: output.choices[].message.content[{image: url}]
        choices = output.get("choices", [])
        for choice in choices:
            content = choice.get("message", {}).get("content", [])
            for item in content:
                if "image" in item:
                    results.append(ImageGenerationResult(url=item["image"]))

        # 备用路径: output.results[].url
        if not results:
            results_list = output.get("results", [])
            for item in results_list:
                if "url" in item:
                    results.append(ImageGenerationResult(url=item["url"]))

        logger.info(f"[ImageGeneration] 解析完成: {len(results)} 张图片")
        return results

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
