"""
图像编辑服务层
封装 DashScope 图像编辑 API 调用逻辑

支持的模型:
- qwen-image-edit-plus (及其变体)
- wan2.6-image
- wan2.5-i2i-preview (向后兼容)
"""
from typing import Optional
from dataclasses import dataclass
import httpx
import logging

from .file_upload import upload_to_dashscope

logger = logging.getLogger(__name__)

# DashScope 官方 API 地址
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com"


@dataclass
class ImageEditResult:
    """图像编辑结果"""
    success: bool
    url: Optional[str] = None
    mime_type: str = "image/png"
    error: Optional[str] = None


@dataclass
class ImageEditOptions:
    """图像编辑选项"""
    n: int = 1
    negative_prompt: Optional[str] = None
    size: Optional[str] = None
    watermark: bool = False
    seed: Optional[int] = None
    prompt_extend: bool = True


class ImageEditService:
    """图像编辑服务"""

    def __init__(self, api_key: str):
        self.api_key = api_key

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
            logger.info(f"[Image Edit] 使用现有 OSS URL: {image_url[:60]}...")
            return image_url

        # 情况 2 & 3: HTTPS URL 或 Base64 data URI
        logger.info(f"[Image Edit] 上传图片到 OSS: {image_url[:60]}...")
        logger.info(f"[Image Edit] 使用模型获取上传凭证: {model}")

        result = upload_to_dashscope(
            image_url=image_url,
            api_key=self.api_key,
            model=model
        )

        if not result.success:
            raise Exception(f"图片上传失败: {result.error}")

        logger.info(f"[Image Edit] ✅ 上传成功: {result.oss_url[:60]}...")
        return result.oss_url

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
                "prompt_extend": options.prompt_extend
            }
        }

        if options.negative_prompt:
            payload["parameters"]["negative_prompt"] = options.negative_prompt
        if options.seed is not None:
            payload["parameters"]["seed"] = options.seed
        if options.size and options.n == 1:
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
                logger.error(f"[Image Edit] API 错误 ({response.status_code}): {error_text}")
                raise Exception(f"DashScope API 错误: {error_text}")

            result = response.json()
            logger.info("[Image Edit] ✅ API 调用成功")
            return result

    def extract_image_url(self, response_data: dict, model: str) -> str:
        """从 API 响应中提取图片 URL"""

        # 检查是否误用了视觉理解模型
        if 'output' in response_data and 'choices' in response_data.get('output', {}):
            choices = response_data['output']['choices']
            if choices and len(choices) > 0:
                content = choices[0].get('message', {}).get('content', [])
                has_text_only = all(isinstance(item, dict) and 'text' in item and 'image' not in item for item in content)
                if has_text_only and content:
                    raise Exception(
                        f"模型错误: '{model}' 是视觉理解模型，不支持图像编辑。\n"
                        f"请使用图像编辑模型如: qwen-image-edit-plus, wan2.6-image"
                    )

        # Qwen 和 wan2.6-image 模型响应格式
        if model.startswith('qwen-') or model == 'wan2.6-image':
            if 'output' in response_data and 'choices' in response_data['output']:
                choices = response_data['output']['choices']
                if choices and len(choices) > 0:
                    content = choices[0].get('message', {}).get('content', [])
                    for item in content:
                        if isinstance(item, dict) and 'image' in item:
                            return item['image']

        # 旧版通义万相响应格式
        if model.startswith('wan') and model != 'wan2.6-image':
            if 'output' in response_data and 'results' in response_data['output']:
                results = response_data['output']['results']
                if results and len(results) > 0:
                    return results[0]['url']

        # 通用格式尝试
        if 'output' in response_data:
            output = response_data['output']
            for field in ['url', 'output_image_url', 'image_url']:
                if field in output:
                    return output[field]

        logger.error(f"[Image Edit] 无法从响应中提取图片 URL: {response_data}")
        raise Exception("API 返回成功但未找到图片 URL")

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
        """
        if options is None:
            options = ImageEditOptions()

        try:
            # 步骤 1: 处理参考图片
            oss_url = await self.process_reference_image(image_url, model)

            # 步骤 2: 根据模型类型构建 payload 和 endpoint
            if model.startswith('qwen-'):
                endpoint = f"{DASHSCOPE_BASE_URL}/api/v1/services/aigc/multimodal-generation/generation"
                payload = self.build_qwen_payload(model, prompt, oss_url, options)
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
            result_url = self.extract_image_url(result, model)

            logger.info(f"[Image Edit] ✅ 图像编辑完成: {result_url[:60]}...")

            return ImageEditResult(success=True, url=result_url)

        except Exception as e:
            logger.error(f"[Image Edit] ❌ 图像编辑失败: {str(e)}")
            return ImageEditResult(success=False, error=str(e))

    async def close(self):
        """关闭服务（预留接口）"""
        pass
