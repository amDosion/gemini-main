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
        import time
        start_time = time.time()
        
        logger.info(f"[ImageGenerationService] ========== 开始图片生成 ==========")
        logger.info(f"[ImageGenerationService] 📥 请求参数:")
        logger.info(f"[ImageGenerationService]     - model_id: {request.model_id}")
        logger.info(f"[ImageGenerationService]     - prompt: {request.prompt[:100] + '...' if len(request.prompt) > 100 else request.prompt}")
        logger.info(f"[ImageGenerationService]     - prompt长度: {len(request.prompt)}")
        logger.info(f"[ImageGenerationService]     - aspect_ratio: {request.aspect_ratio}")
        logger.info(f"[ImageGenerationService]     - resolution: {request.resolution}")
        logger.info(f"[ImageGenerationService]     - num_images: {request.num_images}")
        if request.negative_prompt:
            logger.info(f"[ImageGenerationService]     - negative_prompt: {request.negative_prompt[:50] + '...' if len(request.negative_prompt) > 50 else request.negative_prompt}")
        if request.seed is not None:
            logger.info(f"[ImageGenerationService]     - seed: {request.seed}")
        if request.style:
            logger.info(f"[ImageGenerationService]     - style: {request.style}")
        
        model_id = request.model_id.lower()
        logger.info(f"[ImageGenerationService] 🔄 [步骤1] 识别模型类型...")
        logger.info(f"[ImageGenerationService]     - model_id (lowercase): {model_id}")

        # Z-Image 系列
        if "z-image" in model_id:
            logger.info(f"[ImageGenerationService] ✅ [步骤1] 识别为 Z-Image 系列")
            logger.info(f"[ImageGenerationService] 🔄 [步骤2] 调用 _generate_z_image()...")
            result = await self._generate_z_image(request)
            total_time = (time.time() - start_time) * 1000
            logger.info(f"[ImageGenerationService] ========== 图片生成完成 (总耗时: {total_time:.2f}ms) ==========")
            logger.info(f"[ImageGenerationService]     - 返回图片数量: {len(result)}")
            return result

        # Qwen-Image-Plus
        if "qwen" in model_id:
            logger.info(f"[ImageGenerationService] ✅ [步骤1] 识别为 Qwen-Image-Plus 系列")
            logger.info(f"[ImageGenerationService] 🔄 [步骤2] 调用 _generate_qwen_image()...")
            result = await self._generate_qwen_image(request)
            total_time = (time.time() - start_time) * 1000
            logger.info(f"[ImageGenerationService] ========== 图片生成完成 (总耗时: {total_time:.2f}ms) ==========")
            logger.info(f"[ImageGenerationService]     - 返回图片数量: {len(result)}")
            return result

        # WanV2 系列 (包含 -t2i 后缀的模型)
        if "-t2i" in model_id:
            logger.info(f"[ImageGenerationService] ✅ [步骤1] 识别为 WanV2 系列")
            logger.info(f"[ImageGenerationService] 🔄 [步骤2] 调用 _generate_wan_v2_image()...")
            result = await self._generate_wan_v2_image(request)
            total_time = (time.time() - start_time) * 1000
            logger.info(f"[ImageGenerationService] ========== 图片生成完成 (总耗时: {total_time:.2f}ms) ==========")
            logger.info(f"[ImageGenerationService]     - 返回图片数量: {len(result)}")
            return result

        # wan2.6-image 模型不支持纯文生图
        if model_id == "wan2.6-image":
            logger.error(f"[ImageGenerationService] ❌ [步骤1] 不支持的模型: wan2.6-image (需要流式输出)")
            raise ValueError(
                "wan2.6-image 模型的纯文生图模式需要流式输出，当前暂不支持。\n"
                "请使用以下替代方案：\n"
                "- 文生图：使用 wan2.6-t2i 或其他 -t2i 系列模型\n"
                "- 图像编辑：使用 /api/image-edit/edit 端点"
            )

        logger.error(f"[ImageGenerationService] ❌ [步骤1] 不支持的图像生成模型: {request.model_id}")
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

        import time
        start_time = time.time()
        
        logger.info(f"[ImageGenerationService] ========== [Z-Image] 开始生成 ==========")
        logger.info(f"[ImageGenerationService] 📥 [Z-Image] 请求参数:")
        logger.info(f"[ImageGenerationService]     - model: {request.model_id}")
        logger.info(f"[ImageGenerationService]     - size: {size}")
        logger.info(f"[ImageGenerationService]     - n: {num_images}")
        logger.info(f"[ImageGenerationService]     - prompt长度: {len(request.prompt)}")
        
        logger.info(f"[ImageGenerationService] 🔄 [Z-Image] 调用 DashScope API...")
        logger.info(f"[ImageGenerationService]     - endpoint: {endpoint}")
        api_start = time.time()
        response = await self._call_api(endpoint, payload)
        api_time = (time.time() - api_start) * 1000
        logger.info(f"[ImageGenerationService] ✅ [Z-Image] API调用完成 (耗时: {api_time:.2f}ms)")
        
        logger.info(f"[ImageGenerationService] 🔄 [Z-Image] 解析响应结果...")
        results = self._parse_image_response(response)
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[ImageGenerationService] ✅ [Z-Image] 解析完成 (耗时: {total_time:.2f}ms)")
        logger.info(f"[ImageGenerationService]     - 返回图片数量: {len(results)}")
        logger.info(f"[ImageGenerationService] ========== [Z-Image] 生成完成 ==========")
        
        return results

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

        import time
        start_time = time.time()
        
        logger.info(f"[ImageGenerationService] ========== [Qwen] 开始生成 ==========")
        logger.info(f"[ImageGenerationService] 📥 [Qwen] 请求参数:")
        logger.info(f"[ImageGenerationService]     - model: {request.model_id}")
        logger.info(f"[ImageGenerationService]     - size: {size}")
        logger.info(f"[ImageGenerationService]     - n: {min(request.num_images, 4)}")
        logger.info(f"[ImageGenerationService]     - prompt长度: {len(request.prompt)}")
        
        logger.info(f"[ImageGenerationService] 🔄 [Qwen] 调用 DashScope API...")
        logger.info(f"[ImageGenerationService]     - endpoint: {endpoint}")
        api_start = time.time()
        response = await self._call_api(endpoint, payload)
        api_time = (time.time() - api_start) * 1000
        logger.info(f"[ImageGenerationService] ✅ [Qwen] API调用完成 (耗时: {api_time:.2f}ms)")
        
        logger.info(f"[ImageGenerationService] 🔄 [Qwen] 解析响应结果...")
        results = self._parse_image_response(response)
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[ImageGenerationService] ✅ [Qwen] 解析完成 (耗时: {total_time:.2f}ms)")
        logger.info(f"[ImageGenerationService]     - 返回图片数量: {len(results)}")
        logger.info(f"[ImageGenerationService] ========== [Qwen] 生成完成 ==========")
        
        return results

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

        import time
        start_time = time.time()
        
        logger.info(f"[ImageGenerationService] ========== [WanV2] 开始生成 ==========")
        logger.info(f"[ImageGenerationService] 📥 [WanV2] 请求参数:")
        logger.info(f"[ImageGenerationService]     - model: {request.model_id}")
        logger.info(f"[ImageGenerationService]     - size: {size}")
        logger.info(f"[ImageGenerationService]     - n: {min(request.num_images, 4)}")
        logger.info(f"[ImageGenerationService]     - prompt长度: {len(request.prompt)}")
        
        logger.info(f"[ImageGenerationService] 🔄 [WanV2] 调用 DashScope API...")
        logger.info(f"[ImageGenerationService]     - endpoint: {endpoint}")
        api_start = time.time()
        response = await self._call_api(endpoint, payload)
        api_time = (time.time() - api_start) * 1000
        logger.info(f"[ImageGenerationService] ✅ [WanV2] API调用完成 (耗时: {api_time:.2f}ms)")
        
        logger.info(f"[ImageGenerationService] 🔄 [WanV2] 解析响应结果...")
        results = self._parse_image_response(response)
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[ImageGenerationService] ✅ [WanV2] 解析完成 (耗时: {total_time:.2f}ms)")
        logger.info(f"[ImageGenerationService]     - 返回图片数量: {len(results)}")
        logger.info(f"[ImageGenerationService] ========== [WanV2] 生成完成 ==========")
        
        return results

    async def _call_api(self, endpoint: str, payload: dict) -> dict:
        """调用 DashScope API"""
        import time
        api_start = time.time()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-OssResourceResolve": "enable",
        }

        logger.info(f"[ImageGenerationService] 🔄 [_call_api] 调用 DashScope API...")
        logger.info(f"[ImageGenerationService]     - endpoint: {endpoint}")
        logger.info(f"[ImageGenerationService]     - payload大小: {len(str(payload))} 字符")
        logger.info(f"[ImageGenerationService]     - headers: Authorization, Content-Type, X-DashScope-OssResourceResolve")

        try:
            response = await self.client.post(endpoint, json=payload, headers=headers)
            api_time = (time.time() - api_start) * 1000

            logger.info(f"[ImageGenerationService] ✅ [_call_api] HTTP响应接收 (耗时: {api_time:.2f}ms)")
            logger.info(f"[ImageGenerationService]     - status_code: {response.status_code}")
            logger.info(f"[ImageGenerationService]     - is_success: {response.is_success}")

            if not response.is_success:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", str(response.status_code))
                    error_code = error_data.get("code", "Unknown")
                except Exception:
                    error_msg = response.text
                    error_code = str(response.status_code)

                logger.error(f"[ImageGenerationService] ❌ [_call_api] API错误:")
                logger.error(f"[ImageGenerationService]     - code: {error_code}")
                logger.error(f"[ImageGenerationService]     - message: {error_msg}")
                raise Exception(f"DashScope API Error [{error_code}]: {error_msg}")

            response_data = response.json()
            logger.info(f"[ImageGenerationService] ✅ [_call_api] 响应解析完成")
            logger.info(f"[ImageGenerationService]     - 响应数据大小: {len(str(response_data))} 字符")
            return response_data

        except httpx.TimeoutException:
            api_time = (time.time() - api_start) * 1000
            logger.error(f"[ImageGenerationService] ❌ [_call_api] API调用超时 (耗时: {api_time:.2f}ms)")
            raise Exception("DashScope API 调用超时")
        except httpx.RequestError as e:
            api_time = (time.time() - api_start) * 1000
            logger.error(f"[ImageGenerationService] ❌ [_call_api] API请求失败 (耗时: {api_time:.2f}ms): {str(e)}", exc_info=True)
            raise Exception(f"无法连接到 DashScope API: {str(e)}")

    def _parse_image_response(self, response: dict) -> List[ImageGenerationResult]:
        """解析图像响应"""
        import time
        start_time = time.time()
        
        logger.info(f"[ImageGenerationService] 🔄 [_parse_image_response] 开始解析响应...")
        results = []
        output = response.get("output", {})
        
        logger.info(f"[ImageGenerationService]     - 检查 output.choices 路径...")
        # 主要路径: output.choices[].message.content[{image: url}]
        choices = output.get("choices", [])
        logger.info(f"[ImageGenerationService]     - choices数量: {len(choices)}")
        
        for idx, choice in enumerate(choices):
            content = choice.get("message", {}).get("content", [])
            logger.info(f"[ImageGenerationService]     - choice[{idx}] content数量: {len(content)}")
            for item_idx, item in enumerate(content):
                if "image" in item:
                    image_url = item["image"]
                    url_type = "HTTP" if image_url.startswith('http') else "其他"
                    results.append(ImageGenerationResult(url=image_url))
                    logger.info(f"[ImageGenerationService]     - ✅ 从 choice[{idx}].content[{item_idx}] 解析到图片: URL类型={url_type}")

        # 备用路径: output.results[].url
        if not results:
            logger.info(f"[ImageGenerationService]     - choices路径无结果，检查 output.results 路径...")
            results_list = output.get("results", [])
            logger.info(f"[ImageGenerationService]     - results数量: {len(results_list)}")
            for idx, item in enumerate(results_list):
                if "url" in item:
                    image_url = item["url"]
                    url_type = "HTTP" if image_url.startswith('http') else "其他"
                    results.append(ImageGenerationResult(url=image_url))
                    logger.info(f"[ImageGenerationService]     - ✅ 从 results[{idx}] 解析到图片: URL类型={url_type}")

        parse_time = (time.time() - start_time) * 1000
        logger.info(f"[ImageGenerationService] ✅ [_parse_image_response] 解析完成 (耗时: {parse_time:.2f}ms)")
        logger.info(f"[ImageGenerationService]     - 解析到图片数量: {len(results)}")
        return results

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
